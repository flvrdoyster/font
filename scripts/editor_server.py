"""Local server for the pixel editor.

    python scripts/editor_server.py [--port 8000] [--no-open]

Serves tools/pixel_editor.html at http://localhost:PORT/ and exposes a small
API so the editor can load and SAVE glyphs, per weight (Regular / Light):

  GET  /editor.css        -> tools/editor.css, the shared visual foundation
                             (colour tokens, page shell, card/button/status
                             pill/toast) both this page and /halfwidth link
                             to. Page-specific CSS stays inline in each file.
  GET  /api/glyphs?weight=regular|light
                          -> current glyphs_<weight>.json { "A": [rows], ... }
  POST /api/glyphs?weight=regular|light
                          -> merge { "A": [rows], ... } into that file
  GET  /api/text?weight=..&s=...
                          -> per-char grids, custom (that weight) overrides
                             original (preview). For weight=light Hangul with
                             no custom entry, falls back to the composed
                             PC-98-base + our-consonants default (see
                             scripts/compose_light.py) instead of the raw
                             original, before finally falling back to that.
  GET  /api/ks2350        -> the 2,350 KS X 1001 완성형 syllables (char list),
                             for the editor's full-coverage Light palette.
  GET  /api/kana          -> hiragana + katakana + halfwidth katakana (char
                             list), for the editor's kana palette (Phase 3).
  GET  /api/symref?s=..   -> reference grids for symbols/punctuation, from GNU
                             Unifont (refs/unifont.otf, gitignored) -- native
                             16x16 pixel design, full BMP coverage. Overlay
                             only; never embedded in built output.
  GET  /api/cells         -> jamo-component cells for the 11,172 expansion
                             (scripts/compose_components.py): status, sample
                             counts, affected-syllable counts, and a suggested
                             representative syllable to draw. Backs the 부품 셀
                             palette tab (/components redirects to it).
  POST /api/cell_preview  -> {ch, rows} -> composes the syllables built
                             from the cell(s) `ch` belongs to, against the
                             in-progress drawing. Confirmed syllables show
                             their own saved pixels, not a recomposition.
  POST /api/build?weight=regular|light
                          -> rebuild that weight's TTF (build_ufo -> fontmake
                             -> finalize). regular = full original-bitmap
                             font; light = thinned Latin/numbers + composed
                             KS X 1001 Hangul (scripts/compose_light.py).
  POST /api/build_bmp     -> regenerate build/font_light.bmp (compose_light.py
                             -> build_pc98_bmp.py) from current saved state --
                             completed-form Light Hangul + glyphs_halfwidth.json.
                             Unrelated to the TTF build above.

Also serves tools/halfwidth_editor.html at /halfwidth -- a separate tool for
hand-drawing 반각(halfwidth) Hangul, unrelated to the font build pipeline
(nothing here feeds build_ufo.py):

  GET  /api/halfwidth_ref  -> reference grids for all 188 slots (2 cols x 94)
                              of the PC-98 BIOS's 반각 한글 table (font.bmp
                              cols 10-11, see scripts/pc98_halfwidth_map.py)
                              -- 122 have ink, 66 are blank in the ROM. Slots
                              are keyed "{col}-{ten}" (e.g. "10-5"), not
                              character: this table isn't in KS X 1001 or
                              Unicode order.
  GET  /api/halfwidth_glyphs
                          -> tools/glyphs_halfwidth.json, the user's own
                             hand-drawn slots { "10-5": [rows], ... }
  POST /api/halfwidth_glyphs
                          -> merge { "10-5": [rows], ... } into that file
  GET  /api/halfwidth_charmap
                          -> tools/halfwidth_char_map.json, the user's own
                             slot->character notes { "10-5": "가", ... } (typed
                             in by hand -- this table has no recorded Unicode
                             identity otherwise, see pc98_halfwidth_map.py)
  POST /api/halfwidth_charmap
                          -> merge { "10-5": "가", ... } into that file; a
                             blank value clears the slot's assignment
  GET  /api/halfwidth_light_ref?s=..
                          -> per-char grids: that character's Light 완성형
                             glyph (build/light_hangul.json) squeezed
                             left-right by half (OR-fold column pairs,
                             16px->8px) -- a rough shape guide, second overlay
                             (red) for whichever character the editor's
                             halfwidth_char_map.json says the current slot is

Stdlib only. Run from the repo root.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITOR = os.path.join(ROOT, "tools", "pixel_editor.html")
HALFWIDTH_EDITOR = os.path.join(ROOT, "tools", "halfwidth_editor.html")
GLYPHS_FILES = {
    "regular": os.path.join(ROOT, "tools", "glyphs_bold.json"),  # 2px stems
    "light": os.path.join(ROOT, "tools", "glyphs_light.json"),   # 1px stems
}

EDITOR_CSS = os.path.join(ROOT, "tools", "editor.css")
_CSS_LINK = "<link rel=\"stylesheet\" href=\"editor.css\">"

PAGE_HEAD = (
    "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>도깨비DNR 픽셀 에디터</title>" + _CSS_LINK + "</head><body>"
)
PAGE_TAIL = "</body></html>"

HALFWIDTH_PAGE_HEAD = (
    "<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
    "<title>반각 한글 에디터</title>" + _CSS_LINK + "</head><body>"
)


def _weight_file(weight):
    path = GLYPHS_FILES.get(weight)
    if not path:
        raise ValueError(f"unknown weight: {weight!r}")
    return path


def read_glyphs(weight):
    with open(_weight_file(weight), encoding="utf-8") as f:
        return json.load(f)


def write_glyphs(weight, data):
    # keep sorted + stable formatting so git diffs stay clean
    ordered = {k: data[k] for k in sorted(data)}
    with open(_weight_file(weight), "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)
        f.write("\n")


_ORIG = None  # lazy (strike, cmap) from the original bitmap font


def _orig():
    global _ORIG
    if _ORIG is None:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import pixelfont as pf
        from fontTools.ttLib import TTFont
        font = TTFont(os.path.join(ROOT, "original", "HANKBC.ttf"))
        _ORIG = (pf.read_strike(font), font.getBestCmap())
    return _ORIG


def _original_grid(ch, strike, cmap):
    gname = cmap.get(ord(ch))
    if gname and gname in strike:
        w, rows = strike[gname]
        if w:
            return ["".join("#" if r & (1 << (w - 1 - x)) else "."
                            for x in range(w)) for r in rows]
    return None


_COMPOSER = False  # False = not yet loaded; None = load failed; else the module


def _composer():
    """scripts/compose_light.py, importable from here for the Light Hangul
    default preview (see text_grids). None if it can't be loaded (e.g. PIL or
    the PC-98 bitmap missing) -- callers fall back to the plain original."""
    global _COMPOSER
    if _COMPOSER is False:
        try:
            sys.path.insert(0, os.path.join(ROOT, "scripts"))
            import compose_light
            _COMPOSER = compose_light
        except Exception:
            _COMPOSER = None
    return _COMPOSER


_THINNER = False  # False = not yet loaded; None = load failed; else the module


def _thinner():
    """tools/thin_vertical.py, for the Light Latin/digit preview fallback
    (thin the Regular custom glyph) -- see text_grids."""
    global _THINNER
    if _THINNER is False:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import thin_vertical
            _THINNER = thin_vertical
        except Exception:
            _THINNER = None
    return _THINNER


def text_grids(weight, s):
    """Per-char pixel grids for preview: custom glyphs (for this weight)
    override the original. With no custom entry yet, Light falls back to a
    weight-appropriate default instead of the raw 2px original:
      - Hangul: the composed PC-98-base + our-consonants default (see
        scripts/compose_light.py)
      - Latin/digits: the Regular custom glyph thinned to 1px (see
        tools/thin_vertical.py) -- this is what build_light actually uses,
        so the editor should preview the same thing."""
    custom = read_glyphs(weight)
    try:
        strike, cmap = _orig()
    except Exception:
        strike, cmap = {}, {}
    cl = None
    cho_ref = jong_ref = None
    regular = tv = None
    if weight == "light":
        cl = _composer()
        if cl is not None:
            cho_ref, jong_ref = cl.build_indices(custom)
        tv = _thinner()
        if tv is not None:
            regular = read_glyphs("regular")
    out = []
    for ch in s:
        grid = custom.get(ch)
        if grid is None and weight == "light" and 0xAC00 <= ord(ch) <= 0xD7A3:
            if cl is not None:
                try:
                    if cl.can_compose(ch, cho_ref, jong_ref):
                        grid = cl.compose(ch, _pc98_grid, custom, cho_ref, jong_ref)
                except Exception:
                    grid = None
        elif grid is None and tv is not None and regular is not None and ch in regular:
            try:
                grid = tv.thin_vertical(regular[ch])
            except Exception:
                grid = None
        if grid is None and _is_kana(ch):
            # PC-98's 둥근모꼴 replaces the original bitmap's kana entirely
            # (both weights) -- font.bmp's kana was never touched by the
            # Korean localization, unlike its Hangul/kanji regions.
            grid = _pc98_kana_grid(ch)
        if grid is None:
            grid = _original_grid(ch, strike, cmap)
            # The original strike is the 2px source. Handing it back unchanged
            # for weight=light means a Light request answers with a Bold glyph
            # -- which is what every syllable outside KS X 1001 hit, exactly
            # the ones the component editor works on. Thin it so a Light
            # request is always a 1px shape.
            if grid is not None and weight == "light" and tv is not None:
                try:
                    grid = tv.thin_vertical(grid)
                except Exception:
                    pass
        out.append({"ch": ch, "rows": grid})
    return out



_PC98 = None  # lazy (PIL pixel access, {syllable: [col, row]})
PC98_BMP = os.path.join(ROOT, "..", "gensei-pc98", "docs", "bios", "font.bmp")
PC98_MAP = os.path.join(ROOT, "tools", "pc98_hangul_map.json")


def _pc98():
    """PC-98 BIOS 둥근모꼴 Hangul: the recorded Unicode->cell map
    (tools/pc98_hangul_map.json, see scripts/pc98_hangul_map.py) plus the
    bitmap it indexes into. Cell [col, row] -> pixel origin col*16, row*16."""
    global _PC98
    if _PC98 is None:
        from PIL import Image
        img = Image.open(PC98_BMP).convert("L")
        with open(PC98_MAP, encoding="utf-8") as f:
            cells = json.load(f)["cells"]
        _PC98 = (img.load(), cells)
    return _PC98




_PC98_KANA = None  # lazy (PIL pixel access, {kana: [col, row]})
PC98_KANA_MAP = os.path.join(ROOT, "tools", "pc98_kana_map.json")


def _pc98_kana():
    """PC-98 BIOS 둥근모꼴 hiragana/katakana: tools/pc98_kana_map.json (see
    scripts/pc98_kana_map.py) plus the same font.bmp Hangul indexes into.
    No halfwidth katakana -- not present anywhere in this ROM."""
    global _PC98_KANA
    if _PC98_KANA is None:
        px, _ = _pc98()  # reuse the same bitmap; raises if unavailable
        with open(PC98_KANA_MAP, encoding="utf-8") as f:
            cells = json.load(f)["cells"]
        _PC98_KANA = (px, cells)
    return _PC98_KANA


def _pc98_kana_grid(ch):
    try:
        px, cells = _pc98_kana()
    except Exception:
        return None
    cell = cells.get(ch)
    if not cell:
        return None
    col, row = cell
    x0, y0 = col * 16, row * 16
    return ["".join("#" if px[x0 + x, y0 + y] < 128 else "." for x in range(16))
            for y in range(16)]



_PC98_HALFWIDTH = None  # lazy (PIL pixel access, {"1".."94": [col, row]})
PC98_HALFWIDTH_MAP = os.path.join(ROOT, "tools", "pc98_halfwidth_map.json")
HALFWIDTH_FILE = os.path.join(ROOT, "tools", "glyphs_halfwidth.json")


def _pc98_halfwidth():
    """PC-98 BIOS 반각 한글 table: tools/pc98_halfwidth_map.json (see
    scripts/pc98_halfwidth_map.py), col 10 of the same font.bmp. Slots are
    keyed by ten-index ("1".."94"), not character -- this table isn't in
    KS X 1001 or Unicode-halfwidth-Hangul order, it's a ROM-specific set."""
    global _PC98_HALFWIDTH
    if _PC98_HALFWIDTH is None:
        px, _ = _pc98()  # reuse the same bitmap; raises if unavailable
        with open(PC98_HALFWIDTH_MAP, encoding="utf-8") as f:
            cells = json.load(f)["cells"]
        _PC98_HALFWIDTH = (px, cells)
    return _PC98_HALFWIDTH


