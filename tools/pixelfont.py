"""
Pixel-bitmap -> vector-outline converter for HANKBC restoration.

Core idea: preserve the pixel/staircase look exactly. Every "on" pixel becomes a
64x64 unit square (16px cell over a 1024 upem => 64 units/pixel). Adjacent pixels'
shared edges cancel out, leaving merged rectilinear polygons. Counters (holes) get
the opposite winding automatically, so non-zero fill is always correct.

Coordinate mapping (font space, y-up, baseline at y=0):
  pixel column c  -> x in [c*PX, (c+1)*PX]
  pixel row r     -> y in [(H-1-r)*PX, (H-r)*PX]   (row 0 = top)
with bearingY = H so the whole cell sits above the baseline.
"""

from collections import defaultdict

PX = 64          # font units per pixel (1024 upem / 16px)
CELL = 16        # bitmap cell height in pixels


def read_strike(font):
    """Return {glyphName: (width_px, [row_bitmasks])} for the single EBDT strike.

    Each row is an int whose bit (width-1-x) is set when pixel x is on.
    Width is derived from the image data length (robust, no metric lookup).
    """
    ebdt = font["EBDT"]
    sd = ebdt.strikeData[0]
    out = {}
    for gname, glyph in sd.items():
        glyph.ensureDecompiled()
        data = glyph.imageData
        if not data:
            out[gname] = (0, [])
            continue
        bpr = len(data) // CELL           # bytes per row (1 => 8px, 2 => 16px)
        width = bpr * 8
        rows = []
        for r in range(CELL):
            val = 0
            for k in range(bpr):
                val = (val << 8) | data[r * bpr + k]
            rows.append(val)
        out[gname] = (width, rows)
    return out


def pixels_from_rows(width, rows):
    """Yield (col, row) for every set pixel. row 0 = top."""
    for r, val in enumerate(rows):
        for c in range(width):
            if val & (1 << (width - 1 - c)):
                yield c, r


def _pixel_edges(c, r, h=CELL, px=PX):
    """Four boundary edges of one pixel, wound CCW (interior on the left).

    Returns list of ((x0,y0),(x1,y1)) directed segments.
    """
    x0, x1 = c * px, (c + 1) * px
    yb, yt = (h - 1 - r) * px, (h - r) * px   # bottom, top in y-up space
    bl, br_, tr, tl = (x0, yb), (x1, yb), (x1, yt), (x0, yt)
    # CCW: bottom L->R, right B->T, top R->L, left T->B
    return [(bl, br_), (br_, tr), (tr, tl), (tl, bl)]


def pixels_to_contours(width, rows, h=CELL, px=PX):
    """Convert a bitmap into merged rectilinear contours.

    Returns list of contours; each contour is a list of (x, y) corner points
    (closed implicitly, collinear points removed). Outer contours are CCW,
    holes CW -- i.e. PostScript/UFO winding convention.
    """
    # 1. edge cancellation: shared interior edges annihilate
    edges = set()
    for c, r in pixels_from_rows(width, rows):
        for a, b in _pixel_edges(c, r, h, px):
            if (b, a) in edges:
                edges.remove((b, a))   # opposite edge -> shared interior wall
            else:
                edges.add((a, b))

    if not edges:
        return []

    # 2. build outgoing adjacency (a vertex may have >1 outgoing at pinches)
    out = defaultdict(list)
    for a, b in edges:
        out[a].append(b)

    # 3. stitch loops. At each vertex continue straight if possible, else turn.
    #    "turn right" (clockwise) resolves diagonal pinch points into two loops.
    contours = []
    remaining = set(edges)

    def direction(a, b):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        return (0 if dx == 0 else (1 if dx > 0 else -1),
                0 if dy == 0 else (1 if dy > 0 else -1))

    def pick_next(prev_dir, cur, cands):
        # Prefer straight, then right turn, then left turn, then reverse.
        dx, dy = prev_dir
        straight = (dx, dy)
        right = (dy, -dx)     # clockwise 90
        left = (-dy, dx)      # counter-clockwise 90
        order = {straight: 0, right: 1, left: 2, (-dx, -dy): 3}
        best, best_rank = None, 99
        for nb in cands:
            d = direction(cur, nb)
            rank = order.get(d, 99)
            if rank < best_rank:
                best, best_rank = nb, rank
        return best

    while remaining:
        a, b = next(iter(remaining))
        loop = [a]
        cur_prev, cur = a, b
        remaining.discard((a, b))
        out[a].remove(b)
        while cur != a:
            loop.append(cur)
            pdir = direction(cur_prev, cur)
            nb = pick_next(pdir, cur, out[cur])
            remaining.discard((cur, nb))
            out[cur].remove(nb)
            cur_prev, cur = cur, nb
        # drop collinear intermediate points
        contours.append(_simplify(loop))
    return contours


def _simplify(pts):
    """Remove points that lie on a straight line between neighbours."""
    n = len(pts)
    keep = []
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        # cross product of (p1-p0) x (p2-p1); 0 => collinear
        cross = (p1[0] - p0[0]) * (p2[1] - p1[1]) - (p1[1] - p0[1]) * (p2[0] - p1[0])
        if cross != 0:
            keep.append(p1)
    return keep


def rasterize(contours, width, h=CELL, px=PX):
    """Rasterize contours back to a bitmap by non-zero winding at pixel centres.

    Returns list of row bitmasks matching read_strike's format. Used to verify
    the vector shape reproduces the original bitmap pixel-for-pixel.
    """
    rows = []
    for r in range(h):
        val = 0
        cy = (h - 1 - r) * px + px / 2.0
        for c in range(width):
            cx = c * px + px / 2.0
            if _winding(contours, cx, cy) != 0:
                val |= (1 << (width - 1 - c))
        rows.append(val)
    return rows


def _winding(contours, x, y):
    """Non-zero winding number of point (x,y) w.r.t. all contours."""
    wn = 0
    for contour in contours:
        n = len(contour)
        for i in range(n):
            x0, y0 = contour[i]
            x1, y1 = contour[(i + 1) % n]
            if y0 <= y:
                if y1 > y and _is_left(x0, y0, x1, y1, x, y) > 0:
                    wn += 1
            else:
                if y1 <= y and _is_left(x0, y0, x1, y1, x, y) < 0:
                    wn -= 1
    return wn


def _is_left(x0, y0, x1, y1, x, y):
    return (x1 - x0) * (y - y0) - (x - x0) * (y1 - y0)
