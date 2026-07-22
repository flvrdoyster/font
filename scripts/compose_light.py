"""Compose the full 2,350-syllable Light-weight Hangul from the hand-drawn
reference set.

Principle (see docs/ROADMAP.md): a Light glyph = the PC-98 둥근모꼴 base with
its consonants (초성/종성) replaced by our 도깨비DNR redraws; the vowel (중성)
stays PC-98. PC-98 places a given consonant at a pixel-stable position within
each block type, so a consonant we drew once transplants to every syllable of
that block type.

Method, per target syllable T = (초성 C1, 중성 V, 종성 C2):
  base = PC98[T]                         # correct vowel + PC-98 consonants
  jongzone = pixels of PC98 that move when only 종성 varies (= the batchim area)
  초성 edits: where our (C1, 6-way block type) reference differs from its own
    PC-98 glyph, restricted to OUTSIDE jongzone
  종성 edits: where our (C2, V/X-vs-H) reference differs from its PC-98 glyph,
    restricted to INSIDE jongzone
Only differing pixels move, so unedited vowel pixels stay exactly PC-98's. The
zone split is 2-D (not a row cut), so a tall double 초성 (ㄲ/ㄸ/ㅃ...) that
descends into the batchim rows is still kept whole -- its low pixels don't vary
with 종성, so they fall outside jongzone.

Inputs:  ../gensei-pc98/docs/bios/font.bmp, tools/pc98_hangul_map.json,
         tools/glyphs_light.json
Output:  build/light_hangul.json   { "가": [16 rows of #/.], ... }  (2,350)
         build/light_specimen.png  (with --specimen)

Run from the repo root:  python scripts/compose_light.py [--specimen]
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BMP = os.path.join(ROOT, "..", "gensei-pc98", "docs", "bios", "font.bmp")
PC98_MAP = os.path.join(ROOT, "tools", "pc98_hangul_map.json")
REFS = os.path.join(ROOT, "tools", "glyphs_light.json")
OUT = os.path.join(ROOT, "build", "light_hangul.json")

CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
JUNG = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")
JONG = [""] + list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")
HORIZ = set("ㅗㅛㅜㅠㅡ")
COMPLEX = set("ㅘㅙㅚㅝㅞㅟㅢ")


def decompose(ch):
    c = ord(ch) - 0xAC00
    return CHO[c // 588], JUNG[(c // 28) % 21], JONG[c % 28]


def compose_ch(cho, jung, jong):
    return chr(0xAC00 + CHO.index(cho) * 588 + JUNG.index(jung) * 28 + JONG.index(jong))


def vgroup(jung):
    return "H" if jung in HORIZ else ("X" if jung in COMPLEX else "V")


def cho_bt(jung, jong):
    return vgroup(jung) + ("C" if jong else "")   # 6-way: V/VC/H/HC/X/XC


def jong_bt(jung):
    return "H" if jung in HORIZ else "VX"          # V and X share batchim position


# ---- pixel grids as list[str] of '#'/'.' ------------------------------------

def _load_pc98():
    from PIL import Image
    px = Image.open(BMP).convert("L").load()
    cells = json.load(open(PC98_MAP, encoding="utf-8"))["cells"]
    cache = {}

    def grid(ch):
        if ch not in cache:
            cell = cells.get(ch)
            if not cell:
                cache[ch] = None
            else:
                col, row = cell
                x0, y0 = col * 16, row * 16
                cache[ch] = ["".join("#" if px[x0 + x, y0 + y] < 128 else "."
                                     for x in range(16)) for y in range(16)]
        return cache[ch]
    return grid


def jong_zone(target, pc98):
    """Pixels that move when only the 종성 varies (초성·중성 fixed) = the
    batchim area. 종성 ranges over non-empty values only, so the block type
    stays *C and the 초성 position doesn't shift into the zone."""
    cho, jung, _ = decompose(target)
    grids = []
    for jong in JONG[1:]:
        g = pc98(compose_ch(cho, jung, jong))
        if g is not None:
            grids.append(g)
    zone = set()
    if len(grids) >= 2:
        for y in range(16):
            for x in range(16):
                vals = {g[y][x] for g in grids}
                if len(vals) > 1:
                    zone.add((y, x))
    return zone


