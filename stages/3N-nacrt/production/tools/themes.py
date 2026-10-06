#!/usr/bin/env python3
"""Symbol themes for cSurvey: format, loader and validator (project 0007, task T2).

A theme is a folder of content files, applied after import (KORAK 2, brief
section 3.2). This module only *reads* themes; writing them into a survey is
`theme_apply.py` (T3).

Layout::

    production/themes/<id>/          (in the kit: csurvey_alati/teme/<id>/)
      theme.json
      signs/  lines/  areas/         theme_svg.py split output, each with index.json
                                     (key -> file name; ':' in a key is '@' in a file name)

theme.json (keys starting with `_` are comments, everywhere)::

    {
      "name": "Boja",                  required, display name
      "extends": "base-id",            optional; deep merge, the child wins; cycles rejected
      "monochrome": "#000000",         optional; forced on every sign/line/area colour,
                                       decoration colour and every centerline colour
      "default_color": "#000000",      optional; colour of an entry that names none (default black)

      "signs": { KEY: {
          "svg": "signs/x.svg" | null, path relative to this theme's folder; omitted ->
                                       signs/index.json[KEY] if listed; null -> built-in glyph
          "color": COLOUR,
          "size": 1.0,                 optional factor on the glyph size (baked into
                                       the glyph's csurvey:scale by theme_apply.py)
          "render": "fill",            fill (default) | outline: brush white, the pen in
                                       the colour, so a filled shape reads as its outline
          "outline_pen": false,        optional; cSurvey's pen traced round every path of the
                                       glyph. Unset for fill = auto: off (only the fills
                                       paint: a style-None pen) unless the glyph has strokes
                                       and no fills; always true for outline
          "rotate": 0 } },             optional extra degrees, clockwise as drawn; baked into
                                       the glyph's coordinates by theme_apply.py, which also
                                       undoes the importer's +90 for air-draught/water-flow
                                       (draw every glyph as it looks at orientation 0)

      "lines": { KEY: {
          "svg": "lines/x.svg" | null, the decoration unit; null -> no decoration
          "color": COLOUR,             base stroke colour
          "width": 0.1,                optional base stroke width; omitted -> keep the item's
          "style": "solid",            solid|dash|dot|dashdot|dashdotdot|custom|none
                                       (none = base stroke off: the double-line meander case)
          "dash": [4, 2],              only and required with style custom (multiples of width)
          "decoration": {              only with an svg; the unit is drawn pointing away from
                                       the line, the line along its bottom edge
              "spacing_pct": 3000,     cSurvey's decorationspacepercentage (raw; see README)
              "scale": 1,              decorationscale (unit size: svg units x scale / 40 m)
              "alignment": "auto",     auto (the side of the item's built-in pen) |
                                       outer | center | inner
              "flip": false,           mirror the unit across the line (auto with alignment auto)
              "distance_pct": 0, "position": "behind|above" },
          "decoration_color": COLOUR } },   default: the line colour

      "areas": { KEY: {
          "svg": "areas/x.svg" | null, the scatter tile (clipart hatch)
          "color": COLOUR, "background_color": COLOUR,   background optional
          "density": 1, "zoom": 1, "angle_mode": "random|fixed", "angle": 0,
          "position": "random|fixed", "crop": "subitems|full|none" }
        | {"solid": true, "color": COLOUR}              plain fill
        | {"pattern": {"type": "lines|crossed", "angle": 45, "density": 1,
                       "zoom": 1, "pen_style": "solid|dash|dot|dashdot"},
           "color": COLOUR, "background_color": COLOUR} },  parametric hatch (B/W water)

      "centerline": { NAME: value },   merged over tdx-mapping.json postimport.centerline;
                                       NAME from fix_imported_linetypes.CENTERLINE_TYPES
      "scale_rules": { "200": { "DesignSoilScaleFactor": 0.8 } }
                                       per print scale (100/200/250/300/400/500), design
                                       property multipliers from SCALE_RULE_PROPERTIES
    }

COLOUR is "#RRGGBB", "#AARRGGBB" or a signed 32-bit ARGB int (the convention of
postimport.centerline: red = -65536). Everything resolves to that int.

KEY (signs/lines/areas) is a TopoDroid name of that kind from
tdx-mapping-catalog.json `tdx[*].name` (subtypes included: `slope:steep`), or a
cSurvey target name `targets.<kind>[*].to` (points compared without - and _).
A child theme may set an entry to null to drop the inherited one.

Lookup per item (brief 3.1, T8): the recovered TopoDroid name, else the cSurvey
target name, else None (built-in look).

  python themes.py list
  python themes.py check [ID]                 all themes when ID is omitted; exit 1 on errors
  python themes.py show ID [--kind signs|lines|areas|centerline|scale_rules]

Stdlib only.
"""

