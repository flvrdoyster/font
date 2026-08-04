// Shared with web/index.html (the public specimen page) via a straight
// <script src="preview_presets.js"> -- served at /preview_presets.js by
// scripts/editor_server.py for the local editor, copied into _site/ by
// .github/workflows/webfont.yml for GitHub Pages. One file, one place to
// edit; neither page keeps its own copy of this text.
//
// Each entry mixes character classes on purpose so a single preset can't
// hide a spacing/kerning regression in the untested class: body mixes
// Hangul + Latin + digits + punctuation + quotes; en is Latin-only (all 26
// letters, three pangrams, so no letter's spacing goes unseen); game is the
// project's actual deployment shape (gensei-pc98 HUD text: Hangul, Latin,
// digits, brackets, punctuation together); symbols is punctuation/math/
// box-drawing/blocks; jamo is bare consonants+vowels, which body/game never
// exercise since real words always land on a composed syllable.
const PREVIEW_PRESETS = {
  body: "다람쥐 헌 쳇바퀴에 타고파. 조용한 새벽, 국물 맛이 퍽 깊다.\n" +
        "“어디까지 왔어?” (거의 다 왔지!) 3번 출구, 오전 10:45.\n" +
        "Retro pixel type: ABC abc 0123456789 #&@%",
  en: "The quick brown fox jumps over the lazy dog.\n" +
      "Pack my box with five dozen liquor jugs, Jack!\n" +
      "Waltz, nymph, for quick jigs vex Bud. 0123456789",
  game: "HP 128/128  MP 42/50  Lv.17\n" +
        "［가방］ ［장비］ ［마법］ ［설정］\n" +
        "골드 9,999원  경험치 730/1,000\n" +
        "→ 계속하시겠습니까? (Y/N)",
  symbols: "·… ,.!? ;: ‘’ “” 〈〉《》「」『』【】 ()[]{}\n" +
           "+−±×÷=≠≤≥ ←↑→↓ ₩￦$°℃\n" +
           "─│┌┐└┘├┤┬┴┼ ▀▄█░▒▓ ■□●○◆◇★☆",
  jamo: "ㅋㅋㅋ ㅎㅎ ㅠㅠ ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ ㄲㄸㅃㅆㅉ\n" +
        "ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣ ㅐㅒㅔㅖ ㅘㅙㅚㅝㅞㅟㅢ\n" +
        "ㅥㅦㅧㅨㅩㅪㅫㅬㅭㅮㅯㅰㅱㅲㅳㅴㅵㅶㅷㅸㅹㅺㅻㅼㅽㅾㅿㆀㆁㆂㆃㆄㆅㆆㆇㆈㆉㆊㆋㆌㆍㆎ",
};