def _pc98_halfwidth_grid(slot):
    try:
        px, cells = _pc98_halfwidth()
    except Exception:
        return None
    cell = cells.get(slot)
    if not cell:
        return None
    col, row = cell
    x0, y0 = col * 16, row * 16
    return ["".join("#" if px[x0 + x, y0 + y] < 128 else "." for x in range(16))
            for y in range(16)]


def _halfwidth_sort_key(slot):
    """slot is "{col}-{ten}", e.g. "10-5" -- sort by (col, ten) numerically,
    not lexicographically (else "10-10" < "10-2")."""
    col, ten = slot.split("-")
    return (int(col), int(ten))


def halfwidth_ref_slots():
    """All 반각 한글 reference slots (cols 10-11, 94 each), in (col, ten)
    order. Blank-in-ROM slots still get an entry (all-blank rows) -- the
    editor shows them the same as drawn ones, just with nothing to trace yet."""
    try:
        _, cells = _pc98_halfwidth()
    except Exception:
        return []
    return [{"slot": s, "rows": _pc98_halfwidth_grid(s)}
            for s in sorted(cells, key=_halfwidth_sort_key)]


def read_halfwidth():
    with open(HALFWIDTH_FILE, encoding="utf-8") as f:
        return json.load(f)


def write_halfwidth(data):
    ordered = {k: data[k] for k in sorted(data, key=_halfwidth_sort_key)}
    with open(HALFWIDTH_FILE, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)
        f.write("\n")