import argparse
import copy
import json
import os
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
CATALOG = os.path.join(HERE, "tdx-mapping-catalog.json")
MAPPING = os.path.join(HERE, "tdx-mapping.json")

KINDS = ("signs", "lines", "areas")
CATALOG_KIND = {"signs": "point", "lines": "line", "areas": "area"}
KIND_ALIASES = {"sign": "signs", "point": "signs", "points": "signs",
                "line": "lines", "area": "areas"}

TOP_FIELDS = {"name", "extends", "monochrome", "default_color", "description",
              "signs", "lines", "areas", "centerline", "scale_rules"}
SIGN_FIELDS = {"svg", "color", "size", "render", "outline_pen", "rotate"}
SIGN_RENDERS = ("fill", "outline")    # outline: white brush, pen in the colour (brief 3.8)
LINE_FIELDS = {"svg", "color", "width", "style", "dash", "decoration", "decoration_color"}
DECORATION_FIELDS = {"spacing_pct", "scale", "alignment", "flip", "distance_pct", "position"}
AREA_FIELDS = {"svg", "color", "background_color", "density", "zoom", "angle_mode",
               "angle", "position", "crop", "solid", "pattern"}
PATTERN_FIELDS = {"type", "angle", "density", "zoom", "pen_style"}

# cPen.PenStylesEnum (cPen.vb:1241-1253)
LINE_STYLES = {"solid": 0, "dash": 1, "dot": 2, "dashdot": 3, "dashdotdot": 4,
               "none": 98, "custom": 99}
ALIGNMENTS = {"outer": 0, "center": 1, "inner": 2}      # cPen.DecorationAlignmentEnum
DECORATION_ALIGNMENTS = ("auto",) + tuple(ALIGNMENTS)   # auto: theme_apply.PEN_SIDE
POSITIONS = {"behind": 0, "above": 1}                   # cPen.DecorationPositionEnum
ANGLE_MODES = {"random": 0, "fixed": 1}                 # cBrush.ClipartAngleModeEnum
CLIPART_POSITIONS = {"random": 0, "fixed": 1}           # cBrush.ClipartPositionEnum
CLIPART_CROPS = {"none": 0, "full": 1, "subitems": 2}   # cBrush.ClipartCropEnum
PATTERN_TYPES = {"lines": 0, "crossed": 1}              # cBrush.PatternTypeEnum
PATTERN_PEN_STYLES = {"solid": 0, "dash": 1, "dot": 2, "dashdot": 3}   # cBrush.pRender

# Defaults. spacing 3000 is what cSurvey's own overhang/cliff/meander pens use
# (cPens.vb:346-430): on a spline it puts ~2 unit widths of gap between units.
# cPen's bare default of 100 would pile the units on top of each other (README,
# "Line decorations"). Brush defaults are cSurvey's (cBrush.vb:1430-1431,
# 731-738); crop subitems is what its Pebbles/Debrits brushes use (cBrushes.vb:97-115).
DECORATION_DEFAULTS = {"spacing_pct": 3000.0, "scale": 1.0, "alignment": "auto",
                       "flip": None, "distance_pct": 0.0, "position": "behind"}
AREA_DEFAULTS = {"density": 1.0, "zoom": 1.0, "angle_mode": "random", "angle": 0.0,
                 "position": "random", "crop": "subitems"}
PATTERN_DEFAULTS = {"type": "lines", "angle": 45.0, "density": 1.0, "zoom": 1.0,
                    "pen_style": "solid"}    # = cSurvey's Water brush (cBrushes.vb:55-63)

PRINT_SCALES = {100, 200, 250, 300, 400, 500}
# design properties a scale rule may override (names as cSurvey reads them)
SCALE_RULE_PROPERTIES = {
    "DesignSoilScaleFactor", "DesignTerrainLevelScaleFactor", "DesignSignScaleFactor",
    "DesignClipartScaleFactor", "DesignTextScaleFactor", "DesignTextureScaleFactor",
    "BaseLineWidthScaleFactor", "BaseHeavyLinesScaleFactor", "BaseMediumLinesScaleFactor",
    "BaseLightLinesScaleFactor", "BaseUltraLightLinesScaleFactor", "BaseGeologyLinesScaleFactor",
    "BrushLinesScaleFactor",
}

