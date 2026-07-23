"""Local server for the pixel editor.

    python scripts/editor_server.py [--port 8000] [--no-open]

Serves tools/pixel_editor.html at http://localhost:PORT/ and exposes a small
API so the editor can load and SAVE glyphs, per weight (Regular / Light):

  GET  /api/glyphs?weight=regular|light
                          -> current glyphs_<weight>.json { "A": [rows], ... }
  POST /api/glyphs?weight=regular|light
                          -> merge { "A": [rows], ... } into that file
  GET  /api/text?weight=..&s=...
                          -> per-char grids, custom (that weight) overrides
                             original (preview). For weight=light Hangul with
                             no custom entry, falls back to the composed
                             PC-98-base + our-consonants default (see
                             scripts/compose_light.py) instead of the raw
                             original, before finally falling back to that.
  GET  /api/original?s=.. -> per-char grids from the ORIGINAL bitmap only,
                             ignoring custom overrides (weight-independent --
                             it's always the 2px Dokkaebi Dinaru source used as
                             a reference for both weights)
  GET  /api/pc98?s=..     -> per-char grids from the PC-98 BIOS font
                             (../gensei-pc98/docs/bios/font.bmp, 둥근모꼴), for
                             the 2,350 KS X 1001 Hangul it carries, via the
                             recorded tools/pc98_hangul_map.json. Weight-
                             independent; a second skeleton-reference overlay.
  GET  /api/ks2350        -> the 2,350 KS X 1001 완성형 syllables (char list),
                             for the editor's full-coverage Light palette.
  GET  /api/kana          -> hiragana + katakana + halfwidth katakana (char
                             list), for the editor's kana palette (Phase 3).
  GET  /api/kanaref?s=..  -> per-char grids rasterized from the kana skeleton
                             reference font (refs/, gitignored). Kana only,
                             reference-only overlay -- never embedded in
                             built output.
  POST /api/build?weight=regular|light
                          -> rebuild that weight's TTF (build_ufo -> fontmake
                             -> finalize). regular = full original-bitmap
                             font; light = thinned Latin/numbers + composed
                             KS X 1001 Hangul (scripts/compose_light.py).
  POST /api/build_bmp     -> regenerate build/font_light.bmp (compose_light.py
                             -> build_pc98_bmp.py) from current saved state --
                             completed-form Light Hangul + glyphs_halfwidth.json.
                             Unrelated to the TTF build above.

Also serves tools/halfwidth_editor.html at /halfwidth -- a separate tool for
hand-drawing 반각(halfwidth) Hangul, unrelated to the font build pipeline
(nothing here feeds build_ufo.py):

  GET  /api/halfwidth_ref  -> reference grids for all 188 slots (2 cols x 94)
                              of the PC-98 BIOS's 반각 한글 table (font.bmp
                              cols 10-11, see scripts/pc98_halfwidth_map.py)
                              -- 122 have ink, 66 are blank in the ROM. Slots
                              are keyed "{col}-{ten}" (e.g. "10-5"), not
                              character: this table isn't in KS X 1001 or
                              Unicode order.
  GET  /api/halfwidth_glyphs
                          -> tools/glyphs_halfwidth.json, the user's own
                             hand-drawn slots { "10-5": [rows], ... }
  POST /api/halfwidth_glyphs
                          -> merge { "10-5": [rows], ... } into that file
  GET  /api/halfwidth_charmap
                          -> tools/halfwidth_char_map.json, the user's own
                             slot->character notes { "10-5": "가", ... } (typed
                             in by hand -- this table has no recorded Unicode
                             identity otherwise, see pc98_halfwidth_map.py)
  POST /api/halfwidth_charmap
                          -> merge { "10-5": "가", ... } into that file; a
                             blank value clears the slot's assignment
  GET  /api/halfwidth_light_ref?s=..
                          -> per-char grids: that character's Light 완성형
                             glyph (build/light_hangul.json) squeezed
                             left-right by half (OR-fold column pairs,
                             16px->8px) -- a rough shape guide, second overlay
                             (red) for whichever character the editor's
                             halfwidth_char_map.json says the current slot is

Stdlib only. Run from the repo root.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITOR = os.path.join(ROOT, "tools", "pixel_editor.html")
HALFWIDTH_EDITOR = os.path.join(ROOT, "tools", "halfwidth_editor.html")
GLYPHS_FILES = {
    "regular": os.path.join(ROOT, "tools", "glyphs_regular.json"),
    "light": os.path.join(ROOT, "tools", "glyphs_light.json"),
}

PAGE_HEAD = (
    "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>도깨비DNR 픽셀 에디터</title></head><body>"
)
PAGE_TAIL = "</body></html>"

HALFWIDTH_PAGE_HEAD = (
    "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>반각 한글 에디터</title></head><body>"
)


def _weight_file(weight):
    path = GLYPHS_FILES.get(weight)
    if not path:
        raise ValueError(f"unknown weight: {weight!r}")
    return path


def read_glyphs(weight):
    with open(_weight_file(weight), encoding="utf-8") as f:
        return json.load(f)


def write_glyphs(weight, data):
    # keep sorted + stable formatting so git diffs stay clean
    ordered = {k: data[k] for k in sorted(data)}
    with open(_weight_file(weight), "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)
        f.write("\n")


_ORIG = None  # lazy (strike, cmap) from the original bitmap font


def _orig():
    global _ORIG
    if _ORIG is None:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import pixelfont as pf
        from fontTools.ttLib import TTFont
        font = TTFont(os.path.join(ROOT, "original", "HANKBC.ttf"))
        _ORIG = (pf.read_strike(font), font.getBestCmap())
    return _ORIG


def _original_grid(ch, strike, cmap):
    gname = cmap.get(ord(ch))
    if gname and gname in strike:
        w, rows = strike[gname]
        if w:
            return ["".join("#" if r & (1 << (w - 1 - x)) else "."
                            for x in range(w)) for r in rows]
    return None


_COMPOSER = False  # False = not yet loaded; None = load failed; else the module


def _composer():
    """scripts/compose_light.py, importable from here for the Light Hangul
    default preview (see text_grids). None if it can't be loaded (e.g. PIL or
    the PC-98 bitmap missing) -- callers fall back to the plain original."""
    global _COMPOSER
    if _COMPOSER is False:
        try:
            sys.path.insert(0, os.path.join(ROOT, "scripts"))
            import compose_light
            _COMPOSER = compose_light
        except Exception:
            _COMPOSER = None
    return _COMPOSER


_THINNER = False  # False = not yet loaded; None = load failed; else the module


def _thinner():
    """tools/thin_vertical.py, for the Light Latin/digit preview fallback
    (thin the Regular custom glyph) -- see text_grids."""
    global _THINNER
    if _THINNER is False:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import thin_vertical
            _THINNER = thin_vertical
        except Exception:
            _THINNER = None
    return _THINNER


def text_grids(weight, s):
    """Per-char pixel grids for preview: custom glyphs (for this weight)
    override the original. With no custom entry yet, Light falls back to a
    weight-appropriate default instead of the raw 2px original:
      - Hangul: the composed PC-98-base + our-consonants default (see
        scripts/compose_light.py)
      - Latin/digits: the Regular custom glyph thinned to 1px (see
        tools/thin_vertical.py) -- this is what build_light actually uses,
        so the editor should preview the same thing."""
    custom = read_glyphs(weight)
    try:
        strike, cmap = _orig()
    except Exception:
        strike, cmap = {}, {}
    cl = None
    cho_ref = jong_ref = None
    regular = tv = None
    if weight == "light":
        cl = _composer()
        if cl is not None:
            cho_ref, jong_ref = cl.build_indices(custom)
        tv = _thinner()
        if tv is not None:
            regular = read_glyphs("regular")
    out = []
    for ch in s:
        grid = custom.get(ch)
        if grid is None and weight == "light" and 0xAC00 <= ord(ch) <= 0xD7A3:
            if cl is not None:
                try:
                    if cl.can_compose(ch, cho_ref, jong_ref):
                        grid = cl.compose(ch, _pc98_grid, custom, cho_ref, jong_ref)
                except Exception:
                    grid = None
        elif grid is None and tv is not None and regular is not None and ch in regular:
            try:
                grid = tv.thin_vertical(regular[ch])
            except Exception:
                grid = None
        if grid is None and _is_kana(ch):
            # PC-98's 둥근모꼴 replaces the original bitmap's kana entirely
            # (both weights) -- font.bmp's kana was never touched by the
            # Korean localization, unlike its Hangul/kanji regions.
            grid = _pc98_kana_grid(ch)
        if grid is None:
            grid = _original_grid(ch, strike, cmap)
        out.append({"ch": ch, "rows": grid})
    return out


def original_grids(s):
    """Per-char pixel grids from the ORIGINAL bitmap only, ignoring any
    custom override -- used for the editor's reference-overlay ghost.
    Weight-independent: always the 2px source both weights derive from."""
    try:
        strike, cmap = _orig()
    except Exception:
        strike, cmap = {}, {}
    return [{"ch": ch, "rows": _original_grid(ch, strike, cmap)} for ch in s]


_PC98 = None  # lazy (PIL pixel access, {syllable: [col, row]})
PC98_BMP = os.path.join(ROOT, "..", "gensei-pc98", "docs", "bios", "font.bmp")
PC98_MAP = os.path.join(ROOT, "tools", "pc98_hangul_map.json")


def _pc98():
    """PC-98 BIOS 둥근모꼴 Hangul: the recorded Unicode->cell map
    (tools/pc98_hangul_map.json, see scripts/pc98_hangul_map.py) plus the
    bitmap it indexes into. Cell [col, row] -> pixel origin col*16, row*16."""
    global _PC98
    if _PC98 is None:
        from PIL import Image
        img = Image.open(PC98_BMP).convert("L")
        with open(PC98_MAP, encoding="utf-8") as f:
            cells = json.load(f)["cells"]
        _PC98 = (img.load(), cells)
    return _PC98


def _pc98_grid(ch):
    try:
        px, cells = _pc98()
    except Exception:
        return None
    cell = cells.get(ch)
    if not cell:
        return None
    col, row = cell
    x0, y0 = col * 16, row * 16
    return ["".join("#" if px[x0 + x, y0 + y] < 128 else "." for x in range(16))
            for y in range(16)]


def pc98_grids(s):
    """Per-char pixel grids from the PC-98 BIOS font -- the 2,350 KS X 1001
    완성형 Hangul or the 169 hiragana/katakana it carries. Weight-independent --
    used as a second skeleton-reference overlay (둥근모꼴) alongside the
    original bitmap."""
    return [{"ch": ch, "rows": _pc98_any_grid(ch)} for ch in s]


_PC98_KANA = None  # lazy (PIL pixel access, {kana: [col, row]})
PC98_KANA_MAP = os.path.join(ROOT, "tools", "pc98_kana_map.json")


def _pc98_kana():
    """PC-98 BIOS 둥근모꼴 hiragana/katakana: tools/pc98_kana_map.json (see
    scripts/pc98_kana_map.py) plus the same font.bmp Hangul indexes into.
    No halfwidth katakana -- not present anywhere in this ROM."""
    global _PC98_KANA
    if _PC98_KANA is None:
        px, _ = _pc98()  # reuse the same bitmap; raises if unavailable
        with open(PC98_KANA_MAP, encoding="utf-8") as f:
            cells = json.load(f)["cells"]
        _PC98_KANA = (px, cells)
    return _PC98_KANA


def _pc98_kana_grid(ch):
    try:
        px, cells = _pc98_kana()
    except Exception:
        return None
    cell = cells.get(ch)
    if not cell:
        return None
    col, row = cell
    x0, y0 = col * 16, row * 16
    return ["".join("#" if px[x0 + x, y0 + y] < 128 else "." for x in range(16))
            for y in range(16)]


def _pc98_any_grid(ch):
    """Hangul or kana, whichever this character is. Weight-independent base
    reference: kana now comes from here instead of the original bitmap (see
    docs/ROADMAP.md) -- font.bmp never had the original's kana replaced."""
    return _pc98_grid(ch) or _pc98_kana_grid(ch)


