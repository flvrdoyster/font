"""End-to-end verification: render the BUILT TTF at 16px mono and compare every
glyph to the original bitmap, pixel-for-pixel. Proves the shipped font (after
fontmake's RemoveOverlaps + CubicToQuadratic) is faithful to the source bitmaps.
"""
import sys
import freetype
from fontTools.ttLib import TTFont

sys.path.insert(0, "tools")
import pixelfont as pf

# Defaults to the Bold member: it's the 2px stems = the pixel-exact
# vectorization of the original bitmap, which is what this test validates.
BUILT = sys.argv[1] if len(sys.argv) > 1 else "build/DokkaebiDNRGothic-Bold.ttf"


def render_mono(face, cp, width):
    """Return list of 16 row bitmasks for codepoint cp rendered at 16px mono,
    placed into a width x 16 cell with top at cell top (bearingY = 16)."""
    face.load_char(chr(cp), freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO
                   | freetype.FT_LOAD_NO_HINTING)
    g = face.glyph
    bmp = g.bitmap
    rows = [0] * pf.CELL
    # top of the 16px cell is at y = ascender = 16px above baseline.
    # freetype bitmap_top = pixels from baseline up to bitmap's top row.
    for by in range(bmp.rows):
        cell_row = (pf.CELL - g.bitmap_top) + by   # row 0 = cell top
        if not (0 <= cell_row < pf.CELL):
            continue
        for bx in range(bmp.width):
            byte = bmp.buffer[by * bmp.pitch + (bx >> 3)]
            if (byte >> (7 - (bx & 7))) & 1:
                col = g.bitmap_left + bx
                if 0 <= col < width:
                    rows[cell_row] |= (1 << (width - 1 - col))
    return rows


def main():
    orig = TTFont("original/HANKBC.ttf")
    strike = pf.read_strike(orig)
    cmap = orig.getBestCmap()

    face = freetype.Face(BUILT)
    face.set_pixel_sizes(0, 16)

    total = mism = 0
    examples = []
    for cp, gname in cmap.items():
        if gname not in strike:
            continue
        width, rows = strike[gname]
        if width == 0:
            continue
        total += 1
        got = render_mono(face, cp, width)
        if got != rows:
            mism += 1
            if len(examples) < 8:
                examples.append((cp, gname))

    print(f"built font: {BUILT}")
    print(f"glyphs compared: {total}")
    print(f"pixel-exact mismatches vs original bitmap: {mism}")
    if examples:
        print("examples:", ", ".join(f"U+{cp:04X}({gn})" for cp, gn in examples))


if __name__ == "__main__":
    main()