HALFWIDTH_CHARMAP_FILE = os.path.join(ROOT, "tools", "halfwidth_char_map.json")


def read_halfwidth_charmap():
    with open(HALFWIDTH_CHARMAP_FILE, encoding="utf-8") as f:
        return json.load(f)


def write_halfwidth_charmap(data):
    # empty string clears an assignment rather than storing a blank
    cleaned = {k: v for k, v in data.items() if v}
    ordered = {k: cleaned[k] for k in sorted(cleaned, key=_halfwidth_sort_key)}
    with open(HALFWIDTH_CHARMAP_FILE, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=1)
        f.write("\n")


_LIGHT_HANGUL = None  # lazy build/light_hangul.json (see scripts/compose_light.py)
LIGHT_HANGUL_FILE = os.path.join(ROOT, "build", "light_hangul.json")


def _light_hangul():
    global _LIGHT_HANGUL
    if _LIGHT_HANGUL is None:
        with open(LIGHT_HANGUL_FILE, encoding="utf-8") as f:
            _LIGHT_HANGUL = json.load(f)
    return _LIGHT_HANGUL


def _halved_light_grid(ch):
    """This character's Light 완성형 glyph (16px wide), squeezed left-right by
    half (OR-fold each adjacent column pair -> 8px) -- a rough shape guide
    for hand-drawing its 반각 counterpart. Not a claim that this IS the
    correct halfwidth shape (halfwidth glyphs are independently designed, not
    a mechanical rescale) -- just a starting reference, per user request."""
    try:
        rows = _light_hangul().get(ch)
    except Exception:
        return None
    if not rows:
        return None
    return ["".join("#" if (r[2 * c] == "#" or r[2 * c + 1] == "#") else "."
                     for c in range(8)) for r in rows]