BLACK = -16777216   # 0xFF000000 as a signed ARGB int


class ThemeError(ValueError):
    """A theme failed to load; .errors holds every problem found."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def default_themes_root():
    """production/themes in the repo; csurvey_alati/teme next to the tools in the kit."""
    for cand in (os.path.join(HERE, "..", "themes"), os.path.join(HERE, "teme")):
        if os.path.isdir(cand):
            return os.path.abspath(cand)
    return os.path.abspath(os.path.join(HERE, "..", "themes"))


def _centerline_types():
    import fix_imported_linetypes as fixer   # the vocabulary KORAK 2 writes
    return fixer.CENTERLINE_TYPES


# --------------------------------------------------------------------------
# colours

def to_argb(value):
    """'#RRGGBB' / '#AARRGGBB' / int -> signed 32-bit ARGB int. ValueError otherwise."""
    if isinstance(value, bool):
        raise ValueError("colour must be '#RRGGBB', '#AARRGGBB' or an ARGB int, not %r" % value)
    if isinstance(value, int):
        if not -2 ** 31 <= value < 2 ** 32:
            raise ValueError("colour int %r out of 32-bit range" % value)
        n = value & 0xFFFFFFFF
    elif isinstance(value, str) and value.startswith("#") and len(value) in (7, 9):
        try:
            n = int(value[1:], 16)
        except ValueError:
            raise ValueError("colour %r is not hex" % value) from None
        if len(value) == 7:
            n |= 0xFF000000
    else:
        raise ValueError("colour must be '#RRGGBB', '#AARRGGBB' or an ARGB int, not %r" % (value,))
    return n - 2 ** 32 if n >= 2 ** 31 else n


def argb_hex(n):
    return "#%08X" % (n & 0xFFFFFFFF)


# --------------------------------------------------------------------------
# keys

def _norm(s):
    return s.lower().replace("-", "").replace("_", "")


class KeyIndex:
    """Valid theme keys per kind, from tdx-mapping-catalog.json."""

    def __init__(self, catalog_path=CATALOG):
        with open(catalog_path, encoding="utf-8") as f:
            cat = json.load(f)
        self.tdx = {k: set() for k in KINDS}
        self.targets = {k: set() for k in KINDS}
        for row in cat["tdx"]:
            for kind, ck in CATALOG_KIND.items():
                if row.get("kind") == ck:
                    self.tdx[kind].add(row["name"])
        for kind, ck in CATALOG_KIND.items():
            for t in cat["targets"].get(ck, []):
                self.targets[kind].add(_norm(t["to"]) if kind == "signs" else t["to"])

    def is_target(self, kind, key):
        return (_norm(key) if kind == "signs" else key) in self.targets[kind]

    def valid(self, kind, key):
        return key in self.tdx[kind] or self.is_target(kind, key)


_KEYS = None


def _keys():
    global _KEYS
    if _KEYS is None:
        _KEYS = KeyIndex()
    return _KEYS


# --------------------------------------------------------------------------
# loading

def _is_comment(key):
    return isinstance(key, str) and key.startswith("_")


def _read_json(path, errors, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        errors.append("%s: cannot read (%s)" % (what, e))
    except ValueError as e:
        errors.append("%s: not valid JSON (%s)" % (what, e))
    return None


def _theme_path(theme_dir, rel, where, errors):
    """Resolve a relative svg path inside theme_dir; None (with an error) if it escapes."""
    if not isinstance(rel, str) or not rel:
        errors.append("%s: svg must be a relative path string or null" % where)
        return None
    if os.path.isabs(rel) or rel.replace("\\", "/").startswith("/"):
        errors.append("%s: svg %r must be relative to the theme folder" % (where, rel))
        return None
    full = os.path.normpath(os.path.join(theme_dir, rel))
    if os.path.commonpath([full, os.path.normpath(theme_dir)]) != os.path.normpath(theme_dir):
        errors.append("%s: svg %r points outside the theme folder" % (where, rel))
        return None
    return full


def _layer(theme_id, root, errors):
    """One theme.json with its svg paths made absolute (per layer, before merging)."""
    theme_dir = os.path.join(root, theme_id)
    path = os.path.join(theme_dir, "theme.json")
    if not os.path.isfile(path):
        errors.append("%s: no theme.json in %s" % (theme_id, theme_dir))
        return None
    raw = _read_json(path, errors, "%s/theme.json" % theme_id)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        errors.append("%s/theme.json: must be an object" % theme_id)
        return None
    for k in raw:
        if not _is_comment(k) and k not in TOP_FIELDS:
            errors.append("%s: unknown top-level field %r" % (theme_id, k))
    if not isinstance(raw.get("name"), str) or not raw.get("name"):
        errors.append("%s: name is required (a string)" % theme_id)
    ext = raw.get("extends")
    if ext is not None and (not isinstance(ext, str) or not ext):
        errors.append("%s: extends must be a theme id string or null" % theme_id)

    keys = _keys()
    layer = {k: v for k, v in raw.items() if not _is_comment(k)}
    for kind in KINDS:
        section = raw.get(kind)
        if section is None:
            continue
        if not isinstance(section, dict):
            errors.append("%s.%s: must be an object" % (theme_id, kind))
            layer.pop(kind, None)
            continue
        index = {}
        index_path = os.path.join(theme_dir, kind, "index.json")
        if os.path.isfile(index_path):
            index = _read_json(index_path, errors, "%s/%s/index.json" % (theme_id, kind)) or {}
        out = {}
        for key, entry in section.items():
            if _is_comment(key):
                continue
            where = "%s.%s.%s" % (theme_id, kind, key)
            if not keys.valid(kind, key):
                errors.append("%s: unknown key - not a TopoDroid %s name nor a cSurvey %s target"
                              " in tdx-mapping-catalog.json" % (where, CATALOG_KIND[kind],
                                                              CATALOG_KIND[kind]))
                continue
            if entry is None:
                out[key] = None           # drop the inherited entry
                continue
            if not isinstance(entry, dict):
                errors.append("%s: entry must be an object or null" % where)
                continue
            entry = {k: v for k, v in entry.items() if not _is_comment(k)}
            if "svg" in entry:
                if entry["svg"] is not None:
                    entry["svg"] = _theme_path(theme_dir, entry["svg"], where, errors)
            elif key in index and not (kind == "areas" and (entry.get("solid")
                                                             or entry.get("pattern"))):
                entry["svg"] = _theme_path(theme_dir, os.path.join(kind, index[key]), where, errors)
            out[key] = entry
        layer[kind] = out
    return layer


def _merge(base, over):
    """Deep merge of dicts; over wins; None in over deletes the key."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if v is None and k in KINDS:
            continue
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _chain(theme_id, root, errors):
    """Layers from the root ancestor to theme_id; None on a cycle or a missing parent."""
    chain, seen, tid = [], [], theme_id
    while tid is not None:
        if tid in seen:
            errors.append("%s: extends cycle %s" % (theme_id, " -> ".join(seen + [tid])))
            return None
        seen.append(tid)
        layer = _layer(tid, root, errors)
        if layer is None:
            if tid != theme_id:
                errors.append("%s: extends %r, which cannot be loaded" % (seen[-2], tid))
            return None
        chain.append((tid, layer))
        tid = layer.get("extends")
    return list(reversed(chain))


