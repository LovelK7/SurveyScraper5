"""nacrt_finish — the XML finisher that turns a corrected `_lt` into a printable file.

Two layers of coverage. A **synthetic `.csx`** built in-process exercises every
rule on every machine: the two entrance witnesses and their disagreement, the
Dislivello at the profile's lowest floor point, the scale bar's length, the
compass clipart, the print options, the no-fit fallback, the `.csz` container,
idempotence and `--dry-run`. The **real SB 1103 fixture pair**
(`example/finishing/SB_1103_golobreska_lt_{raw,finished}.csx`) is the oracle for
what cSurvey itself writes — it is gitignored, so those tests skip when absent.
"""

import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import nacrt_finish  # noqa: E402
import nacrt_layout  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "example" / "finishing"
RAW = FIXTURES / "SB_1103_golobreska_lt_raw.csx"
FINISHED = FIXTURES / "SB_1103_golobreska_lt_finished.csx"

needs_fixture = pytest.mark.skipif(
    not RAW.exists(),
    reason="the SB 1103 fixture pair is gitignored (surveys are never committed)")


# ---------------------------------------------------------------------------
# a synthetic survey
#
# Three non-splay stations plus one splay. Plan design coords are (x, y),
# profile design coords are (d, z) — so B, the highest station (z is positive
# downward), sits at (3, -5) in the profile and (3, 0) in the plan.

SEG_AB = "11111111-1111-1111-1111-111111111111"
SEG_BC = "22222222-2222-2222-2222-222222222222"

DEFAULT_STATIONS = [
    # name,  x,   y,    z,     d
    ("A", 0.0, 0.0, 0.0, 0.0),
    ("B", 3.0, 0.0, -5.0, 3.0),
    ("C", 6.0, 0.0, 2.0, 6.0),
    ("A(0)", 0.5, 0.5, -99.0, 0.5),      # a splay, and the lowest z of all
]

PREVIEW_ATTRS = ('drawsplay="1" drawscale="1" drawcompass="1" printername=""'
                 ' pagemargins="0;0;0;0" pageformat="" scalemode="0" scale="0"')


def _layers(borders_points, sign_items):
    rows = ['      <layer name="Base" type="0">', '        <items />',
            '      </layer>']
    rows += ['      <layer name="Borders" type="5">', '        <items>']
    if borders_points:
        rows += ['          <item layer="5" cave="Jama" branch="1" type="1"'
                 ' category="16">',
                 '            <points data="%s" />' % borders_points,
                 '          </item>']
    rows += ['        </items>', '      </layer>']
    rows += ['      <layer name="Signs" type="6">']
    if sign_items:
        rows += ['        <items>'] + sign_items + ['        </items>']
    else:
        rows += ['        <items />']
    rows += ['      </layer>']
    return "\n".join(rows)


def _entrance_sign(x, y, segment=SEG_AB):
    return ['          <item layer="6" cave="Jama" branch="1" type="6"'
            ' category="80" data="DEADBEEF" dataformat="2" sign="263">',
            '            <pen type="10" />',
            '            <brush type="7" />',
            '            <points data="%.2f %.2f S%s " />' % (x, y, segment),
            '          </item>']


def make_csx(path, *, stations=DEFAULT_STATIONS, origin="A",
             plan_borders="-1.00 -1.00 7.00 5.00 ",
             profile_borders="-1.00 -2.00 7.00 3.00 ",
             plan_sign=None, profile_sign=None, cliparts="",
             declaration=True, crlf=False, trigpoints=None):
    """Write a minimal but structurally faithful cSurvey `.csx`."""
    names = [n for n, *_ in stations] if trigpoints is None else trigpoints
    ts = "\n".join(
        '      <t n="%s">\n'
        '        <p x="%.4f" y="%.4f" z="%.4f" d="%.4f" />\n'
        '      </t>' % (name, x, y, z, d) for name, x, y, z, d in stations)
    body = """<csurvey version="1.14" id="synthetic">
  <properties id="" name="" origin="%(origin)s" nordcorrectionmode="0">
    <sessions />
  </properties>
  <segments>
    <segment id="%(seg_ab)s" from="A" to="B" distance="3.00" />
    <segment id="%(seg_bc)s" from="B" to="C" distance="3.00" />
    <segment id="33333333-3333-3333-3333-333333333333" from="A" to="A(0)" splay="1" exclude="1" />
  </segments>
  <trigpoints>
%(trigpoints)s
  </trigpoints>
  <options>
    <_preview.plan %(preview)s />
    <_preview.profile %(preview)s />
  </options>
  <signs>
    <cliparts>%(cliparts)s</cliparts>
  </signs>
  <plan>
    <layers>
%(plan_layers)s
    </layers>
    <pointsjoins />
    <plot />
  </plan>
  <profile>
    <layers>
%(profile_layers)s
    </layers>
    <pointsjoins />
    <plot />
  </profile>
  <sharedsettings>
    <values legacycalculation1="off" />
  </sharedsettings>
  <calculate>
    <ts>
%(ts)s
    </ts>
    <sms>
      <sm pl="4.00" l="10.00" qmx="5.00" qmn="-2.00" />
    </sms>
  </calculate>
</csurvey>""" % {
        "origin": origin,
        "seg_ab": SEG_AB,
        "seg_bc": SEG_BC,
        "trigpoints": "\n".join('    <trigpoint name="%s" labelsymbol="0" />' % n
                                for n in names),
        "preview": PREVIEW_ATTRS,
        "cliparts": cliparts,
        "plan_layers": _layers(plan_borders,
                               _entrance_sign(*plan_sign) if plan_sign else None),
        "profile_layers": _layers(profile_borders,
                                  _entrance_sign(*profile_sign) if profile_sign
                                  else None),
        "ts": ts,
    }
    if declaration:
        body = "<?xml version='1.0' encoding='utf-8'?>\n" + body
    data = body.encode("utf-8")
    if crlf:
        data = data.replace(b"\n", b"\r\n")
    path = Path(path)
    path.write_bytes(data)
    return path


