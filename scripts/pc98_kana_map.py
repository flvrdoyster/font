"""Match the PC-98 BIOS font (둥근모꼴) hiragana/katakana glyphs to Unicode and
record the result as tools/pc98_kana_map.json, the reference used when drawing
Light-weight kana.

Source bitmap: ../gensei-pc98/docs/bios/font.bmp (2048x2048, 1bpp, 16px grid).
Unlike the Hangul block (a custom 25-column replacement, see
pc98_hangul_map.py), kana sit in the ROM's ORIGINAL JIS X 0208 ku allocation:
each ku gets one dedicated column, and within it row = 32 + ten walks that ku's
94 ten positions -- e.g. あ (ku=4, ten=2) is at column 4, row 34.

  col 4 = ku 4 = hiragana (ten 1-83, standard JIS order, small kana before big)
  col 5 = ku 5 = katakana (ten 1-86, plus ヴヵヶ)
  cell -> pixel origin: x = col*16, y = (32+ten)*16

Verified by rendering both columns as contact sheets and reading them against
the standard ku4/ku5 tables (col 6 = Greek confirms the same ku-per-column
scheme independently). No halfwidth katakana found anywhere in this ROM --
row 0's single-byte ANK table stops short of the 0xA1-0xDF range, and there's
no second block for it; halfwidth kana isn't covered here.

Run from the repo root:  python scripts/pc98_kana_map.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BMP = os.path.join(ROOT, "..", "gensei-pc98", "docs", "bios", "font.bmp")
OUT = os.path.join(ROOT, "tools", "pc98_kana_map.json")

ROW0 = 32  # row = ROW0 + ten

HIRAGANA_COL = 4
HIRAGANA = list("ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞ"
                 "ただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽ"
                 "まみむめもゃやゅゆょよらりるれろゎわゐゑをん")

KATAKANA_COL = 5
KATAKANA = list("ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾ"
                 "タダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポ"
                 "マミムメモャヤュユョヨラリルレロヮワヰヱヲンヴヵヶ")


def main():
    from PIL import Image
    px = Image.open(BMP).convert("L").load()

    mapping = {}
    blank = []
    for col, chars in [(HIRAGANA_COL, HIRAGANA), (KATAKANA_COL, KATAKANA)]:
        for ten, ch in enumerate(chars, start=1):
            row = ROW0 + ten
            mapping[ch] = [col, row]
            x0, y0 = col * 16, row * 16
            ink = sum(1 for y in range(16) for x in range(16) if px[x0 + x, y0 + y] < 128)
            if ink == 0:
                blank.append(ch)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "_source": "../gensei-pc98/docs/bios/font.bmp",
            "_note": "PC-98 BIOS 둥근모꼴; cell [col,row], pixel origin = col*16,row*16, "
                     "16x16 glyph. Standard JIS ku4(hiragana)/ku5(katakana) columns -- "
                     "see scripts/pc98_kana_map.py for how this differs from the Hangul "
                     "block. No halfwidth katakana in this ROM.",
            "cells": mapping,
        }, f, ensure_ascii=False, indent=0)
        f.write("\n")

    print(f"wrote {OUT}: {len(mapping)} kana, {len(blank)} blank in ROM")
    if blank:
        print("blank (undrawn):", "".join(blank))


if __name__ == "__main__":
    main()
