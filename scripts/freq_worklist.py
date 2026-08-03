"""Rank unconfirmed (composed-output) syllables by real-world frequency.

The component model ships 7,016 composed syllables, but they are rare by
construction (everything common is inside the confirmed 4,156). This script
measures exactly how rare, against a real spoken-register corpus, and turns
the answer into a hand-confirmation worklist: which composed syllables do
people actually type, in what order.

Measured 2026-08-03 against OpenSubtitles 2018 (688k word types, 17.5M
syllable tokens): the confirmed set already covers 99.983% of usage; only
250 unconfirmed syllables occur at all, and confirming the top 50 removes
90.8% of the remaining composed-glyph exposure. The list is dominated by
informal spellings and typos (됬 쫒 잌 봣 썻...) -- exactly the register a
pixel font meets in games and chat.

Corpus file: one "word count" pair per line, e.g. from
  https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/ko/ko_full.txt
(not vendored -- ~10MB and easily refetched; any corpus in the same format
works, and a informal/spoken one fits this font's use better than news text).

Usage: python scripts/freq_worklist.py path/to/ko_full.txt [-n TOP]
Writes build/freq_worklist.txt (all unconfirmed syllables, tab-separated
"syllable<TAB>count", descending) and prints a summary.
"""
import argparse
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "tools", "glyphs_light.json")
OUT = os.path.join(ROOT, "build", "freq_worklist.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus", help='frequency list, "word count" per line')
    ap.add_argument("-n", type=int, default=50, help="how many to print")
    args = ap.parse_args()

    confirmed = {ch for ch in json.load(open(CORPUS, encoding="utf-8"))
                 if len(ch) == 1 and 0xAC00 <= ord(ch) <= 0xD7A3}

    syll = Counter()
    with open(args.corpus, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) != 2 or not parts[1].isdigit():
                continue
            word, n = parts[0], int(parts[1])
            for ch in word:
                if 0xAC00 <= ord(ch) <= 0xD7A3:
                    syll[ch] += n

    total = sum(syll.values())
    covered = sum(n for ch, n in syll.items() if ch in confirmed)
    uncon = sorted(((ch, n) for ch, n in syll.items() if ch not in confirmed),
                   key=lambda t: -t[1])
    residual = sum(n for _, n in uncon)

    print(f"syllable tokens {total:,} / unique {len(syll):,}")
    print(f"confirmed set covers {covered/total*100:.4f}%")
    print(f"unconfirmed-but-used: {len(uncon)} syllables, {residual:,} tokens")
    run = 0
    for i, (ch, n) in enumerate(uncon[:args.n], 1):
        run += n
        print(f"{i:>4}  {ch}  {n:>8,}   (cum {run/residual*100:5.1f}% of residual)")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(f"{ch}\t{n}" for ch, n in uncon) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
