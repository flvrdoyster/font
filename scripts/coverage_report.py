"""Report commonly-useful characters missing from the font.

Checks curated sets (punctuation, dashes, quotes, currency, math, arrows,
brackets, etc.) against the font's cmap and lists what's absent -- input for
the coverage-extension work (direction 2).
"""
import sys
from fontTools.ttLib import TTFont

# Bold member has the full 11,172-Hangul coverage; Regular (1px) covers the
# 2,350 KS X 1001 set. Default to Bold for the widest cmap check.
FONT = sys.argv[1] if len(sys.argv) > 1 else "build/DokkaebiDNRGothic-Bold.ttf"

SETS = {
    "문장부호/대시": "—–…·‥•※",
    "따옴표": "“”‘’„‚«»‹›",
    "통화기호": "€£¥¢₩₨₪₫฿₴₦",
    "수학/기호": "×÷±≠≤≥≈∞√∑∏∫°′″‰µΩ∆∇∂",
    "화살표": "←↑→↓↔↕⇐⇒⇔↖↗↘↙",
    "괄호/구분": "「」『』【】〈〉《》〔〕｛｝",
    "도형/불릿": "■□▲△▼▽●○◆◇★☆♠♥♦♣",
    "기타 유용": "™®©§¶†‡№℃℉✓✔",
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
