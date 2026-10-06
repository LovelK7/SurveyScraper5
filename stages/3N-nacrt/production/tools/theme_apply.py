#!/usr/bin/env python3
"""Apply a symbol theme to a post-import cSurvey file (project 0007, T3 + phase 2).

Signs, lines, areas and the centerline. Runs after KORAK 2
(fix_imported_linetypes.py, which also runs wall_orient.py).

Per item the theme entry is looked up the T8 way (themes.resolve): the
TopoDroid name recovered from the pre-import file by tdx_name_recover.py first,
then the item's cSurvey target, else the item is left alone. A KORAK 2 wall
merge can fold several TopoDroid strokes into one item: the name is then the
majority of its sequences, and a tie is reported and skipped.

SIGNS (type 6) - phase 1, inline per-item pen and brush:
  glyph   the theme SVG goes into the `<signs><cliparts>` pool under cSurvey's
          own id (nacrt_finish.clipart_hash) - base64 in a .csx, a
          `_data/cliparts/<id>.svg` zip entry in a .csz (the KORAK 3 compass
          route) - named tema-<theme>_<file>.svg; the item's `data` is
          repointed (dataformat 2), `sign=` kept. A theme `size` is baked into
          csurvey:scale; `rotate` into the coordinates. Glyphs are drawn as
          they look at TopoDroid orientation 0 (arrows pointing up/north):
          cSurvey's importer adds +90 to the orientation of points named
          exactly air-draught or water-flow (cImportTopoDroidHelper.vb:331-334),
          so for those items the glyph is turned -90 to compensate - per item,
          from the name that reached the importer (prep_name).
  colour  a coloured sign gets an inline custom solid brush
          (`<brush type="99" ... hatchtype="1"/>`, the T0 oracle's shape);
          black keeps the built-in `<brush type="7"/>`.
  pen     outline_pen false: an inline custom pen with style None (98), no
          outline (cPen.vb:865-867). outline_pen true: TightPen's look in the
          colour. Unset ("auto"): off, unless the glyph has strokes and no
          fills - then the pen draws them, in the sign's colour (reported).
          `render: outline` makes the brush white and the pen the colour.

LINES - a library pen per (theme key, built-in pen type) in the root
`<pens>`: `<pen type="98" id="tema-<theme>-<key>-<type>" name=...>`, written
the way cCustomPen.SaveTo writes it (cPen.vb:484-539), and the item's
`<pen type="N"/>` becomes `<pen type="98" id="..."/>` (cPen.vb:1435-1475).
  width   theme `width`, else the built-in pen's own width: cSurvey draws a
          built-in pen with width 0 at GetPenDefaultWidth(type) (cOptions.vb:
          1394-1426) - but a User (98) pen has no default there (0 = hairline),
          so the number is written out (BaseMediumLinesScaleFactor etc. read
          from the file, cSurvey's defaults otherwise).
  style   solid/dash/dot/... ; custom + stylepattern; none (98) = no base
          stroke, decoration only (the double-line meander).
  unit    decorationstyle 99 with the theme SVG inline in `<clipart data="..."/>`
          (one line, cDrawClipArt.SaveTo writes the string back verbatim).
          clipartpenmode Custom with clipartpenstyle None: the unit is painted
          by its fill only, no outline. clipartbrushmode Custom only when the
          decoration colour differs from the line colour.
  side    alignment `auto` puts the unit on the side the item's built-in pen
          uses (PEN_SIDE; cPens.vb:343-447), flipping it for an Inner pen; a
          plain pen (2, a TopoDroid name cSurvey does not know) takes the side
          of the name's KORAK 1 target (tdx-mapping.json).
  spacing decorationspacepercentage is written as given, at least 0.1
          (cSurvey reads a stored 0 as 100, cPen.vb:434-435).

AREAS - a library brush per (theme key, built-in brush type) in `<brushes>`
(cBrush.vb:1561-1621, items `<brush type="98" id=...>`, cBrush.vb:3083-3112;
the item's own `<seed>` child is kept, cSurvey reads it from the item):
  tile    hatchtype 2, the SVG inline, clipartdensity / clipartzoomfactor /
          clipartanglemode (+angle) / clipartcrop / clipartposition.
  solid   hatchtype 1.
  pattern hatchtype 3, patterntype/penstyle/density/zoom/anglemode/angle and
          an empty `<parameters/>`, as cPatternBrushes.SaveTo writes it
          (cBrush.vb:551-603; the T0 oracle).

Undo: everything written is recorded in two string design properties that
cSurvey keeps through a load + save: CaveDossierTheme = <id> and
CaveDossierThemeState = JSON (sign glyph ids + originals, the library pen and
brush ids with each one's built-in type, whether `<pens>`/`<brushes>` were
created, the overwritten centerline values). A re-run undoes the previous theme
first, so themes replace each other and never stack; re-applying gives a
byte-identical file.

Usage:
  python theme_apply.py apply IN.csx|IN.csz --theme ID --pre PRE.csx [-o OUT]
                        [--dry-run] [--json REPORT] [--themes-root DIR]

  --pre is the pre-import file (raw TopoDroid export or the KORAK 1 _prep
  output). Without it every item falls back to its cSurvey target.
  Default OUT is <in>_<theme>.<ext> (a previous _<theme> suffix replaced).

Stdlib only. Never modifies the input.
"""

import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import fix_imported_linetypes as fixer                           # noqa: E402
import nacrt_finish                                             # noqa: E402
import tdx_name_recover                                         # noqa: E402
import theme_svg                                                # noqa: E402
import themes                                                   # noqa: E402