def halfwidth_light_grids(s):
    return [{"ch": ch, "rows": _halved_light_grid(ch)} for ch in s]


def ks2350_chars():
    """The 2,350 KS X 1001 완성형 syllables, in EUC-KR order (same order as
    tools/pc98_hangul_map.json's cells) -- the full-coverage Light palette."""
    try:
        return list(_pc98()[1].keys())
    except Exception:
        return []


# ---- component cells (11,172 expansion, see docs/ROADMAP.md) ---------------
_CCOMP = False   # False = not loaded; None = load failed; else the module

# Simple, evenly-built jamo make the cleanest sample for the slot that is free
# to vary, so the extracted component isn't fighting an unusual partner. Order
# is a preference list, first available wins.
_SIMPLE_JONG = list("ㅁㅇㄴㄹㅂㄱ")
_SIMPLE_CHO = list("ㅁㅇㄴㄹㅂㄱ")


def _ccomp():
    global _CCOMP
    if _CCOMP is False:
        try:
            sys.path.insert(0, os.path.join(ROOT, "scripts"))
            import compose_components
            _CCOMP = compose_components
        except Exception:
            _CCOMP = None
    return _CCOMP


def _cell_id(cell):
    """('T','ㄽ',('ㅏ',)) <-> 'T:ㄽ:ㅏ' -- JSON/URL friendly."""
    kind, jamo, beol = cell
    return f"{kind}:{jamo}:{''.join(str(b) for b in beol)}"


def _beol_label(cell):
    """The 벌 as something readable. The raw tuple is a bare bool for two of
    the three cases -- and means a different thing in each -- so showing it
    verbatim put "True"/"False" in the editor with no way to tell which axis
    it referred to. See compose_components.lv_beol / t_beol."""
    kind, jamo, beol = cell
    if kind == "LV":
        return "받침" if beol[0] else "민글자"
    if isinstance(beol[0], bool):          # 겹받침: keyed on 초중성 width
        return "넓은 초중성" if beol[0] else "좁은 초중성"
    return beol[0]                          # 홑받침: the 중성 itself


