"""벌식(set-type) jamo-component model -- the generator for the full 11,172 조합형.

This produces a STARTING POINT plus a review queue, not a finished font. At
16px the right pixel is often an optical call that no rule reproduces (the
confirmed 2,350 were finished exactly that way), so the goal here is to get
close and to say clearly which glyphs need a human eye. See docs/ROADMAP.md.

Why 벌식, measured (see ROADMAP for the full table):
  Components are only 68% additive -- across 48,063 rectangle tests, swapping
  the 초성 changes the glyph differently depending on the 종성 a third of the
  time. So a single fixed shape per jamo has a hard ~68% ceiling, which is
  exactly where the previous majority-vote model stalled. The classic Korean
  bitmap-font answer is 벌식: each jamo gets several variants (벌) selected by
  context, which absorbs that interaction.

The cells (leave-one-out 85.5% exact / 0.91px mean once every cell is filled):

  초중성 = (초성, 중성, 받침유무)   19 x 21 x 2 = 798 cells
  종성   = (종성, 중성)             27 x 21     = 567 cells

초성 and 중성 are ONE cell, not two. Splitting them was measured to be
unfounded: a 초성벌 keyed on (중성,받침유무) and a 중성벌 keyed on (받침유무,초성)
are both determined by (초성,중성,받침유무), so the two always appear together
and no corpus evidence can separate them. Merging scored identically (85.5%,
0.91px, <=2px 90.7%) with 798 fewer cells to draw and review.

초중성 is cut out of the confirmed corpus as the ink outside compose_light's
PC-98 받침 variance zone; 종성 is the ink inside it. That cut is unstable (the
same (종성,중성) can yield a 0px or a 57px zone), but note the instability is
NOT only the cut's fault -- extracting 종성 by exact subtraction instead gave
the identical 59% impurity, so most of it is real design variation. Either
way, extracted cells are candidates to review, not truth: `--missing` lists
what has no sample at all, `--report` ranks the rest by how shaky it is.

CLI (run from repo root):
  python scripts/compose_components.py --validate   # rebuild the corpus, px error
  python scripts/compose_components.py --loo        # honest estimate for unseen
  python scripts/compose_components.py --coverage   # 11,172 composability
  python scripts/compose_components.py --missing    # cells with no sample (draw these)
  python scripts/compose_components.py --report     # low-confidence cells, worst first
"""
import argparse
import json
import os
import random
import statistics
from collections import defaultdict, Counter

import compose_light as cl

ROOT = cl.ROOT
# Read the hand-confirmed file directly rather than build/light_hangul.json.
# Both hold the same 2,350 today, but representative syllables drawn to fill
# empty cells land outside KS X 1001, which compose_light.py never emits --
# reading the source of truth lets them feed straight back in.
CORPUS = os.path.join(ROOT, "tools", "glyphs_light.json")
FULL = [chr(c) for c in range(0xAC00, 0xD7A4)]              # all 11,172


# ---- cells ------------------------------------------------------------------
# A cell is (kind, jamo, 벌). Keep the 벌 functions total (never None) so the
# whole cell set is enumerable up front -- that is the drawing worklist.

def cv_beol(jong):
    """초중성 shape depends only on whether a batchim squeezes it from below;
    which 초성/중성 pair it is, is already the cell's identity."""
    return (bool(jong),)


def jong_beol(jung):
    """받침 width/position follows the vowel above it."""
    return (jung,)


def cells_for(ch):
    """The two (or one) library cells this syllable is built from."""
    cho, jung, jong = cl.decompose(ch)
    out = [("cv", cho + jung, cv_beol(jong))]
    if jong:
        out.append(("jong", jong, jong_beol(jung)))
    return out


def required_cells(chars=FULL):
    """Every cell the model needs to render `chars` -- the drawing worklist."""
    req = set()
    for ch in chars:
        req.update(cells_for(ch))
    return req


# ---- extraction -------------------------------------------------------------

