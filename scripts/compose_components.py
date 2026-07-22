"""Jamo-component composer -- the scaling tool for the full 11,172 조합형.

Unlike compose_light.py (which lays consonants over a PC-98 base and so leaks
PC-98's 둥근모 rounding), this extracts angular 초성/중성/종성 components from the
CONFIRMED corpus and composes purely from them -- no PC-98 pixels reach the
output. That is also what the 11,172-syllable scale-up needs, since PC-98 only
covers 2,350: the other ~8,800 have no base to lay consonants over.

Pipeline:
  1. cut each confirmed syllable into 초성/중성/종성 pixel components, using
     PC-98 variance zones (compose_light.cho_zone / jong_zone) as the knife.
  2. bucket the components (finer than V/H/X where the shape actually differs)
     and keep one canonical component per bucket.
  3. compose any syllable by unioning its three canonical components.

CLI (run from repo root):
  python scripts/compose_components.py --validate   # reconstruct the corpus, report px error
  python scripts/compose_components.py --coverage   # 11,172 component coverage
"""
import argparse
import json
import os
from collections import defaultdict, Counter

import compose_light as cl

ROOT = cl.ROOT
CORPUS = os.path.join(ROOT, "build", "light_hangul.json")   # 2,350 confirmed

# ---- bucketing --------------------------------------------------------------
# The vowel's structure decides how the 초성 and 종성 must sit, so buckets are
# keyed on it, not just V/H/X. O/U/E = ㅗ/ㅜ/ㅡ base; N/W = narrow/wide vertical.
O_BASE = set("ㅗㅛㅘㅙㅚ")
U_BASE = set("ㅜㅠㅝㅞㅟ")
EU_BASE = set("ㅡㅢ")
WIDE_V = set("ㅐㅒㅔㅖ")


def vsub(jung):
    if jung in O_BASE:
        return "O"
    if jung in U_BASE:
        return "U"
    if jung in EU_BASE:
        return "E"
    if jung in WIDE_V:
        return "W"
    return "N"                     # narrow vertical (ㅏㅑㅓㅕㅣ)


def cho_bucket(jung, jong):
    return (cl.cho_bt(jung, jong), vsub(jung))


def jung_bucket(jung, jong):
    return (jung, bool(jong))       # vowel shifts with batchim presence


def jong_bucket(jung):
    return (cl.jong_bt(jung), vsub(jung))   # batchim shape tracks vowel width


# ---- component extraction ---------------------------------------------------

def zones(ch, pc98, cho_ref, refs):
    cho, jung, jong = cl.decompose(ch)
    jz = cl.jong_zone(ch, pc98) if jong else set()
    cz = cl.cho_zone(ch, pc98, cho_ref, refs) - jz
    vz = cl.ALL_PX - jz - cz
    return cz, vz, jz


def on(rows, cells):
    return frozenset((y, x) for (y, x) in cells if rows[y][x] == "#")


def build_library(corpus, pc98, cho_ref):
    """Return {kind: {bucket: {jamo: canonical component (frozenset of (y,x))}}}.
    Canonical = the most common component across the corpus for that slot."""
    buckets = {"cho": defaultdict(lambda: defaultdict(Counter)),
               "jung": defaultdict(lambda: defaultdict(Counter)),
               "jong": defaultdict(lambda: defaultdict(Counter))}
    for ch, rows in corpus.items():
        if pc98(ch) is None:
            continue
        cho, jung, jong = cl.decompose(ch)
        cz, vz, jz = zones(ch, pc98, cho_ref, corpus)
        cc, vv = on(rows, cz), on(rows, vz)
        # index under both the fine bucket and a coarse ("*") fallback bucket
        buckets["cho"][cho_bucket(jung, jong)][cho][cc] += 1
        buckets["cho"][(cl.cho_bt(jung, jong), "*")][cho][cc] += 1
        buckets["jung"][jung_bucket(jung, jong)][jung][vv] += 1
        buckets["jung"][(jung, "*")][jung][vv] += 1
        if jong:
            jj = on(rows, jz)
            buckets["jong"][jong_bucket(jung)][jong][jj] += 1
            buckets["jong"][(cl.jong_bt(jung), "*")][jong][jj] += 1

    lib = {"cho": {}, "jung": {}, "jong": {}}
    for kind, bmap in buckets.items():
        for bucket, jmap in bmap.items():
            lib[kind][bucket] = {j: cnt.most_common(1)[0][0] for j, cnt in jmap.items()}
    return lib


def _lookup(lib, kind, jamo, fine, coarse):
    """Fine bucket first, then coarser fallback -- lets a component drawn for
    one vowel stand in when the exact fine bucket is empty (coverage vs fit)."""
    for bucket in (fine, coarse):
        comp = lib[kind].get(bucket, {}).get(jamo)
        if comp is not None:
            return comp
    return None


def compose(ch, lib):
    """Pure-component render: union the three canonical components. None if a
    required component is missing (even after coarse fallback)."""
    cho, jung, jong = cl.decompose(ch)
    c = _lookup(lib, "cho", cho, cho_bucket(jung, jong), (cl.cho_bt(jung, jong), "*"))
    v = _lookup(lib, "jung", jung, jung_bucket(jung, jong), (jung, "*"))
    if c is None or v is None:
        return None
    px = set(c) | set(v)
    if jong:
        j = _lookup(lib, "jong", jong, jong_bucket(jung), (cl.jong_bt(jung), "*"))
        if j is None:
            return None
        px |= set(j)
    return ["".join("#" if (y, x) in px else "." for x in range(16))
            for y in range(16)]


# ---- CLI --------------------------------------------------------------------

def load_corpus():
    with open(CORPUS, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    args = ap.parse_args()

    corpus = load_corpus()
    pc98 = cl.load_pc98()
    cho_ref, _ = cl.build_indices(corpus)
    lib = build_library(corpus, pc98, cho_ref)
    print(f"library: cho {sum(len(v) for v in lib['cho'].values())} / "
          f"jung {sum(len(v) for v in lib['jung'].values())} / "
          f"jong {sum(len(v) for v in lib['jong'].values())} components "
          f"in {len(lib['cho'])}+{len(lib['jung'])}+{len(lib['jong'])} buckets")

    if args.validate:
        exact = miss = 0
        errs = []
        for ch, rows in corpus.items():
            out = compose(ch, lib)
            if out is None:
                miss += 1
                continue
            d = sum(out[y][x] != rows[y][x] for y in range(16) for x in range(16))
            errs.append(d)
            if d == 0:
                exact += 1
        n = len(errs)
        print(f"validate: {exact}/{n} exact, mean {sum(errs)/n:.2f}px, "
              f"max {max(errs)}px, {miss} uncomposable")

    if args.coverage:
        full = [chr(c) for c in range(0xAC00, 0xD7A4)]
        ok = sum(1 for ch in full if compose(ch, lib) is not None)
        print(f"coverage: {ok}/{len(full)} of 11,172 composable from current library")


if __name__ == "__main__":
    main()