_PC98_HALFWIDTH = None  # lazy (PIL pixel access, {"1".."94": [col, row]})
PC98_HALFWIDTH_MAP = os.path.join(ROOT, "tools", "pc98_halfwidth_map.json")
HALFWIDTH_FILE = os.path.join(ROOT, "tools", "glyphs_halfwidth.json")


def _pc98_halfwidth():
    """PC-98 BIOS 반각 한글 table: tools/pc98_halfwidth_map.json (see
    scripts/pc98_halfwidth_map.py), col 10 of the same font.bmp. Slots are
    keyed by ten-index ("1".."94"), not character -- this table isn't in
    KS X 1001 or Unicode-halfwidth-Hangul order, it's a ROM-specific set."""
    global _PC98_HALFWIDTH
    if _PC98_HALFWIDTH is None:
        px, _ = _pc98()  # reuse the same bitmap; raises if unavailable
        with open(PC98_HALFWIDTH_MAP, encoding="utf-8") as f:
            cells = json.load(f)["cells"]
        _PC98_HALFWIDTH = (px, cells)
    return _PC98_HALFWIDTH


def _pc98_halfwidth_grid(slot):
    try:
        px, cells = _pc98_halfwidth()
    except Exception:
        return None
    cell = cells.get(slot)
    if not cell:
        return None
    col, row = cell
    x0, y0 = col * 16, row * 16
    return ["".join("#" if px[x0 + x, y0 + y] < 128 else "." for x in range(16))
            for y in range(16)]


