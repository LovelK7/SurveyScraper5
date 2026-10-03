"""wall_orient — KORAK 2's wall direction and order fix for merged cave borders (project 0006).

The synthetic cave: a straight passage 2 m wide, one leg A(0,0) -> B(10,0) down its
middle, walled by four strokes merged into one Borders item - the ceiling-side wall
y=-1, a right end cap, the floor-side wall y=+1 and a left end cap. Drawn the way
round the cave (cave on the right of every stroke), the fill's joins have length 0.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import wall_orient as wo  # noqa: E402

UPPER = [(0, -1), (5, -1), (10, -1)]
RIGHT = [(10, -1), (12, -1), (12, 1), (10, 1)]
LOWER = [(10, 1), (5, 1), (0, 1)]
LEFT = [(0, 1), (-2, 1), (-2, -1), (0, -1)]


def _data(seqs):
    out = []
    for seq in seqs:
        for k, (x, y) in enumerate(seq):
            out.append("%.2f %.2f%s" % (x, y, " B" if k == 0 else ""))
    return " ".join(out) + " "


def _csx(seqs, pen="1", joins=""):
    return ET.fromstring(
        '<csurvey><segments><segment from="A" to="B" distance="10" /></segments>'
        '<calculate><ts>'
        '<t n="A"><tcons><tcon n="B"><p x="0" y="0" z="0" d="0" /></tcon></tcons></t>'
        '<t n="B"><tcons><tcon n="A"><p x="10" y="0" z="0" d="10" /></tcon></tcons></t>'
        '</ts></calculate>'
        '<plan><layers><layer name="Borders" type="5"><items>'
        '<item layer="5" type="4" category="1"><pen type="%s" /><points data="%s" /></item>'
        '</items></layer></layers>%s</plan><profile /></csurvey>' % (pen, _data(seqs), joins))


def _seqs(root):
    item = root.find("plan/layers/layer/items/item")
    _m, pts = wo.parse_points(item.find("points").get("data"))
    return [[(float(p["x"]), float(p["y"])) for p in pts[s:e + 1]] for s, e in wo.sequence_ranges(pts)]


def test_the_wall_running_against_its_item_is_reversed():
    root = _csx([UPPER, RIGHT, LOWER[::-1], LEFT])
    rep = wo.fix(root)
    assert rep[0]["flipped"] == [2]
    assert _seqs(root) == [UPPER, RIGHT, LOWER, LEFT]
    assert rep[0]["joins_after"] == (0.0, 0)


def test_an_item_drawn_consistently_the_other_way_is_left_alone():
    # every stroke cave-on-LEFT: the fill is fine, a global convention would break it
    seqs = [LEFT[::-1], LOWER[::-1], RIGHT[::-1], UPPER[::-1]]
    root = _csx(seqs)
    rep = wo.fix(root)
    assert rep[0]["flipped"] == [] and not rep[0]["moved"]
    assert _seqs(root) == seqs


def test_sequences_out_of_chain_order_are_reordered_without_reversing():
    root = _csx([UPPER, LOWER, RIGHT, LEFT])
    rep = wo.fix(root)
    assert rep[0]["moved"] and rep[0]["flipped"] == []
    assert _seqs(root) == [UPPER, RIGHT, LOWER, LEFT]


def test_reorder_can_be_switched_off():
    root = _csx([UPPER, LOWER, RIGHT, LEFT])
    wo.fix(root, reorder=False)
    assert _seqs(root) == [UPPER, LOWER, RIGHT, LEFT]


def test_a_decorated_pen_keeps_its_direction():
    # CliffDownPen: ticks on one side, the direction is meaning
    root = _csx([UPPER, RIGHT, LOWER[::-1], LEFT], pen="5")
    wo.fix(root)
    assert _seqs(root) == [UPPER, RIGHT, LOWER[::-1], LEFT]


def test_point_joins_follow_the_reversed_points():
    # point 7 = first point of the reversed stroke (0,1); after the fix it is the stroke's last
    joins = '<pointsjoins><pointsjoin id="j" data="5,0,7 5,0,0 " /></pointsjoins>'
    root = _csx([UPPER, RIGHT, LOWER[::-1], LEFT], joins=joins)
    wo.fix(root)
    assert root.find("plan/pointsjoins/pointsjoin").get("data") == "5,0,9 5,0,0 "


def test_points_round_trip_and_reverse_like_csurvey():
    data = "1.00 2.00 BPT1Sg1 3.00 4.00 S 5.00 6.00 LS 7.00 8.00 BSg2 9.00 10.00 "
    meta, pts = wo.parse_points(data)
    assert wo.serialize_points(meta, pts) == data
    wo.reverse_range(pts, 0, 2)
    # cSequence.Reverse: the B/P/T prefix moves to the new first point; bindings stay resolved
    assert wo.serialize_points(meta, pts) == "5.00 6.00 BPT1LSg1 3.00 4.00 S 1.00 2.00 S 7.00 8.00 BSg2 9.00 10.00 "


def test_metas_prefix_is_kept():
    data = "#C 1.00 2.00 B 3.00 4.00 "
    meta, pts = wo.parse_points(data)
    assert meta == "#C " and wo.serialize_points(meta, pts) == data


EXAMPLE = Path(__file__).resolve().parents[1] / "example" / "csx_entrances"


@pytest.mark.skipif(not (EXAMPLE / "Golobreška_nanoekspedicija-1p-lk_pp_lt_fin_backup.csx").exists(),
                    reason="example corpus is local only")
def test_golobreska_reproduces_the_hand_fix():
    """The user reversed the entrance hook by hand (2026-10-03); the fix must do the same."""
    before = ET.parse(EXAMPLE / "Golobreška_nanoekspedicija-1p-lk_pp_lt_fin_backup.csx").getroot()
    hand = ET.parse(EXAMPLE / "Golobreška_nanoekspedicija-1p-lk_pp_lt_fin.csx").getroot()
    rep = wo.fix(before)
    assert [(r["design"], r["flipped"]) for r in rep if r["flipped"]] == [("profile", [2])]
    got = [i.find("points").get("data") for _, i in wo.borders_items(before.find("profile"))][0].split()
    want = [i.find("points").get("data") for _, i in wo.borders_items(hand.find("profile"))][0].split()
    # cSurvey re-rounded one coordinate of its own on save (0.505 -> 0.50)
    assert [(a, b) for a, b in zip(got, want) if a != b] == [("0.51", "0.50")]
    assert wo.fix(hand) == [] or all(not r["flipped"] and not r["moved"] for r in wo.fix(hand))
