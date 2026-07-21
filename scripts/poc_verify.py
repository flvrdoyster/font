"""Phase 1 PoC: verify pixel->vector conversion is pixel-exact.

For a sample set (and optionally the whole font) we convert each glyph's bitmap
to contours, rasterize the contours back at 16px, and assert the result matches
the original bitmap exactly. Also prints ASCII renders and point counts.
"""
import sys
from fontTools.ttLib import TTFont

sys.path.insert(0, "tools")
import pixelfont as pf

SAMPLES = ["한", "글", "다", "o", "8", "ㅇ", "가", "밝", "쓺", "A", "B", "0", "@"]


def ascii_render(width, rows):
    out = []
    for val in rows:
        out.append("".join("#" if val & (1 << (width - 1 - c)) else "." for c in range(width)))
    return out


def main():
    font = TTFont("original/HANKBC.ttf")
    strike = pf.read_strike(font)
    cmap = font.getBestCmap()

    # --- sample glyphs: show + verify ---
    for ch in SAMPLES:
        gname = cmap.get(ord(ch))
        if gname is None or gname not in strike:
            print(f"[skip] {ch!r} not in font")
            continue
        width, rows = strike[gname]
        contours = pf.pixels_to_contours(width, rows)
        back = pf.rasterize(contours, width)
        ok = back == rows
        pts = sum(len(c) for c in contours)
        naive = sum(bin(r).count("1") for r in rows) * 4
        print(f"== {ch!r}  ({gname})  {width}px  contours={len(contours)} "
              f"points={pts} (naive per-pixel would be {naive})  "
              f"{'OK' if ok else '*** MISMATCH ***'}")
        orig = ascii_render(width, rows)
        got = ascii_render(width, back)
        for a, b in zip(orig, got):
            mark = "" if a == b else "  <-- diff"
            print(f"   {a}   {b}{mark}")
        print()

    # --- full-font pixel-exact sweep ---
    total = mismatches = 0
    worst_pts = 0
    for gname, (width, rows) in strike.items():
        if width == 0:
            continue
        total += 1
        contours = pf.pixels_to_contours(width, rows)
        pts = sum(len(c) for c in contours)
        worst_pts = max(worst_pts, pts)
        if pf.rasterize(contours, width) != rows:
            mismatches += 1
            if mismatches <= 10:
                print(f"MISMATCH: {gname}")
    print(f"\n=== FULL SWEEP ===")
    print(f"glyphs checked: {total}")
    print(f"pixel-exact mismatches: {mismatches}")
    print(f"max points in any glyph: {worst_pts}")


if __name__ == "__main__":
    main()