def run(argv):
    """The CLI, as an operator would reach it. Returns the exit code."""
    return nacrt_finish.main([str(a) for a in argv])


def sidecar_of(out):
    return json.loads(Path(str(Path(out).with_suffix("")) + ".layout.json")
                      .read_text(encoding="utf-8"))


def finish_to(tmp_path, name="cave_lt.csx", extra=(), **kwargs):
    """Build a synthetic survey, finish it, return (out_path, sidecar)."""
    src = make_csx(tmp_path / name, **kwargs)
    out = tmp_path / (src.stem + "_fin" + src.suffix)
    assert run([src, "--yes", *extra]) == 0
    return out, sidecar_of(out)


def items_of(root, design, layer_type=None):
    types = None if layer_type is None else (layer_type,)
    return list(nacrt_finish.iter_items(root.find(design), types))


def warned(sidecar, needle):
    return any(needle in w for w in sidecar["warnings"])


# ---------------------------------------------------------------------------
# witness (a): the highest station


def test_highest_station_is_min_z_and_ignores_splays(tmp_path):
    root, _csz, _style = nacrt_finish.load_root(str(make_csx(tmp_path / "s.csx")))
    stations = nacrt_finish.read_stations(root)
    # A(0) has the lowest z of all four, and is dropped for being a splay
    assert [s.name for s in stations] == ["A", "B", "C"]
    assert nacrt_finish.witness_highest(stations) == ("B", -5.0, [])


def test_highest_station_reports_ties_within_half_a_metre():
    stations = [nacrt_finish.Station("A", 0, 0, 0.0, 0),
                nacrt_finish.Station("B", 0, 0, -5.0, 0),
                nacrt_finish.Station("C", 0, 0, -4.7, 0)]
    name, _z, ties = nacrt_finish.witness_highest(stations)
    assert name == "B"
    assert ties == ["C"]


def test_highest_station_of_nothing_is_nothing():
    assert nacrt_finish.witness_highest([]) == (None, None, [])


# ---------------------------------------------------------------------------
# witness (b): the drawn entrance sign


def test_sign_witness_takes_the_nearest_station_in_plan_coords(tmp_path):
    root, _csz, _style = nacrt_finish.load_root(
        str(make_csx(tmp_path / "s.csx", plan_sign=(3.1, 0.1))))
    stations = nacrt_finish.read_stations(root)
    found = nacrt_finish.witness_sign(root, stations, "plan")
    assert found["station"] == "B"
    assert found["distance"] == pytest.approx(0.14, abs=0.01)
    assert found["segment"] == "A->B"
    assert found["segment_station"] == "B"


def test_sign_witness_uses_d_and_z_in_the_profile(tmp_path):
    # (d, z) of C is (6, 2); its (x, y) is (6, 0). A sign at (6.1, 2.1) is next
    # to C only if the profile is read in (d, z).
    root, _csz, _style = nacrt_finish.load_root(
        str(make_csx(tmp_path / "s.csx", profile_sign=(6.1, 2.1, SEG_BC))))
    stations = nacrt_finish.read_stations(root)
    found = nacrt_finish.witness_sign(root, stations, "profile")
    assert found["station"] == "C"
    assert found["design"] == "profile"


def test_sign_witness_is_none_without_a_sign(tmp_path):
    root, _csz, _style = nacrt_finish.load_root(str(make_csx(tmp_path / "s.csx")))
    stations = nacrt_finish.read_stations(root)
    assert nacrt_finish.witness_sign(root, stations, "plan") is None
    assert nacrt_finish.witness_sign(root, stations, "profile") is None


def test_sign_witness_ignores_other_signs(tmp_path):
    """A blocks sign (1290) next to C must not be read as an entrance."""
    src = make_csx(tmp_path / "s.csx", plan_sign=(3.1, 0.1))
    text = src.read_text(encoding="utf-8").replace(
        'sign="263"', 'sign="263" x="keep"', 1)
    # add a non-entrance sign right on top of station C
    text = text.replace(
        '        </items>\n      </layer>\n    </layers>\n    <pointsjoins />\n'
        '    <plot />\n  </plan>',
        '          <item layer="6" type="6" category="80" sign="1290">\n'
        '            <points data="6.00 0.00 " />\n'
        '          </item>\n'
        '        </items>\n      </layer>\n    </layers>\n    <pointsjoins />\n'
        '    <plot />\n  </plan>', 1)
    src.write_text(text, encoding="utf-8")
    root, _csz, _style = nacrt_finish.load_root(str(src))
    stations = nacrt_finish.read_stations(root)
    assert nacrt_finish.witness_sign(root, stations, "plan")["station"] == "B"


# ---------------------------------------------------------------------------
# the entrance decision


def test_entrance_from_both_witnesses_agreeing(tmp_path):
    _out, sidecar = finish_to(tmp_path, plan_sign=(3.1, 0.1), origin="B")
    assert sidecar["entrance"] == "B"
    assert sidecar["entrance_witnesses"]["highest"] == "B"
    assert sidecar["entrance_witnesses"]["sign"] == "B"
    assert "slozna" in sidecar["entrance_witnesses"]["decision"]
    assert sidecar["warnings"] == []


def test_the_sign_wins_when_the_two_witnesses_disagree(tmp_path):
    """A ponor: the entrance sign sits on C, but B is the highest station."""
    _out, sidecar = finish_to(tmp_path, plan_sign=(6.1, 0.1, SEG_BC))
    assert sidecar["entrance"] == "C"
    assert sidecar["entrance_witnesses"]["highest"] == "B"
    assert warned(sidecar, "uzimam znak ulaza")


def test_plan_beats_profile_when_the_signs_disagree(tmp_path):
    _out, sidecar = finish_to(tmp_path, plan_sign=(3.1, 0.1),
                              profile_sign=(6.1, 2.1, SEG_BC))
    assert sidecar["entrance"] == "B"
    assert warned(sidecar, "uzimam tlocrt")


def test_origin_mismatch_warns_when_there_is_no_sign(tmp_path):
    _out, sidecar = finish_to(tmp_path, origin="A")
    assert sidecar["entrance"] == "B"
    assert warned(sidecar, "properties@origin")