DESIGNS = ("plan", "profile")
SIGN_ITEM = "6"
PEN_TIGHT = "10"            # cPen.PenTypeEnum.TightPen
BRUSH_SIGN = "7"            # cBrush.BrushTypeEnum.SignSolid
USER = "98"                 # library (User) pen/brush, referenced by id
CUSTOM = "99"               # inline per-item pen/brush
HATCH_SOLID = "1"           # cBrush.HatchTypeEnum.Solid
HATCH_CLIPART = "2"
HATCH_PATTERN = "3"
STYLE_SOLID = "0"           # cPen.PenStylesEnum.Solid
STYLE_NONE = "98"           # cPen.PenStylesEnum.None: no GDI pen at all (cPen.vb:865-867)
DECO_CUSTOM = "99"          # cPen.DecorationStylesEnum.Custom
WHITE = -1                  # 0xFFFFFFFF
TRANSPARENT = 16777215      # Color.Transparent.ToArgb (0x00FFFFFF)
MIN_SPACING = 0.1           # a stored 0 reads back as 100 (cPen.vb:434-435)
MARK = "tema:"              # name prefix of every pen/brush this tool writes
PROP_THEME = "CaveDossierTheme"
PROP_STATE = "CaveDossierThemeState"
_SCALE_RE = re.compile(rb'csurvey:scale="([^"]*)"')

# cImportTopoDroidHelper.vb:331-334: these point names get orientation + 90.
IMPORTER_PLUS_90 = ("air-draught", "water-flow")
PLUS_90_SIGNS = ("774", "777")          # their SignEnum, for items with no --pre

# Built-in pen widths (cOptions.GetPenDefaultWidth, cOptions.vb:1340-1426):
# pen type -> (design property, cSurvey default). None = FilettoPenWidth.
_FILETTO = (None, 0.001)
_MEDIUM = ("BaseMediumLinesScaleFactor", 3.0)
PEN_WIDTH = {0: _FILETTO, 10: _FILETTO, 18: _FILETTO, 99: _FILETTO,
             9: ("BaseUltraLightLinesScaleFactor", 0.1), 17: ("BaseUltraLightLinesScaleFactor", 0.1),
             1: ("BaseHeavyLinesScaleFactor", 8.0), 8: ("BaseHeavyLinesScaleFactor", 8.0),
             25: ("BaseHeavyLinesScaleFactor", 8.0), 26: ("BaseHeavyLinesScaleFactor", 8.0)}
for _t in (2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24):
    PEN_WIDTH[_t] = _MEDIUM
for _t in (31, 32, 33, 34, 35, 36, 37, 38, 40, 41):
    PEN_WIDTH[_t] = ("BaseGeologyLinesScaleFactor", 10.0)

# Which side of the line a built-in pen puts its decoration (cPens.vb:343-447),
# as (alignment, flip). The theme unit is drawn pointing away from the line
# with the line along its bottom edge, i.e. like cSurvey's "up" units; an
# Inner pen draws "down" units below the line, so ours is flipped.
PEN_SIDE = {4: ("outer", False), 13: ("outer", False),          # cliff up
            5: ("inner", True), 14: ("inner", True),            # cliff down
            6: ("center", False), 15: ("center", False),        # gradient up
            7: ("center", True), 16: ("center", True),          # gradient down
            11: ("outer", False), 19: ("outer", False),         # overhang up
            12: ("inner", True), 20: ("inner", True),           # overhang down
            21: ("center", False), 22: ("center", False),       # meander
            23: ("center", False), 24: ("center", False)}       # ice
# Built-in pen of a KORAK 1 line target (as imported: zoo runs, r2 mockup).
TARGET_PEN = {"overhang": 12, "pit": 5, "chimney": 14, "slope": 7,
              "floor-meander": 21, "ceiling-meander": 22}
# cSurvey target of an item with no TopoDroid name, from its built-in type.
PEN_TARGET = {1: "wall", 8: "wall:presumed", 2: "border", 3: "presumed",
              4: "pit", 5: "pit", 13: "pit", 14: "chimney",
              11: "overhang", 12: "overhang", 19: "overhang", 20: "overhang",
              6: "slope", 7: "slope", 15: "slope", 16: "slope",
              21: "floor-meander", 22: "ceiling-meander"}
BRUSH_TARGET = {2: "water", 6: "water", 3: "sand", 4: "pebbles", 8: "debris", 9: "blocks"}


# --------------------------------------------------------------------------
# lookups

def sign_targets(catalog_path=themes.CATALOG):
    """SignEnum (str) -> cSurvey target name, from the catalog's point targets
    (the csurvey:sign of each target's gallery SVG), then SIGN_VALUES."""
    with open(catalog_path, encoding="utf-8") as f:
        cat = json.load(f)
    out = {}
    for t in cat.get("targets", {}).get("point", []):
        m = re.search(r'csurvey:sign="(\d+)"', t.get("svg") or "")
        if m:
            out.setdefault(m.group(1), t["to"])
    for name, value in fixer.SIGN_VALUES.items():
        out.setdefault(str(value), name)
    return out


