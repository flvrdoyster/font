"""Post-compile finalize: Korean localized names + smart dropout control.

fontmake bakes the Latin name/OS2/gasp tables from the UFO. This adds the
Korean (ko-KR) localized family/subfamily names so the font shows as
'도깨비DNR 고딕' in Korean environments, and (TTF only) a minimal `prep`
program enabling smart dropout control.

Usage: python scripts/finalize.py build/DokkaebiDNRGothic-Regular.ttf ...
"""
import sys
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram

sys.path.insert(0, "tools")
import metadata as md

WIN, KO = 3, 0x0412   # Windows platform, Korean (Korea) language

# Smart dropout control: at small sizes a 1px stroke can rasterize to nothing
# ("dropout") when its outline straddles pixel centers -- lethal for a pixel
# font whose Regular is 1px strokes throughout. This unhinted-font-standard
# prep snippet (same one gftools-fix-nonhinting injects; fontbakery
# smart_dropout checks for it) turns on smart dropout for all sizes below
# 511ppem. TrueType only -- CFF/OTF has no prep table and its rasterizers
# handle dropout themselves.
_PREP_ASM = ["PUSHW[ ]", "511", "SCANCTRL[ ]", "PUSHB[ ]", "4", "SCANTYPE[ ]"]


def _ensure_smart_dropout(font):
    if "glyf" not in font:
        return False
    prep = font.get("prep")
    if prep is None:
        prep = newTable("prep")
        prep.program = ttProgram.Program()
        font["prep"] = prep
    asm = prep.program.getAssembly()
    if "SCANCTRL[ ]" in asm:      # already enabled (idempotent re-finalize)
        return False
    prep.program.fromAssembly(asm + _PREP_ASM)
    return True


def finalize(path):
    font = TTFont(path)
    name = font["name"]
    # Style/weight name (e.g. "Regular", "Light") isn't localized -- keep
    # whatever fontmake already baked from the UFO's style name.
    style = (name.getDebugName(17) or name.getDebugName(2) or "Regular")
    # nameID -> Korean string
    ko = {
        1: md.FAMILY_KO,
        2: style,
        16: md.FAMILY_KO,
        17: style,
    }
    for nid, val in ko.items():
        name.setName(val, nid, WIN, 1, KO)   # platEncID 1 (Unicode BMP)
    dropout = _ensure_smart_dropout(font)
    font.save(path)
    print(f"finalized {path}: +Korean names ({md.FAMILY_KO})"
          + (" +smart dropout prep" if dropout else ""))


def main():
    if len(sys.argv) < 2:
        print("usage: finalize.py <font.ttf> [<font.otf> ...]")
        sys.exit(1)
    for p in sys.argv[1:]:
        finalize(p)


if __name__ == "__main__":
    main()
