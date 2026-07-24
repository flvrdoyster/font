"""Thin 2px-wide VERTICAL strokes to 1px, leaving horizontal bars, curve
facets, and single-pixel strokes untouched. Core transform for Phase 2
(Regular -> Light weight), applied across the whole font incl. all Hangul.

Approach: for each pair of adjacent columns (x, x+1), find maximal runs of
consecutive rows where both columns are ink. A run qualifies as a "vertical
stem" if it's at least MIN_RUN rows tall. Within that run, only rows whose
local ink width at that point is *exactly* 2 get thinned (drop the right
column of the pair); wider rows are left alone -- this protects horizontal
bars AND the >=3px facets of round jamo (o/h circles), which would otherwise
get an asymmetric one-sided "hole" punched in them if partially thinned.

Validated on: Latin custom glyphs (A/H/a/o/m -- correct 1px stems, bars
untouched) and Hangul stress samples (한글도깨비이응왕뚫옳, i.e. circle jamo,
diagonals, dense batchim clusters) -- see thin_compare.png.
"""
import json

MIN_RUN = 2  # minimum consecutive rows to call it a "stem" run


def grid_to_bits(rows):
    w = len(rows[0])
    return [[c == '#' for c in r] for r in rows], w


def bits_to_rows(bits):
    return [''.join('#' if c else '.' for c in row) for row in bits]


def local_width(bits, y, x, w):
    """width of the ink run in row y that contains column x (or x/x+1)."""
    if not bits[y][x]:
        return 0
    a = x
    while a > 0 and bits[y][a-1]:
        a -= 1
    b = x
    while b < w-1 and bits[y][b+1]:
        b += 1
    return b - a + 1


def thin_vertical(rows):
    bits, w = grid_to_bits(rows)
    h = len(bits)
    drop = [[False]*w for _ in range(h)]

    for x in range(w-1):
        y = 0
        while y < h:
            if bits[y][x] and bits[y][x+1]:
                a = y
                while a < h and bits[a][x] and bits[a][x+1]:
                    a += 1
                run_h = a - y
                if run_h >= MIN_RUN:
                    # thin per-row: rows that are exactly 2px wide (a clean
                    # stem cross-section) get thinned; rows that are wider
                    # (crossing a horizontal bar, OR part of a >=3px curve
                    # facet on round jamo like o/h) are left alone. Requiring
                    # *exactly* 2 (not <=3) avoids punching an asymmetric
                    # hole in 3px-wide circle facets -- those stay untouched
                    # rather than getting a lopsided partial thin.
                    for yy in range(y, a):
                        if local_width(bits, yy, x, w) == 2:
                            drop[yy][x+1] = True   # drop the right column
                y = a
            else:
                y += 1

    out = [[bits[y][x] and not drop[y][x] for x in range(w)] for y in range(h)]
    return bits_to_rows(out)


if __name__ == '__main__':
    import os
    here = os.path.dirname(os.path.abspath(__file__))

    # --- sanity check on our own Latin (known ground truth) ---
    glyphs = json.load(open(os.path.join(here, 'glyphs_bold.json'), encoding='utf-8'))
    for ch in ['A', 'H', 'a', 'o', 'm']:
        thinned = thin_vertical(glyphs[ch])
        print(f'=== {ch} (Latin, thinned) ===')
        for r in thinned:
            print(' ' + r)
        print()
