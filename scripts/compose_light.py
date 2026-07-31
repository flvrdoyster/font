"""Compose the full 2,350-syllable Light-weight Hangul from the hand-drawn
reference set.

Principle (see docs/ROADMAP.md): a Light glyph = the PC-98 둥근모꼴 base with
its consonants (초성/종성) replaced by our 도깨비DNR redraws; the vowel (중성)
stays PC-98. PC-98 places a given consonant at a pixel-stable position within
each block type, so a consonant we drew once transplants to every syllable of
that block type.

Hand-drawn glyphs are authoritative: a syllable present in glyphs_light.json is
used verbatim. Composition only fills the UNSAVED gaps, and never overwrites a
glyph the user has drawn.

To compose an unsaved target T = (초성 C1, 중성 V, 종성 C2): swap the canonical
초성 and 종성 into PC98[T], leaving the vowel as PC-98 drew it.
  종성 zone = pixels of PC98 that move when only 종성 varies (= the batchim area)
  초성 zone = pixels that move when only 초성 varies, plus our canonical 초성's
             own redraw, bounded to the variance bbox so a stray vowel tweak on
             the canonical glyph can't leak into a different target's vowel
Zones are 2-D (not a row cut), so a tall double 초성 (ㄲ/ㄸ/ㅃ...) descending
into the batchim rows stays whole -- its low pixels don't vary with 종성.

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

def load_pc98():
    """A ch -> 16-row grid function reading the PC-98 BIOS font, cached.
    Public: reused by scripts/build_ufo.py's Light build."""
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


def _jong_diff(grids):
    zone = set()
    if len(grids) >= 2:
        for y in range(16):
            for x in range(16):
                if len({g[y][x] for g in grids}) > 1:
                    zone.add((y, x))
    return zone


def _jong_grids(cho, jung, pc98):
    return [g for jong in JONG[1:]
            for g in [pc98(compose_ch(cho, jung, jong))] if g is not None]


def jong_zone(target, pc98):
    """Pixels that move when only the 종성 varies (초성·중성 fixed) = the
    batchim area. 종성 ranges over non-empty values only, so the block type
    stays *C and the 초성 position doesn't shift into the zone.

    ㅒ/ㅖ/ㅢ (and other rare 중성) have so few 받침 syllables in PC-98 -- often
    just 2 -- that a real batchim row can go undetected: if those 2 samples
    happen to draw identically at some row (common, since batchim shapes share
    a stem+bottom-bar template), the diff sees no variance there and misreads
    the row as vowel ink. 걘/걜 (ㄱ+ㅒ+ㄴ/ㄹ) is the case that surfaced this --
    both draw the same at rows 12-13, so those rows leaked into the vowel zone
    and every ㅒ/ㅖ/ㅢ 받침 cell came out rejected (LV_FLOOR sees vowel ink
    below row 9 that never existed).

    Below 4 own samples, pool in the same diff from other 중성 in the same
    vgroup (batchim position tracks V/H/X width class, not the exact vowel) to
    outvote the coincidence. Left alone above the threshold: pooling well-served
    중성 too costs real regressions (measured), since siblings' 초성 redraws
    aren't pixel-identical even within a vgroup."""
    cho, jung, _ = decompose(target)
    own = _jong_grids(cho, jung, pc98)
    if len(own) >= 4:
        return _jong_diff(own)
    vg = vgroup(jung)
    zone = _jong_diff(own)
    for jg in JUNG:
        if jg != jung and vgroup(jg) == vg:
            zone |= _jong_diff(_jong_grids(cho, jg, pc98))
    return zone


CLUSTER_JONG = set("ㄳㄵㄶㄺㄻㄼㄽㄾㄿㅀㅄ")
ALL_PX = frozenset((y, x) for y in range(16) for x in range(16))


def is_syllable(ch):
    return 0xAC00 <= ord(ch) <= 0xD7A3


def build_indices(refs):
    """Index a {char: rows} reference set by (초성, block type) and (종성, jong
    block type). Plain/single-jong references win over cluster ones for the
    same slot (sort key), so a cluster reference never displaces a more common
    plain one. Non-syllable keys (e.g. Latin glyphs also living in
    glyphs_light.json) are ignored -- they carry no 초성/중성/종성."""
    cho_ref, jong_ref = {}, {}
    syllables = [ch for ch in refs if is_syllable(ch)]
    for ch in sorted(syllables, key=lambda c: (decompose(c)[2] in CLUSTER_JONG, c)):
        cho, jung, jong = decompose(ch)
        cho_ref.setdefault((cho, cho_bt(jung, jong)), ch)
        if jong:
            jong_ref.setdefault((jong, jong_bt(jung)), ch)
    return cho_ref, jong_ref