def test_no_origin_warning_when_origin_agrees(tmp_path):
    _out, sidecar = finish_to(tmp_path, origin="B")
    assert sidecar["warnings"] == []


def test_tie_in_z_warns_when_there_is_no_sign(tmp_path):
    stations = [("A", 0.0, 0.0, 0.0, 0.0), ("B", 3.0, 0.0, -5.0, 3.0),
                ("C", 6.0, 0.0, -4.7, 6.0)]
    _out, sidecar = finish_to(tmp_path, stations=stations, origin="B")
    assert sidecar["entrance"] == "B"
    assert warned(sidecar, "unutar 0.5 m po visini")


def test_entrance_attribute_is_the_constant_two_not_the_station_name(tmp_path):
    """`entrance="2"` is EntranceTypeEnum.MainCaveEntrace — on SB 1103 the
    station is also called "2", which makes the value look like a name."""
    out, sidecar = finish_to(tmp_path, origin="B")
    assert sidecar["entrance"] == "B"
    root = ET.parse(str(out)).getroot()
    flagged = [tp.get("name") for tp in root.find("trigpoints")
               if tp.get("entrance") == "2"]
    assert flagged == ["B"]


def test_entrance_is_removed_from_every_other_trigpoint(tmp_path):
    src = make_csx(tmp_path / "cave_lt.csx", origin="B")
    text = src.read_text(encoding="utf-8").replace(
        '<trigpoint name="C" labelsymbol="0" />',
        '<trigpoint name="C" labelsymbol="0" entrance="2" />')
    src.write_text(text, encoding="utf-8")
    out = tmp_path / "cave_lt_fin.csx"
    assert run([src, "--yes"]) == 0
    root = ET.parse(str(out)).getroot()
    flagged = {tp.get("name"): tp.get("entrance")
               for tp in root.find("trigpoints")}
    assert flagged["B"] == "2"
    assert flagged["C"] is None
    assert warned(sidecar_of(out), "uklonio entrance")


def test_a_missing_trigpoint_is_created_rather_than_left_unflagged(tmp_path):
    out, sidecar = finish_to(tmp_path, origin="B",
                            trigpoints=["A", "C", "A(0)"])
    root = ET.parse(str(out)).getroot()
    flagged = [tp.get("name") for tp in root.find("trigpoints")
               if tp.get("entrance") == "2"]
    assert flagged == ["B"]
    assert warned(sidecar, "dodajem ga")


# ---------------------------------------------------------------------------
# the Dislivello quota


def test_dislivello_sits_at_the_lowest_borders_point_and_names_the_entrance(tmp_path):
    out, sidecar = finish_to(tmp_path, origin="B")
    # profile Borders span (-1, -2) to (7, 3); depth grows with y, so (7, 3).
    assert sidecar["dislivello"]["lowest"] == [7.0, 3.0]
    assert sidecar["dislivello"]["source"] == "Borders"
    assert sidecar["dislivello"]["points"] == [8.5, 3.0, 8.85, 3.35]
    root = ET.parse(str(out)).getroot()
    quotas = [i for i in items_of(root, "profile") if i.get("quotatype") == "3"]
    assert len(quotas) == 1
    item = quotas[0]
    assert item.get("quotarelativetrigpoint") == "B"
    assert item.get("type") == "10" and item.get("category") == "82"
    assert item.get("layer") == "6"
    assert item.get("cave") == "Jama" and item.get("branch") == "1"
    # cSurvey computes the printed depth at paint time from quotavalue=0.
    assert item.get("text") == "" and item.get("quotavalue") == "0"
    assert item.find("points").get("data") == "8.50 3.00 8.85 3.35 "
    # cItemQuota has HavePen/HaveBrush False, so cSurvey writes neither.
    assert [child.tag for child in item] == ["points", "font"]


def test_dislivello_falls_back_to_all_layers_when_borders_is_empty(tmp_path):
    _out, sidecar = finish_to(tmp_path, origin="B", profile_borders="",
                              profile_sign=(6.1, 2.1, SEG_BC))
    # the only remaining profile points are the entrance sign's
    assert sidecar["dislivello"]["source"] == "svi slojevi"
    assert warned(sidecar, "sloj Borders je prazan")


def test_dislivello_is_skipped_when_one_is_already_there(tmp_path):
    out, _sidecar = finish_to(tmp_path, origin="B")
    second = tmp_path / "again_fin.csx"
    assert run([out, "-o", second, "--yes"]) == 0
    root = ET.parse(str(second)).getroot()
    assert len([i for i in items_of(root, "profile")
                if i.get("quotatype") == "3"]) == 1
    assert warned(sidecar_of(second), "vec ima dislivello")


# ---------------------------------------------------------------------------
# height and depth: the boundary wall and the shots, nothing else


def test_vertical_extent_ignores_a_symbol_drawn_above_the_entrance(tmp_path):
    """The bug this rule exists for (user, 2026-09-20).

    cSurvey takes the profile design's whole bounding box, so SB 1103's
    entrance sign — drawn 1.4 m above station `2` — made a cave that does not
    rise above its entrance at all report `pvr = 1 m`.
    """
    root, _csz, _style = nacrt_finish.load_root(str(make_csx(
        tmp_path / "s.csx",
        # the Borders run from 1 m above the entrance to 4 m below it
        profile_borders="-1.00 -6.00 7.00 -1.00 ",
        # ...and a sign floats 3 m higher again
        profile_sign=(2.0, -9.0, SEG_BC),
        # every station is between the walls, so the walls are the only bound
        stations=[("A", 0.0, 0.0, -2.0, 0.0), ("B", 3.0, 0.0, -5.0, 3.0),
                  ("C", 6.0, 0.0, -3.0, 6.0)])))
    stations = nacrt_finish.read_stations(root)
    extent = nacrt_finish.vertical_extent(root, "B", stations)
    # entrance B is at z -5: the wall reaches -6 (1 m above) and -1 (4 m below);
    # the sign at -9 is 4 m higher still and must not count.
    assert extent["pvr_m"] == 1.0
    assert extent["nvr_m"] == 4.0
    assert "Borders" in extent["from"]


