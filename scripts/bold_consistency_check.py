"""Find Bold (original bitmap) glyphs where a wrong jamo shape was pasted in.

Not a pixel-defect scanner (has_blob/has_double_stem in compose_components.py
already cover "shape that could never be hand-drawn") -- this looks for the
opposite failure: a glyph that is internally clean and well-formed, but shows
the WRONG jamo for its own codepoint. Plausible in a machine-generated
조합형 font like the original 1989 bitmap (docs/ROADMAP.md) if a component
got pasted from the wrong donor during its construction; harder to catch by
eye precisely because nothing about the shape itself looks broken.

Two checks, both exploiting the same fact: the font is componentized enough
to check itself against its own overwhelming regularity.

  TOP  (초중성, rows 0-7, above LV_FLOOR): fixing (초성,중성), all 27 batchim
       variants should share pixel-identical rows 0-7 -- measured 396/399
       (초성,중성) groups do. A minority within an otherwise-unanimous group
       is a candidate (e.g. 쏀's top is pixel-identical to ㅆ+ㅔ's template,
       not its own ㅆ+ㅖ -- the wrong vowel was pasted in).

  BOTTOM (종성, rows 9-15): fixing (종성, wide-vowel-class), the batchim
       shape should be near-identical across every (초성,중성) host that
       carries it. Measured over the full 11,172: legitimate variation
       exists (multiple real clusters per group, not always exactly one),
       so "smaller than the largest cluster, individually" is the right
       minority test -- an earlier version of this script used "total
       minority share < 15%" and that aggregate buried true singleton
       outliers under legitimate multi-cluster variation. Fixed version
       finds 45, not 3 -- e.g. ALL 27 batchim variants of ㅆ+ㅕ turned out
       wrong, not just the one (쎻) the top-band check alone could see.

A TOP candidate is then checked against every OTHER (초성,중성)'s canonical
template -- an exact match names the likely donor and turns "something
looks off" into "the ㅔ vowel was pasted where ㅖ should be", a call a human
can act on directly. BOTTOM candidates are reported against the largest
cluster for their (종성,wide) group instead (there is no "canonical
(종성,wide)" naming scheme as legible as (초성,중성) is, since legitimate
multi-cluster variation means several hosts can be simultaneously normal).

Usage: python scripts/bold_consistency_check.py [--specimen]
Fixes go in tools/glyphs_bold.json (same hand-override mechanism as every
other Bold correction) -- this script only finds candidates, never writes.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "tools")
sys.path.insert(0, "scripts")
import pixelfont as pf
import compose_light as cl
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANKBC = os.path.join(ROOT, "original", "HANKBC.ttf")
GLYPHS_BOLD = os.path.join(ROOT, "tools", "glyphs_bold.json")
SPECIMEN = os.path.join(ROOT, "build", "bold_consistency_specimen.png")

# 초중성(LV) 잉크는 받침이 있어도 이 행 아래로 안 내려간다-- compose_components.py
# LV_FLOOR와 같은 값, 같은 근거(원본을 그대로 벡터화한 게 Bold라 행 번호가 동일).
TOP_ROWS = 8

# t_beol()과 같은 폭-분류 기준(compose_components.py) -- 받침이 자리를 잡을 때
# 위 초중성이 얼마나 넓은지가 갈리는 축. 여기서도 같은 축으로 묶어야 "정상 변주"와
# "진짜 이상치"가 안 섞인다.
WIDE_JUNG = frozenset("ㅏㅑㅘ")


def _art(strike, cmap, ch):
    gn = cmap.get(ord(ch))
    if gn is None or gn not in strike:
        return None
    w, rows = strike[gn]
    return tuple("".join("#" if r & (1 << (w - 1 - x)) else "." for x in range(w))
                 for r in rows)


def find_candidates(strike, cmap):
    """{ch: (own_top, exact_donor_or_None, nearest_(cho,jung,dist))}, plus the
    canon dict itself (needed by --specimen to draw the "should be" row)."""
    canon = {}   # (cho,jung) -> majority top-8 tuple
    per_group = defaultdict(dict)   # (cho,jung) -> {top: [ch,...]}
    for cho in cl.CHO:
        for jung in cl.JUNG:
            counts = Counter()
            for jong in cl.JONG[1:]:
                ch = cl.compose_ch(cho, jung, jong)
                art = _art(strike, cmap, ch)
                if art is None:
                    continue
                top = art[:TOP_ROWS]
                counts[top] += 1
                per_group[(cho, jung)].setdefault(top, []).append(ch)
            if counts:
                best = counts.most_common(1)[0][0]
                canon[(cho, jung)] = best

    def dist(a, b):
        return sum(1 for r1, r2 in zip(a, b) for x in range(len(r1)) if r1[x] != r2[x])

    out = {}
    for (cho, jung), buckets in per_group.items():
        if len(buckets) <= 1:
            continue
        ranked = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
        majority_n = len(ranked[0][1])
        for top, chars in ranked[1:]:
            if len(chars) >= majority_n:   # not actually a minority -- skip
                continue
            exact = [k for k, t in canon.items() if t == top and k != (cho, jung)]
            nearest = min(((k, dist(t, top)) for k, t in canon.items() if k != (cho, jung)),
                          key=lambda kt: kt[1])
            for ch in chars:
                out[ch] = (top, exact[0] if exact else None, nearest)
    return out, canon


def find_bottom_candidates(strike, cmap):
    """{ch: (own_bottom, majority_bottom, majority_rep, group_size)} for
    batchims that don't match the largest cluster for their (종성,wide) group.

    Not a simple "smaller than the biggest cluster" majority-vote -- real
    (종성,wide) groups often split into several legitimate clusters (measured:
    e.g. jong=ㄴ non-wide alone has 4, sized 189/113/19/19, ALL real: "smaller
    than the largest" alone would wrongly flag the 113 and both 19s too, 151
    characters of false positives from that one group alone). What actually
    separates true outliers is size, not rank: they measure as singletons or
    near-singletons (<=5% of the largest cluster, floor 2) while every real
    cluster this project has found is a meaningful double-digit-or-bigger
    fraction of the group."""
    per_group = defaultdict(dict)   # (jong,wide) -> {bottom: [ch,...]}
    for jong in cl.JONG[1:]:
        for wide in (False, True):
            for jung in cl.JUNG:
                if (jung in WIDE_JUNG) != wide:
                    continue
                for cho in cl.CHO:
                    ch = cl.compose_ch(cho, jung, jong)
                    art = _art(strike, cmap, ch)
                    if art is None:
                        continue
                    bottom = art[TOP_ROWS:]
                    per_group[(jong, wide)].setdefault(bottom, []).append(ch)

    out = {}
    for (jong, wide), buckets in per_group.items():
        if len(buckets) <= 1:
            continue
        ranked = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
        top_bottom, top_chars = ranked[0]
        cutoff = max(2, len(top_chars) * 0.05)
        for bottom, chars in ranked[1:]:
            if len(chars) > cutoff:   # a real cluster, not a true outlier -- see docstring
                continue
            for ch in chars:
                out[ch] = (bottom, top_bottom, top_chars[0], len(top_chars))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specimen", action="store_true",
                    help="write a PNG comparing each candidate to its own "
                         "syllable's correct template")
    ap.add_argument("--all", action="store_true",
                    help="also list candidates already overridden in "
                         "glyphs_bold.json (default: hide them -- they're done)")
    args = ap.parse_args()

    font = TTFont(HANKBC)
    strike = pf.read_strike(font)
    cmap = font.getBestCmap()
    fixed = set(json.load(open(GLYPHS_BOLD, encoding="utf-8")))

    top_cands, canon = find_candidates(strike, cmap)
    bot_cands = find_bottom_candidates(strike, cmap)
    union = sorted(set(top_cands) | set(bot_cands))
    remaining = [ch for ch in union if args.all or ch not in fixed]

    print(f"top-band(rows 0-{TOP_ROWS - 1}) 후보: {len(top_cands)}자   "
          f"bottom-band(rows {TOP_ROWS}-15) 후보: {len(bot_cands)}자   "
          f"합집합: {len(union)}자   glyphs_bold.json에 이미 있음: {len(union) - len(remaining)}자\n")

    by_group = defaultdict(list)
    for ch in remaining:
        cho, jung, jong = cl.decompose(ch)
        by_group[(cho, jung)].append((ch, jong))
    for (cho, jung), members in sorted(by_group.items()):
        tags = []
        for ch, jong in members:
            t = "T" if ch in top_cands else ""
            b = "B" if ch in bot_cands else ""
            tags.append(f"{ch}({jong or '-'}{t}{b})")
        print(f"  {cho}+{jung}: {len(members)}자  " + " ".join(tags))
    print(f"\n(T=top-band 후보, B=bottom-band 후보. --specimen으로 이미지 생성,"
          f" --all로 이미 고친 것도 같이 보기)")

    if args.specimen and remaining:
        _write_specimen(strike, cmap, top_cands, canon, bot_cands, remaining)
        print(f"\nwrote {SPECIMEN}")


def _write_specimen(strike, cmap, top_cands, canon, bot_cands, remaining):
    """Three columns per candidate: actual (as shipped) / expected (own
    canonical top if TOP-flagged, own majority bottom if BOTTOM-flagged,
    the actual glyph's own data otherwise) / a same-family reference glyph
    that shows where the wrong piece likely came from."""
    from PIL import Image, ImageDraw

    scale, pad, label_h, gap = 14, 3, 16, 24
    cell = 16 * scale + pad * 2
    col_w = cell + gap
    row_h = cell + label_h + 10
    img = Image.new("RGB", (col_w * 3, row_h * len(remaining) + 10), "white")
    draw_ctx = ImageDraw.Draw(img)

    def draw_art(art, x0, y0):
        for y in range(16):
            for x in range(len(art[0])):
                if art[y][x] == "#":
                    for dy in range(scale):
                        for dx in range(scale):
                            img.putpixel((x0 + pad + x * scale + dx,
                                          y0 + pad + y * scale + dy), (20, 20, 20))

    for i, ch in enumerate(remaining):
        y0 = i * row_h
        actual = _art(strike, cmap, ch)
        cho, jung, jong = cl.decompose(ch)
        is_top = ch in top_cands
        is_bot = ch in bot_cands
        tag = ("T" if is_top else "") + ("B" if is_bot else "")
        draw_art(actual, 0, y0)
        draw_ctx.text((pad, y0 + cell), f"{ch} actual [{tag}]", fill=(0, 0, 0))

        new_top = canon[(cho, jung)] if is_top else actual[:TOP_ROWS]
        new_bot = bot_cands[ch][1] if is_bot else actual[TOP_ROWS:]
        draw_art(new_top + new_bot, col_w, y0)
        draw_ctx.text((col_w + pad, y0 + cell), "expected", fill=(0, 100, 0))

        ref_ch, ref_label = None, ""
        if is_top:
            top, exact, (nk, nd) = top_cands[ch]
            ec, ej = exact if exact else nk
            ref_ch = next((cl.compose_ch(ec, ej, j) for j in cl.JONG[1:]
                           if cl.compose_ch(ec, ej, j) not in top_cands), None)
            ref_label = f"{ref_ch} top {'donor' if exact else f'nearest({nd}px)'}"
        elif is_bot:
            ref_ch = bot_cands[ch][2]
            ref_label = f"{ref_ch} bottom donor (n={bot_cands[ch][3]})"
        if ref_ch:
            draw_art(_art(strike, cmap, ref_ch), col_w * 2, y0)
            draw_ctx.text((col_w * 2 + pad, y0 + cell), ref_label, fill=(150, 0, 0))

    img.save(SPECIMEN)


if __name__ == "__main__":
    main()
