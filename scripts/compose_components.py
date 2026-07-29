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

The cells (leave-one-out 79.4% exact / 1.48px mean at full coverage). Kind
tags follow Unicode's own L/V/T (초성/중성/종성) names for a Hangul syllable;
초성+중성 are one fused cell, tagged LV, and 종성 is T:

  LV (초중성) = (초성, 중성, 받침유무)                     19 x 21 x 2 = 798 cells
  T  (종성)   = (종성, 중성), 겹받침 11종만 (종성, 가로/세로) = 16 x 21 + 22 = 358 cells

초성 and 중성 are ONE cell, not two. Splitting them was measured to be
unfounded: a 초성벌 keyed on (중성,받침유무) and a 중성벌 keyed on (받침유무,초성)
are both determined by (초성,중성,받침유무), so the two always appear together
and no corpus evidence can separate them.

겹받침(두 자음이 겹친 11종: ㄳㄵㄶㄺㄻㄼㄽㄾㄿㅀㅄ)만 중성별 대신 compose_light의
가로/세로 받침 구분(jong_bt)으로 거칠게 잡는다 -- 231칸이 22칸이 되고 정확도 손실은
전체 격차의 1/5. 자세한 수치와, 한때 이걸 11칸으로 더 합쳤다가 가로모음 1,045자를
망가뜨린 경위는 t_beol()의 주석 참고. ㅆ은 21벌 그대로다.

측정 시 주의: 모음 계열(가로/세로)을 뭉쳐서 평균만 보면 안 된다. 겹받침 표본은
세로모음에 치우쳐 있어(107 대 53) 가로모음이 망가져도 평균은 멀쩡해 보인다.

초중성 is cut out of the confirmed corpus as the ink outside compose_light's
PC-98 받침 변화 zone; 종성 is the ink inside it. That zone is passed through
batchim_block() first -- raw, it also swallows part of the 초성 and so deletes
strokes when a 종성 component is pasted from another syllable. See that
function; it is the single biggest correctness fix this cut has had.

Do NOT read that instability as a quality signal. A `--report` used to rank
cells by how much their samples disagreed; measuring what it actually
contained killed it. Of 184 flagged cells, 49% had source glyphs that were
pixel-identical where the extracts disagreed (the zone merely caught different
pixels), 19% were artifacts of the subtraction path below, and the remaining
32% differed by 1-3px -- deliberate optical corrections at 16px, which the
confirmed glyphs are full of and which are not errors. Nothing actionable
survived, so only `--missing` (cells with no sample at all) is left.

The same caveat applies to --validate and --loo: they count an exact pixel
match, so they read low even where the output is perfectly usable.

CLI (run from repo root):
  python scripts/compose_components.py --validate   # rebuild the corpus, px error
  python scripts/compose_components.py --loo        # honest estimate for unseen
  python scripts/compose_components.py --coverage   # 11,172 composability
  python scripts/compose_components.py --missing    # cells with no sample (draw these)
  python scripts/compose_components.py --build      # write the full 11,172 for review

--build is a REVIEW draft, not a shipping build: build_ufo.py doesn't read
its output. LOO says ~20% of the composed (non-hand-confirmed) syllables
will need a human eye before this is ready to fold into the real font.
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
FULL_OUT = os.path.join(ROOT, "build", "light_hangul_full.json")
FULL_SPECIMEN = os.path.join(ROOT, "build", "light_hangul_full_specimen.png")


# ---- cells ------------------------------------------------------------------
# A cell is (kind, jamo, 벌). Keep the 벌 functions total (never None) so the
# whole cell set is enumerable up front -- that is the drawing worklist.

def lv_beol(jong):
    """초중성 shape depends only on whether a batchim squeezes it from below;
    which 초성/중성 pair it is, is already the cell's identity."""
    return (bool(jong),)


# 초중성이 오른쪽으로 가장 멀리 뻗는 중성들. 측정해보면 초중성의 오른쪽 끝은
# 초성과 무관하게 중성만으로 정해지고 12/13/14 세 값만 나오는데, 그중 14인 것들.
WIDE_JUNG = frozenset("ㅏㅑㅘ")


def t_beol(jong, jung):
    """받침 width/position follows the vowel above it. 겹받침 (two stacked
    consonants) instead key on whether the 초중성 above them runs wide, because
    that is what they actually make room for -- a wide 초중성 gets a narrower
    batchim and vice versa:

        ㄵ  얹(초중성 12칸) -> 종성 11칸    앉(14칸) -> 10칸
        ㄺ  얽(12) -> 11                   갉(14) -> 10
        ㄻ  걺(12) -> 11                   갊(14) -> 10
        ㄼ  넓(12) -> 11                   닯(14) -> 10

    Two 벌, same 22 cells as the 가로/세로 split it replaces, but the split is
    on the axis the shapes actually vary along (leave-one-out over 119
    confirmed 겹받침):

        가로/세로 (이전)   22 cells  exact 72.4%  2.40px
        넓다/아니다        22 cells  exact 91.2%  0.41px
        초중성 끝 3벌      33 cells  exact 92.0%  0.21px

    Stop at two: the 3-벌 and a 넓다x가로세로 4-벌 both cost 11 more cells and
    take unfilled ones from 2 to 9, for 0.8pt.

    Earlier attempts, kept so they are not retried: collapsing 겹받침 to one
    shape per jamo (11 cells) broke every horizontal-vowel syllable -- the
    leave-one-out that endorsed it averaged the vowel classes together and hid
    it. Never judge a batchim change on a pooled mean; split it by vowel class."""
    if jong in cl.CLUSTER_JONG:
        return (jung in WIDE_JUNG,)
    return (jung,)