# --------------------------------------------------------------------------
# validation of the merged result

def _num(entry, field, where, errors, positive=False, default=None):
    v = entry.get(field, default)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        errors.append("%s.%s: must be a number" % (where, field))
        return None
    if positive and v <= 0:
        errors.append("%s.%s: must be > 0" % (where, field))
        return None
    return float(v)


def _enum(entry, field, allowed, where, errors, default=None):
    v = entry.get(field, default)
    if v is None:
        return None
    if v not in allowed:
        errors.append("%s.%s: %r is not one of %s" % (where, field, v, "|".join(allowed)))
        return None
    return v


def _colour(entry, field, where, errors, default=None):
    if field not in entry or entry[field] is None:
        return default
    try:
        return to_argb(entry[field])
    except ValueError as e:
        errors.append("%s.%s: %s" % (where, field, e))
        return default


def _unknown_fields(entry, allowed, where, errors):
    for k in entry:
        if k not in allowed:
            errors.append("%s: unknown field %r (allowed: %s)" % (where, k, ", ".join(sorted(allowed))))


def _svg(entry, where, errors):
    p = entry.get("svg")
    if p is not None and not os.path.isfile(p):
        errors.append("%s: svg not found: %s" % (where, p))
    return p


def _sign_spec(key, entry, default_color, where, errors):
    _unknown_fields(entry, SIGN_FIELDS, where, errors)
    render = _enum(entry, "render", SIGN_RENDERS, where, errors, "fill")
    pen = entry.get("outline_pen")
    if pen is None:
        pen = True if render == "outline" else None     # None = auto (theme_apply)
    elif not isinstance(pen, bool):
        errors.append("%s.outline_pen: must be true or false" % where)
        pen = True if render == "outline" else None
    elif render == "outline" and not pen:
        errors.append("%s.outline_pen: render outline draws only the pen - it cannot be false"
                      % where)
        pen = True
    rotate = _num(entry, "rotate", where, errors)
    if rotate is not None:
        rotate %= 360.0
        if abs(rotate) < 1e-9 or abs(rotate - 360.0) < 1e-9:
            rotate = None
    return {"key": key, "svg": _svg(entry, where, errors),
            "color": _colour(entry, "color", where, errors, default_color),
            "size": _num(entry, "size", where, errors, positive=True),
            "render": render, "outline_pen": pen, "rotate": rotate}