def component_cells():
    """Every cell the 11,172 needs, with its status and a suggested syllable
    to draw. Status: filled (has corpus samples) / empty (draw this one)."""
    cc = _ccomp()
    if cc is None:
        return []
    cl = _composer()
    corpus = cc.load_corpus()
    pc98 = _pc98_grid_or_none()
    seen = cc.observe(corpus, pc98, *_cho_ref(corpus))
    req = cc.required_cells()

    # candidate syllables per cell, preferring a simple free jamo
    cand = {}
    for ch in cc.FULL:
        for cell in cc.cells_for(ch):
            cand.setdefault(cell, []).append(ch)

    def pick(cell, chars):
        kind = cell[0]
        simple = _SIMPLE_JONG if kind == "LV" else _SIMPLE_CHO
        # Never suggest a syllable that's already confirmed. A cell can be
        # empty even though every candidate using it is drawn: extraction
        # rejected the split (PC-98 doesn't cover it and the subtraction
        # guard didn't trust the result), not because nobody drew anything --
        # see 뤔/LV:ㄹㅝ. Redrawing it is a no-op; only the guard can fix that,
        # so there is nothing left to suggest.
        undrawn = [ch for ch in chars if ch not in corpus]
        def is_resolvable(ch):
            other = [c for c in cc.cells_for(ch) if c != cell]
            return bool(other) and other[0] in seen
        def rank(ch):
            cho, jung, jong = cl.decompose(ch)
            free = jong if kind == "LV" else cho
            try:
                fj_rank = simple.index(free)
            except ValueError:
                fj_rank = len(simple)
            # Extraction for a syllable outside PC-98 works by subtraction --
            # one of its two cells must already be known so the ink can be
            # split. A "simplest free jamo" pick with BOTH its cells empty
            # can't resolve either one: drawing it changes nothing (this is
            # what happened with 먝/몍 -- both landed on an unresolvable pair).
            # Rank resolvable candidates first; simplicity only breaks ties.
            return (0 if is_resolvable(ch) else 1, fj_rank)
        if not undrawn:
            return None, False
        best = sorted(undrawn, key=rank)[0]
        return best, is_resolvable(best)

    out = []
    for cell in sorted(req, key=lambda c: (c[0], c[1], str(c[2]))):
        chars = cand.get(cell, [])
        cands = seen.get(cell)
        n = sum(cands.values()) if cands else 0
        # Only an EMPTY cell has anything to suggest. Once a cell has samples
        # its shape comes from the syllables that already fed it, and drawing
        # some other syllable can't change it: extraction outside PC-98 works
        # by subtraction, so with the T cell already known the whole glyph
        # is charged to the LV cell instead (drawing 맋 to fix T:ㄳ put all
        # 43px into LV:ㅁㅏ and left ㄳ untouched). Fixing a filled cell means
        # editing one of its own `examples` -- the preview palette.
        suggest, resolvable = (pick(cell, chars) if chars and n == 0
                               else (None, False))
        out.append({
            "id": _cell_id(cell),
            "kind": cell[0],
            "jamo": cell[1],
            "beol": _beol_label(cell),
            # How many corpus syllables fed this cell. NOT a confidence score:
            # how much those samples disagree measures the 받침 zone cut and
            # the user's own optical corrections, not glyph quality, so the
            # variant count it used to expose has been dropped.
            "samples": n,
            "affects": len(chars),
            "suggest": suggest,
            # False means no candidate's OTHER cell is known yet -- drawing
            # `suggest` alone won't resolve this one; something else needs
            # filling first (see pick()'s docstring-comment above).
            "resolvable": resolvable,
            # True when the cell is empty AND every syllable that could fill
            # it is already confirmed -- drawing cannot fix this one, only a
            # change to the extraction guard can (see pick()'s 뤔 comment).
            "stuck": n == 0 and bool(chars) and suggest is None,
            # Confirmed syllables using this cell -- the palette anchor and the
            # only way to change an already-filled cell. PC-98-covered ones
            # first: those are cut by the 받침 zone and so feed this cell
            # directly, while the rest are split by subtraction and charge
            # their ink to the OTHER cell, leaving this one untouched. Editing
            # one of those would look like work and do nothing (the 맋 trap).
            "examples": sorted((ch for ch in chars if ch in corpus),
                               key=lambda ch: pc98(ch) is None)[:12],
        })
    return out


def cell_preview(ch, rows, cell_id=None, limit=400):
    """The syllables the drawn representative actually affects.

    Drawing one syllable defines a component that dozens to a few hundred
    others are built from, so the useful preview is not the syllable itself
    but what it does to them: a component that looks fine alone can still
    collide or leave holes once another jamo sits next to it. The editor also
    uses this as a palette -- click a wrong-looking one to load and fix it --
    so the limit covers the largest cell (399) rather than a first page.

    cell_id scopes the result to ONE of ch's two cells. Without it a syllable
    pulls in everything sharing either cell, which reads as over-counting when
    a cell is under review: opening T:ㄳ anchors on 넋 and its LV cell drags
    in 넉/넌/널/넘..., 26 syllables with no ㄳ in them at all.

    Confirmed syllables show their OWN saved pixels, not a recomposition --
    when a cell's samples tie (majority-vote picks one arbitrarily), the
    library component can come from a DIFFERENT confirmed syllable than the
    one being previewed, so recomposing would silently show that other
    syllable's shape instead of the real one (seen with 눰/뛈 sharing a tied
    T:ㅁ:ㅝ cell -- 눰's compose() result was actually 뛈's glyph).

    The in-progress drawing is deliberately NOT forced to define its cell here.
    Making it win looks helpful -- edit 넋 and all 280 composed ㄳ syllables
    move with it -- but it previews a build that will never happen: saving adds
    one sample, and majority vote keeps ignoring it while other confirmed
    syllables agree. This panel is for REVIEW, so it has to show what actually
    ships. Where a component is wrong for a whole class the fix is a finer 벌
    key (see t_beol's 가로/세로 split); where it is wrong for one syllable
    the fix is to draw that syllable, which overrides the composition outright."""
    cc = _ccomp()
    cl = _composer()
    if cc is None or cl is None:
        return []
    corpus = cc.load_corpus()
    confirmed = dict(corpus)               # keep the pre-overwrite saved rows
    corpus[ch] = rows                      # the in-progress drawing
    (cho_ref,) = _cho_ref(corpus)
    seen = cc.observe(corpus, _pc98_grid_or_none(), cho_ref)
    lib = {cell: cand.most_common(1)[0][0] for cell, cand in seen.items()}

    mine = set(cc.cells_for(ch))
    if cell_id:
        # compare rendered ids rather than parsing cell_id back into a tuple --
        # the 벌 is a heterogeneous tuple (bool for cv, jamo or empty for jong)
        scoped = {c for c in mine if _cell_id(c) == cell_id}
        if scoped:                         # ignore an id this syllable doesn't use
            mine = scoped
    out = []
    for other in cc.FULL:
        if not mine & set(cc.cells_for(other)):
            continue
        if other == ch:
            out_rows = rows
        elif other in confirmed:
            out_rows = confirmed[other]
        else:
            out_rows = cc.compose(other, lib)
        out.append({"ch": other, "rows": out_rows, "confirmed": other in confirmed})
        if len(out) >= limit:
            break
    return out


