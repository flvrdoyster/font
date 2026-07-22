"""Build the 도깨비DNR 고딕 UFO from HANKBC bitmaps + custom glyph overrides.

Usage:
  python scripts/build_ufo.py [--subset "text..."]        # subset for quick checks
  python scripts/build_ufo.py --all --proportional        # full Regular font
  python scripts/build_ufo.py --weight light --proportional  # Light font

Writes build/DokkaebiDNRGothic(Light).ufo. Compile with fontmake separately.
"""
import argparse
import json
import sys
from fontTools.ttLib import TTFont
import ufoLib2
from ufoLib2.objects import Glyph

sys.path.insert(0, "tools")
import pixelfont as pf
import spacing as sp
import metadata as md
import customglyphs as cg
import thin_vertical as tv
import compose_light as cl   # sibling script; scripts/ is sys.path[0] when run directly

UPEM = 1024
ASCENDER = 1024      # cell top; baseline at bottom of the 16px cell
DESCENDER = 0
CAP = 12 * pf.PX     # rough, informational


def build(chars=None, all_glyphs=False, proportional=False):
    font = TTFont("original/HANKBC.ttf")
    strike = pf.read_strike(font)
    cmap = font.getBestCmap()
    rev = {}
    for cp, gname in cmap.items():
        rev.setdefault(gname, cp)

    ufo = ufoLib2.Font()
    ufo.info.unitsPerEm = UPEM
    md.apply(ufo, ascender=ASCENDER, descender=DESCENDER,
             cap_height=11 * pf.PX, x_height=7 * pf.PX)

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
        cp = rev.get(gname)
        if cp in cg.GLYPHS:                    # hand-drawn override
            width_px, rows = cg.GLYPHS[cp]
        if proportional:
            adv_px, shift_px = sp.proportional(width_px, rows, cp)
        else:
            adv_px, shift_px = (width_px if width_px else 8), 0
        glyph = Glyph(name=gname)
        glyph.width = adv_px * pf.PX
        if cp is not None:
            glyph.unicodes = [cp]
        contours = pf.pixels_to_contours(width_px, rows)
        if shift_px:
            dx = shift_px * pf.PX
            contours = [[(x + dx, y) for x, y in c] for c in contours]
        _draw(glyph, contours)
        ufo.addGlyph(glyph)
        added += 1
        if all_glyphs and added % 2000 == 0:
            print(f"  ...{added} glyphs", flush=True)

    return ufo


def build_light(proportional=False):
    """Light weight: Latin/numbers and Hangul both follow the same
    confirmed-first rule -- a glyph hand-drawn and saved in
    tools/glyphs_light.json is used verbatim; anything unsaved is filled
    mechanically (Latin/numbers: Regular thinned to 1px; Hangul: the composed
    PC-98-base + our-consonants result for the 2,350 KS X 1001 syllables
    gensei-pc98 needs -- see docs/ROADMAP.md Phase 2, not all 11,172 Hangul)."""
    ufo = ufoLib2.Font()
    ufo.info.unitsPerEm = UPEM
    md.apply(ufo, ascender=ASCENDER, descender=DESCENDER,
             cap_height=11 * pf.PX, x_height=7 * pf.PX, style="Light")
    _add_notdef(ufo)
    _add_space(ufo, {})

    with open(cl.REFS, encoding="utf-8") as f:
        refs = json.load(f)

    latin_src = cg.load_src()
    light_latin_src, latin_hand, latin_thinned = {}, 0, 0
    for ch, grid in latin_src.items():
        if ch in refs:
            light_latin_src[ch] = refs[ch]
            latin_hand += 1
        else:
            light_latin_src[ch] = tv.thin_vertical(grid)
            latin_thinned += 1
    light_latin = cg.build(light_latin_src)

    pc98 = cl.load_pc98()
    cho_ref, jong_ref = cl.build_indices(refs)
    ks = cl.ks_x1001_order()
    # hand-drawn glyphs are authoritative; compose only fills the unsaved gaps
    light_hangul_src, hand, gaps = {}, 0, 0
    for ch in ks:
        if ch in refs:
            light_hangul_src[ch] = refs[ch]
            hand += 1
        elif cl.can_compose(ch, cho_ref, jong_ref):
            light_hangul_src[ch] = cl.compose(ch, pc98, refs, cho_ref, jong_ref)
            gaps += 1
    light_hangul = cg.build(light_hangul_src)

    missing = len(ks) - len(light_hangul_src)
    if missing:
        skipped = "".join(ch for ch in ks if ch not in light_hangul_src)[:30]
        print(f"  light: {missing}/{len(ks)} KS X 1001 Hangul skipped "
              f"(missing 초성/종성 refs): {skipped}...")

    added = 0
    for cp, (width_px, rows) in {**light_latin, **light_hangul}.items():
        adv_px, shift_px = (sp.proportional(width_px, rows, cp) if proportional
                            else ((width_px if width_px else 8), 0))
        glyph = Glyph(name=f"uni{cp:04X}")
        glyph.width = adv_px * pf.PX
        glyph.unicodes = [cp]
        contours = pf.pixels_to_contours(width_px, rows)
        if shift_px:
            dx = shift_px * pf.PX
            contours = [[(x + dx, y) for x, y in c] for c in contours]
        _draw(glyph, contours)
        ufo.addGlyph(glyph)
        added += 1

    print(f"  light: {added} glyphs added "
          f"({latin_hand} Latin/numbers hand-drawn + {latin_thinned} thinned, "
          f"{hand} Hangul hand-drawn + {gaps} composed)")
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
    ap.add_argument("--proportional", action="store_true",
                    help="derive proportional advances from pixel ink bounds")
    ap.add_argument("--weight", choices=["regular", "light"], default="regular")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.weight == "light":
        ufo = build_light(proportional=args.proportional)
        out = args.out or "build/DokkaebiDNRGothicLight.ufo"
    elif args.all:
        ufo = build(all_glyphs=True, proportional=args.proportional)
        out = args.out or "build/DokkaebiDNRGothic.ufo"
    else:
        text = args.subset or "안녕하세요세계 다람쥐헌쳇바퀴 Hello, World! 0123456789 @#&"
        ufo = build(chars=set(text), proportional=args.proportional)
        out = args.out or "build/DokkaebiDNRGothic.ufo"
    ufo.save(out, overwrite=True)
    print(f"wrote {out} with {len(ufo)} glyphs")


if __name__ == "__main__":
    main()
