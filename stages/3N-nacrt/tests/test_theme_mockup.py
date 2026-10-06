"""make_theme_mockup — the theme mockup (zoo v4) covers zoo v3 plus every theme key."""

import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import make_theme_mockup as mm  # noqa: E402
import themes  # noqa: E402


def _names(xml):
    root = ET.fromstring(xml)
    out = {"point": set(), "line": set(), "area": set()}
    for it in root.iter("item"):
        out[it.get("type")].add(it.get("name"))
    return out, root


def test_covers_zoo_v3_and_every_theme_key():
    xml, _key, layout, warnings = mm.build()
    names, _root = _names(xml)
    assert set(mm.ZOO_V3_POINTS) - {"section"} <= names["point"]
    assert set(mm.ZOO_V3_LINES) <= names["line"] and set(mm.ZOO_V3_AREAS) <= names["area"]
    boja = themes.load_theme("boja")
    assert set(boja.signs) <= names["point"]          # bones, tree-trunk, vegetable-debris, ...
    assert set(boja.lines) <= names["line"] and set(boja.areas) <= names["area"]
    assert not warnings
    tags = [s["tag"] for s in layout["slots"]]
    assert len(tags) == len(set(tags)) == layout["stations"]


def test_lines_drawn_twice_and_rows_walled():
    xml, _key, layout, _w = mm.build()
    root = ET.fromstring(xml)
    rope = [it for it in root.iter("item") if it.get("name") == "rope"]
    assert len(rope) == 2                                     # straight + curve
    pts = [it.find("points").get("data").split() for it in rope]
    assert sorted(len(p) for p in pts) == [5, 63]             # x y B x y / 31 points
    walls = [it for it in root.iter("item") if it.get("name") == "wall"
             and it.get("outline") == "1"]
    assert len(walls) == 4 + 2                                # one loop per line row and area row
    headings = [it.get("text") for it in root.iter("item") if it.get("name") == "label"
                and it.get("text", "").split(" ")[0] in ("ZNAKOVI", "LINIJE", "PLOHE")]
    assert len(headings) == 3


def test_adding_a_theme_key_adds_it(tmp_path):
    root = tmp_path / "themes"
    shutil.copytree(TOOLS.parent / "themes" / "boja", root / "boja")
    tj = root / "boja" / "theme.json"
    data = json.loads(tj.read_text(encoding="utf-8"))
    data["signs"]["crystal"] = {"color": "#000000"}
    data["signs"]["waterflow"] = {"color": "#0000FF"}         # a cSurvey target key
    tj.write_text(json.dumps(data), encoding="utf-8")
    lists, warnings = mm.symbol_lists(str(root))
    signs = dict(lists["signs"])
    assert signs["crystal"] == ["boja"] and signs["water-flow"] == ["boja"]
    assert not warnings
