"""Local server for the pixel editor.

    python scripts/editor_server.py [--port 8000] [--no-open]

Serves tools/pixel_editor.html at http://localhost:PORT/ and exposes a small
API so the editor can load and SAVE glyphs directly into tools/glyphs.json:

  GET  /api/glyphs        -> current glyphs.json  { "A": [rows], ... }
  POST /api/glyphs        -> merge { "A": [rows], ... } into glyphs.json
  POST /api/build         -> rebuild TTF (build_ufo -> fontmake -> finalize)

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
GLYPHS = os.path.join(ROOT, "tools", "glyphs.json")

PAGE_HEAD = (
    "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>도깨비DNR 픽셀 에디터</title></head><body>"
)
PAGE_TAIL = "</body></html>"


def read_glyphs():
    with open(GLYPHS, encoding="utf-8") as f:
        return json.load(f)


def write_glyphs(data):
    # keep sorted + stable formatting so git diffs stay clean
    ordered = {k: data[k] for k in sorted(data)}
    with open(GLYPHS, "w", encoding="utf-8") as f:
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


def text_grids(s):
    """Per-char pixel grids for preview: custom glyphs override the original."""
    custom = read_glyphs()
    try:
        strike, cmap = _orig()
    except Exception:
        strike, cmap = {}, {}
    out = []
    for ch in s:
        grid = custom.get(ch)
        if grid is None:
            gname = cmap.get(ord(ch))
            if gname and gname in strike:
                w, rows = strike[gname]
                if w:
                    grid = ["".join("#" if r & (1 << (w - 1 - x)) else "."
                                    for x in range(w)) for r in rows]
        out.append({"ch": ch, "rows": grid})
    return out


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

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(EDITOR, encoding="utf-8") as f:
                page = PAGE_HEAD + f.read() + PAGE_TAIL
            return self._send(200, page, "text/html; charset=utf-8")
        if self.path == "/api/glyphs":
            return self._send(200, json.dumps(read_glyphs(), ensure_ascii=False))
        if self.path.startswith("/api/text"):
            qs = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": text_grids(s)},
                                              ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        if self.path == "/api/glyphs":
            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": f"bad json: {e}"}))
            data = read_glyphs()
            data.update(incoming)
            write_glyphs(data)
            return self._send(200, json.dumps({"saved": list(incoming), "total": len(data)}))
        if self.path == "/api/build":
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
    print(f"  editing tools/glyphs.json  ·  POST /api/build to rebuild the font")
    if not args.no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
