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


def proportional(width, rows, cp, side=1, space_px=4, keep_fullwidth=True):
    """Compute (advance_px, x_shift_px) for a glyph.

    - side: side bearing in pixels applied left and right of the ink.
    - space_px: advance for blank glyphs (e.g. space).
    - keep_fullwidth: Hangul syllables (and other wide glyphs) keep width px.
    Ink is shifted so its left edge sits at `side`.
    """
    if keep_fullwidth and _is_fullwidth(cp):
        return width, 0
    b = ink_bounds(width, rows)
    if b is None:
        return space_px, 0
    lo, hi = b
    ink_w = hi - lo + 1
    advance = ink_w + 2 * side
    x_shift = side - lo          # move ink so its left edge lands at `side`
    return advance, x_shift


def _is_fullwidth(cp):
    if cp is None:
        return False
    return (0xAC00 <= cp <= 0xD7A3        # Hangul syllables
            or 0x1100 <= cp <= 0x11FF     # Hangul Jamo
            or 0x3130 <= cp <= 0x318F     # compat Jamo
            or 0x3040 <= cp <= 0x30FF     # kana
            or 0xFF00 <= cp <= 0xFFEF)    # fullwidth forms
