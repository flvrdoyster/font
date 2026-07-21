"""Build a UFO from HANKBC bitmaps via the pixel->polygon converter.

Usage:
  python scripts/build_ufo.py [--subset "text..."]   # subset for PoC
  python scripts/build_ufo.py --all                  # full 12,354-glyph font

Writes build/HANKBC.ufo. Compile with fontmake separately.
"""
import argparse
import sys
from fontTools.ttLib import TTFont
import ufoLib2
from ufoLib2.objects import Glyph

sys.path.insert(0, "tools")
import pixelfont as pf

UPEM = 1024
ASCENDER = 1024      # cell top; baseline at bottom of the 16px cell
DESCENDER = 0
CAP = 12 * pf.PX     # rough, informational


def build(chars=None, all_glyphs=False):
    font = TTFont("original/HANKBC.ttf")
    strike = pf.read_strike(font)
    cmap = font.getBestCmap()
    rev = {}
    for cp, gname in cmap.items():
        rev.setdefault(gname, cp)

    ufo = ufoLib2.Font()
    info = ufo.info
    info.familyName = "HANKBC Restored"
    info.styleName = "Regular"
    info.unitsPerEm = UPEM
    info.ascender = ASCENDER
    info.descender = DESCENDER
    info.capHeight = CAP
    info.xHeight = 7 * pf.PX
    info.versionMajor = 0
    info.versionMinor = 1

    # decide glyph set
    if all_glyphs:
        wanted = list(strike.keys())
    else:
        wanted = []
        for ch in chars:
            gn = cmap.get(ord(ch))
            if gn and gn not in wanted:
                wanted.append(gn)

    # .notdef and space first
    _add_notdef(ufo)
    if "space" in strike or True:
        _add_space(ufo, cmap)

    added = 0
    for gname in wanted:
        if gname in (".notdef", "space") or gname in ufo:
            continue
        if gname not in strike:
            continue
        width_px, rows = strike[gname]
        advance = width_px * pf.PX if width_px else 8 * pf.PX
        glyph = Glyph(name=gname)
        glyph.width = advance
        cp = rev.get(gname)
        if cp is not None:
            glyph.unicodes = [cp]
        contours = pf.pixels_to_contours(width_px, rows)
        _draw(glyph, contours)
        ufo.addGlyph(glyph)
        added += 1
        if all_glyphs and added % 2000 == 0:
            print(f"  ...{added} glyphs", flush=True)

    return ufo


def _draw(glyph, contours):
    pen = glyph.getPen()
    for contour in contours:
        if not contour:
            continue
        pen.moveTo(contour[0])
        for pt in contour[1:]:
            pen.lineTo(pt)
        pen.closePath()


def _add_notdef(ufo):
    g = Glyph(name=".notdef")
    g.width = 16 * pf.PX
    pen = g.getPen()
    # simple box outline
    for rect, ccw in [((1, 1, 15, 15), True), ((2, 2, 14, 14), False)]:
        x0, y0, x1, y1 = [v * pf.PX for v in rect]
        if ccw:
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        else:
            pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()
    ufo.addGlyph(g)


def _add_space(ufo, cmap):
    g = Glyph(name="space")
    g.width = 8 * pf.PX
    g.unicodes = [0x20]
    ufo.addGlyph(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default="build/HANKBC.ufo")
    args = ap.parse_args()

    if args.all:
        ufo = build(all_glyphs=True)
    else:
        text = args.subset or "안녕하세요세계 다람쥐헌쳇바퀴 Hello, World! 0123456789 @#&"
        ufo = build(chars=set(text))
    ufo.save(args.out, overwrite=True)
    print(f"wrote {args.out} with {len(ufo)} glyphs")


if __name__ == "__main__":
    main()
