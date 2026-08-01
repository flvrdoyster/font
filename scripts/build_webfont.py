"""Compress a built OTF/TTF into WOFF2 for web use.

OTF (CFF outlines) is the preferred web source over TTF -- both weights
compress smaller from it (this is a pixel font: very few points per glyph,
so there's nothing subsetting would meaningfully save; the full 11,172-Hangul
+ Latin + symbol repertoire already lands under 150KB per weight).

Usage: python scripts/build_webfont.py build/DokkaebiDNRGothic-Regular.otf ...
Writes alongside the input: build/DokkaebiDNRGothic-Regular.woff2
"""
import os
import sys
from fontTools.ttLib import TTFont


def build_webfont(path):
    font = TTFont(path)
    font.flavor = "woff2"
    out = os.path.splitext(path)[0] + ".woff2"
    font.save(out)
    print(f"{out}  {os.path.getsize(out) / 1024:.1f} KB "
          f"(source {os.path.getsize(path) / 1024:.1f} KB)")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        build_webfont(p)
