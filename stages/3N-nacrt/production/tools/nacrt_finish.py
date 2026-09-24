#!/usr/bin/env python3
"""KORAK 3, step one: finish a corrected `_lt` survey so it can be printed.

Takes the `_lt.csx`/`_lt.csz` the operator saved after correcting the sketch and
writes `<name>_lt_fin.<same ext>` plus a sidecar `<name>_lt_fin.layout.json`.
Pure XML — no cSurvey, no printing. It does by hand exactly what the operator
used to click through (projects/0004-nacrt-finishing brief §2.1):

  1. flag the cave entrance on its `<trigpoint>`;
  2. add the Dislivello (Drop) quota at the profile's lowest floor point;
  3. add the horizontal scale bar right of the plan;
  4. add the north arrow above it, in Manual mode so it reads a plain `N`;
  5. write the A4 print layout into `_preview.plan` / `_preview.profile`,
     with the per-design scale chosen by `nacrt_layout.choose_layout()` (T4);
  6. emit the sidecar JSON the compositor (T3) composes the Nacrt from.

The `-9 m` the profile PDF shows next to the Dislivello is **not** written here:
we write `quotavalue="0"` and cSurvey computes the number at paint time from
`Z(entrance) - Y(midpoint of the quota's two points)` (cItemQuota.vb:485-527).
So the text stays empty in the file and still prints.

The input is never modified, and every other byte of it is preserved: for a
`.csz` every zip entry is copied verbatim, and the XML declaration, the line
endings and the numeric-escape style of the input are reproduced, so a diff of
input against output shows only the elements this tool added.

Usage:
  python production/tools/nacrt_finish.py INPUT_lt.csx|.csz [-o OUT] [--force]
  python production/tools/nacrt_finish.py INTAKE --sb 1103      (pick from the cave folder)
  python production/tools/nacrt_finish.py INPUT --dry-run       (report, write nothing)
  python production/tools/nacrt_finish.py INPUT --yes           (accept the proposed layout)
  python production/tools/nacrt_finish.py INPUT --layout 2      (take alternative 2)

Sidecar keys, for T3: `entrance`, `entrance_witnesses`, `warnings`,
`plan_bbox_m` / `profile_bbox_m` (`[minx, miny, maxx, maxy]` of the finished
design), `plan_size_m` / `profile_size_m` (padded, what the chooser saw),
`plan_scale`, `profile_scale`, `mjerilo`, `arrangement`, `plan_mm` /
`profile_mm` (`{x, y, width, height}`, millimetres from the A4 top-left) and
`chosen`.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The kit runs from a shared Drive folder; don't litter it with __pycache__
# (it would sync to everyone and outlive these tools).
sys.dont_write_bytecode = True
import nacrt_layout                                            # noqa: E402
import sb_select                                               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
COMPASS_ASSET = os.path.join(HERE, "nacrt_finish_compass.xml")

DATA_ENTRY = "_data.xml"

# cLayer.LayerTypeEnum — the two layers this tool reads and writes.
LAYER_BORDERS = "5"
LAYER_SIGNS = "6"

# cIItemSign.SignEnum.Entrance (cIItemSign.vb:44) — TopoDroid's entrance symbol
# imports as this Sign item, clipart ingresso.svg.
SIGN_ENTRANCE = "263"

# cTrigPoint.EntranceTypeEnum.MainCaveEntrace (cTrigPoint.vb:109). It is the
# *constant* 2, not the station name — on SB 1103 the entrance station happens
# to be called "2" as well, which makes `entrance="2"` look like a name.
ENTRANCE_MAIN = "2"

PRINTER = "Microsoft Print to PDF"

# Placement constants, brief §3.1 rows 2-4b.
PAD_M = 0.5            # room for station labels around each design
SCALE_GAP_M = 1.0      # scale bar this far right of the plan bbox
# North arrow this far above the bar (smaller y = up). 1.0 m = 10 mm at 1:100;
# 2.0 m left a hole between the two (user, 2026-09-20, on the first composed sheet).
COMPASS_ABOVE_M = 1.0    # gap between the bar and the arrow's BOTTOM edge (anchored Bottom, see add_compass)
QUOTA_SHIFT_M = 1.5    # quota this far right of whatever is drawn beside it - room for a
                       # station label too (0.3, then 1.0 with the Big text, collided with one on SB 1256)
# The quota clears everything drawn within this much of the floor's depth, and
# nothing higher up. Measuring against the whole design pushed the label a metre
# out past a ceiling that is nowhere near it (user, 2026-09-20).
QUOTA_BAND_M = 0.5
QUOTA_SPAN_M = 0.35    # the quota's two mandatory points, diagonally apart
QUOTA_TEXTSIZE = "4"  # Dislivello text: SizeEnum Large = the "2.00 - Big" combo entry (user, 2026-09-20)
COMPASS_SCALE = "2.00"  # north arrow clipart scale `cs` (user, 2026-09-20: twice the default)
SCALE_BAR_FONT = "2"    # scale-bar text in the "Cave name" font (cItemFont FontTypeEnum.CaveName)
TIE_Z_M = 0.5          # two stations this close in z make the entrance a guess

_NUM_START = set("-0123456789.")


# ---------------------------------------------------------------------------
# container io — the shape fix_imported_linetypes.py uses, plus byte fidelity


class Style(object):
    """How the input was serialized, so the output can look the same.

    ElementTree normalizes what a diff would otherwise light up: it drops the
    XML declaration unless asked (cSurvey writes none, our own tools do), the
    parser turns CRLF into LF, and numeric character references come back out
    in decimal where .NET wrote them in hex. Reproducing all three keeps the
    output diff down to the elements we actually added.
    """

    def __init__(self, data):
        self.declaration = data.lstrip()[:5] == b"<?xml"
        self.crlf = b"\r\n" in data
        self.hex_escapes = b"&#x" in data

    def render(self, root):
        out = ET.tostring(root, encoding="utf-8",
                          xml_declaration=self.declaration)
        if self.hex_escapes:
            # ElementTree escapes \r \n \t in attribute values (and \r in text)
            # as &#13; &#10; &#09;; .NET's XmlWriter uses &#xD; &#xA; &#x9;.
            for dec, hexa in ((b"&#13;", b"&#xD;"), (b"&#10;", b"&#xA;"),
                              (b"&#09;", b"&#x9;")):
                out = out.replace(dec, hexa)
        if self.crlf:
            out = out.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        return out


def is_zip(path):
    with open(path, "rb") as f:
        return f.read(4) == b"PK\x03\x04"


def load_root(path):
    """Return (root, is_csz, style). Reads _data.xml from a .csz, or the .csx."""
    if is_zip(path):
        with zipfile.ZipFile(path) as z:
            if DATA_ENTRY not in z.namelist():
                raise ValueError("zip has no %s — not a cSurvey file" % DATA_ENTRY)
            data = z.read(DATA_ENTRY)
        return ET.fromstring(data), True, Style(data)
    with open(path, "rb") as f:
        data = f.read()
    return ET.fromstring(data), False, Style(data)


def write_root(root, src_path, out, is_csz, style, extra_entries=None):
    """Write root back, preserving the container. For .csz, copy every other
    zip entry (design PNGs, cliparts, surface DEM...) verbatim and add the
    entries in `extra_entries` ({name: bytes}, e.g. a new clipart SVG)."""
    data = style.render(root)
    extra = dict(extra_entries or {})
    if is_csz:
        with zipfile.ZipFile(src_path) as zin, \
                zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename == DATA_ENTRY or info.filename in extra:
                    continue
                zout.writestr(info, zin.read(info.filename))
            zout.writestr(DATA_ENTRY, data)
            for name, blob in extra.items():
                zout.writestr(name, blob)
    else:
        with open(out, "wb") as f:
            f.write(data)


def not_yet_imported(root):
    """True if this is a raw/phone or _pp file (flat <plan>/<item>, no
    <layers>) that has not been through cSurvey's import + Save. The finisher
    would find no layer to write into."""
    for design in ("plan", "profile"):
        d = root.find(design)
        if d is None:
            continue
        if d.find("layers") is not None:
            return False
        if d.findall("item"):
            return True
    return False


# ---------------------------------------------------------------------------
# pretty printing — keep the file's own 2-space indentation


def _indent_after_newline(text, fallback=""):
    if text and "\n" in text:
        return text.rsplit("\n", 1)[1]
    return fallback


def _indent_subtree(el, indent, step):
    kids = list(el)
    if not kids:
        return
    el.text = "\n" + indent + step
    for kid in kids:
        kid.tail = "\n" + indent + step
        _indent_subtree(kid, indent + step, step)
    kids[-1].tail = "\n" + indent


def pretty_append(parent, child, step="  "):
    """Append `child` under `parent` matching the surrounding indentation.

    cSurvey writes the whole file pretty-printed; appending an element without
    fixing the whitespace text nodes would reflow the closing tags and make the
    diff against the input unreadable. Two cases: `parent` already has children
    (copy their indent) or it was written `<items />` (derive the indent from
    the whitespace before parent's own closing context). A file that is not
    pretty-printed there is left alone.
    """
    kids = list(parent)
    if kids:
        if not (parent.text and "\n" in parent.text):
            parent.append(child)
            return
        child_indent = _indent_after_newline(parent.text)
        close_indent = _indent_after_newline(kids[-1].tail, child_indent)
        kids[-1].tail = "\n" + child_indent
    else:
        if not (parent.tail and "\n" in parent.tail):
            parent.append(child)
            return
        close_indent = _indent_after_newline(parent.tail) + step
        child_indent = close_indent + step
        parent.text = "\n" + child_indent
    parent.append(child)
    child.tail = "\n" + close_indent
    _indent_subtree(child, child_indent, step)


def num(value):
    """cSurvey writes design coordinates with two decimals."""
    return "%.2f" % value


# ---------------------------------------------------------------------------
# geometry — points@data, as inspect_survey.py reads it


def iter_points(data):
    """Yield (x, y, flags) over a `<points data>` token stream.

    `X Y [flags]` per point, flags a concatenation of B / P / T<digit> / L /
    S[<guid>] (cPoints.vb:496-599). Mirrors inspect_survey.scan_points, which
    is what `inspect_design` computes its bbox from.
    """
    tokens = (data or "").split()
    i = 0
    while i < len(tokens):
        if tokens[i][0] not in _NUM_START:
            i += 1
            continue
        if i + 1 >= len(tokens) or tokens[i + 1][0] not in _NUM_START:
            i += 1
            continue
        try:
            x, y = float(tokens[i]), float(tokens[i + 1])
        except ValueError:
            i += 1
            continue
        i += 2
        flags = ""
        if i < len(tokens) and tokens[i][0] not in _NUM_START:
            flags = tokens[i]
            i += 1
        yield x, y, flags


def segment_guid(flags):
    """The segment a point is bound to: the guid after `S`, "" when `S` carries
    none, None when the point is unbound."""
    j = 0
    while j < len(flags):
        c = flags[j]
        if c in "BPL":
            j += 1
        elif c == "T":
            j += 2
        elif c == "S":
            return flags[j + 1:]
        else:
            return None
    return None


def iter_items(design, layer_types=None):
    """Items of one <plan>/<profile>: nested under <layers> (post-import) and,
    when no layer filter is given, the flat <item> children a raw TopoDroid
    file has."""
    if design is None:
        return
    layers = design.find("layers")
    if layers is not None:
        for layer in layers.findall("layer"):
            if layer_types is not None and layer.get("type") not in layer_types:
                continue
            items_el = layer.find("items")
            kids = items_el.findall("item") if items_el is not None else []
            kids += layer.findall("item")   # tolerate items directly under <layer>
            for item in kids:
                yield item
    if layer_types is None:
        for item in design.findall("item"):
            yield item


def item_points(item):
    pts = item.find("points")
    if pts is None:
        return []
    return list(iter_points(pts.get("data")))


def items_bbox(items):
    """[minx, miny, maxx, maxy] over every point of `items`, or None."""
    box = None
    for item in items:
        for x, y, _flags in item_points(item):
            if box is None:
                box = [x, y, x, y]
            else:
                box[0] = min(box[0], x)
                box[1] = min(box[1], y)
                box[2] = max(box[2], x)
                box[3] = max(box[3], y)
    return box


def design_bbox(design):
    """The design's extent, computed the way inspect_survey.inspect_design does."""
    return items_bbox(iter_items(design))


def right_of_depth(design, depth, band=QUOTA_BAND_M):
    """Rightmost x among everything drawn within `band` of that depth, or None.

    Where the Dislivello label goes. Two earlier rules both missed: beside the
    lowest point itself buried the label in the floor debris, and beside the
    whole design's right edge pushed it a metre out past a ceiling that is
    nowhere near the floor (user, 2026-09-20, on the first two composed sheets).
    The label only has to clear what is drawn beside it, so only that band is
    measured.
    """
    right = None
    for item in iter_items(design):
        for x, y, _flags in item_points(item):
            if abs(y - depth) <= band and (right is None or x > right):
                right = x
    return right


def vertical_extent(root, entrance, stations):
    """Height above and depth below the entrance, in metres, or None.

    **Only the boundary wall and the shots count** (user, 2026-09-20): cSurvey's
    own `pvr`/`nvr` come from the profile design's *whole* bounding box
    (cCalculate.Plot.cSpeleometrics.vb:88-96 takes `oProfileBounds.Top/Bottom`),
    so a symbol drawn above the entrance inflates the height. On SB 1103 the
    entrance sign sits 1.4 m above station `2` and cSurvey reported `pvr=1`
    where the cave does not rise above its entrance at all.

    Profile design y and a station's z are the same axis — depth, positive
    downward — so the two sources compare directly.
    """
    if entrance is None:
        return None
    entrance_z = next((s.z for s in stations if s.name == entrance), None)
    if entrance_z is None:
        return None
    borders = items_bbox(iter_items(root.find("profile"), (LAYER_BORDERS,)))
    tops = [s.z for s in stations]
    bottoms = list(tops)
    if borders is not None:
        tops.append(borders[1])
        bottoms.append(borders[3])
    if not tops:
        return None
    return {
        "pvr_m": round(max(0.0, entrance_z - min(tops)), 2),
        "nvr_m": round(max(0.0, max(bottoms) - entrance_z), 2),
        "from": "Borders + stanice" if borders is not None else "stanice",
    }


def lowest_floor_point(design):
    """(x, y, source) of the profile's deepest drawn point.

    Profile design Y *is* depth (Z positive downward, cCalculate.vb), so the
    floor's lowest point is the **maximum** y. The Borders layer is the cave
    outline and the right place to look; a file whose Borders layer is empty
    (nothing traced yet, or an unusual layering) falls back to every layer.
    """
    for label, layer_types in (("Borders", (LAYER_BORDERS,)), ("svi slojevi", None)):
        best = None
        for item in iter_items(design, layer_types):
            for x, y, _flags in item_points(item):
                if best is None or y > best[1]:
                    best = (x, y, item)
        if best is not None:
            return best[0], best[1], best[2], label
    return None


# ---------------------------------------------------------------------------
# stations


class Station(object):
    __slots__ = ("name", "x", "y", "z", "d")

    def __init__(self, name, x, y, z, d):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.d = d

    def design_xy(self, design_name):
        """Where the station sits in a design's own coordinates.

        Plan is (x, y) straight off `<p>`; the profile is (d, z) — the
        projected distance along the profile and the depth (frmMain.vb:17386
        builds a profile translation from exactly that pair).
        """
        if design_name == "profile":
            return self.d, self.z
        return self.x, self.y


def read_stations(root):
    """Non-splay stations from `<calculate><ts>`. A splay's name carries the
    parenthesised index its shot got, `0(12)`."""
    stations = []
    ts = root.find("calculate/ts")
    if ts is None:
        return stations
    for t in ts.findall("t"):
        name = t.get("n") or ""
        if not name or "(" in name:
            continue
        p = t.find("p")
        if p is None:
            continue
        try:
            stations.append(Station(name,
                                    float(p.get("x") or 0.0),
                                    float(p.get("y") or 0.0),
                                    float(p.get("z") or 0.0),
                                    float(p.get("d") or 0.0)))
        except ValueError:
            continue
    return stations


# ---------------------------------------------------------------------------
# entrance, witness (a): the highest station
#
# Kept separate from witness (b), with its own tests, so the rule can be
# re-weighed once real caves other than SB 1103 have been through it.


def witness_highest(stations):
    """The highest non-splay station: minimum z, Z being positive downward.

    Returns (station_name, z, ties) where `ties` names the other non-splay
    stations within TIE_Z_M of it — a flat or horizontal cave where "highest"
    does not single out an entrance.
    """
    if not stations:
        return None, None, []
    top = min(stations, key=lambda s: s.z)
    ties = [s.name for s in stations
            if s.name != top.name and abs(s.z - top.z) <= TIE_Z_M]
    return top.name, top.z, ties


# ---------------------------------------------------------------------------
# entrance, witness (b): the entrance sign the surveyor drew


def entrance_sign_items(design):
    """Every Sign item in a design that is TopoDroid's entrance symbol."""
    return [item for item in iter_items(design)
            if item.get("type") == "6" and item.get("sign") == SIGN_ENTRANCE]


def _segment_endpoint_hint(root, guid, sign_xy, stations, design_name):
    """The endpoint of the sign's bound segment that lies nearer to the sign.

    A Sign item's point is bound to a segment (`S<guid>` in `<points data>`),
    so the surveyor's own placement already names two candidate stations.
    """
    if not guid:
        return None, None
    segs = root.find("segments")
    if segs is None:
        return None, None
    for seg in segs.findall("segment"):
        if seg.get("id") != guid:
            continue
        names = [seg.get("from"), seg.get("to")]
        by_name = {s.name: s for s in stations}
        near, dist = None, None
        for name in names:
            st = by_name.get(name)
            if st is None:
                continue
            sx, sy = st.design_xy(design_name)
            d = ((sx - sign_xy[0]) ** 2 + (sy - sign_xy[1]) ** 2) ** 0.5
            if dist is None or d < dist:
                near, dist = name, d
        return near, "%s->%s" % (names[0], names[1])
    return None, None


def witness_sign(root, stations, design_name):
    """The station the drawn entrance sign points at, in one design.

    Returns None when that design carries no entrance sign, else a dict with
    the nearest non-splay station (the answer), its distance, and the hint the
    sign's bound segment gives — kept apart so a disagreement can be reported
    rather than silently resolved.
    """
    design = root.find(design_name)
    signs = entrance_sign_items(design)
    if not signs or not stations:
        return None
    best = None
    for item in signs:
        pts = item_points(item)
        if not pts:
            continue
        x, y, flags = pts[0]
        for st in stations:
            sx, sy = st.design_xy(design_name)
            d = ((sx - x) ** 2 + (sy - y) ** 2) ** 0.5
            if best is None or d < best["distance"]:
                near, seg = _segment_endpoint_hint(
                    root, segment_guid(flags), (x, y), stations, design_name)
                best = {"design": design_name, "station": st.name,
                        "distance": round(d, 2), "sign_at": [round(x, 2), round(y, 2)],
                        "segment_station": near, "segment": seg}
    return best


def decide_entrance(root, stations, warn):
    """Combine the two witnesses into one entrance station.

    They are independent: the highest station is geometry, the drawn sign is
    the surveyor's intent. When they disagree the sign wins — a ponor or a
    horizontal cave rarely has its entrance at the top, and the sign was placed
    on purpose (user rule, brief §3.1 row 4a as amended by the T1 prompt).
    """
    top, top_z, ties = witness_highest(stations)
    plan = witness_sign(root, stations, "plan")
    profile = witness_sign(root, stations, "profile")

    props = root.find("properties")
    origin = (props.get("origin") if props is not None else None) or ""

    sign = plan or profile
    if plan and profile and plan["station"] != profile["station"]:
        warn("znak ulaza pokazuje na razlicite stanice: tlocrt %s, profil %s "
             "- uzimam tlocrt" % (plan["station"], profile["station"]))
    if sign and sign.get("segment_station") \
            and sign["segment_station"] != sign["station"]:
        warn("znak ulaza: najbliza stanica je %s, a vezani segment %s upucuje "
             "na %s - uzimam najblizu"
             % (sign["station"], sign["segment"], sign["segment_station"]))

    witnesses = {
        "highest": top,
        "highest_z": None if top_z is None else round(top_z, 2),
        "highest_ties": ties,
        "sign": None if sign is None else sign["station"],
        "sign_detail": sign,
        "origin": origin,
    }

    if sign is None:
        chosen = top
        witnesses["decision"] = "najvisa stanica (nema nacrtanog znaka ulaza)"
        if chosen is not None and origin and origin != chosen:
            warn("najvisa stanica je %s, a properties@origin je %s - provjeri "
                 "je li ulaz na pravoj stanici" % (chosen, origin))
        if ties:
            warn("stanice %s su unutar %.1f m po visini od %s - 'najvisa' ne "
                 "razlucuje ulaz, provjeri rucno"
                 % (", ".join(ties), TIE_Z_M, chosen))
    elif top is not None and sign["station"] == top:
        chosen = top
        witnesses["decision"] = "oba svjedoka slozna (najvisa stanica i znak ulaza)"
    else:
        chosen = sign["station"]
        witnesses["decision"] = "znak ulaza (ne slaze se s najvisom stanicom)"
        warn("znak ulaza je na stanici %s, a najvisa stanica je %s - uzimam "
             "znak ulaza (ponor ili horizontalna spilja nema ulaz na vrhu)"
             % (sign["station"], top))
    return chosen, witnesses


def set_entrance(root, station, warn):
    """`entrance="2"` (MainCaveEntrace) on that trigpoint, and off every other."""
    if station is None:
        warn("ulaz nije odreden - nijedna stanica nije oznacena kao ulaz")
        return False
    tps = root.find("trigpoints")
    if tps is None:
        warn("nema <trigpoints> - ulaz nije upisan")
        return False
    target = None
    cleared = []
    for tp in tps.findall("trigpoint"):
        if tp.get("name") == station:
            target = tp
        elif tp.get("entrance") is not None:
            cleared.append(tp.get("name"))
            del tp.attrib["entrance"]
    if target is None:
        # cSurvey writes a <trigpoint> per station, so this is pathological;
        # create it rather than leave the cave without an entrance, since the
        # Dislivello quota resolves its depth against it.
        warn("nema <trigpoint name=\"%s\"> - dodajem ga da ulaz bude upisan"
             % station)
        target = ET.Element("trigpoint", {"name": station})
        pretty_append(tps, target)
    if cleared:
        warn("uklonio entrance s ranije oznacenih stanica: %s"
             % ", ".join(cleared))
    already = target.get("entrance") == ENTRANCE_MAIN
    target.set("entrance", ENTRANCE_MAIN)
    return not already


# ---------------------------------------------------------------------------
# the Signs layer, and the three items that go into it


def signs_items(design, warn, design_name):
    """The `<items>` of a design's Signs layer, created if the layer is absent."""
    layers = design.find("layers")
    if layers is None:
        warn("%s: nema <layers> - ne mogu dodati znakove" % design_name)
        return None
    for layer in layers.findall("layer"):
        if layer.get("type") == LAYER_SIGNS:
            items = layer.find("items")
            if items is None:
                items = ET.Element("items")
                pretty_append(layer, items)
            return items
    warn("%s: nema sloja Signs (type=6) - dodajem ga" % design_name)
    layer = ET.Element("layer", {"name": "Signs", "type": LAYER_SIGNS})
    items = ET.SubElement(layer, "items")
    pretty_append(layers, layer)
    return items


def cave_branch(item):
    """The cave/branch a neighbouring item carries — new furniture joins it."""
    if item is None:
        return "", ""
    return item.get("cave") or "", item.get("branch") or ""


def reference_item(design):
    """An item to copy cave/branch off: a Borders one if there is one, else any.

    Explicit `is None` tests, not truthiness — an `<item>` with no children is a
    falsy Element.
    """
    for item in iter_items(design, (LAYER_BORDERS,)):
        return item
    for item in iter_items(design):
        return item
    return None


def quota_item(cave, branch, quotatype, relative, extra=()):
    """A Quota item (type 10, category 82) with the attributes cSurvey writes.

    Attribute order follows the finished SB 1103 fixture so the two are directly
    comparable. `text=""` and `quotavalue="0"` on purpose: cSurvey computes both
    at paint time. No `<pen>`/`<brush>` either — cItemQuota overrides HavePen and
    HaveBrush to False (cItemQuota.vb:261-271), so cSurvey ignores them on load
    and drops them on the next save.
    """
    item = ET.Element("item")
    for key, value in (("layer", LAYER_SIGNS), ("cave", cave),
                       ("branch", branch), ("type", "10"), ("category", "82"),
                       ("text", ""), ("quotaalign", "2"),
                       ("quotatextposition", "1"), ("quotaformat", ""),
                       ("quotatype", quotatype), ("quotavalue", "0"),
                       ("quotavaluetype", "0"),
                       ("quotarelativetrigpoint", relative)):
        item.set(key, value)
    for key, value in extra:
        item.set(key, value)
    return item


def has_quota(design, quotatype):
    return any(item.get("type") == "10" and item.get("quotatype") == quotatype
               for item in iter_items(design))


def add_dislivello(root, entrance, warn):
    """The Drop quota at the profile's deepest floor point (brief §3.1 row 4b).

    Two points are mandatory — cItemQuota.Paint bails on one — and the depth
    cSurvey prints is measured from the midpoint of them up to the entrance.
    """
    design = root.find("profile")
    if design is None:
        warn("nema <profile> - dislivello nije dodan")
        return None
    if has_quota(design, "3"):
        warn("profil vec ima dislivello (quotatype=3) - preskacem")
        return None
    low = lowest_floor_point(design)
    if low is None:
        warn("profil nema nacrtanih tocaka - dislivello nije dodan")
        return None
    x, y, owner, source = low
    items = signs_items(design, warn, "profil")
    if items is None:
        return None
    cave, branch = cave_branch(owner)
    right = right_of_depth(design, y)
    x0, y0 = (x if right is None else right) + QUOTA_SHIFT_M, y
    x1, y1 = x0 + QUOTA_SPAN_M, y0 + QUOTA_SPAN_M
    item = quota_item(cave, branch, "3", entrance or "",
                      extra=(("textsize", QUOTA_TEXTSIZE),))
    ET.SubElement(item, "points", {"data": "%s %s %s %s " % (num(x0), num(y0),
                                                             num(x1), num(y1))})
    ET.SubElement(item, "font", {"type": "0"})
    pretty_append(items, item)
    if source != "Borders":
        warn("profil: sloj Borders je prazan, najnizu tocku sam uzeo iz svih "
             "slojeva - provjeri gdje je dislivello")
    return {"lowest": [round(x, 2), round(y, 2)], "source": source,
            "right_at_depth": None if right is None else round(right, 2),
            "points": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
            "relative_trigpoint": entrance or ""}


def bar_length_m(plan_scale):
    """5 m at 1:100, 10 m otherwise (50 mm on paper either way, near enough)."""
    return 5.0 if plan_scale == 100 else 10.0


def settle_plan_scale(plan_before, profile_before, max_rounds=4):
    """The plan scale the bar must be sized for — found by fixed point.

    The bar's length depends on the plan's scale, which depends on the plan's
    bbox *after* the bar widens it. Simulate the widening (gap + bar; the
    compass sits above the bar, never right of it) and re-choose until the
    scale stops moving. It converges in one or two rounds: a longer bar can
    only push the scale down, and a smaller scale only asks for the same or a
    longer bar. Returns (scale, rounds) — SB 1256 (2026-09-20) was the case
    where the untouched bbox said 1:100 and the widened one 1:200.
    """
    scale = 100
    if plan_before is None:
        return scale, 0
    seen = []
    for rounds in range(1, max_rounds + 1):
        widened = (plan_before[0], plan_before[1],
                   plan_before[2] + SCALE_GAP_M + bar_length_m(scale), plan_before[3])
        best, _alts, _reason = choose(widened, profile_before)
        new_scale = best.plan_scale if best else scale
        if new_scale == scale:
            return scale, rounds
        if new_scale in seen:            # a 100<->200 flip-flop: take the smaller scale
            return max(scale, new_scale), rounds
        seen.append(scale)
        scale = new_scale
    return scale, max_rounds


def add_scale_bar(root, bbox, plan_scale, warn):
    """The horizontal scale bar right of the plan (brief §3.1 row 2).

    A Quota of type HorizontalScale: its length is the distance between its two
    points *in metres*, so it scales with the map. 5 m at 1:100, 10 m otherwise
    (which is 50 mm on paper either way, near enough to read).
    """
    design = root.find("plan")
    if design is None:
        warn("nema <plan> - mjerilo nije dodano")
        return None
    if has_quota(design, "6"):
        warn("tlocrt vec ima mjerilo (quotatype=6) - preskacem")
        return None
    if bbox is None:
        warn("tlocrt nema nacrtanih tocaka - mjerilo nije dodano")
        return None
    items = signs_items(design, warn, "tlocrt")
    if items is None:
        return None
    length = bar_length_m(plan_scale)
    tick, label = (1.0, 5.0) if length == 5.0 else (2.0, 10.0)
    x0 = bbox[2] + SCALE_GAP_M
    y0 = bbox[3]
    cave, branch = cave_branch(reference_item(design))
    # A HorizontalScale measures nothing against a station, so
    # quotarelativetrigpoint stays empty — as on the bar cSurvey writes itself.
    item = quota_item(cave, branch, "6", "", extra=(
        ("quotatickfrequency", "%.2f" % tick),
        ("quotaticklabelfrequency", "%.2f" % label),
        ("quotaticksize", "0.30"),
    ))
    ET.SubElement(item, "points", {"data": "%s %s %s %s " % (
        num(x0), num(y0), num(x0 + length), num(y0))})
    ET.SubElement(item, "font", {"type": SCALE_BAR_FONT})
    pretty_append(items, item)
    return {"length_m": length, "tick": tick, "label_every": label,
            "points": [round(x0, 2), round(y0, 2),
                       round(x0 + length, 2), round(y0, 2)],
            "for_scale": plan_scale}


def load_compass_clipart():
    """The `<clipart>` element for compass3.svg, and its decoded SVG bytes.

    Shipped as an asset beside this tool rather than read out of the SB 1103
    fixture at runtime — the fixture is gitignored and is not on an operator
    machine. The id is the uppercase SHA-1 of the SVG bytes
    (modMain.CalculateHash, cCliparts.vb:463), so a corrupted asset fails here
    instead of writing a clipart id nothing resolves.
    """
    el = ET.parse(COMPASS_ASSET).getroot()
    blob = base64.b64decode("".join((el.get("data") or "").split()))
    cid = el.get("id") or ""
    if hashlib.sha1(blob).hexdigest().upper() != cid:
        raise ValueError("%s: id %s is not the SHA-1 of its data"
                         % (COMPASS_ASSET, cid))
    return cid, el.get("name") or "compass3.svg", blob


def _cliparts_element(root):
    """`<signs><cliparts>` — where sign and compass cliparts live."""
    signs = root.find("signs")
    if signs is None:
        return None
    return signs.find("cliparts")


def ensure_compass_clipart(root, is_csz, warn):
    """Return (clipart_id, extra_zip_entries, added_name_or_None)."""
    cliparts = _cliparts_element(root)
    if cliparts is not None:
        for clipart in cliparts.findall("clipart"):
            if (clipart.get("name") or "").lower() == "compass3.svg":
                return clipart.get("id"), {}, None
    cid, name, blob = load_compass_clipart()
    if cliparts is None:
        warn("nema <signs><cliparts> - ne mogu dodati clipart busole")
        return None, {}, None
    el = ET.Element("clipart", {"id": cid, "name": name})
    extra = {}
    if is_csz:
        # cSurvey stores a .csz clipart as a zip entry and puts the *path* in
        # @data, with backslashes (cCliparts.vb:495-497) — the zip entry itself
        # uses forward slashes, and the loader normalizes them back to the
        # platform separator before looking the path up (cFile.vb:388). A
        # forward-slash @data would therefore resolve to nothing on Windows and
        # take cSurvey down on load, so backslash is the default; only a clipart
        # path already in this file overrides it. The test is "looks like a
        # path", not "contains a slash": base64 @data (a .csx's XML, rezipped)
        # is full of forward slashes.
        sep = "\\"
        for other in cliparts.findall("clipart"):
            data = other.get("data") or ""
            if data.lower().endswith(".svg"):
                sep = "/" if ("/" in data and "\\" not in data) else "\\"
                break
        el.set("data", "_data%scliparts%s%s.svg" % (sep, sep, cid))
        extra["_data/cliparts/%s.svg" % cid] = blob
    else:
        el.set("data", base64.b64encode(blob).decode("ascii"))
    pretty_append(cliparts, el)
    return cid, extra, name


def add_compass(root, bbox, scale_bar, is_csz, warn):
    """The north arrow above the scale bar (brief §3.1 row 3).

    `m="1"` is CompassModeEnum.Manual and no `n` attribute means Geographic, so
    the arrow is labelled a plain `N` — Auto would print `Nm <year>` because the
    drawing is in magnetic north (cItemCompass.vb:344-373).

    `textalignment="0"` is **Center** (`cIItemText.vb:50-54`: Center 0, Left 1,
    Right 2), and that is what puts the arrow *on* its point rather than beside
    it: cItemCompass.vb:398-404 offsets the glyph by half its width only in that
    case, and by nothing at all for Left. With Left — what cSurvey's own UI
    wrote, and what this tool copied from it — the arrow stood a millimetre
    right of the scale bar it is supposed to sit over (user, 2026-09-20).
    Vertical alignment is left unset, which is Middle, so the point is the
    glyph's centre.
    """
    design = root.find("plan")
    if design is None:
        warn("nema <plan> - busola nije dodana")
        return None
    if any(item.get("type") == "15" for item in iter_items(design)):
        warn("tlocrt vec ima busolu (type=15) - preskacem")
        return None
    if bbox is None:
        warn("tlocrt nema nacrtanih tocaka - busola nije dodana")
        return None
    cid, extra, added = ensure_compass_clipart(root, is_csz, warn)
    if cid is None:
        return None
    items = signs_items(design, warn, "tlocrt")
    if items is None:
        return None
    length = scale_bar["length_m"] if scale_bar else 5.0
    x = bbox[2] + SCALE_GAP_M + length / 2.0
    y = bbox[3] - COMPASS_ABOVE_M      # smaller y is up in a design
    cave, branch = cave_branch(reference_item(design))
    item = ET.Element("item")
    for key, value in (("layer", LAYER_SIGNS), ("cave", cave),
                       ("branch", branch), ("type", "15"), ("category", "83"),
                       ("da", "1"), ("data", cid), ("dataformat", "2"),
                       ("cs", COMPASS_SCALE), ("m", "1"), ("textalignment", "0"),
                       # Bottom (2): the point is the block's lower edge, so the gap
                       # above the bar holds whatever size the arrow has (the doubled
                       # arrow crossed the bar when anchored at its middle, 2026-09-20).
                       ("textverticalalignment", "2")):
        item.set(key, value)
    ET.SubElement(item, "pen", {"type": "10"})
    ET.SubElement(item, "brush", {"type": "7"})
    ET.SubElement(item, "points", {"data": "%s %s " % (num(x), num(y))})
    ET.SubElement(item, "font", {"type": "1"})
    pretty_append(items, item)
    return {"clipart": cid, "clipart_added": added,
            "point": [round(x, 2), round(y, 2)], "extra_entries": extra}


# ---------------------------------------------------------------------------
# print options


PREVIEW_COMMON = (
    ("pageformat", "A4"),
    ("pagemargins", "10;10;10;10"),
    # designstyle 0 = Survey (the user's default, 2026-09-20), not Combined.
    ("designstyle", "0"),
    ("drawsplay", "0"),
    # The scale bar and the north arrow are items next to the sketch now, so the
    # page-corner gadgets stay off — otherwise each is drawn twice.
    ("drawscale", "0"),
    ("drawcompass", "0"),
    ("drawbox", "0"),
    ("printername", PRINTER),
)


def write_print_options(root, best, warn):
    """`_preview.plan` / `_preview.profile` + the render quality (brief §3.1 row 6).

    `scalemode` is the print dialog's combo index, not a denominator; `scale`
    carries the denominator and is always written, because 1:400 has no combo
    entry and rides on `scalemode="99"` + `scale="400"`. Render quality is not
    a preview option at all — it lives in `<sharedsettings>`.
    """
    options = root.find("options")
    written = {}
    if options is None:
        warn("nema <options> - postavke ispisa nisu upisane")
    else:
        for design_name, key in (("profile", "_preview.profile"),
                                 ("plan", "_preview.plan")):
            el = options.find(key)
            if el is None:
                warn("nema <options><%s> - postavke ispisa za %s nisu upisane"
                     % (key, design_name))
                continue
            for attr, value in PREVIEW_COMMON:
                el.set(attr, value)
            if el.get("pagelandscape") is not None:
                # A4 portrait only: the sastavnica page T3 composes onto is
                # portrait, and cSurvey centres on whatever page it is given.
                del el.attrib["pagelandscape"]
            if best is None:
                el.set("scalemode", "0")
                el.set("scale", "0")
                written[key] = {"scalemode": "0", "scale": "0"}
            else:
                scale = (best.profile_scale if design_name == "profile"
                         else best.plan_scale)
                mode = (best.scalemodes[0] if design_name == "profile"
                        else best.scalemodes[1])
                el.set("scalemode", str(mode))
                el.set("scale", str(scale))
                written[key] = {"scalemode": str(mode), "scale": str(scale)}

    shared = root.find("sharedsettings")
    values = shared.find("values") if shared is not None else None
    if values is None:
        warn("nema <sharedsettings><values> - kvaliteta ispisa nije upisana")
    else:
        values.set("preview.designquality", "2")   # 2 = High (frmPreview.vb:91)
        values.set("preview.manualrefresh", "0")
    return written


# ---------------------------------------------------------------------------
# the layout menu


def layout_bbox(bbox):
    """A design bbox padded by PAD_M on every side, as nacrt_layout.BBox.

    Station labels and the quota text sit outside the traced outline, so the
    printed area is wider than the geometry by roughly a label's width.
    """
    if bbox is None:
        return None
    return nacrt_layout.BBox(bbox[2] - bbox[0] + 2 * PAD_M,
                             bbox[3] - bbox[1] + 2 * PAD_M)


def choose(plan_bbox, profile_bbox):
    """`nacrt_layout.choose_layout` on the padded bboxes. Argument order is
    (plan, profile) — alphabetical, not importance order."""
    plan, profile = layout_bbox(plan_bbox), layout_bbox(profile_bbox)
    if plan is None or profile is None:
        return None, [], ("nedostaje crtez: %s" % ", ".join(
            name for name, box in (("tlocrt", plan), ("profil", profile))
            if box is None))
    return nacrt_layout.choose_layout(plan, profile)


def print_menu(best, alternatives, out):
    out("")
    out("  MJERILO I RASPORED")
    out("   1) %s  |  %s   <- prijedlog" % (best.mjerilo, best.note))
    for i, layout in enumerate(alternatives, 2):
        out("   %d) %s  |  %s" % (i, layout.mjerilo, layout.note))


def ask_layout(best, alternatives, chooser):
    """Let the operator take an alternative. Returns (layout, label)."""
    if not alternatives:
        return best, "proposal"
    print("")
    print("  Upisi broj rasporeda, Enter = prijedlog (1).")
    try:
        raw = input(chooser).strip()
    except EOFError:
        raw = ""
    if not raw:
        return best, "proposal"
    if raw.isdigit() and 1 <= int(raw) <= len(alternatives) + 1:
        n = int(raw)
        if n == 1:
            return best, "proposal"
        return alternatives[n - 2], "alternative %d" % n
    print("  '%s' nije ponudeni broj - uzimam prijedlog." % raw)
    return best, "proposal"


# ---------------------------------------------------------------------------
# one file


def speleometrics(root):
    """The survey-wide `<sm>` row, for the report: the centerline numbers, which
    describe the cave and not the drawing (the sketch spills past them)."""
    sms = root.find("calculate/sms")
    if sms is None:
        return {}
    for sm in sms.findall("sm"):
        if sm.get("cave") is None:
            return dict(sm.attrib)
    rows = sms.findall("sm")
    return dict(rows[0].attrib) if rows else {}


def fmt_bbox(bbox):
    if bbox is None:
        return "nema tocaka"
    return "%5.2f x %5.2f m   (x %.2f..%.2f, y %.2f..%.2f)" % (
        bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[0], bbox[2], bbox[1], bbox[3])


def finish(inp, out_path, args, report):
    """Run the six edits on one file. Returns (sidecar_dict, ok)."""
    warnings = []

    def warn(message):
        warnings.append(message)

    root, is_csz, style = load_root(inp)
    if not_yet_imported(root):
        print("BLOCKED: %s nije uvezen u cSurvey.\n"
              "  Napravi prvo KORAK 2 (csurvey_2_dovrsi_uvoz.bat), pa ispravi\n"
              "  skicu u cSurveyu i spremi - tek tu datoteku dovrsavamo." % inp,
              file=sys.stderr)
        return None, False
    stem = os.path.splitext(os.path.basename(inp))[0]
    if "_lt" not in stem.lower():
        warn("naziv ne sadrzi _lt - je li ovo datoteka nakon KORAKA 2?")

    report("NACRT FINISH  %s" % inp)
    report("  izlaz:    %s" % out_path)
    report("  sidecar:  %s" % (os.path.splitext(out_path)[0] + ".layout.json"))

    # --- 1. entrance -----------------------------------------------------
    stations = read_stations(root)
    if not stations:
        warn("nema stanica u <calculate><ts> - je li survey izracunat?")
    entrance, witnesses = decide_entrance(root, stations, warn)
    report("")
    report("  ULAZ")
    report("   najvisa stanica (min z): %s" % (
        "nema" if witnesses["highest"] is None
        else "%s  (z = %s)" % (witnesses["highest"], witnesses["highest_z"])))
    sign = witnesses["sign_detail"]
    report("   znak ulaza:             %s" % (
        "nije nacrtan" if sign is None
        else "%s  (%s, %.2f m od znaka; vezani segment %s)"
             % (sign["station"], "tlocrt" if sign["design"] == "plan" else "profil",
                sign["distance"], sign["segment"] or "-")))
    report("   properties@origin:      %s" % (witnesses["origin"] or "-"))
    report("   odluka:                 %s  (%s)" % (entrance or "-",
                                                    witnesses["decision"]))
    changed_entrance = set_entrance(root, entrance, warn)
    vertical = vertical_extent(root, entrance, stations)
    if vertical:
        report("   visina/dubina:          +%.2f / -%.2f m od ulaza  (%s)"
               % (vertical["pvr_m"], vertical["nvr_m"], vertical["from"]))

    # --- bboxes before the furniture, and a provisional scale ------------
    plan_before = design_bbox(root.find("plan"))
    profile_before = design_bbox(root.find("profile"))
    report("")
    report("  CRTEZ (prije mjerila i busole)")
    report("   tlocrt  %s" % fmt_bbox(plan_before))
    report("   profil  %s" % fmt_bbox(profile_before))
    sm = speleometrics(root)
    if sm:
        report("   <sm> (os poligona, ne crtez): %s"
               % "  ".join("%s=%s" % (k, sm[k]) for k in
                           ("l", "pl", "ml", "pvr", "nvr", "qmx", "qmn", "es")
                           if k in sm))

    # The scale bar's length depends on the plan's scale, which depends on the
    # bbox *after* the bar widens it: settle the fixed point first, then add the
    # bar for that scale; the real choice below should agree (warn if not).
    provisional_plan_scale, _rounds = settle_plan_scale(plan_before, profile_before)

    # --- 2-4. the three items -------------------------------------------
    dislivello = add_dislivello(root, entrance, warn)
    scale_bar = add_scale_bar(root, plan_before, provisional_plan_scale, warn)
    compass = add_compass(root, plan_before, scale_bar, is_csz, warn)

    report("")
    report("  IZMJENE")
    report("   ulaz        %s" % ("trigpoint \"%s\" entrance=\"%s\"%s"
                                  % (entrance, ENTRANCE_MAIN,
                                     "" if changed_entrance else "  (vec bilo)")
                                  if entrance else "nije upisan"))
    report("   dislivello  %s" % ("profil/Signs  tocke %s  quotarelativetrigpoint=\"%s\""
                                  % (" ".join(num(v) for v in dislivello["points"]),
                                     dislivello["relative_trigpoint"])
                                  if dislivello else "preskoceno"))
    report("   mjerilo     %s" % ("tlocrt/Signs  %.0f m  tocke %s  tick %.2f/%.2f"
                                  % (scale_bar["length_m"],
                                     " ".join(num(v) for v in scale_bar["points"]),
                                     scale_bar["tick"], scale_bar["label_every"])
                                  if scale_bar else "preskoceno"))
    report("   busola      %s" % ("tlocrt/Signs  tocka %s  clipart %s%s"
                                  % (" ".join(num(v) for v in compass["point"]),
                                     compass["clipart"],
                                     "  (dodan u <signs><cliparts>)"
                                     if compass["clipart_added"] else "")
                                  if compass else "preskoceno"))

    # --- 5. layout + print options ---------------------------------------
    plan_after = design_bbox(root.find("plan"))
    profile_after = design_bbox(root.find("profile"))
    best, alternatives, reason = choose(plan_after, profile_after)
    if best is not None and best.plan_scale != provisional_plan_scale:
        warn("duzina mjerila je odabrana za 1:%d, a tlocrt na kraju ide u "
             "1:%d - provjeri je li stap prave duzine"
             % (provisional_plan_scale, best.plan_scale))

    report("")
    report("  CRTEZ (s mjerilom i busolom, +%.1f m margine za oznake stanica)" % PAD_M)
    report("   tlocrt  %s" % fmt_bbox(plan_after))
    report("   profil  %s" % fmt_bbox(profile_after))

    chosen_label = "fit-to-page"
    if best is None:
        report("")
        report("  MJERILO I RASPORED")
        report("   %s" % reason)
        report("   -> cSurvey fit-to-page (scalemode=0); mjerilo nije vjerno.")
        warn("raspored: %s - upisujem scalemode=0 (cSurvey sam smanjuje), "
             "mjerilo na sastavnici nije vjerno" % reason)
    else:
        print_menu(best, alternatives, report)
        if args.layout:
            n = args.layout
            if n == 1:
                chosen_label = "proposal"
            elif 2 <= n <= len(alternatives) + 1:
                best = alternatives[n - 2]
                chosen_label = "alternative %d" % n
            else:
                print("ERROR: --layout %d nije ponudeni broj (1..%d)"
                      % (n, len(alternatives) + 1), file=sys.stderr)
                return None, False
        elif args.yes or args.dry_run:
            chosen_label = "proposal"
        else:
            best, chosen_label = ask_layout(best, alternatives,
                                           "Koji raspored? ")

    written = write_print_options(root, best, warn)
    report("")
    report("  ISPIS")
    for key in ("_preview.profile", "_preview.plan"):
        if key in written:
            report("   %-17s scalemode=%s scale=%s  %s"
                   % (key, written[key]["scalemode"], written[key]["scale"],
                      " ".join("%s=%s" % pair for pair in PREVIEW_COMMON)))
    report("   sharedsettings    preview.designquality=2 preview.manualrefresh=0")

    sidecar = {
        "source": os.path.basename(inp),
        "output": os.path.basename(out_path),
        "entrance": entrance,
        "entrance_witnesses": {k: v for k, v in witnesses.items()
                               if k != "sign_detail"},
        "entrance_sign": sign,
        "dislivello": dislivello,
        # Ours, not cSurvey's: bounded by the boundary wall and the shots only.
        "pvr_m": None if vertical is None else vertical["pvr_m"],
        "nvr_m": None if vertical is None else vertical["nvr_m"],
        "vertical_from": None if vertical is None else vertical["from"],
        "scale_bar": scale_bar,
        "compass": None if compass is None
                   else {k: v for k, v in compass.items() if k != "extra_entries"},
        "warnings": warnings,
        "plan_bbox_m": plan_after,
        "profile_bbox_m": profile_after,
        "pad_m": PAD_M,
        "chosen": chosen_label,
    }
    if best is None:
        sidecar.update({"plan_scale": None, "profile_scale": None,
                        "mjerilo": None, "arrangement": None,
                        "plan_mm": None, "profile_mm": None,
                        "plan_size_m": None, "profile_size_m": None,
                        "no_fit_reason": reason})
    else:
        plan_box, profile_box = layout_bbox(plan_after), layout_bbox(profile_after)
        sidecar.update({
            "plan_scale": best.plan_scale,
            "profile_scale": best.profile_scale,
            "mjerilo": best.mjerilo,
            "arrangement": best.arrangement,
            "plan_size_m": [round(plan_box.width, 2), round(plan_box.height, 2)],
            "profile_size_m": [round(profile_box.width, 2),
                               round(profile_box.height, 2)],
            "plan_mm": {"x": best.plan.x, "y": best.plan.y,
                        "width": best.plan.width, "height": best.plan.height},
            "profile_mm": {"x": best.profile.x, "y": best.profile.y,
                           "width": best.profile.width,
                           "height": best.profile.height},
        })

    if warnings:
        report("")
        report("  UPOZORENJA")
        for message in warnings:
            report("   ! %s" % message)

    if args.dry_run:
        report("")
        report("  --dry-run: nista nije zapisano.")
        return sidecar, True

    extra = (compass or {}).get("extra_entries") or {}
    write_root(root, inp, out_path, is_csz, style, extra)
    with open(os.path.splitext(out_path)[0] + ".layout.json", "w",
              encoding="utf-8") as f:
        json.dump(sidecar, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    report("")
    report("  OK  %s" % out_path)
    return sidecar, True


# ---------------------------------------------------------------------------
# CLI


def finish_state(path):
    """Short Croatian label for the --sb menu: is this file at this step?"""
    try:
        root, _is_csz, _style = load_root(path)
    except Exception:
        return "ne mogu procitati"
    if not_yet_imported(root):
        return "nije uvezeno u cSurvey - prvo KORAK 2"
    plan = root.find("plan")
    if plan is not None and has_quota(plan, "6"):
        return "vec dovrseno (ima mjerilo)"
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    if stem.endswith("_lt"):
        return "dovrsen uvoz (_lt) - ovo dovrsavas"
    return "nije _lt - provjeri je li skica ispravljena"


def pick_by_sb(inputs, sb):
    """--sb: intake folder + Redni broj -> the file(s) to finish, or None."""
    dirs = [a for a in inputs if os.path.isdir(a)]
    if len(dirs) != len(inputs) or len(dirs) != 1:
        print("ERROR: --sb takes exactly one folder (the intake dir) as input",
              file=sys.stderr)
        return None
    intake = dirs[0]
    leaves = sb_select.resolve(intake, sb)
    if leaves is None:
        return None
    files = sb_select.list_files(leaves, (".csz", ".csx"), skip_suffixes=("_fin",))
    if not files:
        print("nothing to do - u toj mapi nema .csz ni .csx datoteke")
        return None
    # The _lt is what KORAK 2 made and the drafter corrected — the one input
    # here. Ask only if a cave has none, or more than one.
    labels = [finish_state(f) for f in files]
    return sb_select.pick(
        files, lambda f: os.path.splitext(f)[0].lower().endswith("_lt"),
        leaves, labels=labels, root=intake, prompt="Koju datoteku dovrsiti? ")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Dovrsi ispravljeni _lt survey za ispis Nacrta (KORAK 3).")
    ap.add_argument("input", nargs="+",
                    help="corrected _lt .csz or .csx file(s) saved by cSurvey")
    ap.add_argument("-o", "--out",
                    help="output path (default: <input>_fin.<same ext>); "
                         "single input only")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing output")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would change and write nothing")
    ap.add_argument("--yes", action="store_true",
                    help="accept the proposed layout without asking")
    ap.add_argument("--layout", type=int, metavar="N",
                    help="take layout N from the menu (1 = the proposal)")
    ap.add_argument("--sb", nargs="+", metavar="BROJ",
                    help="with a folder input: pick the file from that cave's "
                         "SB_<broj>_... leaf")
    args = ap.parse_args(argv)

    if args.sb:
        picked = pick_by_sb(args.input, args.sb)
        if picked is None:
            return 1
        args.input = picked

    if args.out and len(args.input) > 1:
        print("ERROR: -o/--out works with a single input only", file=sys.stderr)
        return 1

    batch = len(args.input) > 1
    rc = 0
    for inp in args.input:
        base, ext = os.path.splitext(inp)
        if batch and base.lower().endswith("_fin"):
            print("skip %s (already a _fin output)" % inp)
            continue
        if not os.path.exists(inp):
            print("ERROR: %s does not exist" % inp, file=sys.stderr)
            rc = 1
            continue
        out_path = args.out or (base + "_fin" + ext)
        if os.path.abspath(out_path) == os.path.abspath(inp):
            print("ERROR: output must differ from input (%s)" % inp,
                  file=sys.stderr)
            rc = 1
            continue
        if (not args.dry_run and os.path.exists(out_path) and not args.force):
            print("ERROR: %s exists (use --force)" % out_path, file=sys.stderr)
            rc = 1
            continue
        try:
            sidecar, ok = finish(inp, out_path, args, print)
        except (ET.ParseError, ValueError, zipfile.BadZipFile) as e:
            print("ERROR: cannot process %s (%s) — is it really a cSurvey file?"
                  % (inp, e), file=sys.stderr)
            rc = 1
            continue
        if not ok:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
