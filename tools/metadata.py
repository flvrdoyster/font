"""Font metadata for 도깨비DNR 고딕 / Dokkaebi DNR Gothic.

Applied to the UFO so ufo2ft/fontmake bake correct name/OS2/gasp/head tables.
Korean localized name records are added post-compile (see scripts/finalize.py),
since UFO localized names are awkward to carry through the pipeline.
"""

FAMILY = "Dokkaebi DNR Gothic"
FAMILY_KO = "도깨비DNR 고딕"
RFN = "Dokkaebi DNR"                     # OFL Reserved Font Name
RIBBI = {"Regular", "Bold", "Italic", "Bold Italic"}
VERSION = "1.0.1"
VENDOR_ID = "FDoy"                       # OS/2 achVendID (<=4 chars)
DESIGNER = "flvrdoyster"

COPYRIGHT = (
    'Copyright 2026 flvrdoyster. Portions derived from the "Dokkaebi Dinaru" '
    "bitmap font used in the Hangul Dokkaebi (DKBB) DOS Hangul software "
    "(source publicly released, 1989); original bitmap authorship and license "
    "undetermined."
)
DESCRIPTION = (
    "A proportional pixel typeface derived from the Dokkaebi Dinaru 16x16 "
    "bitmap font. Preserves the original pixel/staircase look at any size."
)
LICENSE = (
    "This Font Software is licensed under the SIL Open Font License, "
    "Version 1.1. This license is available with a FAQ at "
    "https://openfontlicense.org"
)
LICENSE_URL = "https://openfontlicense.org"

# gasp: suppress grid-fitting so the pixel grid is never distorted (our coords
# are already pixel-aligned). DOGRAY(1) + SYMMETRIC_SMOOTHING(3); no gridfit.
GASP_RECORDS = [{"rangeMaxPPEM": 65535, "rangeGaspBehavior": [1, 3]}]


def apply(ufo, ascender, descender, cap_height, x_height, style="Regular"):
    info = ufo.info
    if style in RIBBI:
        info.familyName = FAMILY
        info.styleName = style
        info.styleMapFamilyName = FAMILY
        info.styleMapStyleName = style.lower()
    else:
        # Non-RIBBI style (e.g. "Light"): fold into the legacy family name so
        # 4-style OS matching still works; nameID 16/17 (preferred family/
        # subfamily) carry the true "Dokkaebi DNR Gothic" / "Light" pair.
        info.familyName = f"{FAMILY} {style}"
        info.styleName = "Regular"
        info.styleMapFamilyName = f"{FAMILY} {style}"
        info.styleMapStyleName = "regular"
    # versionMajor/versionMinor -> head.fontRevision = major + minor/1000 (UFO
    # spec: versionMinor is thousandths, 0-999), so it must match nameID5
    # ("Version {VERSION}") numerically. "1" alone would mean .001, not .1 --
    # left-justify the minor digits into that 3-digit scale ("1" -> 100 -> .1).
    major_str, minor_str = VERSION.split(".")[:2]
    v_major = int(major_str)
    v_minor = int(minor_str.ljust(3, "0"))
    info.versionMajor = v_major
    info.versionMinor = v_minor

    info.copyright = COPYRIGHT
    info.openTypeNameDesigner = DESIGNER
    info.openTypeNameDescription = DESCRIPTION
    info.openTypeNameLicense = LICENSE
    info.openTypeNameLicenseURL = LICENSE_URL
    info.openTypeNameVersion = f"Version {VERSION}"
    # Reserved Font Name lives in the preferred family; keep unique-ID clean.
    info.openTypeNameUniqueID = f"{FAMILY} {style} {VERSION}; {VENDOR_ID}"
    info.openTypeNamePreferredFamilyName = FAMILY
    info.openTypeNamePreferredSubfamilyName = style

    # OS/2
    info.openTypeOS2VendorID = VENDOR_ID
    info.openTypeOS2Type = []              # fsType 0 = installable embedding
    # The two stroke weights ship as one RIBBI family: 1px stems -> "Regular"
    # (the default member), 2px stems -> "Bold". styleMapStyleName (set above)
    # already drives the fsSelection/head.macStyle bold bits via ufo2ft; this
    # just sets the matching usWeightClass. (Light=300 kept for the legacy
    # standalone-Light path, unused now.)
    info.openTypeOS2WeightClass = {"Bold": 700, "Light": 300}.get(style, 400)
    info.openTypeOS2WidthClass = 5

    # Vertical metrics (baseline at bottom of the 16px cell; no descenders by
    # design). Line gap is 0 ON PURPOSE: ascender-descender alone spans exactly
    # one 16px cell, so default line spacing is exactly 1em -- consecutive
    # lines sit on the same 16px grid the PC-98 terminal used (Hangul keeps
    # 1px of air top and bottom inside the cell, so ink never touches). A
    # nonzero hhea/typo gap used to make line height 18px on gap-honoring
    # platforms while usWin metrics stayed 16px -- the same text measured
    # differently per platform (fontbakery WARN hhea). Every metrics pair now
    # agrees: asc 1024 / desc 0 / gap 0.
    info.ascender = ascender
    info.descender = descender
    info.capHeight = cap_height
    info.xHeight = x_height
    info.openTypeHheaAscender = ascender
    info.openTypeHheaDescender = descender
    info.openTypeHheaLineGap = 0
    info.openTypeOS2TypoAscender = ascender
    info.openTypeOS2TypoDescender = descender
    info.openTypeOS2TypoLineGap = 0
    info.openTypeOS2WinAscent = ascender
    info.openTypeOS2WinDescent = abs(descender)

    # Pixel-crispness: no grid-fit distortion; declare the native size.
    info.openTypeGaspRangeRecords = GASP_RECORDS
    info.openTypeHeadLowestRecPPEM = 16
