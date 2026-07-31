"""Build the 도깨비DNR 고딕 UFO from HANKBC bitmaps + custom glyph overrides.

The two stroke weights compile into one RIBBI family: 1px stems -> the
Regular member (--weight light), 2px stems -> the Bold member (--all). The
internal "light"/"regular" weight keys still describe stroke width; only the
compiled OpenType style names are Regular/Bold.

Usage:
  python scripts/build_ufo.py [--subset "text..."]           # subset for quick checks
  python scripts/build_ufo.py --all --proportional           # 2px stems -> Bold member
  python scripts/build_ufo.py --weight light --proportional  # 1px stems -> Regular member

Writes build/DokkaebiDNRGothic-{Regular,Bold}.ufo. Compile with fontmake separately.
"""
import argparse
import os
import json
import sys
import unicodedata
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
import compose_components as cc

UPEM = 1024
ASCENDER = 1024      # cell top; baseline at bottom of the 16px cell
DESCENDER = 0
CAP = 12 * pf.PX     # rough, informational

# The original bitmap's cmap carries a few codepoints that shouldn't ship:
# C0/C1 control characters with leftover ink from the legacy code page (a
# rendering bug -- fontbakery whitespace_ink/control_chars), and soft hyphen
# (many apps mishandle it; fontbakery soft_hyphen flags its mere presence).
_CONTROL_RANGES = [(0x00, 0x1F), (0x7F, 0x9F)]
_EXPLICIT_EXCLUDE = {
    0xAD,     # soft hyphen
    0x111,    # dcroat (đ) -- no Đ counterpart in the original bitmap to pair it with
    0x212B,   # ANGSTROM SIGN -- case-equivalent to Å/å, neither of which exists either
}


def _excluded_codepoint(cp):
    if cp is None:
        return False
    if cp in _EXPLICIT_EXCLUDE:
        return True
    return any(lo <= cp <= hi for lo, hi in _CONTROL_RANGES)


def _expected_blank(cp):
    """Whitespace/format characters are legitimately blank. Anything else
    (symbols, letters, punctuation) that's blank in the original bitmap was
    just never drawn -- claiming cmap support for an invisible glyph is worse
    than not listing it (fontbakery contour_count)."""
    if cp is None:
        return False
    return unicodedata.category(chr(cp)) in ("Zs", "Zl", "Zp", "Cf")


def build(chars=None, all_glyphs=False, proportional=False):
    font = TTFont("original/HANKBC.ttf")
    strike = pf.read_strike(font)
    cmap = font.getBestCmap()
    rev = {}
    for cp, gname in cmap.items():
        rev.setdefault(gname, cp)

    ufo = ufoLib2.Font()
    ufo.info.unitsPerEm = UPEM
    # 2px stems compile as the family's Bold member (1px = Regular, see
    # build_light); one RIBBI family so Cmd+B toggles between them.
    md.apply(ufo, ascender=ASCENDER, descender=DESCENDER,
             cap_height=11 * pf.PX, x_height=7 * pf.PX, style="Bold")

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
    skipped_control = skipped_blank = 0
    seen_cps = set()
    for gname in wanted:
        if gname in (".notdef", "space") or gname in ufo:
            continue
        if gname not in strike:
            continue
        width_px, rows = strike[gname]
        cp = rev.get(gname)
        if cp in cg.GLYPHS:                    # hand-drawn override
            width_px, rows = cg.GLYPHS[cp]
        else:
            if _excluded_codepoint(cp):
                skipped_control += 1
                continue
            if not any(rows) and not _expected_blank(cp):
                skipped_blank += 1
                continue
        if proportional:
            adv_px, shift_px = sp.proportional(width_px, rows, cp)
        else:
            adv_px, shift_px = (width_px if width_px else 8), 0
        glyph = Glyph(name=gname)
        glyph.width = adv_px * pf.PX
        if cp is not None:
            glyph.unicodes = [cp]
            seen_cps.add(cp)
        contours = pf.pixels_to_contours(width_px, rows)
        if shift_px:
            dx = shift_px * pf.PX
            contours = [[(x + dx, y) for x, y in c] for c in contours]
        _draw(glyph, contours)
        ufo.addGlyph(glyph)
        added += 1
        if all_glyphs and added % 2000 == 0:
            print(f"  ...{added} glyphs", flush=True)

    # cg.GLYPHS (glyphs_bold.json) can hold codepoints with no counterpart in
    # the original HANKBC strike at all -- e.g. most of the kana palette
    # beyond the 169 characters that bitmap happens to include. The loop
    # above only visits strike-derived glyph names, so those would otherwise
    # be silently dropped even though they're hand-drawn and ready. Add them
    # directly, scoped to the same requested character set as the main pass.
    wanted_cps = None if all_glyphs else {ord(ch) for ch in (chars or ())}
    extra = 0
    for cp, (width_px, rows) in cg.GLYPHS.items():
        if cp in seen_cps:
            continue
        if wanted_cps is not None and cp not in wanted_cps:
            continue
        if proportional:
            adv_px, shift_px = sp.proportional(width_px, rows, cp)
        else:
            adv_px, shift_px = (width_px if width_px else 8), 0
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
        extra += 1

    if skipped_control or skipped_blank:
        print(f"  skipped {skipped_control} control-char/soft-hyphen codepoints, "
              f"{skipped_blank} blank-in-original codepoints (e.g. registered, Euro)")
    if extra:
        print(f"  +{extra} hand-drawn glyphs with no original-strike counterpart "
              f"(e.g. kana beyond the original 169)")
    return ufo