def _halfwidth_sort_key(slot):
    """slot is "{col}-{ten}", e.g. "10-5" -- sort by (col, ten) numerically,
    not lexicographically (else "10-10" < "10-2")."""
    col, ten = slot.split("-")
    return (int(col), int(ten))


def halfwidth_ref_slots():
    """All 반각 한글 reference slots (cols 10-11, 94 each), in (col, ten)
    order. Blank-in-ROM slots still get an entry (all-blank rows) -- the
    editor shows them the same as drawn ones, just with nothing to trace yet."""
    try:
        _, cells = _pc98_halfwidth()
    except Exception:
        return []
    return [{"slot": s, "rows": _pc98_halfwidth_grid(s)}
            for s in sorted(cells, key=_halfwidth_sort_key)]


def read_halfwidth():
    with open(HALFWIDTH_FILE, encoding="utf-8") as f:
        return json.load(f)


def write_halfwidth(data):
    ordered = {k: data[k] for k in sorted(data, key=_halfwidth_sort_key)}
    with open(HALFWIDTH_FILE, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)
        f.write("\n")


HALFWIDTH_CHARMAP_FILE = os.path.join(ROOT, "tools", "halfwidth_char_map.json")


def read_halfwidth_charmap():
    with open(HALFWIDTH_CHARMAP_FILE, encoding="utf-8") as f:
        return json.load(f)


