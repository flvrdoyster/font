"""Font metadata for 도깨비DNR 고딕 / Dokkaebi DNR Gothic.

Applied to the UFO so ufo2ft/fontmake bake correct name/OS2/gasp/head tables.
Korean localized name records are added post-compile (see scripts/finalize.py),
since UFO localized names are awkward to carry through the pipeline.
"""

FAMILY = "Dokkaebi DNR Gothic"
FAMILY_KO = "도깨비DNR 고딕"
STYLE = "Regular"
RFN = "Dokkaebi DNR"                     # OFL Reserved Font Name
VERSION = "0.1.0"
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


def apply(ufo, ascender, descender, cap_height, x_height):
    info = ufo.info
    info.familyName = FAMILY
    info.styleName = STYLE
    info.styleMapFamilyName = FAMILY
    info.styleMapStyleName = "regular"
    v_major, v_minor = (int(x) for x in VERSION.split(".")[:2])
    info.versionMajor = v_major
    info.versionMinor = v_minor

    info.copyright = COPYRIGHT
    info.openTypeNameDesigner = DESIGNER
    info.openTypeNameDescription = DESCRIPTION
    info.openTypeNameLicense = LICENSE
    info.openTypeNameLicenseURL = LICENSE_URL
    info.openTypeNameVersion = f"Version {VERSION}"
    # Reserved Font Name lives in the preferred family; keep unique-ID clean.
    info.openTypeNameUniqueID = f"{FAMILY} {VERSION}; {VENDOR_ID}"
    info.openTypeNamePreferredFamilyName = FAMILY
    info.openTypeNamePreferredSubfamilyName = STYLE

    # OS/2
    info.openTypeOS2VendorID = VENDOR_ID
    info.openTypeOS2Type = []              # fsType 0 = installable embedding
    info.openTypeOS2WeightClass = 400
    info.openTypeOS2WidthClass = 5

    # Vertical metrics (baseline at bottom of the 16px cell; no descenders by
    # design). Small line gap for legible line spacing.
    line_gap = 2 * 64
    info.ascender = ascender
    info.descender = descender
    info.capHeight = cap_height
    info.xHeight = x_height
    info.openTypeHheaAscender = ascender
    info.openTypeHheaDescender = descender
    info.openTypeHheaLineGap = line_gap
    info.openTypeOS2TypoAscender = ascender
    info.openTypeOS2TypoDescender = descender
    info.openTypeOS2TypoLineGap = line_gap
    info.openTypeOS2WinAscent = ascender
    info.openTypeOS2WinDescent = abs(descender)

    # Pixel-crispness: no grid-fit distortion; declare the native size.
    info.openTypeGaspRangeRecords = GASP_RECORDS
    info.openTypeHeadLowestRecPPEM = 16