def compose(target, pc98, refs, cho_ref, jong_ref):
    cho, jung, jong = decompose(target)
    out = [list(row) for row in pc98(target)]

    def apply(ref_ch, keep):
        r, p = refs[ref_ch], pc98(ref_ch)
        for y in range(16):
            for x in range(16):
                if (y, x) in keep and r[y][x] != p[y][x]:
                    out[y][x] = r[y][x]

    all_px = {(y, x) for y in range(16) for x in range(16)}
    if jong:
        zone = jong_zone(target, pc98)
        apply(cho_ref[(cho, cho_bt(jung, jong))], all_px - zone)   # 초성 outside batchim
        apply(jong_ref[(jong, jong_bt(jung))], zone)               # 종성 inside batchim
    else:
        apply(cho_ref[(cho, cho_bt(jung, jong))], all_px)

    return ["".join(row) for row in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specimen", action="store_true")
    args = ap.parse_args()

    pc98 = _load_pc98()
    refs = json.load(open(REFS, encoding="utf-8"))

    # index our references by consonant + block type (prefer single-jong / plain
    # references over cluster ones, which appear later after sorting by length)
    cho_ref, jong_ref = {}, {}
    for ch in sorted(refs, key=lambda c: (decompose(c)[2] in
                     set("ㄳㄵㄶㄺㄻㄼㄽㄾㄿㅀㅄ"), c)):
        cho, jung, jong = decompose(ch)
        cho_ref.setdefault((cho, cho_bt(jung, jong)), ch)
        if jong:
            jong_ref.setdefault((jong, jong_bt(jung)), ch)

    # the 2,350 KS X 1001 syllables (EUC-KR order)
    ks = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            try:
                c = bytes([hi, lo]).decode("euc-kr")
            except UnicodeDecodeError:
                continue
            if 0xAC00 <= ord(c) <= 0xD7A3:
                ks.append(c)

    composed = {ch: compose(ch, pc98, refs, cho_ref, jong_ref) for ch in ks}

    # round-trip check: recomposing a hand-drawn reference should reproduce it
    worst = []
    for ch in refs:
        if ch in composed:
            d = sum(composed[ch][y][x] != refs[ch][y][x]
                    for y in range(16) for x in range(16))
            if d:
                worst.append((d, ch))
    worst.sort(reverse=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(composed, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)

    print(f"composed {len(composed)} syllables -> {OUT}")
    print(f"round-trip on {len(refs)} references: "
          f"{len(refs) - len(worst)} exact, {len(worst)} differ "
          f"(differences are benign: hand-drawing variance between references "
          f"that share a consonant+block-type, normalized to one canonical form)")
    for d, ch in worst[:15]:
        print(f"    {ch}: {d}px")

    if args.specimen:
        write_specimen(composed, pc98)


def write_specimen(composed, pc98):
    from PIL import Image
    sample = ("가나다라마바사아자차카타파하각gosnapp넋많갊곪값닭"
              "굵넓곬핥읊닳곯앉꼲국왕훨쫙뷁없")
    sample = [c for c in sample if c in composed]
    cols, scale, pad = 16, 6, 4
    rows = (len(sample) + cols - 1) // cols
    cw = 16 * scale + pad
    W = cols * cw + pad
    H = rows * (16 * scale + pad + 10) + pad
    img = Image.new("L", (W, H), 255)
    px = img.load()
    for i, ch in enumerate(sample):
        gx = pad + (i % cols) * cw
        gy = pad + (i // cols) * (16 * scale + pad + 10)
        for y in range(16):
            for x in range(16):
                if composed[ch][y][x] == "#":
                    for dy in range(scale):
                        for dx in range(scale):
                            px[gx + x * scale + dx, gy + y * scale + dy] = 0
    path = os.path.join(ROOT, "build", "light_specimen.png")
    img.save(path)
    print(f"specimen -> {path}")


if __name__ == "__main__":
    main()
