"""Proportional spacing derived from pixel ink bounds.

For a pixel font, a good proportional advance = ink width + fixed side bearings,
measured in whole pixels so the grid stays intact. Latin/symbols become
proportional; Hangul syllables stay full-width (they're designed to fill a
square cell). All values in pixels; multiply by pf.PX for font units.
"""
import sys
sys.path.insert(0, "tools")
import pixelfont as pf


def ink_bounds(width, rows):
    """Return (min_col, max_col) of set pixels, or None if blank."""
    lo, hi = None, None
    for r in rows:
        for c in range(width):
            if r & (1 << (width - 1 - c)):
                lo = c if lo is None else min(lo, c)
                hi = c if hi is None else max(hi, c)
    if lo is None:
        return None
    return lo, hi


def body_bounds(width, rows, cp=None):
    """(lo, hi, body_lo, body_hi) -- bbox edges plus the "body" edges spacing
    should anchor to, or None if blank.

    The body edge differs from the bbox edge only where a SINGLE row sets the
    bbox: i/l/j's stem-top flare and t/f's crossbar stick out 1px past the
    stem on one side. Anchoring the side bearing at the bbox there means the
    stem -- every other row -- sits `side`+1 from the glyph's edge, so e.g.
    'i' shows a 3px gap to its left neighbor but 2px to its right, on every
    row except the flare's. Measured on glyphs_light.json: i 7/8 rows, l
    9/10, t 7/9, f 8/10 rows recessed 1px behind a lone-row bbox edge; in
    running text these letters visibly lean right inside their own advance
    ("가운데 기준 한쪽으로 쏠림"). Anchoring at the body edge instead lets
    the lone protrusion overhang 1px into the bearing -- the same treatment
    serifs get in outline fonts -- with the glyph pixels untouched.

    "Single row" is literal (exactly one row at margin 0) and needs >=3 rows
    sitting EXACTLY 1px in to prove there is a FLAT body behind the
    protrusion. The exactness matters: a pointed shape (arrow head, ◆, <,
    the tip of a brace) also has one row at its extreme, but its neighbors
    recede gradually -- at most ~2 rows sit exactly 1px in -- and its tip is
    the design's edge, not an ornament past it. Measured: with the looser
    "within 1px" test, 50+ symbols fired per weight and facing tips (>< «
    ←→ ◆◆ ...) landed at 0px gaps; with the flat-body test only the
    flare/crossbar letters and Q's tail remain. Two-row-deep features like
    r's arm stay bbox-anchored either way (margin-0 count is 1 but the flat
    check fails).

    Applies to ASCII LETTERS only (pass cp; anything else keeps bbox
    anchoring). Measured reasons for each exclusion: digits -- '1'/'4' have
    flat-body serifs so the rule fires and breaks the uniform tabular
    advance every other digit shares; symbols -- ∏'s serifs and ☆/{/}'s
    profiles pass even the flat-body test, and two of them facing (∏∏, ☆☆,
    }{) would land at a 0px gap since both sides overhang. Letters can't
    collide this way: the survivors' overhangs (f i l t left at x-height
    top, Q right at the baseline tail row) never share a row from opposite
    sides."""
    b = ink_bounds(width, rows)
    if b is None:
        return None
    lo, hi = b
    lefts, rights = [], []
    for r in rows:
        cols = [c for c in range(width) if r & (1 << (width - 1 - c))]
        if not cols:
            continue
        lefts.append(min(cols) - lo)
        rights.append(hi - max(cols))
    body_lo, body_hi = lo, hi
    is_letter = cp is not None and (0x41 <= cp <= 0x5A or 0x61 <= cp <= 0x7A)
    if is_letter:
        if lefts.count(0) == 1 and lefts.count(1) >= 3:
            body_lo = lo + 1
        if rights.count(0) == 1 and rights.count(1) >= 3:
            body_hi = hi - 1
    return lo, hi, body_lo, body_hi


def proportional(width, rows, cp, side=1, space_px=4, keep_fullwidth=True):
    """Compute (advance_px, x_shift_px) for a glyph.

    - side: side bearing in pixels applied left and right of the ink BODY
      (see body_bounds; a lone-row protrusion overhangs the bearing by 1px).
    - space_px: advance for blank glyphs (e.g. space).
    - keep_fullwidth: Hangul syllables (and other wide glyphs) keep width px.
    Ink is shifted so its body's left edge sits at `side`.
    """
    if keep_fullwidth and _is_fullwidth(cp):
        return width, 0
    b = body_bounds(width, rows, cp)
    if b is None:
        return space_px, 0
    lo, hi, body_lo, body_hi = b
    advance = (body_hi - body_lo + 1) + 2 * side
    x_shift = side - body_lo     # body left edge lands at `side`
    return advance, x_shift


def _is_fullwidth(cp):
    """True for anything whose advance must come from its CELL, not its ink
    -- either genuine CJK fullwidth, or box-drawing/block glyphs, which tile
    edge-to-edge and silently produced nonsense proportional advances until
    this was measured while building kerning (v1.0.1 shipped with e.g. '│'
    at advance=3px, shift=-6px -- eleven of them next to each other landed in
    a third of the space a straight vertical rule needs). Same U+2500-259F
    boundary scripts/editor_server.py already uses for their reference-
    overlay baseline placement ("cell_glyph"), for the same underlying fact:
    these are cells, not text."""
    if cp is None:
        return False
    return (0xAC00 <= cp <= 0xD7A3        # Hangul syllables
            or 0x1100 <= cp <= 0x11FF     # Hangul Jamo
            or 0x3130 <= cp <= 0x318F     # compat Jamo
            or 0xFF00 <= cp <= 0xFFEF     # fullwidth forms
            or 0x2500 <= cp <= 0x259F)    # box drawing + block elements
