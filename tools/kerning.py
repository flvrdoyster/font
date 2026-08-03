"""Measured kerning for proportional glyphs (Latin/digits/symbols -- NOT
Hangul, which stays monospace on purpose: gensei-pc98 renders it into a
fixed 16px grid, so kerning would misalign it against the game's tiles).

The problem this fixes: tools/spacing.py gives every glyph the same 1px side
bearing regardless of shape. That is exactly right for flat-edged pairs
(H|I) but visibly too loose for diagonal ones (A|V, W|A, ...) -- their
strokes taper away from the edge, so the 1+1px gap between BOUNDING BOXES
reads as a much bigger gap between the actual ink.

The fix is measured, not a hand-typed list of "classic" pairs (AV, WA, ...):
that folklore only covers Latin capitals, and this project also kerns
digits and symbols, which have no such folklore. Instead:

  For a glyph shifted the way proportional() already shifts it (left ink
  edge at the 1px side bearing), define per row:
    right profile  R(row) = bbox_right_col - rightmost_ink_col_in_that_row
    left  profile  L(row) = leftmost_ink_col_in_that_row - bbox_left_col
  both >= 0 ("how many px this row is recessed from that glyph's own ink
  bounding box edge"). A rectangular glyph like H has R(row)=L(row)=0 on
  every row; a diagonal one like A has R(row) growing as the stroke tapers.

  Placing X then Y adjacent, algebra collapses the actual row-by-row ink
  gap to exactly `2 + R_X(row) + L_Y(row)` (2 = the two 1px side bearings)
  -- independent of either glyph's width or advance. So the closest
  approach across all rows where both have ink is `2 + min(R_X + L_Y)`,
  and the kern needed to bring that back to the baseline 2px is simply
  `-min(R_X(row) + L_Y(row))`: never positive under this model (a glyph's
  ink never extends past its own bounding box, so two glyphs can never
  already be CLOSER than 2px), rounds to an exact integer pixel count with
  no threshold-picking, and needs no cross-corpus calibration to know what
  "normal" looks like -- 2px (the side bearings already in place) IS normal
  by construction.

  Kerning CLASSES fall out of the same fact for free: two glyphs with an
  identical right profile behave identically as the first half of any pair
  (the formula only ever consults R_X(row), never X's width/advance/
  identity), so grouping by the exact profile is lossless, not an
  approximation -- unlike typical class kerning, no member is a slightly-
  wrong compromise for the group.

Not covered, on purpose: optical compensation for round vs. flat shapes at
an EQUAL 2px gap (an O|O pair can look tighter than an H|H pair at the same
literal spacing because roundness reads as leaning into the gap). That is a
real, separate refinement with no ink-bounds measurement behind it -- would
need to be an eyeballed override, not something this script computes.

Usage: python tools/kerning.py --weight light|regular [--report] [--specimen]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spacing as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLYPHS_FILES = {
    "regular": os.path.join(ROOT, "tools", "glyphs_bold.json"),   # 2px stems
    "light": os.path.join(ROOT, "tools", "glyphs_light.json"),    # 1px stems
}
OVERRIDES_FILE = os.path.join(ROOT, "tools", "kerning_overrides.json")
SIDE = 1   # must match spacing.proportional's default


def _bits(row_str):
    return int(row_str.replace("#", "1").replace(".", "0"), 2)


def kernable_chars(weight):
    """Single-char keys from glyphs_<weight>.json eligible for kerning:
    proportional (not Hangul, not fullwidth -- spacing.py already keeps
    those monospace), non-blank, and not a digit.

    Digits are excluded on purpose, not because the measurement is wrong for
    them: fontbakery's has-tabular-kerning check caught this directly (e.g.
    "four"+radical -64) once digits were included -- the general convention
    that digits must never be kerned, so columns of figures stay aligned in
    any tabular use of the font. (An earlier version of this comment also
    cited gensei-pc98's HUD; that was wrong -- the game draws fixed cells
    and never consumes TTF metrics, so only general typography is at stake
    here. Note Bold digits all share an 8px advance, but Light '1' is 5px
    vs 7px for the other nine -- Light figures are proportional, a separate,
    deliberate leave-as-is.) Kerning a digit against a NEIGHBORING symbol
    (radical, Ω, lozenge, ...) would be correct for that one pair and wrong
    for the tabular property every other digit pairing relies on; excluding
    digits entirely is the one rule that can't break it. Non-digit-vs-
    non-digit kerning is unaffected."""
    data = json.load(open(GLYPHS_FILES[weight], encoding="utf-8"))
    out = {}
    for ch, rows in data.items():
        if len(ch) != 1:
            continue
        cp = ord(ch)
        if 0xAC00 <= cp <= 0xD7A3 or sp._is_fullwidth(cp) or ch in "0123456789":
            continue
        width = len(rows[0])
        bits = [_bits(r) for r in rows]
        if sp.ink_bounds(width, bits) is None:
            continue
        out[ch] = (width, bits)
    return out


def profiles(width, bits, cp=None):
    """(right_profile, left_profile): {row: recession_px}, ink rows only.

    Anchored at spacing.body_bounds' BODY edges -- the same edges the side
    bearings anchor to -- so the pair-gap identity `gap(row) = 2 + R + L`
    keeps holding after body-edge spacing landed. A lone-row protrusion
    (i/l's flare, t/f's crossbar) shows up as recession -1: genuinely 1px
    closer to the neighbor than the body, exactly how it renders."""
    _, _, body_lo, body_hi = sp.body_bounds(width, bits, cp)
    right, left = {}, {}
    for row, mask in enumerate(bits):
        cols = [c for c in range(width) if mask & (1 << (width - 1 - c))]
        if not cols:
            continue
        right[row] = body_hi - max(cols)
        left[row] = min(cols) - body_lo
    return right, left


# A pair needs at least this many shared ink rows before its kern is
# trusted. Below this, "closest approach" is one coincidental row deciding
# the whole value -- measured: symbol pairs with 1-3 shared rows (e.g. an
# arrow's tiny tip row lining up with an unrelated mark) produced the most
# extreme values (up to -12px, average |kern| 2.6) precisely because a
# single thin overlap has no other row to corroborate it; every genuine
# Latin-letter/digit pair, across the full 62-glyph alphabet x alphabet
# grid, shares at least 7 rows (the tightest case: digits against x-height
# lowercase, e.g. "0a"). MIN_SHARED_ROWS sits with margin below that real
# floor, so no genuine Latin/digit signal is at risk -- only the sub-Latin
# sparse-symbol coincidences it was measured to explain.
MIN_SHARED_ROWS = 5


def pair_kern(right_x, left_y):
    """Measured kern (<=0 px) for X followed by Y, from their profiles."""
    shared = right_x.keys() & left_y.keys()
    if len(shared) < MIN_SHARED_ROWS:
        return 0
    closest = min(right_x[row] + left_y[row] for row in shared)
    return -closest if closest > 0 else 0


def build_classes(chars):
    """glyph -> (right_class_id, left_class_id), plus the class -> profile
    maps. Classing is exact (see module docstring): same profile, same id."""
    right_ids, left_ids = {}, {}
    right_of, left_of = {}, {}
    for ch, (width, bits) in chars.items():
        r, l = profiles(width, bits, ord(ch))
        rk, lk = tuple(sorted(r.items())), tuple(sorted(l.items()))
        if rk not in right_ids:
            right_ids[rk] = f"R{len(right_ids):03d}"
            right_of[right_ids[rk]] = r
        if lk not in left_ids:
            left_ids[lk] = f"L{len(left_ids):03d}"
            left_of[left_ids[lk]] = l
        chars[ch] = (width, bits, right_ids[rk], left_ids[lk])
    return chars, right_of, left_of


def kern_table(weight):
    """{(right_class, left_class): kern_px} for every non-zero class pair,
    plus the glyph->class assignment. Hand overrides (tools/
    kerning_overrides.json, keyed "X\\tY" -- see the editor's 커닝 tab) win
    over the measured value for that specific GLYPH pair; anything not
    overridden uses its class value."""
    chars = kernable_chars(weight)
    chars, right_of, left_of = build_classes(chars)
    classes = {ch: (rc, lc) for ch, (w, b, rc, lc) in chars.items()}

    table = {}
    for rc, rprof in right_of.items():
        for lc, lprof in left_of.items():
            v = pair_kern(rprof, lprof)
            if v:
                table[(rc, lc)] = v
    return table, classes


def load_overrides(weight):
    if not os.path.exists(OVERRIDES_FILE):
        return {}
    all_over = json.load(open(OVERRIDES_FILE, encoding="utf-8"))
    return all_over.get(weight, {})


def effective_pairs(weight):
    """{(X, Y): kern_px} for every kernable glyph pair with a nonzero final
    value -- class value, with hand overrides applied per-pair. This is
    what build_ufo.py should actually write (as glyph-level kerning; UFO
    groups are an optimization this doesn't need at ~250 glyphs)."""
    table, classes = kern_table(weight)
    overrides = load_overrides(weight)
    chars = sorted(classes)
    out = {}
    for x in chars:
        rc = classes[x][0]
        for y in chars:
            lc = classes[y][1]
            key = f"{x}\t{y}"
            if key in overrides:
                v = overrides[key]
                if v:
                    out[(x, y)] = v
                continue
            v = table.get((rc, lc), 0)
            if v:
                out[(x, y)] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weight", choices=["light", "regular"], default="light")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--specimen", action="store_true")
    args = ap.parse_args()

    pairs = effective_pairs(args.weight)
    chars = kernable_chars(args.weight)
    table, classes = kern_table(args.weight)
    n_right = len({c[0] for c in classes.values()})
    n_left = len({c[1] for c in classes.values()})
    print(f"{args.weight}: {len(chars)}자, 오른쪽 클래스 {n_right}개 x 왼쪽 클래스 "
          f"{n_left}개, 0이 아닌 클래스쌍 {len(table)}개 -> 실제 글자쌍 {len(pairs)}개")

    if args.report:
        worst = sorted(pairs.items(), key=lambda kv: kv[1])[:40]
        print("\n가장 많이 당겨지는 쌍:")
        for (x, y), v in worst:
            print(f"  {x}{y}  {v:+d}px")

    if args.specimen and pairs:
        _write_specimen(args.weight, chars, pairs)


def _write_specimen(weight, chars, pairs):
    from PIL import Image
    worst = sorted(pairs.items(), key=lambda kv: kv[1])[:60]
    scale, gap_px = 8, 24
    row_h = 16 * scale + 6
    img_w = 400
    img = Image.new("RGB", (img_w, row_h * len(worst) + 10), "white")

    def draw(x0, y0, ch, dx_extra=0):
        width, bits = chars[ch]
        for row in range(16):
            for col in range(width):
                if bits[row] & (1 << (width - 1 - col)):
                    for dy in range(scale):
                        for dxp in range(scale):
                            px = x0 + dx_extra * scale + col * scale + dxp
                            py = y0 + row * scale + dy
                            if 0 <= px < img.width:
                                img.putpixel((px, py), (20, 20, 20))

    for i, ((x, y), v) in enumerate(worst):
        y0 = i * row_h
        wx, _ = chars[x]
        adv_x, shift_x = sp.proportional(wx, chars[x][1], ord(x))
        draw(10, y0, x, shift_x)
        draw(10 + adv_x * scale + v * scale, y0, y,
             sp.proportional(chars[y][0], chars[y][1], ord(y))[1])
    img.save(os.path.join(ROOT, "build", f"kerning_specimen_{weight}.png"))
    print(f"wrote build/kerning_specimen_{weight}.png")


if __name__ == "__main__":
    main()