def build_light(proportional=False):
    """Light weight: Latin/numbers and Hangul both follow the same
    confirmed-first rule -- a glyph hand-drawn and saved in
    tools/glyphs_light.json is used verbatim; anything unsaved is filled
    mechanically (Latin/numbers: Regular thinned to 1px; Hangul: the
    jamo-component union over all 11,172 syllables -- see
    scripts/compose_components.py / docs/ROADMAP.md)."""
    ufo = ufoLib2.Font()
    ufo.info.unitsPerEm = UPEM
    # 1px stems compile as the family's default Regular member (2px = Bold,
    # see build() above). The internal "light" weight key / glyphs_light.json
    # still means "1px stems" -- only the compiled style name is "Regular".
    md.apply(ufo, ascender=ASCENDER, descender=DESCENDER,
             cap_height=11 * pf.PX, x_height=7 * pf.PX, style="Regular")
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
    corpus = cc.load_corpus()
    lib = cc.build_library(corpus, pc98, cc.build_zone_indices(corpus, pc98))
    # hand-drawn glyphs are authoritative; compose only fills the unsaved gaps
    light_hangul_src, hand, gaps = {}, 0, 0
    for ch in cc.FULL:
        if ch in refs:
            light_hangul_src[ch] = refs[ch]
            hand += 1
        else:
            out = cc.compose(ch, lib)
            if out is not None:
                light_hangul_src[ch] = out
                gaps += 1
    light_hangul = cg.build(light_hangul_src)

    missing = len(cc.FULL) - len(light_hangul_src)
    if missing:
        skipped = "".join(ch for ch in cc.FULL if ch not in light_hangul_src)[:30]
        print(f"  light: {missing}/{len(cc.FULL)} Hangul skipped "
              f"(missing component cells): {skipped}...")

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
    g.unicodes = [0x20, 0xA0]   # regular + non-breaking space, same glyph
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
        out = args.out or "build/DokkaebiDNRGothic-Regular.ufo"
    elif args.all:
        ufo = build(all_glyphs=True, proportional=args.proportional)
        out = args.out or "build/DokkaebiDNRGothic-Bold.ufo"
    else:
        text = args.subset or "안녕하세요세계 다람쥐헌쳇바퀴 Hello, World! 0123456789 @#&"
        ufo = build(chars=set(text), proportional=args.proportional)
        out = args.out or "build/DokkaebiDNRGothic-Bold.ufo"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    ufo.save(out, overwrite=True)
    print(f"wrote {out} with {len(ufo)} glyphs")


if __name__ == "__main__":
    main()
