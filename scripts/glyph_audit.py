"""Measure the built fonts for glyph-level inconsistencies.

Usage: python scripts/glyph_audit.py [build/DokkaebiDNRGothic-Regular.ttf build/DokkaebiDNRGothic-Bold.ttf]
"""
import os
import sys
import freetype

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT = [os.path.join(ROOT, "build", f"DokkaebiDNRGothic-{w}.ttf") for w in ("Regular", "Bold")]

HANGUL = range(0xAC00, 0xD7A4)
SHAPES = range(0x2500, 0x2600)
BRACKETS = "()[]{}（）［］｛｝〈〉《》「」『』【】〔〕"
KNOWN_THIN_IN_BOLD = set("↑↓↕W")


def rasterize(path):
    face = freetype.Face(path)
    face.set_pixel_sizes(0, 16)
    cache = {}

    def get(cp):
        if cp not in cache:
            face.load_char(chr(cp), freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO
                           | freetype.FT_LOAD_NO_HINTING)
            g = face.glyph
            bmp = g.bitmap
            width = max(g.advance.x // 64, g.bitmap_left + bmp.width, 1)
            rows = [[0] * width for _ in range(16)]
            for by in range(bmp.rows):
                r = 16 - g.bitmap_top + by
                if not 0 <= r < 16:
                    continue
                for bx in range(bmp.width):
                    if (bmp.buffer[by * bmp.pitch + (bx >> 3)] >> (7 - (bx & 7))) & 1:
                        c = g.bitmap_left + bx
                        if 0 <= c < width:
                            rows[r][c] = 1
            cache[cp] = rows
        return cache[cp]

    cmap = {cp for cp, _ in face.get_chars() if cp > 0x20}
    return get, cmap


def vertical_extent(rows):
    ink = [i for i, r in enumerate(rows) if any(r)]
    return (ink[0], ink[-1]) if ink else None


def thin_vertical_runs(rows):
    width = len(rows[0])
    count = 0
    for x in range(width):
        run = 0
        for y in range(16):
            lone = rows[y][x] and not (x and rows[y][x - 1]) and not (x + 1 < width and rows[y][x + 1])
            run = run + 1 if lone else 0
            if run == 3:
                count += 1
    return count


def main():
    paths = sys.argv[1:] or DEFAULT
    (get_r, cmap_r), (get_b, cmap_b) = rasterize(paths[0]), rasterize(paths[1])
    common = sorted(cmap_r & cmap_b)
    others = [cp for cp in common if cp not in HANGUL]

    print("== Bold glyphs with 1px vertical strokes")
    thin = [chr(cp) for cp in others
            if cp not in SHAPES and chr(cp) not in KNOWN_THIN_IN_BOLD and thin_vertical_runs(get_b(cp))]
    print("  " + ("".join(thin) or "-"))
    same = [chr(cp) for cp in others if cp not in SHAPES and get_r(cp) == get_b(cp)]
    print("== identical in both weights (outside box/shape blocks)")
    print("  " + ("".join(same) or "-"))

    print("== vertical extent differs between weights (top-bottom, Regular / Bold)")
    for cp in others:
        er, eb = vertical_extent(get_r(cp)), vertical_extent(get_b(cp))
        if er != eb:
            print(f"  {chr(cp)} U+{cp:04X}  {er} / {eb}")

    print("== bracket heights (Regular / Bold)")
    for ch in BRACKETS:
        if ord(ch) in cmap_r:
            print(f"  {ch} {vertical_extent(get_r(ord(ch)))} / {vertical_extent(get_b(ord(ch)))}")


if __name__ == "__main__":
    main()