def _cho_ref(corpus):
    # Must exclude syllables PC-98 lacks -- see compose_components
    # .build_zone_indices for why a drawn representative winning the canonical
    # slot crashes cho_zone.
    cc = _ccomp()
    return (cc.build_zone_indices(corpus, _pc98_grid_or_none()),)


def _pc98_grid_or_none():
    """compose_light.load_pc98() equivalent, reusing our own bitmap handle."""
    cl = _composer()
    return cl.load_pc98()


# Kana helper -- also used by text_grids to route kana to the PC-98 둥근모꼴
# reference instead of the original bitmap (see docs/ROADMAP.md).
def _is_kana(ch):
    return (0x3041 <= ord(ch) <= 0x30FF) or (0xFF61 <= ord(ch) <= 0xFF9F)


# Symbol/punctuation reference: GNU Unifont (refs/unifont.otf, gitignored like
# the other refs). Picked because it is drawn natively on a 16x16 pixel grid --
# the same cell we use -- so it needs no rescaling, and it covers the whole BMP,
# so every symbol tier resolves (MS Gothic, our kana reference, turned out to be
# a JIS subset with no Latin-1/currency/dashes at all). Reference only: shapes
# are looked at and redrawn by hand, never copied, same as every other ref here.
UNIFONT_TTF = os.path.join(ROOT, "refs", "unifont.otf")
UNIFONT_PX = 16
# Unifont's own baseline sits at row 14 of its 16-row cell; ours sits at row 13
# (editor guide), so text glyphs shift up by one. Cell-filling glyphs (box
# drawing, block elements) are the exception -- they must span 0..15 edge to
# edge so runs connect, which is exactly how the original bitmap draws them
# (verified: '┼' spans all 16 rows with its bar on row 7, same as Unifont).
UNIFONT_BASELINE_ROW = 13
_UNIFONT = None


def _unifont():
    global _UNIFONT
    if _UNIFONT is None:
        import freetype
        face = freetype.Face(UNIFONT_TTF)
        face.set_pixel_sizes(0, UNIFONT_PX)
        _UNIFONT = face
    return _UNIFONT