def ks_x1001_order():
    """The 2,350 KS X 1001 완성형 syllables, in EUC-KR code order."""
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            try:
                ch = bytes([hi, lo]).decode("euc-kr")
            except UnicodeDecodeError:
                continue
            if 0xAC00 <= ord(ch) <= 0xD7A3:
                out.append(ch)
    return out


def can_compose(ch, cho_ref, jong_ref):
    """Whether the indices cover every part ch needs: a 초성 reference and, if
    ch has a batchim, a 종성 reference. The vowel always comes from PC-98."""
    cho, jung, jong = decompose(ch)
    if (cho, cho_bt(jung, jong)) not in cho_ref:
        return False
    return not jong or (jong, jong_bt(jung)) in jong_ref


def cho_zone(target, pc98, cho_ref, refs):
    """The 초성 region only. Start from where PC-98 varies as the 초성 changes
    (that IS the initial, by definition). Add our canonical 초성's own redraw
    (it can reach past PC-98's initial), but ONLY within the bounding box of
    that variance -- so a stray vowel tweak on the canonical glyph, which sits
    far from the initial, can't leak a dot into a different target's vowel."""
    cho, jung, jong = decompose(target)
    grids = [g for g in (pc98(compose_ch(c, jung, jong)) for c in CHO)
             if g is not None]
    seed = set()
    if len(grids) >= 2:
        for y in range(16):
            for x in range(16):
                if len({g[y][x] for g in grids}) > 1:
                    seed.add((y, x))
    zone = set(seed)
    cr = cho_ref.get((cho, cho_bt(jung, jong)))
    if cr:
        p, r = pc98(cr), refs[cr]
        jzr = jong_zone(cr, pc98) if decompose(cr)[2] else set()
        footprint = {(y, x) for (y, x) in ALL_PX
                     if (y, x) not in jzr and p[y][x] != r[y][x]}
        if seed:
            ys = [y for y, x in seed]
            xs = [x for y, x in seed]
            y0, y1, x0, x1 = min(ys) - 1, max(ys) + 1, min(xs) - 1, max(xs) + 1
            footprint = {(y, x) for (y, x) in footprint
                         if y0 <= y <= y1 and x0 <= x <= x1}
        zone |= footprint
    return zone


def compose(target, pc98, refs, cho_ref, jong_ref):
    """Rebuild target over the PC-98 둥근모꼴 base: swap in the canonical 초성
    (within cho_zone) and, if present, 종성 (within the batchim area). The vowel
    is left exactly as PC-98 drew it. Only pixels where a reference differs from
    PC-98 move, so untouched regions stay verbatim PC-98."""
    cho, jung, jong = decompose(target)
    out = [list(row) for row in pc98(target)]

    def apply(ref_ch, keep):
        if ref_ch is None:
            return
        r, p = refs[ref_ch], pc98(ref_ch)
        for (y, x) in keep:
            if r[y][x] != p[y][x]:
                out[y][x] = r[y][x]

    jz = jong_zone(target, pc98) if jong else set()
    cz = cho_zone(target, pc98, cho_ref, refs) - jz
    apply(cho_ref.get((cho, cho_bt(jung, jong))), cz)
    if jong:
        apply(jong_ref.get((jong, jong_bt(jung))), jz)

    return ["".join(row) for row in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--specimen", action="store_true")
    args = ap.parse_args()

    pc98 = load_pc98()
    refs = json.load(open(REFS, encoding="utf-8"))
    cho_ref, jong_ref = build_indices(refs)
    ks = ks_x1001_order()

    # hand-drawn glyphs are authoritative; compose only fills the unsaved gaps
    composed = {ch: (refs[ch] if ch in refs else
                     compose(ch, pc98, refs, cho_ref, jong_ref))
                for ch in ks if ch in refs or can_compose(ch, cho_ref, jong_ref)}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(composed, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)

    hand = sum(1 for ch in composed if ch in refs)
    gaps = len(composed) - hand
    missing = len(ks) - len(composed)
    print(f"{len(composed)}/{len(ks)} syllables -> {OUT}")
    print(f"  {hand} hand-drawn (verbatim) + {gaps} composed"
          + (f", {missing} uncomposable (missing 초성/종성 refs)" if missing else ""))

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
