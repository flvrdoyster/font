"""Match the PC-98 BIOS font (둥근모꼴) Hangul glyphs to Unicode and record the
result as tools/pc98_hangul_map.json, the authoritative reference used when
drawing the Light-weight Hangul.

Source bitmap: ../gensei-pc98/docs/bios/font.bmp (2048x2048, 1bpp, 16px grid).
It carries the 2,350 KS X 1001 완성형 Hangul in a 25-col x 94-row block, packed
COLUMN-MAJOR in EUC-KR order:

    가 at cell (col 16, row 33);  index = (col-16)*94 + (row-33)
    cell -> pixel origin: x = col*16, y = row*16

(This is the actual glyph layout in the ROM dump. It is unrelated to
gensei-pc98's tools/charmap.json, which is a game-text SJIS map pointing at the
kanji region -- do not use that for glyph lookup.)

Run from the repo root:  python scripts/pc98_hangul_map.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BMP = os.path.join(ROOT, "..", "gensei-pc98", "docs", "bios", "font.bmp")
OUT = os.path.join(ROOT, "tools", "pc98_hangul_map.json")

COL0, ROW0, ROWS = 16, 33, 94  # block origin (cell coords) and column height


def ksx1001_order():
    """The 2,350 완성형 syllables in EUC-KR (KS X 1001) code order."""
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            try:
                ch = bytes([hi, lo]).decode("euc-kr")
            except UnicodeDecodeError:
                continue
            if 0xAC00 <= ord(ch) <= 0xD7A3:
                out.append(ch)
    return out


def cell_for_index(i):
    return COL0 + i // ROWS, ROW0 + i % ROWS  # col, row


def main():
    from PIL import Image
    px = Image.open(BMP).convert("L").load()

    order = ksx1001_order()
    mapping = {}
    blank = []
    for i, ch in enumerate(order):
        col, row = cell_for_index(i)
        mapping[ch] = [col, row]
        x0, y0 = col * 16, row * 16
        ink = sum(1 for y in range(16) for x in range(16) if px[x0 + x, y0 + y] < 128)
        if ink == 0:
            blank.append(ch)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "_source": "../gensei-pc98/docs/bios/font.bmp",
            "_note": "PC-98 BIOS 둥근모꼴; cell [col,row], pixel origin = col*16,row*16, 16x16 glyph",
            "_layout": {"col0": COL0, "row0": ROW0, "rows_per_col": ROWS,
                        "order": "KS X 1001 (EUC-KR), column-major"},
            "cells": mapping,
        }, f, ensure_ascii=False, indent=0)
        f.write("\n")

    print(f"wrote {OUT}: {len(mapping)} syllables, {len(blank)} blank in ROM")
    if blank:
        print("blank (undrawn) samples:", "".join(blank[:40]))


if __name__ == "__main__":
    main()