def write_halfwidth_charmap(data):
    # empty string clears an assignment rather than storing a blank
    cleaned = {k: v for k, v in data.items() if v}
    ordered = {k: cleaned[k] for k in sorted(cleaned, key=_halfwidth_sort_key)}
    with open(HALFWIDTH_CHARMAP_FILE, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)
        f.write("\n")


_LIGHT_HANGUL = None  # lazy build/light_hangul.json (see scripts/compose_light.py)
LIGHT_HANGUL_FILE = os.path.join(ROOT, "build", "light_hangul.json")


def _light_hangul():
    global _LIGHT_HANGUL
    if _LIGHT_HANGUL is None:
        with open(LIGHT_HANGUL_FILE, encoding="utf-8") as f:
            _LIGHT_HANGUL = json.load(f)
    return _LIGHT_HANGUL


def _halved_light_grid(ch):
    """This character's Light 완성형 glyph (16px wide), squeezed left-right by
    half (OR-fold each adjacent column pair -> 8px) -- a rough shape guide
    for hand-drawing its 반각 counterpart. Not a claim that this IS the
    correct halfwidth shape (halfwidth glyphs are independently designed, not
    a mechanical rescale) -- just a starting reference, per user request."""
    try:
        rows = _light_hangul().get(ch)
    except Exception:
        return None
    if not rows:
        return None
    return ["".join("#" if (r[2 * c] == "#" or r[2 * c + 1] == "#") else "."
                     for c in range(8)) for r in rows]


