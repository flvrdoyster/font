"""Hand-drawn glyphs that override the bitmap-derived ones (Regular weight).

Glyph pixels live in tools/glyphs_regular.json as { "A": [16 rows of '#'/'.'],
... }. Width is the length of a row (8 for half-width Latin, 16 for
full-width). Designed to match the Dokkaebi Dinaru Hangul: 2px strokes, caps
on rows 2-12.

Light weight (1px stems) is a separate, parallel data file:
tools/glyphs_light.json -- not loaded here; see scripts/thin_vertical.py and
docs/ROADMAP.md.

Edit with tools/pixel_editor.html (served by scripts/editor_server.py, which
writes to the file for whichever weight tab is active), or edit the JSON by
hand. build_ufo.py uses these pixels instead of the original strike for any
listed character.
"""
import json
import os

_JSON = os.path.join(os.path.dirname(__file__), "glyphs_regular.json")


def load_src():
    with open(_JSON, encoding="utf-8") as f:
        return json.load(f)


def _to_rows(grid):
    width = len(grid[0])
    rows = []
    for line in grid:
        val = 0
        for x in range(width):
            if x < len(line) and line[x] == "#":
                val |= (1 << (width - 1 - x))
        rows.append(val)
    return width, rows


def build(src=None):
    """codepoint -> (width_px, [row bitmasks])."""
    if src is None:
        src = load_src()
    return {ord(ch): _to_rows(grid) for ch, grid in src.items()}


GLYPHS_SRC = load_src()
GLYPHS = build(GLYPHS_SRC)