def build_zone_indices(corpus, pc98):
    """cho_ref for zones(), built ONLY from syllables PC-98 also has.

    cho_zone picks a canonical syllable per (초성, 블록타입) and diffs it against
    its PC-98 counterpart. Representative syllables drawn to fill empty cells
    are outside KS X 1001, so PC-98 has no counterpart -- if one of them wins
    the canonical slot, cho_zone dereferences a None grid and dies. Restricting
    the index to the PC-98-covered subset keeps the canonical pick valid; the
    drawn syllables still contribute components, just through observe()'s
    subtraction path, which needs no zone."""
    covered = {ch: rows for ch, rows in corpus.items() if pc98(ch) is not None}
    return cl.build_indices(covered)[0]


def zones(ch, pc98, cho_ref, refs):
    cho, jung, jong = cl.decompose(ch)
    jz = cl.jong_zone(ch, pc98) if jong else set()
    cz = cl.cho_zone(ch, pc98, cho_ref, refs) - jz
    vz = cl.ALL_PX - jz - cz
    return cz, vz, jz


def on(rows, cells):
    return frozenset((y, x) for (y, x) in cells if rows[y][x] == "#")


def _ink(rows):
    return frozenset((y, x) for y in range(16) for x in range(16) if rows[y][x] == "#")


def observe(corpus, pc98, cho_ref):
    """cell -> Counter of candidate pixel sets seen in the corpus.

    Two extraction paths. Syllables PC-98 also has get cut by its 받침 variance
    zone, as before. Representative syllables drawn to fill an empty cell are
    by definition outside KS X 1001, so PC-98 has no such glyph and no zone can
    be derived -- those are split by subtraction instead: whichever of the two
    cells is already known is removed, and the remainder is the other one.
    Sound because the model composes by union, so subtraction is its inverse;
    it just needs one side known, which holds for every cell that currently
    needs drawing."""
    seen = defaultdict(Counter)
    deferred = []
    for ch, rows in corpus.items():
        cv_c, *rest = cells_for(ch)
        if pc98(ch) is not None:
            cz, vz, jz = zones(ch, pc98, cho_ref, corpus)
            seen[cv_c][on(rows, cz) | on(rows, vz)] += 1   # everything above 받침
            if rest:
                seen[rest[0]][on(rows, jz)] += 1
        else:
            deferred.append((ch, rows))

    # Resolve by subtraction, repeating while anything still gets solved: a
    # syllable filled this round can be the known side for the next one.
    while deferred:
        progressed = []
        for ch, rows in deferred:
            cv_c, *rest = cells_for(ch)
            jong_c = rest[0] if rest else None
            px = _ink(rows)
            cv_known = seen.get(cv_c)
            jong_known = seen.get(jong_c) if jong_c else None
            if jong_c is None:
                seen[cv_c][px] += 1                       # no 받침: all of it
            elif jong_known:
                seen[cv_c][px - jong_known.most_common(1)[0][0]] += 1
            elif cv_known:
                seen[jong_c][px - cv_known.most_common(1)[0][0]] += 1
            else:
                progressed.append((ch, rows))             # neither side known yet
        if len(progressed) == len(deferred):
            break                                          # nothing solvable left
        deferred = progressed
    return seen


def build_library(corpus, pc98, cho_ref):
    """cell -> component. Most common candidate wins; ties keep the first."""
    return {cell: cand.most_common(1)[0][0]
            for cell, cand in observe(corpus, pc98, cho_ref).items()}


def compose(ch, lib):
    """Union the syllable's cells. None if any cell is missing -- no silent
    fallback, since borrowing a component from an unrelated context is what
    made the old model's worst output look wrong."""
    px = set()
    for cell in cells_for(ch):
        comp = lib.get(cell)
        if comp is None:
            return None
        px |= comp
    return ["".join("#" if (y, x) in px else "." for x in range(16))
            for y in range(16)]


# ---- CLI --------------------------------------------------------------------

def load_corpus():
    """Confirmed Hangul syllables only -- the file also holds Latin/kana."""
    with open(CORPUS, encoding="utf-8") as f:
        data = json.load(f)
    return {ch: rows for ch, rows in data.items()
            if len(ch) == 1 and 0xAC00 <= ord(ch) <= 0xD7A3}