def halfwidth_light_grids(s):
    return [{"ch": ch, "rows": _halved_light_grid(ch)} for ch in s]


def ks2350_chars():
    """The 2,350 KS X 1001 완성형 syllables, in EUC-KR order (same order as
    tools/pc98_hangul_map.json's cells) -- the full-coverage Light palette."""
    try:
        return list(_pc98()[1].keys())
    except Exception:
        return []


# Kana skeleton/proportion reference. Named by role (KANA_REF_*), not by the
# specific font, since this has already been swapped repeatedly (Meiryo ->
# PixelMplus12 -> Noto Sans JP -> Hiragino Kaku Gothic -> MS UI Gothic ->
# MS Gothic) chasing something plain, angular, and full-cell enough at small
# sizes -- swapping the font again should mean changing this path/size, not
# renaming every call site. Currently **MS Gothic** (refs/msgothic.ttf, user-
# supplied, gitignored), same family/era as Windows' Gulim/Dotum for Korean
# -- pre-ClearType, hand-drawn embedded bitmap strikes rather than a scaled
# outline (not a traced curve, so it reads far more angular/legible at this
# size than Hiragino or Noto did). Picked over MS UI Gothic (tried first)
# because MS Gothic is the full monospace-cell variant -- MS UI Gothic's
# narrower proportional cells read too narrow next to our fixed-width grid.
# Genuinely pixel-hinted at this exact size (not a traced curve), so its
# loops are already close to the chamfered-rectangle grammar (see Hangul ㅇ
# in glyphs_light.json) -- still redraw by hand rather than copying pixels,
# but there's much less to "square off" than with the earlier vector-font
# references.
KANA_REF_TTF = os.path.join(ROOT, "refs", "msgothic.ttf")
KANA_REF_PX = 12         # this face has real embedded bitmap strikes at
                          # every pixel size 12-22; ink is a tight 11 rows
                          # at this size for the samples checked (ら/わ/が/あ)
KANA_REF_BASELINE_ROW = 12  # last row of the cap~baseline band (editor's
                             # baseline guide sits at row 13) -- ink bottom
                             # is pinned here, not centered in the band.
_KANA_REF = None            # lazy freetype Face


def _is_kana(ch):
    return (0x3041 <= ord(ch) <= 0x30FF) or (0xFF61 <= ord(ch) <= 0xFF9F)


def _kana_ref():
    """Kana skeleton reference face, a visual-only overlay for hand-drawing
    kana in our own angular style. Never embedded in built output, kana only."""
    global _KANA_REF
    if _KANA_REF is None:
        import freetype
        face = freetype.Face(KANA_REF_TTF)
        # width=0 -> derive from height, required to land on the matching
        # embedded bitmap strike rather than an (absent/scaled) outline.
        face.set_pixel_sizes(0, KANA_REF_PX)
        _KANA_REF = face
    return _KANA_REF


