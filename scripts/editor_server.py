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
  GET  /api/dotgothic16?s=..
                          -> per-char grids rasterized from DotGothic16 (SIL
                             OFL 1.1, refs/dotgothic16/) at its native 16px
                             size. Reference-only overlay for hand-drawing
                             kana/symbols -- never embedded in built output.
  POST /api/build?weight=regular|light
                          -> rebuild that weight's TTF (build_ufo -> fontmake
                             -> finalize). regular = full original-bitmap
                             font; light = thinned Latin/numbers + composed
                             KS X 1001 Hangul (scripts/compose_light.py).

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
    """Per-char pixel grids from the PC-98 BIOS font, for the 2,350 KS X 1001
    완성형 Hangul it carries. Weight-independent -- used as a second
    skeleton-reference overlay (둥근모꼴) alongside the original bitmap."""
    return [{"ch": ch, "rows": _pc98_grid(ch)} for ch in s]


def ks2350_chars():
    """The 2,350 KS X 1001 완성형 syllables, in EUC-KR order (same order as
    tools/pc98_hangul_map.json's cells) -- the full-coverage Light palette."""
    try:
        return list(_pc98()[1].keys())
    except Exception:
        return []


_DOTGOTHIC16 = None  # lazy freetype Face
DOTGOTHIC16_TTF = os.path.join(ROOT, "refs", "dotgothic16", "DotGothic16-Regular.ttf")
DOTGOTHIC16_BASELINE_ROW = 13   # matches the editor's baseline guide row


def _dotgothic16():
    """DotGothic16 (SIL OFL 1.1, The DotGothic16 Project Authors / Fontworks
    Inc.) -- a visual-only reference overlay for hand-drawing kana/symbols in
    our own style. Never embedded in built output; see refs/dotgothic16/OFL.txt."""
    global _DOTGOTHIC16
    if _DOTGOTHIC16 is None:
        import freetype
        face = freetype.Face(DOTGOTHIC16_TTF)
        face.set_pixel_sizes(16, 16)
        _DOTGOTHIC16 = face
    return _DOTGOTHIC16


def _dotgothic16_grid(ch):
    try:
        face = _dotgothic16()
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
    grid = [["."] * 16 for _ in range(16)]
    for y in range(bmp.rows):
        gy = DOTGOTHIC16_BASELINE_ROW - slot.bitmap_top + y
        if not (0 <= gy < 16):
            continue
        for x in range(bmp.width):
            gx = slot.bitmap_left + x
            if not (0 <= gx < 16):
                continue
            byte = bmp.buffer[y * bmp.pitch + x // 8]
            if (byte >> (7 - (x % 8))) & 1:
                grid[gy][gx] = "#"
    return ["".join(row) for row in grid]


def dotgothic16_grids(s):
    """Per-char pixel grids rasterized from DotGothic16 at its native 16px
    size, roughly aligned to our baseline row. Reference overlay only."""
    return [{"ch": ch, "rows": _dotgothic16_grid(ch)} for ch in s]


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
        if parsed.path == "/api/dotgothic16":
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": dotgothic16_grids(s)},
                                              ensure_ascii=False))
        if parsed.path == "/api/kana":
            return self._send(200, json.dumps({"chars": kana_chars()},
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}/"
    print(f"pixel editor: {url}  (Ctrl+C to stop)")
    print(f"  editing tools/glyphs_regular.json / glyphs_light.json  ·  POST /api/build?weight=regular|light to rebuild")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
