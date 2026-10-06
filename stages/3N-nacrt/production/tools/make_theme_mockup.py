#!/usr/bin/env python3
"""Generate the theme mockup: one synthetic TopoDroid survey with every symbol a
theme can reach (project 0007; zoo v4, the successor of project 0002's
symbol zoo v3).

The mockup is the permanent test case for symbol themes (it replaces SB 1103
there). It holds, as a raw TopoDroid .csx export (pre-import):

  * every symbol the 0002 symbol zoo v3 had (ZOO_V3_* below), and
  * every key of every kind (signs, lines, areas) of every theme under
    production/themes - read at run time, so adding a symbol to a theme adds
    it to the mockup. A key that is a cSurvey target rather than a TopoDroid
    name is drawn with the TopoDroid name that spells it (`waterflow` ->
    `water-flow`) or that tdx-mapping.json maps onto it; one with neither is
    reported and skipped.

Layout (plan only; y grows south as in every TopoDroid csx):

  * three sections, top to bottom, each with a heading label:
    ZNAKOVI (points), LINIJE (lines), PLOHE (areas);
  * one slot per symbol, alphabetical within its section, a centerline
    station per slot named after the slot (P00, L00, A00 - the station label
    identifies the slot) and a text label "P07 crystal" with the TopoDroid
    name;
  * points: the sign sits 1.2 m north of its station, the label under it;
  * lines: each symbol twice - a straight 3 m stroke and a full sine wave
    (amplitude 0.45 m) under it, so decoration spacing, meander chords and
    dash patterns can be judged on both;
  * areas: a 2 x 1.5 m rectangle per symbol, so scatter tiles show;
  * every line and area row sits inside a closed `wall` loop: cSurvey prints
    the layers below Borders only inside a cave border (0002 RUNLOG step-04).

The point `section` is label-only (it can make the import fail, 0002); the
line `section` gets the `-scrap` option as in v3.

Usage:
  python make_theme_mockup.py OUTDIR [--name theme-mockup] [--themes-root DIR]

Writes OUTDIR/<name>.csx (raw TopoDroid, import it into cSurvey),
OUTDIR/<name>-key.md (slot table) and OUTDIR/<name>-layout.json (world
coordinates of every slot and section, for cropping prints).

Stdlib only.
"""

import argparse
import json
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import themes                                                   # noqa: E402

CAVE = "THEME_MOCKUP"
SESSION = "20261007_mockup"

# Everything the 0002 symbol zoo v3 drew (make_symbol_zoo.py, 2026-07-19).
ZOO_V3_POINTS = [
    "air-draught", "anchor", "aragonite", "archeo-material", "blocks",
    "clay", "continuation", "crystal", "curtain", "danger", "debris",
    "dig", "entrance", "flowstone", "gradient", "guano", "gypsum",
    "helictite", "ice", "label", "minus", "moonmilk", "mud", "narrow-end",
    "paleo-material", "pebbles", "pillar", "plus", "plus-minus", "popcorn",
    "root", "sand", "scallop", "section", "sink", "snow", "soda-straw",
    "spring", "stalactite", "stalagmite", "user", "wall-calcite", "water",
    "water-drip", "water-flow",
]
ZOO_V3_LINES = [
    "arrow", "border", "ceiling-meander", "chimney", "floor-meander",
    "overhang", "pit", "presumed", "rock-border", "section", "slope",
    "user", "wall", "wall:blocks", "wall:clay", "wall:debris",
    "wall:ice", "wall:presumed", "water", "water-flow",
]
ZOO_V3_AREAS = [
    "blocks", "clay", "debris", "ice", "pebbles", "sand", "snow",
    "user", "water",
]

# (kind, tag letter, heading, columns, slot width m, row pitch m)
SECTIONS = [
    ("signs", "P", "ZNAKOVI – točke (signs)", 10, 3.0, 5.0),
    ("lines", "L", "LINIJE – ravno i krivulja (lines)", 8, 4.0, 6.5),
    ("areas", "A", "PLOHE – površine (areas)", 8, 3.0, 5.0),
]
SECTION_GAP = 5.0          # m between the last row of a section and the next heading
CATALOG_KIND = {"signs": "point", "lines": "line", "areas": "area"}
MAPPING_KIND = {"signs": "points", "lines": "lines", "areas": "areas"}


def _norm(s):
    return s.lower().replace("-", "").replace("_", "").replace(":", "")


def theme_keys(themes_root=None):
    """{kind: {key: [theme ids]}} over every theme (raw theme.json keys, so a
    theme that fails validation still contributes its keys)."""
    out = {k: {} for k in themes.KINDS}
    root = themes_root or themes.default_themes_root()
    for tid in themes.list_themes(root):
        with open(os.path.join(root, tid, "theme.json"), encoding="utf-8") as f:
            raw = json.load(f)
        for kind in themes.KINDS:
            for key, entry in (raw.get(kind) or {}).items():
                if key.startswith("_") or entry is None:
                    continue
                out[kind].setdefault(key, []).append(tid)
    return out