def _line_spec(key, entry, default_color, where, errors):
    _unknown_fields(entry, LINE_FIELDS, where, errors)
    svg = _svg(entry, where, errors)
    color = _colour(entry, "color", where, errors, default_color)
    style = _enum(entry, "style", LINE_STYLES, where, errors, default="solid")
    dash = entry.get("dash")
    if style == "custom":
        if (not isinstance(dash, list) or len(dash) < 2 or len(dash) % 2
                or not all(isinstance(d, (int, float)) and not isinstance(d, bool) and d > 0
                           for d in dash)):
            errors.append("%s.dash: style custom needs an even-length list of positive numbers"
                          " (dash, gap, ...)" % where)
            dash = None
        else:
            dash = [float(d) for d in dash]
    elif dash is not None:
        errors.append("%s.dash: only allowed with style custom" % where)
        dash = None
    deco = entry.get("decoration")
    decoration = None
    if deco is not None and not isinstance(deco, dict):
        errors.append("%s.decoration: must be an object" % where)
        deco = None
    if deco is not None and svg is None:
        errors.append("%s.decoration: set but the line has no svg decoration unit" % where)
    if svg is not None:
        deco = {k: v for k, v in (deco or {}).items() if not _is_comment(k)}
        dw = where + ".decoration"
        _unknown_fields(deco, DECORATION_FIELDS, dw, errors)
        decoration = {
            "spacing_pct": _num(deco, "spacing_pct", dw, errors,
                                default=DECORATION_DEFAULTS["spacing_pct"]),
            "scale": _num(deco, "scale", dw, errors, positive=True,
                          default=DECORATION_DEFAULTS["scale"]),
            "alignment": _enum(deco, "alignment", DECORATION_ALIGNMENTS, dw, errors,
                               default=DECORATION_DEFAULTS["alignment"]),
            "flip": _bool(deco, "flip", dw, errors),
            "distance_pct": _num(deco, "distance_pct", dw, errors,
                                 default=DECORATION_DEFAULTS["distance_pct"]),
            "position": _enum(deco, "position", POSITIONS, dw, errors,
                              default=DECORATION_DEFAULTS["position"]),
        }
        if decoration["spacing_pct"] is not None and decoration["spacing_pct"] < 0:
            errors.append("%s.spacing_pct: must be >= 0" % dw)
    elif "decoration_color" in entry:
        errors.append("%s.decoration_color: set but the line has no svg decoration unit" % where)
    if style == "none" and svg is None:
        errors.append("%s: style none with no decoration svg draws nothing" % where)
    return {"key": key, "svg": svg, "color": color,
            "width": _num(entry, "width", where, errors, positive=True),
            "style": style, "dash": dash, "decoration": decoration,
            "decoration_color": _colour(entry, "decoration_color", where, errors, color)}


def _bool(entry, field, where, errors):
    v = entry.get(field)
    if v is not None and not isinstance(v, bool):
        errors.append("%s.%s: must be true or false" % (where, field))
        return None
    return v


_NO_TILE = {"density": None, "zoom": None, "angle_mode": None, "angle": None,
            "position": None, "crop": None}