def _kana_ref_grid(ch):
    if not _is_kana(ch):
        return None
    try:
        face = _kana_ref()
    except Exception:
        return None
    import freetype
    try:
        face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    except Exception:
        return None
    slot = face.glyph
    if slot.bitmap.width == 0 or slot.bitmap.rows == 0:
        return None  # e.g. .notdef / unsupported char
    bmp = slot.bitmap
    bits = [[(bmp.buffer[y * bmp.pitch + x // 8] >> (7 - (x % 8))) & 1
             for x in range(bmp.width)] for y in range(bmp.rows)]
    ink_rows = [y for y, row in enumerate(bits) if any(row)]
    ink_cols = [x for x in range(bmp.width) if any(row[x] for row in bits)]
    if not ink_rows or not ink_cols:
        return None  # blank glyph (e.g. space)
    row_min, row_max = min(ink_rows), max(ink_rows)
    col_min, col_max = min(ink_cols), max(ink_cols)
    grid = [["."] * 16 for _ in range(16)]
    # Crop to the *tight* ink bounding box (this font pads a blank trailing
    # row in its bitmap allocation) then center horizontally / pin the ink
    # bottom to our baseline row -- ignoring the font's own metrics
    # (left-side bearing, baseline) entirely, since this is a proportion/
    # size guide, not a typographically-correct overlay.
    dx = (16 - (col_max - col_min + 1)) // 2 - col_min
    dy = KANA_REF_BASELINE_ROW - row_max
    for y in range(row_min, row_max + 1):
        gy = dy + y
        if not (0 <= gy < 16):
            continue
        for x in range(col_min, col_max + 1):
            gx = dx + x
            if not (0 <= gx < 16):
                continue
            if bits[y][x]:
                grid[gy][gx] = "#"
    return ["".join(row) for row in grid]


def kana_ref_grids(s):
    """Per-char pixel grids rasterized from the kana skeleton reference font
    at its configured size, aligned to our baseline row. Kana only,
    reference overlay only."""
    return [{"ch": ch, "rows": _kana_ref_grid(ch)} for ch in s]


def kana_chars():
    """Hiragana + katakana + halfwidth katakana (Unicode-assigned codepoints
    only), for the editor's kana palette (Phase 3)."""
    import unicodedata

    def assigned(lo, hi):
        out = []
        for cp in range(lo, hi + 1):
            try:
                unicodedata.name(chr(cp))
            except ValueError:
                continue
            out.append(chr(cp))
        return out
    return assigned(0x3041, 0x309F) + assigned(0x30A1, 0x30FF) + assigned(0xFF61, 0xFF9F)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass  # quiet

    def _weight_qs(self, qs):
        w = qs.get("weight", ["regular"])[0]
        if w not in GLYPHS_FILES:
            w = "regular"
        return w

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query, keep_blank_values=True)

        if parsed.path in ("/", "/index.html"):
            with open(EDITOR, encoding="utf-8") as f:
                page = PAGE_HEAD + f.read() + PAGE_TAIL
            return self._send(200, page, "text/html; charset=utf-8")
        if parsed.path == "/api/glyphs":
            weight = self._weight_qs(qs)
            return self._send(200, json.dumps(read_glyphs(weight), ensure_ascii=False))
        if parsed.path == "/api/text":
            weight = self._weight_qs(qs)
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": text_grids(weight, s)},
                                              ensure_ascii=False))
        if parsed.path == "/api/original":
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": original_grids(s)},
                                              ensure_ascii=False))
        if parsed.path == "/api/pc98":
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": pc98_grids(s)},
                                              ensure_ascii=False))
        if parsed.path == "/api/ks2350":
            return self._send(200, json.dumps({"chars": ks2350_chars()},
                                              ensure_ascii=False))
        if parsed.path == "/api/kanaref":
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": kana_ref_grids(s)},
                                              ensure_ascii=False))
        if parsed.path == "/api/kana":
            return self._send(200, json.dumps({"chars": kana_chars()},
                                              ensure_ascii=False))
        if parsed.path in ("/halfwidth", "/halfwidth.html", "/halfwidth/"):
            with open(HALFWIDTH_EDITOR, encoding="utf-8") as f:
                page = HALFWIDTH_PAGE_HEAD + f.read() + PAGE_TAIL
            return self._send(200, page, "text/html; charset=utf-8")
        if parsed.path == "/api/halfwidth_ref":
            return self._send(200, json.dumps({"slots": halfwidth_ref_slots()},
                                              ensure_ascii=False))
        if parsed.path == "/api/halfwidth_glyphs":
            return self._send(200, json.dumps(read_halfwidth(), ensure_ascii=False))
        if parsed.path == "/api/halfwidth_charmap":
            return self._send(200, json.dumps(read_halfwidth_charmap(), ensure_ascii=False))
        if parsed.path == "/api/halfwidth_light_ref":
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": halfwidth_light_grids(s)},
                                              ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        if parsed.path == "/api/glyphs":
            weight = self._weight_qs(qs)
            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": f"bad json: {e}"}))
            data = read_glyphs(weight)
            data.update(incoming)
            write_glyphs(weight, data)
            return self._send(200, json.dumps({"saved": list(incoming), "total": len(data)}))
        if parsed.path == "/api/build":
            weight = self._weight_qs(qs)
            ok, log = run_build(weight)
            return self._send(200 if ok else 500, json.dumps({"ok": ok, "log": log}))
        if parsed.path == "/api/build_bmp":
            ok, log = run_build_bmp()
            return self._send(200 if ok else 500, json.dumps({"ok": ok, "log": log}))
        if parsed.path == "/api/halfwidth_glyphs":
            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": f"bad json: {e}"}))
            data = read_halfwidth()
            data.update(incoming)
            write_halfwidth(data)
            return self._send(200, json.dumps({"saved": list(incoming), "total": len(data)}))
        if parsed.path == "/api/halfwidth_charmap":
            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": f"bad json: {e}"}))
            data = read_halfwidth_charmap()
            data.update(incoming)
            write_halfwidth_charmap(data)
            return self._send(200, json.dumps({"saved": list(incoming), "total": len(data)}))
        self._send(404, json.dumps({"error": "not found"}))