def _unifont_grid(ch):
    import freetype
    try:
        face = _unifont()
    except Exception:
        return None
    if face.get_char_index(ord(ch)) == 0:
        return None  # unmapped -- would render .notdef
    try:
        face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    except Exception:
        return None
    slot = face.glyph
    bmp = slot.bitmap
    if bmp.width == 0 or bmp.rows == 0:
        return None  # blank (space and friends)
    # Grid width follows Unifont's own advance: 8 for halfwidth symbols/Latin,
    # 16 for fullwidth/CJK. The editor centers a narrower grid on a wider canvas.
    grid_w = max(1, min(16, slot.advance.x // 64 or bmp.width))
    grid = [["."] * grid_w for _ in range(16)]
    # Box drawing (U+2500-257F) and block elements (U+2580-259F) are cell
    # glyphs, not text: they tile edge to edge, so they keep Unifont's own
    # cell placement (its baseline is row 14) rather than being re-seated on
    # our text baseline -- otherwise '─' lands a row above '┼''s crossbar and
    # runs stop connecting.
    cell_glyph = 0x2500 <= ord(ch) <= 0x259F
    dy = (14 - slot.bitmap_top) if cell_glyph else (UNIFONT_BASELINE_ROW - slot.bitmap_top)
    for y in range(bmp.rows):
        gy = dy + y
        if not (0 <= gy < 16):
            continue
        for x in range(bmp.width):
            gx = slot.bitmap_left + x
            if not (0 <= gx < grid_w):
                continue
            if (bmp.buffer[y * bmp.pitch + x // 8] >> (7 - (x % 8))) & 1:
                grid[gy][gx] = "#"
    return ["".join(row) for row in grid]


def sym_ref_grids(s):
    """Per-char pixel grids from GNU Unifont -- the symbol/punctuation
    reference overlay. Reference only, never embedded in built output."""
    return [{"ch": ch, "rows": _unifont_grid(ch)} for ch in s]


def kana_chars():
    """Hiragana + katakana + halfwidth katakana (Unicode-assigned codepoints
    only), for the editor's kana palette (Phase 3)."""
    import unicodedata

    def assigned(lo, hi):
        out = []
        for cp in range(lo, hi + 1):
            try:
                unicodedata.name(chr(cp))
            except ValueError:
                continue
            out.append(chr(cp))
        return out
    return assigned(0x3041, 0x309F) + assigned(0x30A1, 0x30FF) + assigned(0xFF61, 0xFF9F)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        payload = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass  # quiet

    def _weight_qs(self, qs):
        w = qs.get("weight", ["regular"])[0]
        if w not in GLYPHS_FILES:
            w = "regular"
        return w

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query, keep_blank_values=True)

        if parsed.path in ("/", "/index.html"):
            with open(EDITOR, encoding="utf-8") as f:
                page = PAGE_HEAD + f.read() + PAGE_TAIL
            return self._send(200, page, "text/html; charset=utf-8")
        if parsed.path == "/editor.css":
            with open(EDITOR_CSS, encoding="utf-8") as f:
                return self._send(200, f.read(), "text/css; charset=utf-8")
        if parsed.path == "/api/glyphs":
            weight = self._weight_qs(qs)
            return self._send(200, json.dumps(read_glyphs(weight), ensure_ascii=False))
        if parsed.path == "/api/text":
            weight = self._weight_qs(qs)
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": text_grids(weight, s)},
                                              ensure_ascii=False))
        if parsed.path == "/api/ks2350":
            return self._send(200, json.dumps({"chars": ks2350_chars()},
                                              ensure_ascii=False))
        if parsed.path == "/api/symref":
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": sym_ref_grids(s)},
                                              ensure_ascii=False))
        if parsed.path == "/api/kana":
            return self._send(200, json.dumps({"chars": kana_chars()},
                                              ensure_ascii=False))
        if parsed.path in ("/components", "/components.html", "/components/"):
            # The component-cell editor is now the main editor's 부품 셀 palette
            # tab -- its drawing half was a duplicate of that editor's. Kept as
            # a redirect so existing bookmarks and the startup prompt still work.
            self.send_response(302)
            self.send_header("Location", "/#cells")
            self.end_headers()
            return
        if parsed.path == "/api/cells":
            return self._send(200, json.dumps({"cells": component_cells()},
                                              ensure_ascii=False))
        if parsed.path in ("/halfwidth", "/halfwidth.html", "/halfwidth/"):
            with open(HALFWIDTH_EDITOR, encoding="utf-8") as f:
                page = HALFWIDTH_PAGE_HEAD + f.read() + PAGE_TAIL
            return self._send(200, page, "text/html; charset=utf-8")
        if parsed.path == "/api/halfwidth_ref":
            return self._send(200, json.dumps({"slots": halfwidth_ref_slots()},
                                              ensure_ascii=False))
        if parsed.path == "/api/halfwidth_glyphs":
            return self._send(200, json.dumps(read_halfwidth(), ensure_ascii=False))
        if parsed.path == "/api/halfwidth_charmap":
            return self._send(200, json.dumps(read_halfwidth_charmap(), ensure_ascii=False))
        if parsed.path == "/api/halfwidth_light_ref":
            s = qs.get("s", [""])[0]
            return self._send(200, json.dumps({"chars": halfwidth_light_grids(s)},
                                              ensure_ascii=False))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        if parsed.path == "/api/glyphs":
            weight = self._weight_qs(qs)
            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": f"bad json: {e}"}))
            data = read_glyphs(weight)
            data.update(incoming)
            write_glyphs(weight, data)
            return self._send(200, json.dumps({"saved": list(incoming), "total": len(data)}))
        if parsed.path == "/api/build":
            weight = self._weight_qs(qs)
            ok, log = run_build(weight)
            return self._send(200 if ok else 500, json.dumps({"ok": ok, "log": log}))
        if parsed.path == "/api/build_bmp":
            ok, log = run_build_bmp()
            return self._send(200 if ok else 500, json.dumps({"ok": ok, "log": log}))
        if parsed.path == "/api/cell_preview":
            try:
                body = json.loads(raw)
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": f"bad json: {e}"}))
            ch = body.get("ch") or ""
            rows = body.get("rows") or []
            if not ch or not rows:
                return self._send(400, json.dumps({"error": "ch and rows required"}))
            return self._send(200, json.dumps(
                {"chars": cell_preview(ch, rows, body.get("cell"))},
                ensure_ascii=False))
        if parsed.path == "/api/halfwidth_glyphs":
            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": f"bad json: {e}"}))
            data = read_halfwidth()
            data.update(incoming)
            write_halfwidth(data)
            return self._send(200, json.dumps({"saved": list(incoming), "total": len(data)}))
        if parsed.path == "/api/halfwidth_charmap":
            try:
                incoming = json.loads(raw)
            except json.JSONDecodeError as e:
                return self._send(400, json.dumps({"error": f"bad json: {e}"}))
            data = read_halfwidth_charmap()
            data.update(incoming)
            write_halfwidth_charmap(data)
            return self._send(200, json.dumps({"saved": list(incoming), "total": len(data)}))
        self._send(404, json.dumps({"error": "not found"}))


