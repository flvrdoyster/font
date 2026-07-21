"""Post-compile finalize: add Korean localized name records.

fontmake bakes the Latin name/OS2/gasp tables from the UFO. This adds the
Korean (ko-KR) localized family/subfamily names so the font shows as
'도깨비DNR 고딕' in Korean environments.

Usage: python scripts/finalize.py build/DokkaebiDNRGothic-Regular.ttf ...
"""
import sys
from fontTools.ttLib import TTFont

sys.path.insert(0, "tools")
import metadata as md

WIN, KO = 3, 0x0412   # Windows platform, Korean (Korea) language


def finalize(path):
    font = TTFont(path)
    name = font["name"]
    # nameID -> Korean string
    ko = {
        1: md.FAMILY_KO,
        2: md.STYLE,
        16: md.FAMILY_KO,
        17: md.STYLE,
    }
    for nid, val in ko.items():
        name.setName(val, nid, WIN, 1, KO)   # platEncID 1 (Unicode BMP)
    font.save(path)
    print(f"finalized {path}: +Korean names ({md.FAMILY_KO})")


def main():
    if len(sys.argv) < 2:
        print("usage: finalize.py <font.ttf> [<font.otf> ...]")
        sys.exit(1)
    for p in sys.argv[1:]:
        finalize(p)


if __name__ == "__main__":
    main()