def _pattern(pat, where, errors):
    if not isinstance(pat, dict):
        errors.append("%s: must be an object {type, angle, density, zoom, pen_style}" % where)
        return None
    pat = {k: v for k, v in pat.items() if not _is_comment(k)}
    _unknown_fields(pat, PATTERN_FIELDS, where, errors)
    return {"type": _enum(pat, "type", PATTERN_TYPES, where, errors, PATTERN_DEFAULTS["type"]),
            "angle": _num(pat, "angle", where, errors, default=PATTERN_DEFAULTS["angle"]),
            "density": _num(pat, "density", where, errors, positive=True,
                            default=PATTERN_DEFAULTS["density"]),
            "zoom": _num(pat, "zoom", where, errors, positive=True,
                         default=PATTERN_DEFAULTS["zoom"]),
            "pen_style": _enum(pat, "pen_style", PATTERN_PEN_STYLES, where, errors,
                               PATTERN_DEFAULTS["pen_style"])}


def _area_spec(key, entry, default_color, where, errors):
    """One of three looks: a scatter tile (svg), a solid fill, or a parametric
    pattern hatch - mutually exclusive (brief 3.8)."""
    _unknown_fields(entry, AREA_FIELDS, where, errors)
    color = _colour(entry, "color", where, errors, default_color)
    solid = entry.get("solid", False)
    if not isinstance(solid, bool):
        errors.append("%s.solid: must be true or false" % where)
        solid = False
    pattern = entry.get("pattern")
    looks = [n for n, on in (("svg", entry.get("svg") is not None), ("solid", solid),
                             ("pattern", pattern is not None)) if on]
    if len(looks) > 1:
        errors.append("%s: %s are mutually exclusive (one look per area; a child theme"
                      " clears the inherited one with null)" % (where, " and ".join(looks)))
    if pattern is not None:
        extra = sorted(set(entry) - {"pattern", "color", "background_color", "svg"})
        if extra:
            errors.append("%s: a pattern area takes only pattern, color, background_color"
                          " (not %s)" % (where, ", ".join(extra)))
        return dict(_NO_TILE, key=key, solid=False, svg=None, color=color,
                    background_color=_colour(entry, "background_color", where, errors, None),
                    pattern=_pattern(pattern, where + ".pattern", errors))
    if solid:
        extra = sorted(set(entry) - {"solid", "color", "svg"})
        if extra:
            errors.append("%s: a solid area takes only color (not %s)" % (where, ", ".join(extra)))
        return dict(_NO_TILE, key=key, solid=True, svg=None, color=color,
                    background_color=None, pattern=None)
    return {"key": key, "solid": False, "pattern": None,
            "svg": _svg(entry, where, errors), "color": color,
            "background_color": _colour(entry, "background_color", where, errors, None),
            "density": _num(entry, "density", where, errors, positive=True,
                            default=AREA_DEFAULTS["density"]),
            "zoom": _num(entry, "zoom", where, errors, positive=True,
                         default=AREA_DEFAULTS["zoom"]),
            "angle_mode": _enum(entry, "angle_mode", ANGLE_MODES, where, errors,
                                default=AREA_DEFAULTS["angle_mode"]),
            "angle": _num(entry, "angle", where, errors, default=AREA_DEFAULTS["angle"]),
            "position": _enum(entry, "position", CLIPART_POSITIONS, where, errors,
                              default=AREA_DEFAULTS["position"]),
            "crop": _enum(entry, "crop", CLIPART_CROPS, where, errors,
                          default=AREA_DEFAULTS["crop"])}


def _centerline(section, where, errors):
    types = _centerline_types()
    out = {}
    if section is None:
        return out
    if not isinstance(section, dict):
        errors.append("%s.centerline: must be an object" % where)
        return out
    for name, value in section.items():
        if _is_comment(name):
            continue
        w = "%s.centerline.%s" % (where, name)
        t = types.get(name)
        if t is None:
            errors.append("%s: unknown key (see fix_imported_linetypes.CENTERLINE_TYPES)" % w)
        elif t == "color":
            try:
                out[name] = to_argb(value)
            except ValueError as e:
                errors.append("%s: %s" % (w, e))
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append("%s: must be a number" % w)
        elif t == "integer" and not isinstance(value, int):
            errors.append("%s: must be an integer" % w)
        else:
            out[name] = value
    return out