def line_targets(mapping_path=themes.MAPPING):
    """TopoDroid line name -> KORAK 1 target (tdx-mapping.json `lines`, with
    the subtype stripped the way KORAK 1 strips it)."""
    try:
        with open(mapping_path, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {k: (v or {}).get("to") for k, v in (m.get("lines") or {}).items()
           if isinstance(v, dict)}
    out["_strip"] = (m.get("generic") or {}).get("strip_line_subtypes", True)
    return out


def iter_items(root):
    """Every item in (design, layer, index) order - the order of
    tdx_name_recover.post_units, so the two can be zipped."""
    for design in DESIGNS:
        layers = root.find(design + "/layers")
        if layers is None:
            continue
        for layer in layers.findall("layer"):
            its = layer.find("items")
            if its is None:
                continue
            for item in its.findall("item"):
                yield design, item


def _majority(seqs):
    """(name, kind, prep_name, note) from an item's recovered sequences."""
    counts, kinds, preps = {}, {}, {}
    for sq in seqs:
        src = sq.get("source")
        if not src or sq.get("status") not in ("exact", "tolerant"):
            continue
        counts[src["tdx_name"]] = counts.get(src["tdx_name"], 0) + 1
        kinds[src["tdx_name"]] = src["kind"]
        preps[src["tdx_name"]] = src.get("prep_name")
    if not counts:
        return None, None, None, None
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    if len(ranked) == 1:
        n = ranked[0][0]
        return n, kinds[n], preps[n], None
    if ranked[0][1] > ranked[1][1]:
        n = ranked[0][0]
        return n, kinds[n], preps[n], "mixed %s - majority %s" % (
            ", ".join("%s x%d" % kv for kv in ranked), n)
    return None, None, None, "mixed %s - tie, not themed" % ", ".join(
        "%s x%d" % kv for kv in ranked)


def recovered_names(pre_path, in_path, root):
    """[{design, item, tdx, kind, status, prep, note}] for every item."""
    items = list(iter_items(root))
    if not pre_path:
        return [{"design": d, "item": it, "tdx": None, "kind": None, "status": "no-pre",
                 "prep": None, "note": None} for d, it in items]
    res = tdx_name_recover.recover(pre_path, in_path)
    if len(res["items"]) != len(items):
        raise ValueError("name recovery saw %d items, the file has %d"
                         % (len(res["items"]), len(items)))
    out = []
    for (design, item), info in zip(items, res["items"]):
        name, kind, prep, note = _majority(info["sequences"])
        out.append({"design": design, "item": item, "tdx": name, "kind": kind,
                    "status": info["status"], "prep": prep, "note": note})
    return out


# --------------------------------------------------------------------------
# xml helpers

def reflow(parent):
    """Re-indent parent's children the way cSurvey writes them (2 spaces a
    level), so adding and removing elements leaves byte-identical files
    whatever the order. A parent that is not pretty-printed is left alone."""
    kids = list(parent)
    if not kids:
        if parent.text is not None and not parent.text.strip():
            parent.text = None
        return
    if not (parent.text and "\n" in parent.text):
        return
    child = parent.text.rsplit("\n", 1)[1]
    close = child[:-2] if child.endswith("  ") else ""
    for k in kids:
        k.tail = "\n" + child
    kids[-1].tail = "\n" + close


def _replace(item, old, new):
    new.tail = old.tail
    kids = list(new)
    if kids and item.text and "\n" in item.text:     # indent new's children like cSurvey
        indent = item.text.rsplit("\n", 1)[1]
        new.text = "\n" + indent + "  "
        for k in kids:
            k.tail = "\n" + indent + "  "
        kids[-1].tail = "\n" + indent
    item[list(item).index(old)] = new


def is_ours(el):
    return (el is not None and el.get("type") == CUSTOM
            and (el.get("name") or "").startswith(MARK))


def solid_brush(color, theme_id):
    """Inline custom solid brush, attribute set and order as cBrush.SaveTo
    writes it for hatchtype Solid (cBrush.vb:1561-1575; oracle: the
    `Water (not standard)` brush)."""
    return ET.Element("brush", {"type": CUSTOM, "name": MARK + theme_id,
                                "color": str(color), "backgroundcolor": "0",
                                "hatchtype": HATCH_SOLID})


def tight_pen(color, theme_id, style=STYLE_SOLID):
    """Inline custom pen = TightPen (black, width 0, solid; cPens.vb:292) in
    another colour. Width 0 renders at the same FilettoPenWidth as TightPen
    (cOptions.vb:1404-1425). Attributes and the empty `<clipart data=""/>` as
    cCustomPen.SaveTo writes them (cPen.vb:484-512), so a cSurvey load + save
    leaves the pen byte-identical (checked headless, 2026-10-06; the style-None
    pen too, 2026-10-07)."""
    pen = ET.Element("pen", {"type": CUSTOM, "name": MARK + theme_id,
                             "color": str(color), "style": style, "width": "0.00",
                             "decorationstyle": "0",
                             "decorationspacepercentage": "100.0",
                             "decorationalignment": "0",
                             "decorationscale": "1.00"})
    ET.SubElement(pen, "clipart", {"data": ""})
    return pen


def no_pen(color, theme_id):
    """Inline custom pen with style None: the glyph's paths get no outline."""
    return tight_pen(color, theme_id, STYLE_NONE)


def _n2(v):
    """modNumbers.NumberToString default format "0.00"."""
    return "%.2f" % v


def _design_props(root):
    props = root.find("properties")
    if props is None:
        raise ValueError("no <properties> element - not a cSurvey file")
    dp = props.find("designproperties")
    if dp is None:
        dp = ET.SubElement(props, "designproperties")
    return dp


def _prop(dp, name):
    for it in dp.findall("item"):
        if it.get("name") == name:
            return it
    return None


def read_state(root):
    """(theme_id, state dict) recorded by a previous run, or (None, None)."""
    props = root.find("properties")
    dp = props.find("designproperties") if props is not None else None
    if dp is None:
        return None, None
    tid = _prop(dp, PROP_THEME)
    st = _prop(dp, PROP_STATE)
    state = None
    if st is not None and (st.text or "").strip():
        try:
            state = json.loads(st.text)
        except ValueError:
            state = None
    return (tid.text if tid is not None else None), state


def _library(root, tag, create):
    """The root `<pens>` / `<brushes>` element -> (element, created now)."""
    el = root.find(tag)
    if el is not None or not create:
        return el, False
    kids = list(root)
    anchor = next((i for i, k in enumerate(kids) if k.tag in ("plan", "profile")), len(kids))
    if tag == "brushes":
        pens = root.find("pens")
        if pens is not None:
            anchor = kids.index(pens) + 1
    el = ET.Element(tag)
    el.tail = kids[anchor - 1].tail if anchor else "\n  "
    root.insert(anchor, el)
    return el, True


def _lib_append(lib, el):
    """Append a library entry, indented like cSurvey (the container sits at
    depth 1, its entries at 2, their children at 3)."""
    outer = (lib.tail or "\n  ").rsplit("\n", 1)[-1]
    ind = outer + "  "
    if not (lib.text and "\n" in lib.text):
        lib.text = "\n" + ind
    kids = list(el)
    if kids:
        el.text = "\n" + ind + "  "
        for k in kids:
            k.tail = "\n" + ind + "  "
        kids[-1].tail = "\n" + ind
    lib.append(el)
    reflow(lib)


# --------------------------------------------------------------------------
# glyphs (signs)

def scale_svg(blob, factor):
    """Multiply the glyph's csurvey:scale (default 1) by factor."""
    m = _SCALE_RE.search(blob)
    if m:
        new = float(m.group(1).decode()) * factor
        return blob[:m.start(1)] + (b"%g" % round(new, 4)) + blob[m.end(1):]
    i = blob.find(b"<svg")
    if i < 0:
        raise ValueError("not an SVG")
    attrs = b' csurvey:scale="%g"' % round(factor, 4)
    if b"xmlns:csurvey" not in blob:
        attrs = b' xmlns:csurvey="http://www.csurvey.it"' + attrs
    return blob[:i + 4] + attrs + blob[i + 4:]


def pool_name(theme_id, svg_path, rotate=0):
    """Pool entry name: tema-<theme>_<file>.svg, so a themed glyph never looks
    like a duplicate of cSurvey's own gallery entry (blocks.svg) in the
    Clipart gallery's Survey list. Display only - the id is the content hash."""
    base = os.path.basename(svg_path)
    if rotate:
        base = "%s_r%d%s" % (os.path.splitext(base)[0], round(rotate) % 360,
                             os.path.splitext(base)[1])
    return "tema-%s_%s" % (theme_id, base)


_STROKE_ONLY_RE = re.compile(rb'<path\b[^>]*\bfill="none"')
_FILLED_RE = re.compile(rb'<path\b[^>]*\bfill="(?!none")')


def stroke_only_paths(blob):
    """Paths with no fill: with the pen off (outline_pen false) they do not paint."""
    return len(_STROKE_ONLY_RE.findall(blob))


def filled_paths(blob):
    return len(_FILLED_RE.findall(blob))


def glyph_for(spec, theme_id, rotate=0.0):
    """(id, pool name, bytes) of the spec's glyph, or None (built-in glyph).
    rotate: degrees on top of the spec's own (the importer compensation)."""
    if not spec.get("svg"):
        return None
    with open(spec["svg"], "rb") as f:
        blob = f.read()
    size = spec.get("size")
    if size and abs(size - 1.0) > 1e-9:
        blob = scale_svg(blob, size)
    turn = ((spec.get("rotate") or 0.0) + rotate) % 360.0
    if turn > 1e-9 and abs(turn - 360.0) > 1e-9:
        blob = theme_svg.rotate_svg(blob, turn)
    else:
        turn = 0
    return (nacrt_finish.clipart_hash(blob), pool_name(theme_id, spec["svg"], rotate and turn),
            blob)


def _pool(root):
    cl = nacrt_finish._cliparts_element(root)
    return cl, ({c.get("id") for c in cl.findall("clipart")} if cl is not None else set())


def _referenced_ids(root):
    return {it.get("data") for d in DESIGNS for it in (root.find(d).iter("item")
                                                       if root.find(d) is not None else [])
            if it.get("data")}


def importer_turn(prep_name, sign):
    """Degrees cSurvey's importer added to this point's angle (0 or 90)."""
    if prep_name is not None:
        return 90.0 if prep_name in IMPORTER_PLUS_90 else 0.0
    return 90.0 if sign in PLUS_90_SIGNS else 0.0


# --------------------------------------------------------------------------
# pens and brushes (lines, areas)

def default_width(root, pen_type):
    """The width cSurvey draws built-in pen `pen_type` with, in pen-width
    units (x BaseLineWidthScaleFactor): its design property, else the default."""
    prop, dflt = PEN_WIDTH.get(pen_type, _MEDIUM)
    if prop is None:
        return dflt
    props = root.find("properties")
    dp = props.find("designproperties") if props is not None else None
    el = _prop(dp, prop) if dp is not None else None
    try:
        return float(el.text) if el is not None and el.text else dflt
    except ValueError:
        return dflt


def side_for(pen_type, tdx, ltargets):
    """(alignment, flip) of the built-in pen, or of the name's KORAK 1 target."""
    if pen_type in PEN_SIDE:
        return PEN_SIDE[pen_type]
    if tdx:
        to = ltargets.get(tdx)
        if to is None and ltargets.get("_strip", True) and ":" in tdx:
            base = tdx.split(":", 1)[0]
            to = ltargets.get(base, base)
        to = to or tdx
        if TARGET_PEN.get(to) in PEN_SIDE:
            return PEN_SIDE[TARGET_PEN[to]]
    return ("outer", False)


def unit_svg(path, flip):
    with open(path, "rb") as f:
        blob = f.read()
    if flip:
        blob = theme_svg.flip_svg(blob)
    return theme_svg.compact_svg(blob)


def library_pen(pid, name, spec, width, pen_type, tdx, ltargets):
    """`<pen type="98">` as cCustomPen.SaveTo writes it (cPen.vb:484-539)."""
    a = {"type": USER, "id": pid, "name": name, "color": str(spec["color"]),
         "style": str(themes.LINE_STYLES[spec["style"]])}
    if spec["style"] == "custom":
        a["stylepattern"] = " ".join(_n2(d) for d in spec["dash"])
    a["width"] = _n2(width)
    deco = spec.get("decoration")
    data = ""
    if spec.get("svg") and deco:
        align, flip = deco["alignment"], deco.get("flip")
        if align == "auto":
            align, auto_flip = side_for(pen_type, tdx, ltargets)
            flip = auto_flip if flip is None else flip
        data = unit_svg(spec["svg"], bool(flip))
        a["decorationstyle"] = DECO_CUSTOM
        a["decorationspacepercentage"] = "%.1f" % max(deco["spacing_pct"], MIN_SPACING)
        if deco["distance_pct"]:
            a["decorationdistancepercentage"] = "%.1f" % deco["distance_pct"]
        a["decorationalignment"] = str(themes.ALIGNMENTS[align])
        if deco["position"] != "behind":
            a["decorationposition"] = str(themes.POSITIONS[deco["position"]])
        a["decorationscale"] = _n2(deco["scale"])
        # the unit is painted by its fill only: no outline round it
        a.update({"clipartpenmode": "1", "clipartpenwidth": "0.00",
                  "clipartpenstyle": STYLE_NONE, "clipartpencolor": str(spec["decoration_color"])})
        if spec["decoration_color"] != spec["color"]:
            a.update({"clipartbrushmode": "1", "clipartbrushstyle": "0",
                      "clipartbrushcolor": str(spec["decoration_color"])})
    else:
        a.update({"decorationstyle": "0", "decorationspacepercentage": "100.0",
                  "decorationalignment": "0", "decorationscale": "1.00"})
    pen = ET.Element("pen", {k: a[k] for k in ("type", "id", "name", "color", "style")})
    for k in ("stylepattern", "width"):
        if k in a:
            pen.set(k, a[k])
    ET.SubElement(pen, "clipart", {"data": data})
    for k, v in a.items():
        if k not in pen.attrib:
            pen.set(k, v)
    return pen


def library_brush(bid, name, spec):
    """`<brush type="98">` as cCustomBrush.SaveTo writes it (cBrush.vb:1561-1621)."""
    color = str(spec["color"])
    bg = spec.get("background_color")
    br = ET.Element("brush", {"type": USER, "id": bid, "name": name, "color": color})
    if spec.get("pattern"):
        p = spec["pattern"]
        br.set("backgroundcolor", str(TRANSPARENT if bg is None else bg))
        br.set("hatchtype", HATCH_PATTERN)
        br.set("patterntype", str(themes.PATTERN_TYPES[p["type"]]))
        br.set("patternpenstyle", str(themes.PATTERN_PEN_STYLES[p["pen_style"]]))
        br.set("patterndensity", _n2(p["density"]))
        br.set("patternzoomfactor", "%.4f" % p["zoom"])
        br.set("patternanglemode", "0")
        br.set("patternangle", _n2(p["angle"]))
        ET.SubElement(br, "parameters")
        br.set("clipartalternativecolor", color)
    elif spec.get("solid") or not spec.get("svg"):
        br.set("backgroundcolor", "0")
        br.set("hatchtype", HATCH_SOLID)
    else:
        with open(spec["svg"], "rb") as f:
            data = theme_svg.compact_svg(f.read())
        br.set("backgroundcolor", str(TRANSPARENT if bg is None else bg))
        br.set("hatchtype", HATCH_CLIPART)
        ET.SubElement(br, "clipart", {"data": data})
        br.set("clipartdensity", _n2(spec["density"]))
        br.set("clipartzoomfactor", "%.4f" % spec["zoom"])
        br.set("clipartanglemode", str(themes.ANGLE_MODES[spec["angle_mode"]]))
        if spec["angle_mode"] == "fixed":
            br.set("clipartangle", _n2(spec["angle"]))
        crop = themes.CLIPART_CROPS[spec["crop"]]
        if crop:
            br.set("clipartcrop", str(crop))
        if spec["position"] != "random":
            br.set("clipartposition", str(themes.CLIPART_POSITIONS[spec["position"]]))
        br.set("clipartalternativecolor", color)
    return br


def lib_id(theme_id, kind, key, builtin):
    return "tema-%s-%s-%s-%s" % (theme_id, kind, key, builtin)


# --------------------------------------------------------------------------
# undo a previous theme

def undo(root, state):
    """Undo what a previous run wrote. -> (restored items, removed pool ids)."""
    state = state or {}
    glyphs = set(state.get("glyphs") or [])
    orig = state.get("orig") or {}
    lib = {"pen": state.get("pens") or {}, "brush": state.get("brushes") or {}}
    cl, pool = _pool(root)
    n = 0
    for _design, item in iter_items(root):
        touched = False
        for tag in ("pen", "brush"):
            el = item.find(tag)
            if el is not None and el.get("type") == USER and el.get("id") in lib[tag]:
                el.set("type", str(lib[tag][el.get("id")]))
                el.attrib.pop("id", None)
                touched = True
        if item.get("type") == SIGN_ITEM:
            pen, brush = item.find("pen"), item.find("brush")
            if is_ours(pen):
                _replace(item, pen, ET.Element("pen", {"type": PEN_TIGHT}))
                touched = True
            if is_ours(brush):
                _replace(item, brush, ET.Element("brush", {"type": BRUSH_SIGN}))
                touched = True
            if item.get("data") in glyphs:
                back = orig.get(item.get("sign") or "")
                if back and back in pool:
                    item.set("data", back)
                    item.set("dataformat", "2")
                else:                       # cSurvey takes the gallery default for sign=
                    item.attrib.pop("data", None)
                    item.attrib.pop("dataformat", None)
                touched = True
        n += touched
    for tag, key, created in (("pens", "pen", state.get("pens_created")),
                              ("brushes", "brush", state.get("brushes_created"))):
        el = root.find(tag)
        if el is None or not lib[key]:
            continue
        for e in list(el):
            if e.get("id") in lib[key]:
                el.remove(e)
        reflow(el)
        if created and not len(el):
            root.remove(el)
    removed = []
    if cl is not None and glyphs:
        used = _referenced_ids(root)
        for c in list(cl.findall("clipart")):
            if c.get("id") in glyphs and c.get("id") not in used:
                cl.remove(c)
                removed.append(c.get("id"))
        reflow(cl)
    dp = _design_props(root)
    for name, was in (state.get("centerline") or {}).items():
        el = _prop(dp, name)
        if was is None:
            if el is not None:
                dp.remove(el)
        else:
            if el is None:
                el = ET.SubElement(dp, "item", {"name": name})
            el.set("type", was[0])
            el.text = was[1]
    for name in (PROP_THEME, PROP_STATE):
        el = _prop(dp, name)
        if el is not None:
            dp.remove(el)
    reflow(dp)
    return n, removed


# --------------------------------------------------------------------------
# apply

def _count(d, key):
    d[key] = d.get(key, 0) + 1


def _builtin(el):
    """The element's built-in type as an int, or None (custom/user/absent)."""
    if el is None:
        return None
    try:
        t = int(el.get("type"))
    except (TypeError, ValueError):
        return None
    return None if t in (98, 99) else t


def _theme_sign(root, is_csz, theme, row, targets, rep, extra, added, orig):
    design, item, tdx = row["design"], row["item"], row["tdx"]
    rep["signs"] += 1
    target = targets.get(item.get("sign") or "")
    spec = themes.resolve(theme, "signs", tdx, target)
    method = ("tdx" if tdx and tdx in theme.signs else
              "target" if spec is not None else
              "none")
    _count(rep["lookup"], "%s (%s)" % (method, "recovered" if tdx else row["status"]))
    if spec is None:
        return
    pen, brush = item.find("pen"), item.find("brush")
    if (pen is None or pen.get("type") != PEN_TIGHT
            or brush is None or brush.get("type") != BRUSH_SIGN):
        rep["skipped_custom"] += 1
        rep["notes"].append("%s sign=%s: own pen/brush set in cSurvey - not themed"
                            % (design, item.get("sign")))
        return
    rep["themed"] += 1
    turn = -importer_turn(row.get("prep"), item.get("sign"))
    g = glyph_for(spec, theme.id, turn)
    outline_pen = spec.get("outline_pen")
    if g is None:
        if (spec.get("size") and abs(spec["size"] - 1.0) > 1e-9) or spec.get("rotate"):
            rep["size_ignored"] += 1
    else:
        cid, gname, blob = g
        was_added, ex = nacrt_finish.splice_sign_clipart(root, is_csz, cid, gname, blob)
        extra.update(ex)
        if was_added:
            added.append(cid)
            rep["pool_added"].append("%s %s" % (cid, gname))
        elif cid not in added and cid not in rep["pool_reused"]:
            rep["pool_reused"].append(cid)
        old = item.get("data")
        if old and old != cid and old not in added:
            orig.setdefault(item.get("sign") or "", old)
        item.set("data", cid)
        item.set("dataformat", "2")
        rep["glyph"] += 1
        if turn:
            rep["importer_turn"] = rep.get("importer_turn", 0) + 1
        strokes = stroke_only_paths(blob)
        if outline_pen is None and strokes and not filled_paths(blob):
            outline_pen = True
            note = ("%s: stroke-only glyph - outline pen turned on (auto), drawn in the sign's"
                    " colour at cSurvey's pen width" % spec["key"])
            if note not in rep["notes"]:
                rep["notes"].append(note)
        elif strokes and not outline_pen:
            note = ("%s: %d stroke-only path(s) in the glyph do not print with the pen off"
                    " (outline_pen false)" % (spec["key"], strokes))
            if note not in rep["notes"]:
                rep["notes"].append(note)
    outline_pen = bool(outline_pen)
    color = spec["color"]
    if spec.get("render") == "outline":
        _replace(item, brush, solid_brush(WHITE, theme.id))
        _replace(item, pen, tight_pen(color, theme.id))
        rep["outline"] += 1
    else:
        if color != themes.BLACK:
            _replace(item, brush, solid_brush(color, theme.id))
            rep["colour"] += 1
        if not outline_pen:
            _replace(item, pen, no_pen(color, theme.id))
            rep["pen_off"] += 1
        elif color != themes.BLACK:
            _replace(item, pen, tight_pen(color, theme.id))
        else:
            rep["black_builtin"] += 1


def _section_for(row):
    """'lines' / 'areas' / None: what a non-sign item is themed as."""
    kind, item = row["kind"], row["item"]
    if kind == "line":
        return "lines"
    if kind == "area":
        return "areas"
    if kind is None and not row["tdx"]:          # drawn in cSurvey / no --pre
        if item.find("brush") is not None and item.get("type") == "3":
            return "areas"
        if item.find("pen") is not None and item.get("type") in ("1", "4"):
            return "lines"
    return None


def _theme_line(root, theme, row, rep, libs, state, ltargets):
    item, tdx = row["item"], row["tdx"]
    pen = item.find("pen")
    builtin = _builtin(pen)
    target = PEN_TARGET.get(builtin)
    spec = themes.resolve(theme, "lines", tdx, target)
    sec = rep["lines"]
    if spec is None:
        return
    key = spec["key"]
    if builtin is None:
        sec["skipped"].append("%s: own pen set in cSurvey (type %s) - not themed"
                              % (tdx or target or "?", pen.get("type") if pen is not None else "-"))
        return
    _count(sec["themed"], "%s (%s)" % (key, "tdx" if tdx and tdx in theme.lines else "target"))
    pid = lib_id(theme.id, "line", key, builtin)
    if pid not in state["pens"]:
        width = spec["width"] if spec.get("width") is not None else default_width(root, builtin)
        lib, created = _library(root, "pens", True)
        state["pens_created"] = state["pens_created"] or created
        el = library_pen(pid, "%s%s:%s/%d" % (MARK, theme.id, key, builtin), spec, width,
                         builtin, tdx, ltargets)
        _lib_append(lib, el)
        state["pens"][pid] = builtin
        libs["pens"].append(pid)
    pen.set("type", USER)
    pen.set("id", pid)


def _theme_area(root, theme, row, rep, libs, state):
    item, tdx = row["item"], row["tdx"]
    brush = item.find("brush")
    builtin = _builtin(brush)
    target = BRUSH_TARGET.get(builtin)
    spec = themes.resolve(theme, "areas", tdx, target)
    sec = rep["areas"]
    if spec is None:
        return
    key = spec["key"]
    if builtin is None:
        sec["skipped"].append("%s: own brush set in cSurvey (type %s) - not themed"
                              % (tdx or target or "?",
                                 brush.get("type") if brush is not None else "-"))
        return
    look = "pattern" if spec.get("pattern") else "solid" if (
        spec.get("solid") or not spec.get("svg")) else "tile"
    _count(sec["themed"], "%s (%s, %s)" % (key, "tdx" if tdx and tdx in theme.areas
                                           else "target", look))
    bid = lib_id(theme.id, "area", key, builtin)
    if bid not in state["brushes"]:
        lib, created = _library(root, "brushes", True)
        state["brushes_created"] = state["brushes_created"] or created
        _lib_append(lib, library_brush(bid, "%s%s:%s/%d" % (MARK, theme.id, key, builtin), spec))
        state["brushes"][bid] = builtin
        libs["brushes"].append(bid)
    brush.set("type", USER)
    brush.set("id", bid)


def apply_theme(root, is_csz, theme, names, targets, ltargets=None):
    """Theme signs, lines, areas and the centerline of an undone root.

    names: recovered_names() output. -> (report dict, extra zip entries, added ids)
    """
    ltargets = line_targets() if ltargets is None else ltargets
    rep = {"theme": theme.id, "signs": 0, "lookup": {}, "themed": 0, "glyph": 0,
           "colour": 0, "outline": 0, "black_builtin": 0, "pen_off": 0,
           "skipped_custom": 0, "size_ignored": 0, "pool_added": [], "pool_reused": [],
           "lines": {"themed": {}, "skipped": []}, "areas": {"themed": {}, "skipped": []},
           "library": {"pens": [], "brushes": []}, "notes": []}
    extra, added, orig = {}, [], {}
    state = {"pens": {}, "brushes": {}, "pens_created": False, "brushes_created": False}
    for row in names:
        if row.get("note"):
            note = "%s %s" % (row["design"], row["note"])
            if note not in rep["notes"]:
                rep["notes"].append(note)
        if row["item"].get("type") == SIGN_ITEM:
            _theme_sign(root, is_csz, theme, row, targets, rep, extra, added, orig)
            continue
        section = _section_for(row)
        if section == "lines" and row["item"].find("pen") is not None:
            _theme_line(root, theme, row, rep, rep["library"], state, ltargets)
        elif section == "areas" and row["item"].find("brush") is not None:
            _theme_area(root, theme, row, rep, rep["library"], state)

    # centerline: theme overrides over whatever the file has (KORAK 2 wrote
    # postimport.centerline); the overwritten values are kept for undo.
    dp = _design_props(root)
    cl_orig = {}
    for name in theme.centerline:
        el = _prop(dp, name)
        cl_orig[name] = None if el is None else [el.get("type"), el.text]
    rep["centerline"] = fixer.apply_centerline(root, theme.centerline)

    st = {"glyphs": sorted(added), "orig": orig, "centerline": cl_orig}
    if state["pens"]:
        st.update({"pens": state["pens"], "pens_created": state["pens_created"]})
    if state["brushes"]:
        st.update({"brushes": state["brushes"], "brushes_created": state["brushes_created"]})
    fixer._set_design_property(dp, PROP_THEME, "string", theme.id)
    fixer._set_design_property(dp, PROP_STATE, "string",
                               json.dumps(st, sort_keys=True, separators=(",", ":")))
    reflow(dp)
    return rep, extra, added


def theme_file(in_path, theme_id, pre_path=None, out_path=None, dry_run=False,
               themes_root=None):
    """Load, undo any previous theme, apply theme_id, write. -> report dict."""
    theme = themes.load_theme(theme_id, themes_root)
    root, is_csz, style = nacrt_finish.load_root(in_path)
    if nacrt_finish.not_yet_imported(root):
        raise ValueError("%s has not been imported into cSurvey yet" % in_path)
    prev_id, state = read_state(root)
    names = recovered_names(pre_path, in_path, root)
    restored, removed = undo(root, state)
    rep, extra, added = apply_theme(root, is_csz, theme, names, sign_targets())
    rep.update({"input": in_path, "output": None if dry_run else out_path,
                "previous_theme": prev_id, "undone_items": restored,
                "pool_removed": removed,
                "recovery": _recovery_counts(names)})
    if not dry_run:
        drop = {"_data/cliparts/%s.svg" % i for i in removed if i not in added}
        write(root, in_path, out_path, is_csz, style, extra, drop)
    return rep


def _recovery_counts(names):
    out = {}
    for row in names:
        kind = "sign" if row["item"].get("type") == SIGN_ITEM else "other"
        _count(out, "%s %s" % (kind, "recovered" if row["tdx"] else row["status"]))
    return out


def write(root, src, out, is_csz, style, extra, drop):
    data = style.render(root)
    if is_csz:
        tmp = out + ".tmp"
        with zipfile.ZipFile(src) as zin, \
                zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                n = info.filename
                if n == nacrt_finish.DATA_ENTRY or n in extra or n in drop \
                        or n.replace("\\", "/") in drop:
                    continue
                zout.writestr(info, zin.read(n))
            zout.writestr(nacrt_finish.DATA_ENTRY, data)
            for name in sorted(extra):
                zout.writestr(name, extra[name])
        os.replace(tmp, out)
    else:
        with open(out, "wb") as f:
            f.write(data)


def default_out(in_path, theme_id, themes_root=None):
    base, ext = os.path.splitext(in_path)
    for tid in sorted(themes.list_themes(themes_root), key=len, reverse=True):
        if base.endswith("_" + tid):
            base = base[:-len(tid) - 1]
            break
    return "%s_%s%s" % (base, theme_id, ext)


def print_report(rep, out=sys.stdout):
    w = out.write
    w("%s  tema %s%s\n" % (rep["output"] or "(dry run)", rep["theme"],
                            "  (bila: %s)" % rep["previous_theme"] if rep["previous_theme"] else ""))
    w("  imena: %s\n" % ", ".join("%s %d" % kv for kv in sorted(rep["recovery"].items())))
    w("  znakovi: %d, trazenje: %s\n" % (rep["signs"], ", ".join(
        "%s %d" % kv for kv in sorted(rep["lookup"].items())) or "-"))
    w("  tematizirano %d: glif %d, boja %d, obrub %d, bez olovke %d, "
      "crno (ugradeno) %d, preskoceno (rucno) %d\n"
      % (rep["themed"], rep["glyph"], rep["colour"], rep["outline"], rep["pen_off"],
         rep["black_builtin"], rep["skipped_custom"]))
    w("  bazen: +%d %s, ponovno %d, uklonjeno %d\n" % (
        len(rep["pool_added"]), "; ".join(rep["pool_added"]),
        len(rep["pool_reused"]), len(rep["pool_removed"])))
    for sec, label in (("lines", "linije"), ("areas", "plohe")):
        hits = rep[sec]["themed"]
        w("  %s: %d stavki %s\n" % (label, sum(hits.values()),
                                    ", ".join("%s %d" % kv for kv in sorted(hits.items()))))
        for s in rep[sec]["skipped"]:
            w("    preskoceno: %s\n" % s)
    w("  knjiznica: %d olovaka, %d cetki\n" % (len(rep["library"]["pens"]),
                                             len(rep["library"]["brushes"])))
    w("  centerline: %d svojstava; ponisteno iz prethodne teme: %d stavki\n"
      % (rep["centerline"], rep["undone_items"]))
    if rep["size_ignored"]:
        w("  NAPOMENA: size/rotate bez glifa teme zanemaren na %d znakova\n"
          % rep["size_ignored"])
    for n in rep["notes"]:
        w("  NAPOMENA: %s\n" % n)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply", help="theme a post-import .csx/.csz")
    a.add_argument("input")
    a.add_argument("--theme", required=True)
    a.add_argument("--pre", help="pre-import file for TopoDroid name recovery")
    a.add_argument("-o", "--out")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--json", help="write the report as JSON here")
    a.add_argument("--themes-root")
    args = ap.parse_args(argv)
    out = args.out or default_out(args.input, args.theme, args.themes_root)
    if not args.dry_run and os.path.abspath(out) == os.path.abspath(args.input):
        print("ERROR: output must differ from input", file=sys.stderr)
        return 1
    if not args.pre:
        print("WARNING: no --pre - TopoDroid names not recovered, cSurvey targets only",
              file=sys.stderr)
    try:
        rep = theme_file(args.input, args.theme, args.pre, out, args.dry_run,
                         args.themes_root)
    except themes.ThemeError as e:
        print("ERROR: theme %s: %s" % (args.theme, e), file=sys.stderr)
        return 1
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
    print_report(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