def cells_for(ch):
    """The two (or one) library cells this syllable is built from."""
    cho, jung, jong = cl.decompose(ch)
    out = [("LV", cho + jung, lv_beol(jong))]
    if jong:
        out.append(("T", jong, t_beol(jong, jung)))
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


def batchim_block(jz):
    """jong_zone minus the 초성 pixels it wrongly picks up.

    PC-98 reshapes the 초성 depending on the batchim, so "pixels that move when
    only the 종성 varies" catches part of the initial too -- for 각/간/... it
    grabs (1,6) and (2..3, 5..6), the 6th cell of ㄱ's bar and its stem. Those
    then live in the 종성 component, and pasting some other syllable's 종성
    deletes them: 갃 came out with a 5-wide stemless ㄱ because its ㄳ component
    was cut from 넋 (ㄴ+ㅓ), which has no ink there.

    The initial's leak is always separated from the real batchim by at least
    one blank row, so keeping only the bottom contiguous run of rows drops it.
    Measured over the confirmed corpus: 87.2% -> 88.4% exact, 0.96 -> 0.93px."""
    if not jz:
        return jz
    rows = sorted({y for y, _ in jz})
    cut = rows[0]
    for a, b in zip(rows, rows[1:]):
        if b - a > 1:
            cut = b
    return {(y, x) for (y, x) in jz if y >= cut}


def zones(ch, pc98, cho_ref, refs):
    cho, jung, jong = cl.decompose(ch)
    jz = batchim_block(cl.jong_zone(ch, pc98)) if jong else set()
    cz = cl.cho_zone(ch, pc98, cho_ref, refs) - jz
    vz = cl.ALL_PX - jz - cz
    return cz, vz, jz


def on(rows, cells):
    return frozenset((y, x) for (y, x) in cells if rows[y][x] == "#")


def _ink(rows):
    return frozenset((y, x) for y in range(16) for x in range(16) if rows[y][x] == "#")


def zone_parts(ch, rows, pc98, cho_ref, corpus):
    """This syllable's own cell -> pixels, cut by PC-98's 받침 variance zone.
    None when the zone cut cannot be trusted and the caller must fall back to
    subtraction: either PC-98 has no such glyph (outside KS X 1001), or it has
    too few of this (초성,중성) to measure the 받침 zone at all.

    That second case is not rare and it was corrupting the library. jong_zone
    needs at least two PC-98 syllables sharing (초성,중성) to see what moves; for
    combinations KS X 1001 barely covers (ㅍ+ㅝ, say) it finds none and returns
    an EMPTY zone. The 받침 then counts as 초중성 ink, so the 초중성 component
    ships with a batchim baked in -- and composing adds the real 종성 on top of
    it. 풜 came out with two stacked batchims filling the lower half. Hand-drawn
    glyphs never contain a filled 3x3 block (0 of 2,669); composed ones did in
    159 syllables, which this cut to 84."""
    if pc98(ch) is None:
        return None
    lv_c, *rest = cells_for(ch)
    cz, vz, jz = zones(ch, pc98, cho_ref, corpus)
    if rest and not jz:
        return None
    parts = {lv_c: on(rows, cz) | on(rows, vz)}            # everything above 받침
    if rest:
        parts[rest[0]] = on(rows, jz)
    return parts


# A 초중성(LV) sitting above a 받침 never reaches below this row. Anything
# deeper is batchim ink the cut failed to take out, and unioning a real 종성(T)
# on top of it is what produced solid bricks (풜, 뒐). Rejecting those splits
# outright took filled-3x3 blobs from 159 to 0; hand-drawn glyphs have none in
# 2,669.
LV_FLOOR = 9


def _lv_polluted(cell, px):
    return (cell[0] == "LV" and cell[2][0] and px
            and max(y for y, _ in px) > LV_FLOOR)


