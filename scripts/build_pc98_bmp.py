"""Assemble a test PC-98 BIOS font.bmp with our Light Hangul dropped in.

Takes the original gensei-pc98 font.bmp untouched (ANK table, kana, kanji,
symbols, ...) and overwrites:

  - the 완성형 Hangul cells (tools/pc98_hangul_map.json, cols 16-40) with our
    Light-weight 2,350-syllable set (build/light_hangul.json, see
    scripts/compose_light.py)
  - the 반각 한글 cells the user has drawn so far (tools/pc98_halfwidth_map.json,
    cols 10-11; tools/glyphs_halfwidth.json, see tools/halfwidth_editor.html)
    -- each glyph is 8px wide, written left-aligned in its 16px cell with the
    remaining 8 columns cleared (matches how the ROM's own halfwidth glyphs
    are laid out)

Everything else in the bitmap -- including kana, which now also lives in the
완성형 block per the PC-98 kana discovery -- is left exactly as the original
ROM drew it.

This is a test/preview output only: it writes a new file, never touches
../gensei-pc98 itself.

Inputs:  ../gensei-pc98/docs/bios/font.bmp,
         tools/pc98_hangul_map.json, build/light_hangul.json
           (run scripts/compose_light.py first if stale)
         tools/pc98_halfwidth_map.json, tools/glyphs_halfwidth.json
Output:  build/font_light.bmp

Run from the repo root:  python scripts/build_pc98_bmp.py
"""
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BMP = os.path.join(ROOT, "..", "gensei-pc98", "docs", "bios", "font.bmp")
PC98_MAP = os.path.join(ROOT, "tools", "pc98_hangul_map.json")
LIGHT_HANGUL = os.path.join(ROOT, "build", "light_hangul.json")
HALFWIDTH_MAP = os.path.join(ROOT, "tools", "pc98_halfwidth_map.json")
HALFWIDTH_GLYPHS = os.path.join(ROOT, "tools", "glyphs_halfwidth.json")
OUT = os.path.join(ROOT, "build", "font_light.bmp")


def main():
    im = Image.open(BMP).copy()  # mode '1', 2048x2048, 16px cells

    with open(PC98_MAP, encoding="utf-8") as f:
        hangul_cells = json.load(f)["cells"]
    with open(LIGHT_HANGUL, encoding="utf-8") as f:
        hangul = json.load(f)

    missing = 0
    for ch, rows in hangul.items():
        cell = hangul_cells.get(ch)
        if not cell:
            missing += 1
            continue
        col, row = cell
        x0, y0 = col * 16, row * 16
        for y, line in enumerate(rows):
            for x in range(16):
                c = line[x] if x < len(line) else "."
                im.putpixel((x0 + x, y0 + y), 0 if c == "#" else 255)

    with open(HALFWIDTH_MAP, encoding="utf-8") as f:
        halfwidth_cells = json.load(f)["cells"]
    with open(HALFWIDTH_GLYPHS, encoding="utf-8") as f:
        halfwidth = json.load(f)

    hw_missing = 0
    for slot, rows in halfwidth.items():
        cell = halfwidth_cells.get(slot)
        if not cell:
            hw_missing += 1
            continue
        col, row = cell
        x0, y0 = col * 16, row * 16
        for y, line in enumerate(rows):
            for x in range(16):  # 8px glyph, left-aligned; rest cleared
                c = line[x] if x < len(line) and x < 8 else "."
                im.putpixel((x0 + x, y0 + y), 0 if c == "#" else 255)

    im.save(OUT)
    print(f"wrote {OUT}: {len(hangul) - missing}/{len(hangul)} 완성형 syllables placed"
          + (f", {missing} missing cell mapping" if missing else ""))
    print(f"  + {len(halfwidth) - hw_missing}/{len(halfwidth)} 반각 slots placed"
          + (f", {hw_missing} missing cell mapping" if hw_missing else ""))


if __name__ == "__main__":
    main()