BUILD_TARGETS = {
    "regular": {
        "ufo": "build/DokkaebiDNRGothic.ufo",
        "ttf": "build/DokkaebiDNRGothic.ttf",
        "build_args": ["--all"],
    },
    "light": {
        "ufo": "build/DokkaebiDNRGothicLight.ufo",
        "ttf": "build/DokkaebiDNRGothicLight.ttf",
        "build_args": ["--weight", "light"],
    },
}


def run_build(weight):
    target = BUILD_TARGETS.get(weight, BUILD_TARGETS["regular"])
    py = sys.executable
    steps = [
        [py, "scripts/build_ufo.py", *target["build_args"], "--proportional",
         "--out", target["ufo"]],
        [py, "-m", "fontmake", "-u", target["ufo"],
         "-o", "ttf", "--output-path", target["ttf"]],
        [py, "scripts/finalize.py", target["ttf"]],
    ]
    out = []
    for cmd in steps:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out.append(f"$ {' '.join(cmd[1:])}\n{(p.stdout or '')[-400:]}{(p.stderr or '')[-400:]}")
        if p.returncode != 0:
            return False, "\n".join(out)
    return True, "\n".join(out)


def run_build_bmp():
    """Regenerate build/font_light.bmp from current saved state -- recompose
    Light Hangul (build/light_hangul.json) then drop it + the saved 반각 한글
    (glyphs_halfwidth.json) into a copy of the PC-98 font.bmp. Unsaved edits
    in the editor aren't included (both scripts read from disk)."""
    py = sys.executable
    steps = [
        [py, "scripts/compose_light.py"],
        [py, "scripts/build_pc98_bmp.py"],
    ]
    out = []
    for cmd in steps:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out.append(f"$ {' '.join(cmd[1:])}\n{(p.stdout or '')[-400:]}{(p.stderr or '')[-400:]}")
        if p.returncode != 0:
            return False, "\n".join(out)
    return True, "\n".join(out)


def _ensure_venv():
    """Re-exec under this project's .venv if we're not already running there.

    fontTools/PIL (via tools/pixelfont.py, the PC-98/kana/halfwidth lookups,
    etc.) only live in .venv, and every one of those call sites imports them
    lazily and fails closed (try/except -> blank grid) rather than raising --
    so running under plain system `python3` doesn't error, it just silently
    renders Regular Hangul (and kana, and the PC-98/kana-ref overlays) as
    nothing but blank cells. Re-exec here removes the whole "did you
    activate the venv" failure mode instead of relying on people remembering."""
    venv_dir = os.path.join(ROOT, ".venv")
    venv_py = os.path.join(venv_dir, "bin", "python3")
    # Compare sys.prefix, not sys.executable/realpath: .venv/bin/python3 is
    # usually just a symlink to the same base interpreter binary, so the
    # executable path (even resolved) is identical either way -- sys.prefix
    # is what actually flips to .venv once its site-packages are active.
    if os.path.exists(venv_py) and os.path.realpath(sys.prefix) != os.path.realpath(venv_dir):
        os.execv(venv_py, [venv_py] + sys.argv)


def main():
    _ensure_venv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}/"
    print(f"pixel editor: {url}  (Ctrl+C to stop)")
    print(f"  editing tools/glyphs_regular.json / glyphs_light.json  ·  POST /api/build?weight=regular|light to rebuild")
    print(f"  반각 한글 에디터: {url}halfwidth  ·  editing tools/glyphs_halfwidth.json (separate from the font build)")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
