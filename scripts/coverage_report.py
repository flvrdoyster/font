"""Report symbols missing from the font, by coverage tier.

The tiers below are the general font-production baselines, not a wishlist:

  Tier 1 -- what any professional text font is expected to carry. Follows
            WGL4 (the classic 652-glyph Windows compatibility set) and the
            Adobe Latin 1-3 / Google Fonts Latin Core repertoires, which
            agree on this core: Latin-1 symbols, the dash/quote/reference
            marks of General Punctuation, common currency, and core math.
  Tier 2 -- conventions of Korean/CJK fonts specifically (CJK punctuation
            and bracket forms, fullwidth variants, degree/unit marks).
  Tier 3 -- box drawing and block elements. Optional for a text face, but
            effectively required here: this font ships as the PC-98 BIOS
            font, where those glyphs draw the actual terminal UI.

Deliberately NOT included: playing-card suits, check marks, and assorted
national currency signs (₨ ₪ ₫ ฿ ₴ ₦). No standard requires them and there
is no reason to draw a Thai baht sign for a Korean pixel font.

Watch the near-duplicates -- these are separate characters and the legacy
Korean encodings picked the ones on the right:
  −  U+2212 MINUS   vs  -  U+002D HYPHEN-MINUS
  —  U+2014 EM DASH vs  ―  U+2015 HORIZONTAL BAR  (KS X 1001 has ―)
  ₩  U+20A9 WON     vs  ￦  U+FFE6 FULLWIDTH WON   (KS X 1001 has ￦)
"""
import sys
from fontTools.ttLib import TTFont

# Bold member has the full 11,172-Hangul coverage; Regular (1px) covers the
# 2,350 KS X 1001 set. Default to Bold for the widest cmap check.
FONT = sys.argv[1] if len(sys.argv) > 1 else "build/DokkaebiDNRGothic-Bold.ttf"

SETS = {
    "T1 Latin-1 기호": "¡¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿×÷",
    "T1 문장부호/대시": "–—―…·‥•※†‡‰′″⁄",
    "T1 따옴표": "“”‘’„‚«»‹›",
    "T1 통화기호": "€₩￦£¥¢¤",
    "T1 수학": "−±×÷≠≤≥≈∞√∑∏∫∂∇∆◊°µΩ",
    "T1 Letterlike": "™№℮",
    "T2 CJK 문장부호": "、。〃〈〉《》「」『』【】〔〕",
    "T2 괄호/구분": "｛｝℃℉",
    "T2 화살표": "←↑→↓↔↕⇐⇒⇔↖↗↘↙",
    "T2 도형/불릿": "■□▲△▼▽●○◆◇★☆",
    "T3 괘선": "─│┌┐└┘├┤┬┴┼━┃┏┓┗┛┣┫┳┻╋",
    "T3 블록": "░▒▓█▀▄▌▐",
}


def main():
    font = TTFont(FONT)
    cmap = font.getBestCmap()
    print(f"font: {FONT}  (cmap {len(cmap)} chars)\n")
    total_missing = 0
    for label, chars in SETS.items():
        missing = [c for c in dict.fromkeys(chars) if ord(c) not in cmap]
        have = len(chars) - len(missing)
        if missing:
            total_missing += len(missing)
            shown = " ".join(f"{c}(U+{ord(c):04X})" for c in missing)
            print(f"[{label}] 있음 {have}/{len(set(chars))} · 빠짐: {shown}")
        else:
            print(f"[{label}] 모두 있음 ({len(set(chars))})")
    print(f"\n총 빠진 문자: {total_missing}")


if __name__ == "__main__":
    main()
