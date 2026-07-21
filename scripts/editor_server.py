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
                             original (preview)
  GET  /api/original?s=.. -> per-char grids from the ORIGINAL bitmap only,
                             ignoring custom overrides (weight-independent --
                             it's always the 2px Dokkaebi Dinaru source used as
                             a reference for both weights)
  POST /api/build?weight=regular
                          -> rebuild TTF (build_ufo -> fontmake -> finalize).
                             Regular only for now; Light has no build pipeline
                             yet (see docs/ROADMAP.md Phase 2).

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


def text_grids(weight, s):
    """Per-char pixel grids for preview: custom glyphs (for this weight)
    override the original."""
    custom = read_glyphs(weight)
    try:
        strike, cmap = _orig()
    except Exception:
        strike, cmap = {}, {}
    out = []
    for ch in s:
        grid = custom.get(ch) or _original_grid(ch, strike, cmap)
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
            if weight != "regular":
                return self._send(400, json.dumps({
                    "ok": False,
                    "log": "Light 웨이트는 아직 빌드 파이프라인이 없습니다 (docs/ROADMAP.md Phase 2 참고).",
                }, ensure_ascii=False))
            ok, log = run_build()
            return self._send(200 if ok else 500, json.dumps({"ok": ok, "log": log}))
        self._send(404, json.dumps({"error": "not found"}))


def run_build():
    py = sys.executable
    steps = [
        [py, "scripts/build_ufo.py", "--all", "--proportional",
         "--out", "build/DokkaebiDNRGothic.ufo"],
        [py, "-m", "fontmake", "-u", "build/DokkaebiDNRGothic.ufo",
         "-o", "ttf", "--output-path", "build/DokkaebiDNRGothic.ttf"],
        [py, "scripts/finalize.py", "build/DokkaebiDNRGothic.ttf"],
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
    print(f"  editing tools/glyphs_regular.json / glyphs_light.json  ·  POST /api/build?weight=regular to rebuild")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