def _scale_rules(section, where, errors):
    out = {}
    if section is None:
        return out
    if not isinstance(section, dict):
        errors.append("%s.scale_rules: must be an object" % where)
        return out
    for scale, props in section.items():
        if _is_comment(scale):
            continue
        w = "%s.scale_rules.%s" % (where, scale)
        try:
            s = int(scale)
        except (TypeError, ValueError):
            s = None
        if s not in PRINT_SCALES:
            errors.append("%s: scale must be one of %s" % (w, sorted(PRINT_SCALES)))
            continue
        if not isinstance(props, dict):
            errors.append("%s: must be an object {property: number}" % w)
            continue
        rule = {}
        for name, value in props.items():
            if _is_comment(name):
                continue
            if name not in SCALE_RULE_PROPERTIES:
                errors.append("%s.%s: not an allowed scale-rule property (%s)"
                              % (w, name, ", ".join(sorted(SCALE_RULE_PROPERTIES))))
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                errors.append("%s.%s: must be a number > 0" % (w, name))
            else:
                rule[name] = float(value)
        out[s] = rule
    return out


# --------------------------------------------------------------------------
# public API

class ResolvedTheme:
    """A fully merged, validated theme. Colours are signed ARGB ints, svg paths absolute.

    signs/lines/areas: key -> spec dict (see _sign_spec/_line_spec/_area_spec);
    centerline: overrides to merge over tdx-mapping.json postimport.centerline;
    scale_rules: {print scale int: {design property: factor}}.
    """

    def __init__(self, theme_id, name, chain, folder, monochrome, default_color,
                 signs, lines, areas, centerline, scale_rules):
        self.id = theme_id
        self.name = name
        self.chain = chain              # ids, root ancestor first
        self.folder = folder
        self.monochrome = monochrome
        self.default_color = default_color
        self.signs = signs
        self.lines = lines
        self.areas = areas
        self.centerline = centerline
        self.scale_rules = scale_rules

    def section(self, kind):
        return getattr(self, _kind(kind))

    def centerline_over(self, base):
        """postimport.centerline (base) with this theme's overrides on top."""
        out = dict(base or {})
        out.update(self.centerline)
        return out

    def as_dict(self, hex_colours=False):
        def conv(v, field=None):
            if isinstance(v, dict):
                return {k: conv(x, k) for k, x in v.items()}
            if isinstance(v, list):
                return [conv(x) for x in v]
            if (hex_colours and isinstance(v, int) and not isinstance(v, bool) and field
                    and ("color" in field.lower() or field == "monochrome")):
                return argb_hex(v)
            return v
        return conv({"id": self.id, "name": self.name, "chain": self.chain,
                     "monochrome": self.monochrome, "default_color": self.default_color,
                     "signs": self.signs, "lines": self.lines, "areas": self.areas,
                     "centerline": self.centerline,
                     "scale_rules": {str(k): v for k, v in self.scale_rules.items()}})


def _kind(kind):
    k = KIND_ALIASES.get(kind, kind)
    if k not in KINDS:
        raise ValueError("kind must be one of %s, not %r" % (", ".join(KINDS), kind))
    return k


def _load(theme_id, themes_root, errors):
    root = os.path.abspath(themes_root or default_themes_root())
    chain = _chain(theme_id, root, errors)
    if chain is None:
        return None
    merged = {}
    for _tid, layer in chain:
        layer = dict(layer)
        layer.pop("extends", None)
        merged = _merge(merged, layer)
    where = theme_id
    mono = None
    if merged.get("monochrome") is not None:
        try:
            mono = to_argb(merged["monochrome"])
        except ValueError as e:
            errors.append("%s.monochrome: %s" % (where, e))
    default_color = _colour(merged, "default_color", where, errors, BLACK)
    if mono is not None:
        default_color = mono

    specs = {}
    builders = {"signs": _sign_spec, "lines": _line_spec, "areas": _area_spec}
    for kind in KINDS:
        specs[kind] = {}
        for key, entry in (merged.get(kind) or {}).items():
            if entry is None:
                continue
            spec = builders[kind](key, entry, default_color, "%s.%s.%s" % (where, kind, key), errors)
            if mono is not None:
                spec["color"] = mono
                if "decoration_color" in spec:
                    spec["decoration_color"] = mono
            specs[kind][key] = spec

    centerline = _centerline(merged.get("centerline"), where, errors)
    if mono is not None:
        for name, t in _centerline_types().items():
            if t == "color":
                centerline[name] = mono
    scale_rules = _scale_rules(merged.get("scale_rules"), where, errors)
    return ResolvedTheme(theme_id, merged.get("name"), [t for t, _ in chain],
                         os.path.join(root, theme_id), mono, default_color,
                         specs["signs"], specs["lines"], specs["areas"], centerline, scale_rules)


def load_theme(theme_id, themes_root=None):
    """Merged, validated theme; raises ThemeError listing every problem."""
    errors = []
    theme = _load(theme_id, themes_root, errors)
    if errors or theme is None:
        raise ThemeError(errors or ["%s: cannot be loaded" % theme_id])
    return theme