# The two internal weight keys map to the two members of one RIBBI family:
# "regular" = 2px stems -> compiled Bold; "light" = 1px stems -> compiled
# Regular (the family default). See tools/metadata.py / build_ufo.py.
BUILD_TARGETS = {
    "regular": {
        "ufo": "build/DokkaebiDNRGothic-Bold.ufo",
        "ttf": "build/DokkaebiDNRGothic-Bold.ttf",
        "build_args": ["--all"],
    },
    "light": {
        "ufo": "build/DokkaebiDNRGothic-Regular.ufo",
        "ttf": "build/DokkaebiDNRGothic-Regular.ttf",
        "build_args": ["--weight", "light"],
    },
}


def run_build(weight):
    target = BUILD_TARGETS.get(weight, BUILD_TARGETS["regular"])
    py = sys.executable
    steps = [
        [py, "scripts/build_ufo.py", *target["build_args"], "--proportional",
         "--out", target["ufo"]],
        [py, "-m", "fontmake", "-u", target["ufo"],
         "-o", "ttf", "--output-path", target["ttf"]],
        [py, "scripts/finalize.py", target["ttf"]],
    ]
    out = []
    for cmd in steps:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out.append(f"$ {' '.join(cmd[1:])}\n{(p.stdout or '')[-400:]}{(p.stderr or '')[-400:]}")
        if p.returncode != 0:
            return False, "\n".join(out)
    return True, "\n".join(out)


def run_build_bmp():
    """Regenerate build/font_light.bmp from current saved state -- recompose
    Light Hangul (build/light_hangul.json) then drop it + the saved 반각 한글
    (glyphs_halfwidth.json) into a copy of the PC-98 font.bmp. Unsaved edits
    in the editor aren't included (both scripts read from disk)."""
    py = sys.executable
    steps = [
        [py, "scripts/compose_light.py"],
        [py, "scripts/build_pc98_bmp.py"],
    ]
    out = []
    for cmd in steps:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out.append(f"$ {' '.join(cmd[1:])}\n{(p.stdout or '')[-400:]}{(p.stderr or '')[-400:]}")
        if p.returncode != 0:
            return False, "\n".join(out)
    return True, "\n".join(out)


def _ensure_venv():
    """Re-exec under this project's .venv if we're not already running there.

    fontTools/PIL (via tools/pixelfont.py, the PC-98/kana/halfwidth lookups,
    etc.) only live in .venv, and every one of those call sites imports them
    lazily and fails closed (try/except -> blank grid) rather than raising --
    so running under plain system `python3` doesn't error, it just silently
    renders Regular Hangul (and kana, and the PC-98/kana-ref overlays) as
    nothing but blank cells. Re-exec here removes the whole "did you
    activate the venv" failure mode instead of relying on people remembering."""
    venv_dir = os.path.join(ROOT, ".venv")
    venv_py = os.path.join(venv_dir, "bin", "python3")
    # Compare sys.prefix, not sys.executable/realpath: .venv/bin/python3 is
    # usually just a symlink to the same base interpreter binary, so the
    # executable path (even resolved) is identical either way -- sys.prefix
    # is what actually flips to .venv once its site-packages are active.
    if os.path.exists(venv_py) and os.path.realpath(sys.prefix) != os.path.realpath(venv_dir):
        os.execv(venv_py, [venv_py] + sys.argv)


# 부품 셀 is a palette tab of the main editor, not a page -- listing it
# separately would offer the same page twice.
PAGES = [
    ("메인 에디터", "/"),
    ("반각 한글 에디터", "/halfwidth"),
]


def main():
    _ensure_venv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}/"
    print(f"pixel editor: {url}  (Ctrl+C to stop)")
    print(f"  editing tools/glyphs_bold.json / glyphs_light.json  ·  POST /api/build?weight=regular|light to rebuild")
    print(f"  부품 셀: 메인 에디터의 팔레트 탭  ·  11,172자 확장용 (docs/ROADMAP.md)")
    print(f"  반각 한글 에디터: {url}halfwidth  ·  editing tools/glyphs_halfwidth.json (separate from the font build)")

    # Serve in the background so the terminal prompt below can run while the
    # server is already up -- opening a browser before serve_forever() starts
    # would just hit connection-refused.
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    if not args.no_open:
        print("\n열 페이지를 골라주세요 (Enter만 누르면 안 엽니다):")
        for i, (name, path) in enumerate(PAGES, 1):
            print(f"  {i}) {name} ({path})")
        try:
            choice = input("> ").strip()
        except EOFError:
            choice = ""
        if choice:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(PAGES):
                    webbrowser.open(url.rstrip("/") + PAGES[idx][1])
                else:
                    print("범위 밖 번호라 안 엽니다.")
            except ValueError:
                print("숫자가 아니라서 안 엽니다.")

    try:
        server_thread.join()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
