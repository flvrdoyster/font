"""Recenter kana ink horizontally within their 16px cell (advance unchanged).

Hand-drawn kana glyphs currently ship with whatever left margin they happened
to be drawn with, and that varies a lot -- measured left bounds from 2 to 4px,
right bounds from 3 to 6px across a small sample. Since kana render at a fixed
full-width advance with no glyph-specific horizontal shift (see spacing.py's
_is_fullwidth), that unevenness shows up as inconsistent-looking gaps between
characters in running text.

This mechanically centers each kana glyph's own ink bounding box within its 16
columns (advance stays 16 either way -- only the ink moves). Half-width
katakana (U+FF61-FF9F, 8px, already left-aligned by design -- a different,
intentional convention) are left untouched. Applies independently to
glyphs_light.json and glyphs_bold.json: their kana entries have already
diverged (Bold's are thickened, not copies of Light's), so each gets centered
against its own ink, not shifted by Light's amount.

This is a mechanical first pass, not a final answer -- centering by the raw
bounding box can still look optically off for some shapes (round vs. angular
ink reads differently even at equal pixel margins), so review the result
(--specimen) and hand-adjust outliers afterward, same as any other optical
correction in this project.

Usage:
  python scripts/center_kana.py            # apply and overwrite both files
  python scripts/center_kana.py --dry-run   # report shifts, write nothing
  python scripts/center_kana.py --specimen  # also write build/kana_center_{before,after}.png
"""
import argparse
import json
import os
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIGHT = os.path.join(ROOT, "tools", "glyphs_light.json")
BOLD = os.path.join(ROOT, "tools", "glyphs_bold.json")
CELL = 16


def kana_chars():
    def assigned(lo, hi):
        out = []
        for cp in range(lo, hi + 1):
            try:
                unicodedata.name(chr(cp))
            except ValueError:
                continue
            out.append(chr(cp))
        return out
    return assigned(0x3041, 0x309F) + assigned(0x30A1, 0x30FF)  # full-width only


def ink_bounds(rows):
    lo = hi = None
    for row in rows:
        for x, c in enumerate(row):
            if c == "#":
                lo = x if lo is None else min(lo, x)
                hi = x if hi is None else max(hi, x)
    return None if lo is None else (lo, hi)


def shift_rows(rows, dx):
    if dx == 0:
        return rows
    width = len(rows[0])
    out = []
    for row in rows:
        new = ["."] * width
        for x, c in enumerate(row):
            if c == "#":
                nx = x + dx
                if 0 <= nx < width:
                    new[nx] = "#"
        out.append("".join(new))
    return out


def center_file(path, chars, dry_run):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    changes = []
    for ch in chars:
        if ch not in data:
            continue
        rows = data[ch]
        if len(rows[0]) != CELL:
            continue  # not a full-width slot, skip
        b = ink_bounds(rows)
        if b is None:
            continue
        lo, hi = b
        ink_w = hi - lo + 1
        dx = (CELL - ink_w) // 2 - lo
        if dx != 0:
            changes.append((ch, lo, hi, dx))
            data[ch] = shift_rows(rows, dx)
    if changes and not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({k: data[k] for k in sorted(data)}, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return changes


def write_specimen(path, chars, out_path):
    from PIL import Image
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    chars = [c for c in chars if c in data]
    cols, scale, pad = 20, 6, 2
    cw = CELL * scale + pad
    rows_n = (len(chars) + cols - 1) // cols
    img = Image.new("RGB", (cols * cw + pad, rows_n * cw + pad), (255, 255, 255))
    px = img.load()
    for i, ch in enumerate(chars):
        gx, gy = pad + (i % cols) * cw, pad + (i // cols) * cw
        rows = data[ch]
        for y in range(CELL):
            for x in range(CELL):
                color = (20, 20, 20) if rows[y][x] == "#" else (255, 255, 255)
                for dy in range(scale):
                    for dx in range(scale):
                        px[gx + x * scale + dx, gy + y * scale + dy] = color
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path)
    print(f"  specimen -> {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--specimen", action="store_true")
    args = ap.parse_args()

    chars = kana_chars()

    if args.specimen:
        write_specimen(LIGHT, chars, os.path.join(ROOT, "build", "kana_center_before_light.png"))
        write_specimen(BOLD, chars, os.path.join(ROOT, "build", "kana_center_before_bold.png"))

    for label, path in (("light", LIGHT), ("bold", BOLD)):
        changes = center_file(path, chars, args.dry_run)
        print(f"{label}: {len(changes)}/{len(chars)} kana shifted"
              f"{' (dry-run, not written)' if args.dry_run else ''}")
        for ch, lo, hi, dx in changes:
            print(f"  {ch}  ink=({lo},{hi})  dx={dx:+d}")

    if args.specimen:
        write_specimen(LIGHT, chars, os.path.join(ROOT, "build", "kana_center_after_light.png"))
        write_specimen(BOLD, chars, os.path.join(ROOT, "build", "kana_center_after_bold.png"))


if __name__ == "__main__":
    main()