def test_vertical_extent_counts_a_shot_outside_the_drawing(tmp_path):
    """A wall is not the only bound: a station below the traced floor counts."""
    root, _csz, _style = nacrt_finish.load_root(str(make_csx(
        tmp_path / "s.csx", profile_borders="-1.00 -6.00 7.00 -1.00 ")))
    stations = nacrt_finish.read_stations(root)
    # C sits at z 2, five metres below the entrance B and below the wall's -1
    assert nacrt_finish.vertical_extent(root, "B", stations)["nvr_m"] == 7.0


def test_vertical_extent_is_none_without_an_entrance(tmp_path):
    root, _csz, _style = nacrt_finish.load_root(str(make_csx(tmp_path / "s.csx")))
    stations = nacrt_finish.read_stations(root)
    assert nacrt_finish.vertical_extent(root, None, stations) is None
    assert nacrt_finish.vertical_extent(root, "nema", stations) is None


def test_the_extents_reach_the_sidecar(tmp_path):
    _out, sidecar = finish_to(tmp_path, origin="B")
    # entrance B is the highest of everything (stations 0/-5/2, Borders -2..3),
    # so nothing is above it and the floor is 8 m below
    assert sidecar["pvr_m"] == 0.0
    assert sidecar["nvr_m"] == 8.0
    assert sidecar["vertical_from"] == "Borders + stanice"


# ---------------------------------------------------------------------------
# where the Dislivello label goes


def test_the_label_clears_only_what_is_drawn_beside_it(tmp_path):
    """Not the whole design: a ceiling far above the floor must not push the
    label out (user, 2026-09-20)."""
    root, _csz, _style = nacrt_finish.load_root(str(make_csx(
        tmp_path / "s.csx",
        # a wide ceiling at y -5, a narrow floor at y 3
        profile_borders="0.00 -5.00 20.00 -5.00 0.00 3.00 4.00 3.00 ")))
    design = root.find("profile")
    assert nacrt_finish.right_of_depth(design, 3.0) == 4.0      # the floor only
    assert nacrt_finish.right_of_depth(design, -5.0) == 20.0    # the ceiling only
    # a band wide enough to reach both sees both
    assert nacrt_finish.right_of_depth(design, 3.0, band=10.0) == 20.0


def test_the_label_sits_beside_the_floor_not_beside_the_ceiling(tmp_path):
    out, sidecar = finish_to(
        tmp_path, origin="B",
        profile_borders="0.00 -5.00 20.00 -5.00 0.00 3.00 4.00 3.00 ")
    assert sidecar["dislivello"]["right_at_depth"] == 4.0
    assert sidecar["dislivello"]["points"][0] == 5.5            # 4.0 + the gap
    root = ET.parse(str(out)).getroot()
    quota = [i for i in items_of(root, "profile") if i.get("quotatype") == "3"][0]
    assert quota.find("points").get("data").startswith("5.50 3.00 ")


# ---------------------------------------------------------------------------
# the horizontal scale bar


def test_scale_bar_is_five_metres_at_one_to_a_hundred(tmp_path):
    out, sidecar = finish_to(tmp_path, origin="B")
    assert sidecar["plan_scale"] == 100
    bar = sidecar["scale_bar"]
    assert (bar["length_m"], bar["tick"], bar["label_every"]) == (5.0, 1.0, 5.0)
    # plan Borders span (-1, -1) to (7, 5). Beside the plan the bar would end
    # 10.5 m right of the plan's centre - 105 mm at 1:100, past the printable
    # 92 mm - so it goes under: right-aligned (ends at maxx 7), 5 m long, and
    # dropped by gap 1 + arrow 2.5 + gap 1 below maxy 5.
    assert bar["place"] == "under"
    assert bar["points"] == [2.0, 9.5, 7.0, 9.5]
    root = ET.parse(str(out)).getroot()
    bars = [i for i in items_of(root, "plan") if i.get("quotatype") == "6"]
    assert len(bars) == 1
    assert bars[0].get("quotatickfrequency") == "1.00"
    assert bars[0].get("quotaticklabelfrequency") == "5.00"
    assert bars[0].get("quotaticksize") == "0.30"
    # a HorizontalScale measures nothing against a station
    assert bars[0].get("quotarelativetrigpoint") == ""


def test_scale_bar_is_ten_metres_at_a_coarser_scale(tmp_path):
    """A 30 m plan cannot be printed at 1:100 on A4, so the bar doubles."""
    out, sidecar = finish_to(tmp_path, origin="B",
                             plan_borders="0.00 0.00 30.00 20.00 ",
                             profile_borders="0.00 0.00 30.00 20.00 ")
    assert sidecar["plan_scale"] != 100
    bar = sidecar["scale_bar"]
    assert (bar["length_m"], bar["tick"], bar["label_every"]) == (10.0, 2.0, 10.0)
    root = ET.parse(str(out)).getroot()
    bars = [i for i in items_of(root, "plan") if i.get("quotatype") == "6"]
    assert bars[0].get("quotatickfrequency") == "2.00"
    assert bars[0].get("quotaticklabelfrequency") == "10.00"


def test_scale_bar_is_skipped_when_one_is_already_there(tmp_path):
    out, _sidecar = finish_to(tmp_path, origin="B")
    second = tmp_path / "again_fin.csx"
    assert run([out, "-o", second, "--yes"]) == 0
    root = ET.parse(str(second)).getroot()
    assert len([i for i in items_of(root, "plan")
                if i.get("quotatype") == "6"]) == 1
    assert warned(sidecar_of(second), "vec ima mjerilo")


# ---------------------------------------------------------------------------
# the compass


COMPASS_ID = "DAD658813B5353C9F1CF3BC916D482D323A3ABBB"