def _err(out, rows):
    return sum(out[y][x] != rows[y][x] for y in range(16) for x in range(16))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--loo", type=int, nargs="?", const=300, metavar="N")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--missing", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    corpus = load_corpus()
    pc98 = cl.load_pc98()
    cho_ref = build_zone_indices(corpus, pc98)
    seen = observe(corpus, pc98, cho_ref)
    lib = {cell: c.most_common(1)[0][0] for cell, c in seen.items()}

    req = required_cells()
    kinds = Counter(k for k, _, _ in req)
    print(f"library: {len(lib)} cells filled / {len(req)} required "
          f"(초중성 {kinds['cv']} + 종성 {kinds['jong']}), "
          f"{len(req - set(lib))} to draw")

    if args.validate:
        errs = [_err(compose(ch, lib), rows) for ch, rows in corpus.items()
                if compose(ch, lib) is not None]
        miss = sum(1 for ch in corpus if compose(ch, lib) is None)
        exact = sum(1 for d in errs if d == 0)
        print(f"validate: {exact}/{len(errs)} exact ({exact/len(errs)*100:.1f}%), "
              f"mean {statistics.mean(errs):.2f}px, max {max(errs)}px, "
              f"{miss} uncomposable")

    if args.loo:
        # Honest estimate for the 8,822 unseen: rebuild without the target.
        # Cells that vanish with it are cells you'd have drawn, so they are
        # skipped rather than counted as model error.
        random.seed(0)
        sample = random.sample(sorted(corpus), min(args.loo, len(corpus)))
        errs, skipped = [], 0
        for ch in sample:
            held = {cell: Counter(c) for cell, c in seen.items()}
            czs, vz, jz = zones(ch, pc98, cho_ref, corpus)
            rows = corpus[ch]
            parts = [on(rows, czs) | on(rows, vz)]
            if cl.decompose(ch)[2]:
                parts.append(on(rows, jz))
            for cell, part in zip(cells_for(ch), parts):
                held[cell][part] -= 1
                if held[cell][part] <= 0:
                    del held[cell][part]
            sub = {cell: c.most_common(1)[0][0] for cell, c in held.items() if c}
            out = compose(ch, sub)
            if out is None:
                skipped += 1
                continue
            errs.append(_err(out, rows))
        exact = sum(1 for d in errs if d == 0)
        within2 = sum(1 for d in errs if d <= 2)
        print(f"leave-one-out (n={len(errs)}, {skipped} skipped as to-draw): "
              f"{exact/len(errs)*100:.1f}% exact, mean {statistics.mean(errs):.2f}px, "
              f"<=2px {within2/len(errs)*100:.1f}%")

    if args.coverage:
        ok = sum(1 for ch in FULL if compose(ch, lib) is not None)
        print(f"coverage: {ok}/{len(FULL)} composable ({ok/len(FULL)*100:.1f}%)")

    if args.missing:
        todo = sorted(req - set(lib), key=lambda c: (c[0], c[1], str(c[2])))
        blocked = Counter()
        for ch in FULL:
            for cell in cells_for(ch):
                if cell in todo:
                    blocked[cell] += 1
        print(f"\ncells with no sample -- draw these ({len(todo)}):")
        for cell in sorted(todo, key=lambda c: -blocked[c]):
            kind, jamo, beol = cell
            print(f"  {kind:4s} {jamo}  벌{beol}  잠긴 음절 {blocked[cell]}")

    if args.report:
        # Extracted-but-shaky cells: one sample, or the corpus disagreed.
        rows_out = []
        for cell, cand in seen.items():
            n = sum(cand.values())
            top = cand.most_common(1)[0][1]
            rows_out.append((len(cand), n - top, n, cell))
        rows_out.sort(key=lambda r: (-r[0], -r[1]))
        shaky = [r for r in rows_out if r[0] > 1 or r[2] == 1]
        print(f"\nlow-confidence cells ({len(shaky)} of {len(seen)}), worst first:")
        for variants, lost, n, cell in shaky[:40]:
            kind, jamo, beol = cell
            print(f"  {kind:4s} {jamo} 벌{str(beol):18s} 샘플 {n:3d} · 변이 {variants} · 불일치 {lost}")


if __name__ == "__main__":
    main()