def tdx_name_for(kind, key, catalog, mapping):
    """The TopoDroid name to draw a theme key with, or None."""
    names = [r["name"] for r in catalog["tdx"] if r.get("kind") == CATALOG_KIND[kind]]
    if key in names:
        return key
    for n in names:                                    # waterflow -> water-flow
        if _norm(n) == _norm(key):
            return n
    for n, action in sorted((mapping.get(MAPPING_KIND[kind]) or {}).items()):
        if isinstance(action, dict) and _norm(action.get("to") or "") == _norm(key) \
                and n in names:
            return n
    return None


def symbol_lists(themes_root=None, catalog_path=themes.CATALOG, mapping_path=themes.MAPPING):
    """{kind: [(tdx name, [themes listing it])]} sorted, plus warnings."""
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)
    with open(mapping_path, encoding="utf-8") as f:
        mapping = json.load(f)
    tk = theme_keys(themes_root)
    base = {"signs": ZOO_V3_POINTS, "lines": ZOO_V3_LINES, "areas": ZOO_V3_AREAS}
    warnings, out = [], {}
    for kind in themes.KINDS:
        names = {n: [] for n in base[kind]}
        for key, tids in sorted(tk[kind].items()):
            n = tdx_name_for(kind, key, catalog, mapping)
            if n is None:
                warnings.append("%s key %r (%s): no TopoDroid name draws it - skipped"
                                % (kind, key, ", ".join(tids)))
                continue
            names.setdefault(n, [])
            names[n] = sorted(set(names[n]) | set(tids))
        out[kind] = sorted(names.items())
    return out, warnings


# --------------------------------------------------------------------------
# TopoDroid csx elements (the shape run-validated in 0002's zoo)

def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def el_point(name, x, y, text=""):
    return ('<item type="point" name="%s" cave="%s" branch="1" text="%s" '
            'scale="0" orientation="0.00" options="" >\n'
            ' <points data="%.2f %.2f " />\n</item>' % (_esc(name), CAVE, _esc(text), x, y))


def el_label(text, x, y):
    return el_point("label", x, y, text)


def el_line(name, pts, outline="0", options=""):
    data = "%.2f %.2f B " % pts[0] + " ".join("%.2f %.2f" % p for p in pts[1:])
    return ('<item type="line" name="%s" cave="%s" branch="1" reversed="0" '
            'closed="0" outline="%s" options="%s" >\n'
            '            <points data="%s " />\n          </item>'
            % (_esc(name), CAVE, outline, options, data))


def el_area(name, pts):
    pts = list(pts) + [pts[0]]
    data = "%.2f %.2f B " % pts[0] + " ".join("%.2f %.2f" % p for p in pts[1:])
    return ('<item type="area" name="%s" cave="%s" branch="1" '
            'orientation="0.00" options="" >\n'
            '            <points data="%s " />\n          </item>'
            % (_esc(name), CAVE, data))


def wall_loop(x0, y0, x1, y1):
    """A closed wall stroke round a rectangle (back to its start)."""
    return el_line("wall", [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], outline="1")


def straight(x, y):
    return [(x, y), (x + 3.0, y)]


