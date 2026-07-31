"""Locate the PC-98 BIOS font's 반각(halfwidth) Hangul syllable table and
record it as tools/pc98_halfwidth_map.json, the reference used by
tools/halfwidth_editor.html.

Source bitmap: original/pc98_font.bmp (2048x2048, 1bpp, 16px grid) -- a
read-only copy of gensei-pc98's font.bmp as it stood before any of our own
Hangul was ever delivered into it (see docs/ROADMAP.md).
Columns 10-11 (starting 6 columns left of the 완성형 Hangul block's col 16 =
'가') hold a 2x94-slot table of pre-composed halfwidth Hangul syllables (plus
a few punctuation marks in col 11's tail) -- NOT the standard KS X 1001 order,
and not the Unicode Halfwidth Hangul Jamo block (which only covers individual
jamo, not syllables). This looks like a fixed, ROM-specific set: col 9 is
ordinary fullwidth ASCII and col 12 is box-drawing, so 10-11 are a Korean-
specific insertion sandwiched between two otherwise-JIS columns.

  cell -> pixel origin: x = col*16, y = (32+ten)*16, ten = 1..94

Since these don't correspond to any standard Unicode identity, slots are keyed
by "{col}-{ten}" (e.g. "10-1") rather than by character.

Run from the repo root:  python scripts/pc98_halfwidth_map.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BMP = os.path.join(ROOT, "original", "pc98_font.bmp")
OUT = os.path.join(ROOT, "tools", "pc98_halfwidth_map.json")

COLS = [10, 11]
ROW0 = 32  # row = ROW0 + ten


def main():
    from PIL import Image
    px = Image.open(BMP).convert("L").load()

    cells = {}
    blank = []
    for col in COLS:
        for ten in range(1, 95):
            row = ROW0 + ten
            key = f"{col}-{ten}"
            cells[key] = [col, row]
            x0, y0 = col * 16, row * 16
            ink = sum(1 for y in range(16) for x in range(16) if px[x0 + x, y0 + y] < 128)
            if ink == 0:
                blank.append(key)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "_source": "../gensei-pc98/docs/bios/font.bmp",
            "_note": "PC-98 BIOS 반각 한글 후보 테이블(94칸 x 2열, col=10,11); cell "
                     "[col,row], pixel origin = col*16,row*16, 16x16 glyph. Standard "
                     "완성형/조합형 순서가 아니고 유니코드 반각 한글 자모 블록과도 무관한 "
                     "ROM 고유 표 -- 슬롯은 문자 대신 \"{col}-{ten}\"으로 식별한다. "
                     "scripts/pc98_halfwidth_map.py 참고.",
            "cols": COLS,
            "cells": cells,
        }, f, ensure_ascii=False, indent=0)
        f.write("\n")

    print(f"wrote {OUT}: {len(cells)} slots, {len(blank)} blank in ROM")
    print("blank slots:", blank)


if __name__ == "__main__":
    main()
