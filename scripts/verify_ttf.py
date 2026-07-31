"""End-to-end verification: render the BUILT TTF at 16px mono and compare
every glyph to what build_ufo.py actually intended to produce, pixel-for-
pixel. Proves the shipped font (after fontmake's RemoveOverlaps +
CubicToQuadratic) is faithful to its own source -- a hand correction in
glyphs_bold.json, or a compose_components result, is the intended output,
not a mismatch, so "intended" is not simply "the original bitmap."

Weight is inferred from the filename ("Regular" = Light/1px, else Bold/2px):
  Bold (2px):    original bitmap, tools/glyphs_bold.json overrides win
  Regular (1px): tools/glyphs_light.json hand-drawn wins, compose_components
                 fills the rest (see docs/ROADMAP.md). Hangul only -- Latin/
                 kana/symbols go through thin_vertical, a separate path this
                 script doesn't reproduce.

Assumes --proportional (both README build commands use it): tools/spacing.py
shifts each glyph's ink left/right within its advance, so the rendered
position won't match the plain source grid unless that same shift is applied
here first -- pass --no-proportional if BUILT was built without the flag."""
import argparse
import os
import sys
import freetype
from fontTools.ttLib import TTFont

sys.path.insert(0, "tools")
import pixelfont as pf
import customglyphs as cg
import compose_components as cc
import compose_light as cl
import spacing as sp
import build_ufo as bu   # sibling script; scripts/ is sys.path[0] when run directly

ap = argparse.ArgumentParser()
ap.add_argument("built", nargs="?", default="build/DokkaebiDNRGothic-Bold.ttf")
ap.add_argument("--no-proportional", dest="proportional", action="store_false")
ARGS = ap.parse_args()
BUILT = ARGS.built
IS_LIGHT = "Regular" in os.path.basename(BUILT)


def render_mono(face, cp, width):
    """Return list of 16 row bitmasks for codepoint cp rendered at 16px mono,
    placed into a width x 16 cell with top at cell top (bearingY = 16)."""
    face.load_char(chr(cp), freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO
                   | freetype.FT_LOAD_NO_HINTING)
    g = face.glyph
    bmp = g.bitmap
    rows = [0] * pf.CELL
    # top of the 16px cell is at y = ascender = 16px above baseline.
    # freetype bitmap_top = pixels from baseline up to bitmap's top row.
    for by in range(bmp.rows):
        cell_row = (pf.CELL - g.bitmap_top) + by   # row 0 = cell top
        if not (0 <= cell_row < pf.CELL):
            continue
        for bx in range(bmp.width):
            byte = bmp.buffer[by * bmp.pitch + (bx >> 3)]
            if (byte >> (7 - (bx & 7))) & 1:
                col = g.bitmap_left + bx
                if 0 <= col < width:
                    rows[cell_row] |= (1 << (width - 1 - col))
    return rows


def expected_bold():
    """cp -> (width, rows): original bitmap, with glyphs_bold.json hand
    corrections winning, skipping what build_ufo.py's build() itself skips
    (control chars, soft hyphen, legitimately-blank-only-if-whitespace) --
    otherwise a codepoint the font never ships shows up as a fake mismatch."""
    orig = TTFont("original/HANKBC.ttf")
    strike = pf.read_strike(orig)
    cmap = orig.getBestCmap()
    out = {}
    for cp, gname in cmap.items():
        if gname not in strike:
            continue
        width, rows = strike[gname]
        if cp in cg.GLYPHS:
            width, rows = cg.GLYPHS[cp]
        elif bu._excluded_codepoint(cp):
            continue
        elif not any(rows) and not bu._expected_blank(cp):
            continue
        if width == 0:
            continue
        out[cp] = (width, rows)
    return out


def expected_light():
    """cp -> (width, rows), Hangul only: glyphs_light.json hand-drawn wins,
    compose_components fills the rest -- mirrors build_ufo.py's
    build_light() Hangul loop exactly."""
    pc98 = cl.load_pc98()
    corpus = cc.load_corpus()
    lib = cc.build_library(corpus, pc98, cc.build_zone_indices(corpus, pc98))
    out = {}
    for ch in cc.FULL:
        grid = corpus.get(ch) or cc.compose(ch, lib)
        if grid is not None:
            out[ord(ch)] = cg._to_rows(grid)
    return out


def _shift_cols(width, row, dx):
    """Move a row bitmask dx columns right (negative = left), dropping
    anything that falls outside [0, width) -- matches what pf.pixels_to_
    contours + the dx offset in build_ufo.py actually draw."""
    val = 0
    for x in range(width):
        if row & (1 << (width - 1 - x)):
            nx = x + dx
            if 0 <= nx < width:
                val |= (1 << (width - 1 - nx))
    return val


def main():
    expected = expected_light() if IS_LIGHT else expected_bold()

    if ARGS.proportional:
        shifted = {}
        for cp, (width, rows) in expected.items():
            _, dx = sp.proportional(width, rows, cp)
            shifted[cp] = (width, [_shift_cols(width, r, dx) for r in rows]) if dx else (width, rows)
        expected = shifted

    face = freetype.Face(BUILT)
    face.set_pixel_sizes(0, 16)

    total = mism = 0
    examples = []
    for cp, (width, rows) in expected.items():
        total += 1
        got = render_mono(face, cp, width)
        if got != rows:
            mism += 1
            if len(examples) < 8:
                examples.append(cp)

    print(f"built font: {BUILT}  ({'Regular/Light, Hangul only' if IS_LIGHT else 'Bold'})")
    print(f"glyphs compared: {total}")
    print(f"pixel-exact mismatches vs intended source: {mism}")
    if examples:
        print("examples:", ", ".join(f"U+{cp:04X}" for cp in examples))


if __name__ == "__main__":
    main()