def sine(x, y, n=30, amp=0.45):
    return [(x + 3.0 * i / n, y - amp * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


# --------------------------------------------------------------------------

def build(themes_root=None):
    """-> (csx text, key markdown lines, layout dict, warnings)."""
    lists, warnings = symbol_lists(themes_root)
    items, stations = [], []
    layout = {"cave": CAVE, "sections": {}, "slots": []}
    key = ["# Theme mockup key (station name = slot tag)", "",
           "Generated by `production/tools/make_theme_mockup.py`. Themed = the themes "
           "that list the symbol.", "",
           "| station | kind | TopoDroid name | themed in | row | col | note |",
           "|---|---|---|---|---|---|---|"]
    y = 0.0
    for kind, tag, heading, cols, dx, dy in SECTIONS:
        syms = lists[kind]
        rows = (len(syms) + cols - 1) // cols
        top = y
        items.append(el_label(heading, -1.0, y - 3.0))
        for i, (name, tids) in enumerate(syms):
            row, col = divmod(i, cols)
            x, yb = dx * col, y + dy * row
            st = "%s%02d" % (tag, i)
            stations.append((st, x, yb))
            note = ""
            if kind == "signs":
                lab_y = yb + (0.9 if col % 2 == 0 else 1.7)
                if name == "section":
                    note = "label-only, item excluded (import risk)"
                elif name == "label":
                    items.append(el_label("%s label" % st, x, yb - 1.2))
                else:
                    items.append(el_point(name, x, yb - 1.2))
                items.append(el_label("%s %s" % (st, name), x - 0.4, lab_y))
                box = (x - 1.4, yb - 2.6, x + 1.4, yb + 2.2)
            elif kind == "lines":
                opts = "-scrap mockup-xx0" if name == "section" else ""
                items.append(el_line(name, straight(x, yb + 1.9), options=opts))
                items.append(el_line(name, sine(x, yb + 3.5), options=opts))
                items.append(el_label("%s %s" % (st, name), x, yb + 0.9))
                box = (x - 0.3, yb - 0.5, x + 3.5, yb + 4.4)
            else:
                items.append(el_area(name, [(x, yb + 1.6), (x + 2.0, yb + 1.6),
                                            (x + 2.0, yb + 3.1), (x, yb + 3.1)]))
                items.append(el_label("%s %s" % (st, name), x, yb + 0.9))
                box = (x - 0.3, yb - 0.5, x + 2.5, yb + 3.6)
            layout["slots"].append({"tag": st, "kind": kind, "name": name, "themes": tids,
                                    "station": [x, yb], "box": [round(v, 2) for v in box]})
            key.append("| %s | %s | %s | %s | %d | %d | %s |"
                       % (st, CATALOG_KIND[kind], name, ", ".join(tids) or "–", row, col, note))
        if kind in ("lines", "areas"):         # print the row only inside a cave border
            for row in range(rows):
                n = min(cols, len(syms) - row * cols)
                yb = y + dy * row
                lo, hi = (1.2, 4.4) if kind == "lines" else (1.2, 3.5)
                items.append(wall_loop(-0.6, yb + lo, dx * (n - 1) + (3.6 if kind == "lines" else 2.6),
                                       yb + hi))
        bottom = y + dy * (rows - 1) + (4.6 if kind != "signs" else 2.4)
        layout["sections"][kind] = {"heading": heading, "box": [-4.0, top - 3.6,
                                                               dx * (cols - 1) + 4.0, bottom],
                                    "count": len(syms)}
        y = bottom + SECTION_GAP + 3.0

    shots = []
    for i in range(1, len(stations)):
        (f, fx, fy), (t, tx, ty) = stations[i - 1], stations[i]
        ddx, ddy = tx - fx, ty - fy
        shots.append('    <segment id="%d" cave="%s" branch="1" session="%s" '
                     'from="%s" to="%s" distance="%.2f" bearing="%.1f" '
                     'inclination="0.0" l="0" r="0" u="0" d="0" >\n    </segment>'
                     % (i, CAVE, SESSION, f, t, math.hypot(ddx, ddy),
                        math.degrees(math.atan2(ddx, -ddy)) % 360.0))

    xml = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<csurvey version="1.11" id="">',
        '  <properties id="" name="%s" origin="%s" creatid="TopoDroid" '
        'creatversion="6.4.29" creatdate="2026-10-07" calculatemode="1" '
        'calculatetype="2" calculateversion="-1" ringcorrectionmode="2" '
        'nordcorrectionmode="0" inversionmode="1" designwarpingmode="1" '
        'bindcrosssection="1">' % (CAVE, stations[0][0]),
        '    <note />',
        '    <sessions>',
        '      <session date="2026.10.07" description="mockup" team="" nordtype="0" >',
        '      </session>',
        '    </sessions>',
        '    <caveinfos>',
        '      <caveinfo name="%s" color="1724697804" comment="">' % CAVE,
        '        <branches>',
        '          <branch name="1" >  </branch>',
        '        </branches>',
        '      </caveinfo>',
        '    </caveinfos>',
        '    <gps enabled="0" refpointonorigin="1" geo="WGS84" format="" sendtotherion="0" />',
        '  </properties>',
        '  <segments>',
        "\n".join(shots),
        '  </segments>',
        '  <trigpoints>',
        '  </trigpoints>',
        '  <plan>',
        '          ' + "\n          ".join(items),
        '    <plot />',
        '  </plan>',
        '  <profile>',
        '    <plot />',
        '  </profile>',
        '</csurvey>',
        '',
    ])
    layout["stations"] = len(stations)
    return xml, key, layout, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("outdir")
    ap.add_argument("--name", default="theme-mockup")
    ap.add_argument("--themes-root")
    args = ap.parse_args(argv)
    xml, key, layout, warnings = build(args.themes_root)
    os.makedirs(args.outdir, exist_ok=True)
    base = os.path.join(args.outdir, args.name)
    with open(base + ".csx", "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    with open(base + "-key.md", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(key) + "\n")
    with open(base + "-layout.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(layout, f, ensure_ascii=False, indent=1)
    counts = {k: v["count"] for k, v in layout["sections"].items()}
    print("wrote %s.csx: %d signs, %d lines, %d areas, %d stations"
          % (base, counts["signs"], counts["lines"], counts["areas"], layout["stations"]))
    for w in warnings:
        print("  WARNING: " + w)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