def test_compass_clipart_is_spliced_in_when_missing(tmp_path):
    out, sidecar = finish_to(tmp_path, origin="B")
    assert sidecar["compass"]["clipart"] == COMPASS_ID
    assert sidecar["compass"]["clipart_added"] == "compass3.svg"
    root = ET.parse(str(out)).getroot()
    cliparts = root.find("signs/cliparts").findall("clipart")
    assert [c.get("name") for c in cliparts] == ["compass3.svg"]
    assert len(cliparts[0].get("data")) > 1000          # inline base64, .csx form
    items = [i for i in items_of(root, "plan") if i.get("type") == "15"]
    assert len(items) == 1
    compass = items[0]
    assert compass.get("category") == "83"
    assert compass.get("data") == COMPASS_ID
    assert compass.get("dataformat") == "2"
    # m=1 is CompassModeEnum.Manual and no @n means Geographic, so the label is
    # a plain "N" instead of Auto's "Nm <year>".
    assert compass.get("m") == "1"
    assert compass.get("n") is None
    assert [child.tag for child in compass] == ["pen", "brush", "points", "font"]
    # above the middle of the bar: bar runs 2.0..7.0 at y 9.5, and the arrow's
    # bottom sits COMPASS_ABOVE_M up from it
    assert compass.find("points").get("data") == "4.50 8.50 "


def test_an_existing_compass_clipart_is_reused(tmp_path):
    existing = ('<clipart id="CAFE01" name="compass3.svg" data="Zm9v" />')
    out, sidecar = finish_to(tmp_path, origin="B", cliparts=existing)
    assert sidecar["compass"]["clipart"] == "CAFE01"
    assert sidecar["compass"]["clipart_added"] is None
    root = ET.parse(str(out)).getroot()
    assert len(root.find("signs/cliparts").findall("clipart")) == 1


def test_compass_is_skipped_when_one_is_already_there(tmp_path):
    out, _sidecar = finish_to(tmp_path, origin="B")
    second = tmp_path / "again_fin.csx"
    assert run([out, "-o", second, "--yes"]) == 0
    root = ET.parse(str(second)).getroot()
    assert len([i for i in items_of(root, "plan") if i.get("type") == "15"]) == 1
    assert warned(sidecar_of(second), "vec ima busolu")


def test_the_shipped_clipart_asset_hashes_to_its_own_id():
    cid, name, blob = nacrt_finish.load_compass_clipart()
    assert (cid, name) == (COMPASS_ID, "compass3.svg")
    assert blob.startswith(b"<?xml") and b"<svg" in blob


# ---------------------------------------------------------------------------
# print options


def test_print_options_and_render_quality_are_written(tmp_path):
    out, sidecar = finish_to(tmp_path, origin="B")
    root = ET.parse(str(out)).getroot()
    for key in ("_preview.plan", "_preview.profile"):
        el = root.find("options/" + key)
        assert el.get("pageformat") == "A4"
        assert el.get("pagemargins") == "10;10;10;10"
        assert el.get("designstyle") == "0"
        assert el.get("drawsplay") == "0"
        assert el.get("drawscale") == "0"
        assert el.get("drawcompass") == "0"
        assert el.get("drawbox") == "0"
        assert el.get("printername") == "Microsoft Print to PDF"
        assert el.get("pagelandscape") is None
        assert el.get("scalemode") == "1"
        assert el.get("scale") == "100"
    values = root.find("sharedsettings/values")
    assert values.get("preview.designquality") == "2"
    assert values.get("preview.manualrefresh") == "0"
    assert sidecar["mjerilo"] == "1:100"


def test_pagelandscape_is_removed(tmp_path):
    src = make_csx(tmp_path / "cave_lt.csx", origin="B")
    src.write_text(src.read_text(encoding="utf-8").replace(
        'pageformat=""', 'pageformat="" pagelandscape="1"'), encoding="utf-8")
    out = tmp_path / "cave_lt_fin.csx"
    assert run([src, "--yes"]) == 0
    root = ET.parse(str(out)).getroot()
    for key in ("_preview.plan", "_preview.profile"):
        assert root.find("options/" + key).get("pagelandscape") is None


def test_the_custom_scale_rides_on_scalemode_99(tmp_path):
    """1:400 has no combo entry: it goes out as scalemode=99 + scale=400."""
    assert nacrt_layout.SCALEMODE[400] == 99
    # a profile this long needs 1:400 and pulls the plan to 1:300
    out, sidecar = finish_to(tmp_path, origin="B",
                             plan_borders="0.00 0.00 20.00 20.00 ",
                             profile_borders="0.00 0.00 20.00 85.00 ")
    assert sidecar["profile_scale"] == 400
    root = ET.parse(str(out)).getroot()
    profile = root.find("options/_preview.profile")
    assert profile.get("scalemode") == "99"
    assert profile.get("scale") == "400"


def test_nothing_fits_falls_back_to_cSurvey_fit_to_page(tmp_path):
    out, sidecar = finish_to(tmp_path, origin="B",
                             plan_borders="0.00 0.00 200.00 150.00 ",
                             profile_borders="0.00 0.00 300.00 200.00 ")
    assert sidecar["chosen"] == "fit-to-page"
    assert sidecar["plan_scale"] is None
    assert sidecar["mjerilo"] is None
    assert sidecar["plan_mm"] is None
    assert "1:500" in sidecar["no_fit_reason"]
    assert warned(sidecar, "scalemode=0")
    root = ET.parse(str(out)).getroot()
    for key in ("_preview.plan", "_preview.profile"):
        el = root.find("options/" + key)
        assert (el.get("scalemode"), el.get("scale")) == ("0", "0")
        assert el.get("pageformat") == "A4"     # the page is still set up


# ---------------------------------------------------------------------------
# the layout menu


def test_layout_picks_an_alternative_non_interactively(tmp_path):
    src = make_csx(tmp_path / "cave_lt.csx", origin="B")
    out = tmp_path / "cave_lt_fin.csx"
    assert run([src, "--layout", 2]) == 0
    sidecar = sidecar_of(out)
    assert sidecar["chosen"] == "alternative 2"
    assert sidecar["arrangement"] == "side_by_side"


