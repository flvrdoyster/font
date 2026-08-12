"""Where fullwidth alphanumerics live in the PC-98 BIOS font.bmp.

They sit in JIS X 0208 ku 3, which in this ROM's column-major layout is
column 3 -- the same block scripts/pc98_hangul_map.py indexes with
`row = 33 + (ten - 1)`. Verified against the standard ku 3 arrangement:
scanning col 3 finds exactly 62 inked cells, at ten 16-25 / 33-58 / 65-90 and
nowhere else, matching ０-９ / Ａ-Ｚ / ａ-ｚ with no leftovers on either side.

This lives in its own module because two callers must agree on it exactly:
scripts/editor_server.py reads these cells to draw the reference overlay, and
scripts/build_pc98_bmp.py WRITES our own glyphs back into them. If the two
ever drifted, the build would quietly stamp glyphs into cells the editor was
never showing.
"""

COL = 3          # ku 3 -> column 3 in the ROM's column-major layout
ROW0 = 33        # ten 1 lands on this row; row = ROW0 + (ten - 1)

# (first codepoint, last codepoint, ten of the first) per contiguous run.
_RUNS = (
    (0xFF10, 0xFF19, 16),   # ０-９
    (0xFF21, 0xFF3A, 33),   # Ａ-Ｚ
    (0xFF41, 0xFF5A, 65),   # ａ-ｚ
)


def ten_for(cp):
    """JIS ku-3 ten (1-94) for a fullwidth alnum codepoint, else None."""
    for lo, hi, ten0 in _RUNS:
        if lo <= cp <= hi:
            return ten0 + (cp - lo)
    return None


def cell_for(ch):
    """(col, row) of `ch`'s cell in font.bmp, or None if it isn't a
    fullwidth alnum. Cell -> pixel origin is col*16, row*16, same as every
    other map here."""
    ten = ten_for(ord(ch))
    if ten is None:
        return None
    return COL, ROW0 + (ten - 1)


def chars():
    """All 62 fullwidth alnum characters, in ten order."""
    return [chr(cp) for lo, hi, _ in _RUNS for cp in range(lo, hi + 1)]