def observe(corpus, pc98, cho_ref):
    """cell -> Counter of candidate pixel sets.

    Measured first: a syllable splits by PC-98's 받침 zone only when PC-98 can
    actually show where the 받침 ends (zone_parts returns None otherwise), and
    only when the resulting LV respects LV_FLOOR. A syllable with no 받침
    needs no split, so it always counts.

    Everything else -- representative syllables drawn to fill a cell, which are
    outside KS X 1001 by definition -- gets ONE subtraction pass: remove the
    already-measured other cell, keep the remainder. Two rules make this safe,
    both learned the hard way:

      * subtract only MEASURED components, never another subtraction's output.
        Chaining let one bad split seed the next and manufactured components
        nobody drew.
      * drop an LV remainder that breaks LV_FLOOR rather than storing it.

    Without the pass a drawn representative could never fill its own cell (맔
    is outside PC-98, so 종성 ㄽ stayed empty however often it was drawn), which
    makes the --missing worklist unfulfillable. With it, and the two rules:
    93.6% exact, 0.49px, 0 blobs, 176 cells left to draw."""
    measured = defaultdict(Counter)
    leftover = []
    for ch, rows in corpus.items():
        parts = zone_parts(ch, rows, pc98, cho_ref, corpus)
        if parts is None or any(_lv_polluted(c, px) for c, px in parts.items()):
            cells = cells_for(ch)
            if len(cells) == 1:               # no 받침 -> nothing to split off
                measured[cells[0]][_ink(rows)] += 1
            else:
                leftover.append((ch, rows))
            continue
        for cell, px in parts.items():
            measured[cell][px] += 1

    seen = {cell: Counter(c) for cell, c in measured.items()}
    for ch, rows in leftover:
        lv_c, t_c = cells_for(ch)
        px = _ink(rows)
        for target, other in ((t_c, lv_c), (lv_c, t_c)):
            if target in measured or other not in measured:
                continue
            cand = px - measured[other].most_common(1)[0][0]
            if _lv_polluted(target, cand):
                continue
            seen.setdefault(target, Counter())[cand] += 1
            break
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
    ap.add_argument("--build", action="store_true")
    args = ap.parse_args()

    corpus = load_corpus()
    pc98 = cl.load_pc98()
    cho_ref = build_zone_indices(corpus, pc98)
    seen = observe(corpus, pc98, cho_ref)
    lib = {cell: c.most_common(1)[0][0] for cell, c in seen.items()}

    req = required_cells()
    kinds = Counter(k for k, _, _ in req)
    print(f"library: {len(lib)} cells filled / {len(req)} required "
          f"(초중성 {kinds['LV']} + 종성 {kinds['T']}), "
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
            rows = corpus[ch]
            # Mirror observe()'s own accept/reject, then hold out exactly what
            # this syllable contributed. A split it rejected never entered the
            # library, so there is nothing to remove and nothing to test.
            own = zone_parts(ch, rows, pc98, cho_ref, corpus)
            if own is None or any(_lv_polluted(c, px) for c, px in own.items()):
                skipped += 1
                continue
            held = {cell: Counter(c) for cell, c in seen.items()}
            for cell, part in own.items():
                if held.get(cell, {}).get(part):
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
            print(f"  {kind:4s} {jamo}  벌{beol}  영향 음절 {blocked[cell]}")

    if args.build:
        full = {}
        composed_flag = {}
        for ch in FULL:
            if ch in corpus:
                full[ch] = corpus[ch]
                composed_flag[ch] = False
            else:
                out = compose(ch, lib)
                if out is not None:
                    full[ch] = out
                    composed_flag[ch] = True
        os.makedirs(os.path.dirname(FULL_OUT), exist_ok=True)
        json.dump(full, open(FULL_OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        hand = sum(1 for v in composed_flag.values() if not v)
        made = sum(1 for v in composed_flag.values() if v)
        print(f"\nbuild: {len(full)}/{len(FULL)} -> {FULL_OUT}")
        print(f"  {hand} hand-drawn (verbatim) + {made} composed"
              f" ({len(FULL) - len(full)} uncomposable)")
        write_full_specimen(full, composed_flag)


def write_full_specimen(full, composed_flag):
    """One PNG over all 11,172 in codepoint order, no labels (too dense to be
    legible at this scale) -- composed (non-hand-confirmed) cells get a faint
    tint so the ones that still need a human eye stand out while scanning."""
    from PIL import Image
    cols, scale, pad = 100, 2, 1
    cw = 16 * scale + pad
    chars = FULL
    rows = (len(chars) + cols - 1) // cols
    W = cols * cw + pad
    H = rows * cw + pad
    img = Image.new("RGB", (W, H), (255, 255, 255))
    px = img.load()
    for i, ch in enumerate(chars):
        gx = pad + (i % cols) * cw
        gy = pad + (i // cols) * cw
        rows_px = full.get(ch)
        if rows_px is None:
            continue
        tint = (238, 238, 245) if composed_flag.get(ch) else (255, 255, 255)
        for y in range(16):
            for x in range(16):
                on_px = rows_px[y][x] == "#"
                color = (20, 20, 20) if on_px else tint
                for dy in range(scale):
                    for dx in range(scale):
                        px[gx + x * scale + dx, gy + y * scale + dy] = color
    img.save(FULL_SPECIMEN)
    print(f"  specimen -> {FULL_SPECIMEN}")


if __name__ == "__main__":
    main()