def validate(theme_id, themes_root=None):
    """Every problem in a theme (and its ancestors) as strings; [] when clean."""
    errors = []
    _load(theme_id, themes_root, errors)
    return errors


def list_themes(themes_root=None):
    """Theme ids (folders holding a theme.json), sorted."""
    root = themes_root or default_themes_root()
    if not os.path.isdir(root):
        return []
    return sorted(d for d in os.listdir(root)
                  if os.path.isfile(os.path.join(root, d, "theme.json")))


def resolve(theme, kind, tdx_name, target_name):
    """The spec for one item: TopoDroid name first, then the cSurvey target, else None."""
    section = theme.section(kind)
    k = _kind(kind)
    if tdx_name and tdx_name in section:
        return section[tdx_name]
    if target_name:
        if target_name in section:
            return section[target_name]
        if k == "signs":             # point targets are spelt with or without dashes
            want = _norm(target_name)
            keys = _keys()
            hits = sorted((key for key in section
                           if _norm(key) == want and keys.is_target(k, key)),
                          key=lambda key: (key in keys.tdx[k], key))
            if hits:
                return section[hits[0]]
    return None


def unused_svgs(theme):
    """SVG files under the theme's own signs/lines/areas that no entry uses (informational)."""
    used = {os.path.normcase(s["svg"]) for kind in KINDS
            for s in theme.section(kind).values() if s.get("svg")}
    out = []
    for kind in KINDS:
        d = os.path.join(theme.folder, kind)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if f.lower().endswith(".svg") and os.path.normcase(p) not in used:
                    out.append("%s/%s" % (kind, f))
    return out


# --------------------------------------------------------------------------
# CLI

def _cmd_list(args):
    ids = list_themes(args.root)
    if not ids:
        print("no themes under %s" % (args.root or default_themes_root()))
        return 0
    for tid in ids:
        errors = []
        t = _load(tid, args.root, errors)
        if t is None:
            print("%-16s  (cannot load: %s)" % (tid, errors[0] if errors else "?"))
            continue
        print("%-16s  %-16s  extends %-12s  %d signs, %d lines, %d areas%s%s"
              % (tid, t.name, (t.chain[-2] if len(t.chain) > 1 else "-"),
                 len(t.signs), len(t.lines), len(t.areas),
                 ", monochrome %s" % argb_hex(t.monochrome) if t.monochrome is not None else "",
                 "  [%d problems]" % len(errors) if errors else ""))
    return 0


def _cmd_check(args):
    ids = [args.id] if args.id else list_themes(args.root)
    bad = 0
    for tid in ids:
        errors = []
        t = _load(tid, args.root, errors)
        if errors or t is None:
            bad += 1
            print("%s: %d problem(s)" % (tid, len(errors)))
            for e in errors:
                print("  - " + e)
            continue
        print("%s: OK (%d signs, %d lines, %d areas, %d centerline, %d scale rules)"
              % (tid, len(t.signs), len(t.lines), len(t.areas), len(t.centerline),
                 len(t.scale_rules)))
        for f in unused_svgs(t):
            print("  note: %s is in the folder but no entry uses it" % f)
    return 1 if bad else 0


def _cmd_show(args):
    try:
        t = load_theme(args.id, args.root)
    except ThemeError as e:
        print("%s: %d problem(s)" % (args.id, len(e.errors)))
        for x in e.errors:
            print("  - " + x)
        return 1
    d = t.as_dict(hex_colours=True)
    for kind in KINDS:
        for spec in d[kind].values():
            if spec.get("svg"):
                spec["svg"] = os.path.relpath(spec["svg"], t.folder).replace("\\", "/") \
                    if spec["svg"].startswith(t.folder) else spec["svg"]
    if args.kind:
        d = d[args.kind]
    print(json.dumps(d, indent=2, ensure_ascii=False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", help="themes folder (default: %s)" % default_themes_root())
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list the themes")
    p = sub.add_parser("check", help="validate one theme, or all")
    p.add_argument("id", nargs="?")
    p = sub.add_parser("show", help="print the resolved theme (colours as #AARRGGBB)")
    p.add_argument("id")
    p.add_argument("--kind", choices=KINDS + ("centerline", "scale_rules"))
    args = ap.parse_args(argv)
    return {"list": _cmd_list, "check": _cmd_check, "show": _cmd_show}[args.cmd](args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
