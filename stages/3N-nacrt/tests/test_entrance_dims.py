"""entrance_dims — the entrance size (Širina / Visina ulaza) at the decided station.

Synthetic surveys built with test_nacrt_finish.make_csx: B is the entrance
(highest station, z = -5, plan (3, 0), profile (3, -5)); the first in-cave
shot is A→B, so the passage axis at B points toward A (−x) and "across" is ±y.
Rules under test are the five from project 0005 (see entrance_dims.py).
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import entrance_dims  # noqa: E402
import nacrt_finish  # noqa: E402
import wall_orient  # noqa: E402

from test_nacrt_finish import (DEFAULT_STATIONS, finish_to, make_csx,  # noqa: E402
                               sidecar_of, warned)

B_SPLAYS_LATERAL = [
    ("B(1)", 3.0, -0.3, -5.0, 3.0),     # 0.3 m to one side, level
    ("B(2)", 3.0, 0.4, -5.0, 3.0),      # 0.4 m to the other side
    ("B(3)", 3.0, 0.0, -6.5, 3.0),      # 1.5 m straight up (z positive down)
]
B_SPLAYS_DIVING = [
    ("B(%d)" % i, 3.0 + 0.2 * i, 0.1 * i, -5.0 + 3.0, 3.0) for i in range(1, 6)
]  # five splays dropping 3 m within a metre: a rim looking down a shaft

TWO_WALLS = "0.00 -1.00 4.00 -1.00 0.00 1.00 B 4.00 1.00 "   # y = -1 and y = +1, two sequences


def measured(tmp_path, *, stations, plan_sign=(3.1, 0.1), plan_borders=TWO_WALLS,
             profile_borders="-1.00 -2.00 7.00 3.00 ", plan_items=()):
    """`plan_items`: (layer type, type, name or None, points data) added to the plan."""
    path = make_csx(tmp_path / "cave_postp.csx", stations=stations, plan_sign=plan_sign,
                    plan_borders=plan_borders, profile_borders=profile_borders)
    root = ET.parse(path).getroot()
    layers = root.find("plan/layers")
    for layer_type, item_type, name, data in plan_items:
        layer = next((l for l in layers.findall("layer") if l.get("type") == layer_type), None)
        if layer is None:
            layer = ET.SubElement(layers, "layer", {"type": layer_type})
        items = layer.find("items")
        if items is None:
            items = ET.SubElement(layer, "items")
        item = ET.SubElement(items, "item", {"layer": layer_type, "type": item_type})
        if name:
            item.set("name", name)
        ET.SubElement(item, "points", {"data": data})
    sts = nacrt_finish.read_stations(root)
    warnings = []
    entrance, witnesses = nacrt_finish.decide_entrance(root, sts, warnings.append)
    witnessed = not witnesses["decision"].startswith("najvisa stanica")
    count = nacrt_finish.entrance_count(root, sts, witnesses)
    block = entrance_dims.measure(root, sts, entrance, witnessed, count, warnings.append)
    return block, warnings


# ---------------------------------------------------------------------------
# rule 1: splays first, best-aligned per direction, up-without-down = floor


def test_width_and_height_from_the_splays(tmp_path):
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS + B_SPLAYS_LATERAL)
    assert block["witnessed"] is True
    h = block["horizontal"]
    assert h["width_m"] == 0.7 and h["width_source"] == "splays"
    assert {h["side_a"]["splay"], h["side_b"]["splay"]} == {"B(1)", "B(2)"}
    assert h["height_m"] == 1.5 and h["height_source"] == "splays"
    assert h["up"]["splay"] == "B(3)" and h["down"]["source"] == "floor"


def test_a_splay_outside_the_cone_does_not_count(tmp_path):
    # a splay 60 degrees off the "across" direction is not a left/right shot
    off = [("B(1)", 3.0 - 0.52, -0.3, -5.0, 3.0), ("B(2)", 3.0, 0.4, -5.0, 3.0)]
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS + off)
    assert block["horizontal"]["width_source"] == "walls"


# ---------------------------------------------------------------------------
# rule 2: walls as fallback, one source per opening


def test_walls_when_there_are_no_lateral_splays(tmp_path):
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS)
    h = block["horizontal"]
    assert h["width_m"] == 2.0 and h["width_source"] == "walls"
    assert h["side_a"]["source"] == "wall" and h["side_b"]["source"] == "wall"


def test_one_lateral_splay_means_walls_for_both_sides(tmp_path):
    one = [("B(1)", 3.0, -0.3, -5.0, 3.0)]
    block, warnings = measured(tmp_path, stations=DEFAULT_STATIONS + one)
    assert block["horizontal"]["width_m"] == 2.0
    assert block["horizontal"]["width_source"] == "walls"
    # how a reading was obtained stays in the block; the finisher's own
    # warnings carry only what needs the operator (rule 5, no shot at all)
    assert any("splay samo s jedne strane" in w for w in block["warnings"])
    assert not any("splay samo s jedne strane" in w for w in warnings)


def test_a_borders_item_is_split_into_sequences_on_the_B_flag(tmp_path):
    path = make_csx(tmp_path / "cave_postp.csx", plan_borders=TWO_WALLS)
    root = ET.parse(path).getroot()
    paths, bridges = entrance_dims.wall_paths(root, "plan")
    assert paths == [[(0.0, -1.0), (4.0, -1.0)], [(0.0, 1.0), (4.0, 1.0)]]
    # the fill joins: end of the first → start of the second, last → first
    assert sorted(bridges) == sorted([[(4.0, -1.0), (0.0, 1.0)], [(4.0, 1.0), (0.0, -1.0)]])


def test_a_long_fill_join_is_not_a_wall():
    # SB 1220's closing join ran 15 m across the cave and 5 cm above the station
    assert entrance_dims.BRIDGE_MAX_M < 15.0


# ---------------------------------------------------------------------------
# rule 3: a pit is the hole in the plan, small x large


def test_the_pit_reading_is_the_splay_cloud_small_by_large(tmp_path):
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS + B_SPLAYS_DIVING)
    assert block["kind_geo"] == "pit" and "strmo dolje" in block["kind_why"]
    pit = block["pit"]
    assert pit["source"] == "splays"
    assert pit["width_m"] <= pit["length_m"]
    assert pit["splay_cloud"]["splays"] == 5


# A pit rim around B (3, 0) drawn in two pieces 0.5 m apart: x 2..6, y -2..1.
RIM_A = "2.00 -2.00 B 6.00 -2.00 6.00 0.50 "
RIM_B = "6.00 1.00 B 2.00 1.00 2.00 -1.50 "


def test_the_drawn_rim_is_the_pit_opening_and_wins_over_the_splays(tmp_path):
    # SB 968 (user, 2026-10-22): the rim is right, two flat splays overshoot it
    block, warnings = measured(
        tmp_path, stations=DEFAULT_STATIONS + B_SPLAYS_DIVING,
        plan_items=[("5", "4", wall_orient.RING_NAME, RIM_A), ("5", "4", wall_orient.RING_NAME, RIM_B)])
    pit = block["pit"]
    assert pit["source"] == "rim" and pit["rim"]["rings"] == 2
    assert pit["width_m"] == 3.0 and 4.9 <= pit["length_m"] <= 5.0      # 4 x 3, the extent is the diagonal
    assert block["kind_geo"] == "pit" and block["kind_why"] == "nacrtan rub ulaza u jamu"
    assert pit["splay_cloud"] is not None                                # still reported beside it
    assert any("uzet rub" in w for w in warnings)                        # they disagree


def test_a_rim_from_an_earlier_korak2_is_found_by_its_points(tmp_path):
    # before 2026-10-22 the ring copies were named like the walls outline
    block, _ = measured(
        tmp_path, stations=DEFAULT_STATIONS + B_SPLAYS_LATERAL,
        plan_items=[("2", "1", None, RIM_A), ("5", "4", wall_orient.CAVE_AREA_NAME, RIM_A),
                    ("5", "4", wall_orient.CAVE_AREA_NAME, "0.00 -1.00 4.00 -1.00 B 4.00 1.00 B 0.00 1.00 ")])
    assert block["pit"]["source"] == "rim" and block["pit"]["rim"]["rings"] == 1   # not the walls outline


def test_a_rim_far_from_the_entrance_is_another_opening(tmp_path):
    far = "40.00 0.00 B 44.00 0.00 44.00 3.00 40.00 3.00 "
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS + B_SPLAYS_LATERAL,
                        plan_items=[("5", "4", wall_orient.RING_NAME, far)])
    assert block["pit"]["rim"] is None and block["pit"]["source"] == "splays"
    assert block["kind_geo"] == "horizontal"


def test_two_splays_and_the_station_span_a_pit_opening(tmp_path):
    two = [("B(1)", 7.0, 0.0, -5.0, 3.0), ("B(2)", 3.0, 3.0, -5.0, 3.0)]   # 4 m and 3 m, at right angles
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS + two)
    pit = block["pit"]
    assert pit["source"] == "splays" and pit["splay_cloud"]["splays"] == 2
    assert pit["length_m"] == 5.0


def test_both_readings_travel_whatever_the_geometry_says(tmp_path):
    # the OSZ prefill picks pit vs horizontal by the zapisnik's Vrsta objekta
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS + B_SPLAYS_LATERAL)
    assert block["kind_geo"] == "horizontal"
    assert block["horizontal"] is not None and block["pit"] is not None


# ---------------------------------------------------------------------------
# rule 5: no size without a witnessed entrance


def test_no_sign_no_surface_leg_means_no_size(tmp_path):
    block, warnings = measured(tmp_path, stations=DEFAULT_STATIONS + B_SPLAYS_LATERAL,
                               plan_sign=None)
    assert block["witnessed"] is False
    assert block["horizontal"] is None and block["pit"] is None
    assert any("nacrtaj znak ulaza" in w for w in warnings)


# ---------------------------------------------------------------------------
# Broj ulaza, the finisher's plumbing, and the station reader


def test_broj_ulaza_counts_the_plan_signs_by_station(tmp_path):
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS + B_SPLAYS_LATERAL)
    assert block["count"] == 1


def test_broj_ulaza_is_unknown_without_any_sign(tmp_path):
    block, _ = measured(tmp_path, stations=DEFAULT_STATIONS, plan_sign=None)
    assert block["count"] is None


def test_the_sidecar_carries_the_entrance_size(tmp_path):
    _out, sidecar = finish_to(tmp_path, plan_sign=(3.1, 0.1),
                              stations=DEFAULT_STATIONS + B_SPLAYS_LATERAL)
    size = sidecar["entrance_size"]
    assert size["station"] == "B" and size["witnessed"] is True and size["count"] == 1
    assert size["horizontal"]["width_m"] == 0.7
    assert size["horizontal"]["height_m"] == 1.5


def test_read_stations_takes_d_from_the_tcon_copy(tmp_path):
    # the direct <p> says d="0" in every cSurvey file; the <tcon><p> has the real one
    path = make_csx(tmp_path / "cave_postp.csx")
    data = path.read_text(encoding="utf-8")
    data = data.replace(
        '      <t n="B">\n        <p x="3.0000" y="0.0000" z="-5.0000" d="3.0000" />',
        '      <t n="B">\n        <tcons><tcon n="A" dst="3.00">'
        '<p x="3.0000" y="0.0000" z="-5.0000" d="3.0000" /></tcon></tcons>\n'
        '        <p x="3.0000" y="0.0000" z="-5.0000" d="0" />')
    path.write_text(data, encoding="utf-8")
    root = ET.parse(path).getroot()
    b = next(s for s in nacrt_finish.read_stations(root) if s.name == "B")
    assert b.d == 3.0


def test_describe_is_one_line():
    assert entrance_dims.describe(None) == "-"
    assert "nije oznacen" in entrance_dims.describe({"witnessed": False})