def test_layout_out_of_range_is_an_error(tmp_path, capsys):
    src = make_csx(tmp_path / "cave_lt.csx", origin="B")
    assert run([src, "--layout", 9]) == 1
    assert "nije ponudeni broj" in capsys.readouterr().err
    assert not (tmp_path / "cave_lt_fin.csx").exists()


def test_the_sidecar_carries_millimetres_for_the_compositor(tmp_path):
    _out, sidecar = finish_to(tmp_path, origin="B")
    for key in ("plan_mm", "profile_mm"):
        box = sidecar[key]
        assert set(box) == {"x", "y", "width", "height"}
        assert box["x"] >= 10.0 and box["y"] >= 10.0
        assert box["x"] + box["width"] <= 200.0
        assert box["y"] + box["height"] <= 287.0
    # the profile is the primary drawing and sits on top
    assert sidecar["profile_mm"]["y"] <= sidecar["plan_mm"]["y"]
    assert sidecar["arrangement"] == "vertical"


# ---------------------------------------------------------------------------
# containers, byte fidelity, idempotence, --dry-run


def test_csz_round_trip_keeps_every_zip_entry(tmp_path):
    inner = make_csx(tmp_path / "inner.csx", origin="B")
    src = tmp_path / "cave_lt.csz"
    entries = {"_data.xml": inner.read_bytes(),
               "_data/images/sketch.png": b"\x89PNG not really",
               "_data/surface/dem.bin": b"\x00\x01\x02"}
    with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in entries.items():
            z.writestr(name, blob)
    out = tmp_path / "cave_lt_fin.csz"
    assert run([src, "--yes"]) == 0
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert names == set(entries) | {
            "_data/cliparts/%s.svg" % COMPASS_ID}
        for name, blob in entries.items():
            if name != "_data.xml":
                assert z.read(name) == blob
        root = ET.fromstring(z.read("_data.xml"))
        clipart = root.find("signs/cliparts/clipart")
        # the .csz form: @data is the *path*, with backslashes, and the SVG is
        # a zip entry — a forward-slash @data would not resolve on load.
        assert clipart.get("data") == "_data\\cliparts\\%s.svg" % COMPASS_ID
        assert z.read("_data/cliparts/%s.svg" % COMPASS_ID).startswith(b"<?xml")
    assert src.read_bytes() != out.read_bytes()


def test_only_our_elements_show_up_in_a_diff(tmp_path):
    """Everything else survives byte for byte, line endings included."""
    src = make_csx(tmp_path / "cave_lt.csx", origin="B",
                   declaration=False, crlf=True)
    out = tmp_path / "cave_lt_fin.csx"
    assert run([src, "--yes"]) == 0
    before = src.read_bytes()
    after = out.read_bytes()
    assert not after.startswith(b"<?xml version")     # cSurvey writes none
    assert b"\r\n" in after and b"\n\n" not in after
    gone = [line for line in before.split(b"\r\n")
            if line not in after.split(b"\r\n")]
    # exactly the five lines this tool writes on: the entrance trigpoint, the
    # two `_preview.*`, the `<cliparts>` the compass joins, and `<values>`.
    assert [line.strip().split(b" ")[0] for line in gone] == [
        b"<trigpoint", b"<_preview.plan", b"<_preview.profile",
        b"<cliparts></cliparts>", b"<values"]
    added = [line for line in after.split(b"\r\n")
             if line not in before.split(b"\r\n")]
    assert sum(1 for line in added if b"<item " in line) == 3
    assert sum(1 for line in added if b"<clipart " in line) == 1


def test_running_on_the_output_changes_nothing(tmp_path):
    out, _sidecar = finish_to(tmp_path, origin="B")
    again = tmp_path / "again_fin.csx"
    assert run([out, "-o", again, "--yes"]) == 0
    assert again.read_bytes() == out.read_bytes()
    sidecar = sidecar_of(again)
    assert all(warned(sidecar, needle) for needle in
               ("vec ima dislivello", "vec ima mjerilo", "vec ima busolu"))
    assert sidecar["entrance"] == "B"


