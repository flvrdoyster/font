"""Match the genuine Japanese PC-98 BIOS font's kanji to Unicode and record
the result as tools/pc98_kanji_map.json.

Source bitmap: original/pc98_jp.bmp -- a DIFFERENT ROM dump than
pc98_font.bmp (the Korean-localized one everything else here reads); see
docs/ROADMAP.md. This one is unlocalized, so its JIS X 0208 allocation is
intact end to end.

Same col=ku, row=32+ten scheme as the kana block (scripts/pc98_kana_map.py),
confirmed directly: ku16-ten1 (col 16, row 33) renders 亜, matching what
EUC-JP decodes ku16-ten1 to. Kanji sit in ku 16-84 (levels 1+2); this script
just decodes every (ku, ten) via EUC-JP and keeps whatever lands in the CJK
Unified Ideographs block (0x4E00-0x9FFF) -- 6,356 cells, matching the
standard JIS X 0208 kanji count exactly, so no need to hardcode the ku
range. Kana/symbols/Greek/Cyrillic that also decode from other ku are
already handled by their own dedicated maps -- skipped here on purpose.

Run from the repo root:  python scripts/pc98_kanji_map.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BMP = os.path.join(ROOT, "original", "pc98_jp.bmp")
OUT = os.path.join(ROOT, "tools", "pc98_kanji_map.json")

ROW0 = 32  # row = ROW0 + ten, same as kana


def main():
    from PIL import Image
    px = Image.open(BMP).convert("L").load()

    mapping = {}
    blank = 0
    for ku in range(1, 95):
        for ten in range(1, 95):
            try:
                ch = bytes([0xA0 + ku, 0xA0 + ten]).decode("euc-jp")
            except UnicodeDecodeError:
                continue
            if not (0x4E00 <= ord(ch) <= 0x9FFF):
                continue
            row = ROW0 + ten
            mapping[ch] = [ku, row]
            x0, y0 = ku * 16, row * 16
            if not any(px[x0 + x, y0 + y] < 128 for x in range(16) for y in range(16)):
                blank += 1

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({
            "_source": "original/pc98_jp.bmp",
            "_note": "Genuine (unlocalized) Japanese PC-98 BIOS font, kanji only "
                     "(CJK Unified Ideographs, JIS X 0208 levels 1+2). cell [col,row] "
                     "= [ku, 32+ten], pixel origin = col*16,row*16, 16x16 glyph. See "
                     "scripts/pc98_kanji_map.py.",
            "cells": mapping,
        }, f, ensure_ascii=False, indent=0)
        f.write("\n")

    print(f"wrote {OUT}: {len(mapping)} kanji, {blank} blank in ROM")


if __name__ == "__main__":
    main()