def test_dry_run_writes_nothing(tmp_path, capsys):
    src = make_csx(tmp_path / "cave_lt.csx", origin="B")
    before = sorted(p.name for p in tmp_path.iterdir())
    assert run([src, "--dry-run"]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    out = capsys.readouterr().out
    assert "--dry-run: nista nije zapisano." in out
    assert "MJERILO I RASPORED" in out
    assert "dislivello" in out


def test_the_input_is_never_modified(tmp_path):
    src = make_csx(tmp_path / "cave_lt.csx", origin="B")
    before = src.read_bytes()
    assert run([src, "--yes"]) == 0
    assert src.read_bytes() == before


def test_an_existing_output_needs_force(tmp_path, capsys):
    src = make_csx(tmp_path / "cave_lt.csx", origin="B")
    out = tmp_path / "cave_lt_fin.csx"
    out.write_bytes(b"busy")
    assert run([src, "--yes"]) == 1
    assert "use --force" in capsys.readouterr().err
    assert out.read_bytes() == b"busy"
    assert run([src, "--yes", "--force"]) == 0
    assert out.read_bytes() != b"busy"


def test_a_file_not_yet_imported_is_blocked(tmp_path, capsys):
    src = tmp_path / "phone.csx"
    src.write_bytes(b'<csurvey version="1.14"><plan><item type="1">'
                    b'<points data="0 0 1 1 " /></item></plan>'
                    b"<profile /></csurvey>")
    assert run([src, "--yes"]) == 1
    assert "BLOCKED" in capsys.readouterr().err
    assert not (tmp_path / "phone_fin.csx").exists()


def test_a_name_without_lt_is_only_a_warning(tmp_path):
    _out, sidecar = finish_to(tmp_path, name="cave.csx", origin="B")
    assert warned(sidecar, "naziv ne sadrzi _lt")


# ---------------------------------------------------------------------------
# the real SB 1103 fixture — the oracle for what cSurvey writes


@needs_fixture
def test_sb1103_reproduces_the_manual_result(tmp_path):
    out = tmp_path / "SB_1103_golobreska_lt_fin.csx"
    assert run([RAW, "-o", out, "--yes"]) == 0
    sidecar = sidecar_of(out)
    root = ET.parse(str(out)).getroot()

    # entrance: station 2 by both witnesses (the oracle's <trigpoint name="2"
    # entrance="2">), even though properties@origin says 1.
    assert sidecar["entrance"] == "2"
    assert sidecar["entrance_witnesses"]["highest"] == "2"
    assert sidecar["entrance_witnesses"]["sign"] == "2"
    assert sidecar["entrance_witnesses"]["origin"] == "1"
    assert sidecar["warnings"] == []
    assert [tp.get("name") for tp in root.find("trigpoints")
            if tp.get("entrance") == "2"] == ["2"]

    # the three items, in the layers the manual steps put them in
    quotas = [i for i in items_of(root, "profile", "6")
              if i.get("quotatype") == "3"]
    assert len(quotas) == 1
    assert quotas[0].get("quotarelativetrigpoint") == "2"
    bars = [i for i in items_of(root, "plan", "6") if i.get("quotatype") == "6"]
    assert len(bars) == 1
    compasses = [i for i in items_of(root, "plan", "6") if i.get("type") == "15"]
    assert len(compasses) == 1
    assert compasses[0].get("m") == "1"

    # 1:100 / 1:100 vertical, per T4's worked example for this cave
    assert (sidecar["plan_scale"], sidecar["profile_scale"]) == (100, 100)
    assert sidecar["arrangement"] == "vertical"
    assert sidecar["mjerilo"] == "1:100"
    for key in ("_preview.plan", "_preview.profile"):
        el = root.find("options/" + key)
        assert el.get("pageformat") == "A4"
        assert el.get("scalemode") == "1"
        assert el.get("scale") == "100"


@needs_fixture
@pytest.mark.skipif(not FINISHED.exists(), reason="finished fixture missing")
def test_sb1103_matches_what_cSurvey_itself_wrote(tmp_path):
    """The attributes of our items equal the manual ones, `text` aside — cSurvey
    fills that in at paint time (`-9 m`), which is why we leave it empty."""
    out = tmp_path / "ours.csx"
    assert run([RAW, "-o", out, "--yes"]) == 0
    ours = ET.parse(str(out)).getroot()
    oracle = ET.parse(str(FINISHED)).getroot()

    def only(root, design, predicate):
        found = [i for i in items_of(root, design, "6") if predicate(i)]
        assert len(found) == 1, found
        return found[0]

    for design, predicate in (
            ("profile", lambda i: i.get("quotatype") == "3"),
            ("plan", lambda i: i.get("quotatype") == "6"),
            ("plan", lambda i: i.get("type") == "15")):
        mine, theirs = only(ours, design, predicate), only(oracle, design, predicate)
        for key, value in theirs.attrib.items():
            # text: cSurvey fills it at paint time, so ours is empty.
            # data: the clipart id, compared on its own below.
            # textalignment: a deliberate divergence — cSurvey's UI wrote Left
            #   (1), which anchors the compass glyph at its left edge and left
            #   the arrow a millimetre right of the scale bar; we write Center.
            if key in ("text", "data", "textalignment"):
                continue
            assert mine.get(key) == value, (design, key, mine.get(key), value)
        assert [c.tag for c in mine] == [c.tag for c in theirs]

    # the same clipart, resolved out of our shipped asset rather than the file
    assert (only(ours, "plan", lambda i: i.get("type") == "15").get("data")
            == only(oracle, "plan", lambda i: i.get("type") == "15").get("data"))
    # ...but centred on its point, which cSurvey's own item is not
    assert only(ours, "plan", lambda i: i.get("type") == "15").get(
        "textalignment") == "0"


@needs_fixture
def test_sb1103_dry_run_reports_the_drawing_and_the_centerline(tmp_path, capsys):
    assert run([RAW, "--dry-run"]) == 0
    out = capsys.readouterr().out
    # the drawing's bbox and the <sm> centerline numbers side by side, so the
    # difference between "the cave" and "the sketch" is visible (T4 handoff §7)
    assert "11.22 m" in out          # profile bbox height
    assert "l=10.00" in out and "pl=4.00" in out
    assert "znak ulaza:             2" in out


# the bar-length / plan-scale fixed point (SB 1256, 2026-09-20)


def test_bar_is_sized_for_the_scale_the_plan_ends_up_with(tmp_path):
    # SB 1256's geometry: plan 6 x 13 m, profile 14.6 x 15 m. Beside the plan
    # a 5 m bar + gap drops it to 1:200 (see the fixed-point test); under the
    # plan it keeps 1:100, so the bar goes under - and is sized for 1:100.
    out, sidecar = finish_to(tmp_path, plan_borders="-1.72 -6.42 4.29 6.63 ",
                             profile_borders="-6.25 -0.76 8.34 14.24 ")
    assert sidecar["plan_scale"] == 100
    assert sidecar["scale_bar"]["place"] == "under"
    assert sidecar["scale_bar"]["length_m"] == 5.0
    assert sidecar["scale_bar"]["for_scale"] == 100
    assert not warned(sidecar, "duzina mjerila")


def test_settle_plan_scale_is_a_fixed_point():
    import nacrt_finish
    # a plan that fits 1:100 even with its bar: one round, stays 100
    assert nacrt_finish.settle_plan_scale((0, 0, 3, 4), (0, 0, 4, 5)) == (100, 1)
    # SB 1256: 100 -> 200, then stable
    scale, rounds = nacrt_finish.settle_plan_scale((-1.72, -6.42, 4.29, 6.63),
                                                   (-6.25, -0.76, 8.34, 14.24))
    assert scale == 200 and rounds == 2
    assert nacrt_finish.settle_plan_scale(None, (0, 0, 4, 5)) == (100, 0)


# sizes and fonts the user set on 2026-09-20


def test_dislivello_is_big_scale_bar_uses_cave_name_font_and_arrow_is_doubled(tmp_path):
    out, _ = finish_to(tmp_path)
    root = ET.parse(str(out)).getroot()
    drop = [i for i in items_of(root, "profile") if i.get("quotatype") == "3"][0]
    assert drop.get("textsize") == "4"                      # "2.00 - Big"
    bar = [i for i in items_of(root, "plan") if i.get("quotatype") == "6"][0]
    assert bar.get("textsize") is None
    assert bar.find("font").get("type") == "2"              # Cave name
    compass = [i for i in items_of(root, "plan") if i.get("type") == "15"][0]
    assert compass.get("cs") == "2.00"
    assert compass.get("textverticalalignment") == "2"      # anchored by its bottom edge


# ---------------------------------------------------------------------------
# surface / excluded shots (SB 1220: the surface leg 4 -> 5 put the entrance
# on the surface)


def _with_surface_leg(tmp_path, flags='exclude="1" surface="1"', start="B",
                      **kwargs):
    """<start> -> S is a surface leg; S sits far above every cave station."""
    src = make_csx(tmp_path / "cave_lt.csx",
                   stations=DEFAULT_STATIONS + [("S", 3.0, 4.0, -9.0, 3.0)],
                   **kwargs)
    text = src.read_text(encoding="utf-8").replace(
        "  </segments>",
        '    <segment id="44444444-4444-4444-4444-444444444444" from="%s" to="S"'
        ' distance="5.00" %s />\n  </segments>' % (start, flags))
    src.write_text(text, encoding="utf-8")
    return src


@pytest.mark.parametrize("flags", ['exclude="1" surface="1"', 'exclude="1"',
                                   'duplicate="1"', 'calibration="1"'])
def test_a_station_reached_only_by_a_flagged_shot_is_not_in_the_cave(tmp_path, flags):
    root, _csz, _style = nacrt_finish.load_root(str(_with_surface_leg(tmp_path, flags)))
    kept, outside = nacrt_finish.split_cave_stations(
        root, nacrt_finish.read_stations(root))
    assert [s.name for s in kept] == ["A", "B", "C"]
    assert outside == ["S"]


def test_surface_station_is_neither_the_entrance_nor_the_height(tmp_path):
    src = _with_surface_leg(tmp_path)
    assert run([src, "--yes"]) == 0
    sidecar = sidecar_of(tmp_path / "cave_lt_fin.csx")
    assert sidecar["entrance"] == "B"
    assert sidecar["entrance_witnesses"]["highest"] == "B"


def test_the_filter_stands_down_when_every_shot_is_flagged(tmp_path):
    root, _csz, _style = nacrt_finish.load_root(str(make_csx(tmp_path / "s.csx")))
    for seg in root.find("segments").findall("segment"):
        seg.set("exclude", "1")
    kept, outside = nacrt_finish.split_cave_stations(
        root, nacrt_finish.read_stations(root))
    assert [s.name for s in kept] == ["A", "B", "C"] and outside == []


def test_the_cave_end_of_a_surface_leg_is_the_entrance(tmp_path):
    # C is the lowest cave station; only the surface leg says it is the entrance
    src = _with_surface_leg(tmp_path, start="C")
    assert run([src, "--yes"]) == 0
    sidecar = sidecar_of(tmp_path / "cave_lt_fin.csx")
    assert sidecar["entrance"] == "C"
    assert sidecar["entrance_witnesses"]["surface_leg"] == ["C"]
    assert "povrsinski" in sidecar["entrance_witnesses"]["decision"]


def test_a_sign_drawn_at_the_surface_station_points_at_the_leg_s_cave_end(tmp_path):
    # SB 1220: the surveyor drew the entrance sign at the surface station
    src = _with_surface_leg(tmp_path, start="C", plan_sign=(3.1, 4.1))
    assert run([src, "--yes"]) == 0
    sidecar = sidecar_of(tmp_path / "cave_lt_fin.csx")
    sign = sidecar["entrance_sign"]
    assert sign["station"] == "C" and sign["via"] == "S"
    assert not warned(sidecar, "povrsinski vlak veze")


def test_an_excluded_shot_that_is_not_surface_names_no_entrance(tmp_path):
    src = _with_surface_leg(tmp_path, flags='exclude="1"', start="C")
    assert run([src, "--yes"]) == 0
    sidecar = sidecar_of(tmp_path / "cave_lt_fin.csx")
    assert sidecar["entrance_witnesses"]["surface_leg"] == []
    assert sidecar["entrance"] == "B"          # the highest cave station


# ---------------------------------------------------------------------------
# where the bar + arrow go (SB 1220: beside a 20 m plan at 1:200 the bar ran
# off the A4 and its "10" was cut)


def test_gadgets_beside_a_wide_plan_would_leave_the_page():
    plan = (-0.48, -6.33, 19.46, 3.90)                       # SB 1220's plan
    beside = nacrt_finish.with_gadgets(plan, 10.0, "beside")
    under = nacrt_finish.with_gadgets(plan, 10.0, "under")
    assert not nacrt_finish.gadgets_on_page(plan, beside, 200)
    assert nacrt_finish.gadgets_on_page(plan, under, 200)


def test_sb1220_puts_the_bar_under_the_plan_inside_its_width():
    place, scale, _notes = nacrt_finish.place_gadgets(
        (-0.48, -6.33, 19.46, 3.90), (-0.36, -5.36, 19.05, 5.16))
    assert (place, scale) == ("under", 200)
    x0, _y = nacrt_finish.gadget_anchor((-0.48, -6.33, 19.46, 3.90), 10.0, "under")
    assert -0.48 <= x0 and x0 + 10.0 <= 19.46                 # right-aligned inside


def test_a_small_plan_keeps_the_bar_beside_it():
    # SB 1103: both places allow 1:100, and the tie keeps the original place
    place, scale, _notes = nacrt_finish.place_gadgets(
        (-1.22, -4.12, 1.90, 0.98), (-1.10, -8.18, 4.34, 3.04))
    assert (place, scale) == ("beside", 100)


def test_a_plan_narrower_than_the_bar_gets_it_centred_underneath():
    x0, _y = nacrt_finish.gadget_anchor((0.0, 0.0, 4.0, 3.0), 10.0, "under")
    assert x0 == -3.0                                         # 2 m centre - 5 m
