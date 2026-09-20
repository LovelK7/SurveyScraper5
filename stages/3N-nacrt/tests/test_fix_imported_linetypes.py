"""fix_imported_linetypes — the KORAK 2 post-import fixer: the centerline rule."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import fix_imported_linetypes as fixer  # noqa: E402

DP = ('    <designproperties>\n      <item name="PlotPenColor" type="color">-16777216</item>\n'
      '    </designproperties>\n')
CSX = ('<csurvey version="1.14" id="synthetic">\n  <properties id="" name="" origin="A">\n' + DP +
       '  </properties>\n  <plan><layers><layer name="Base" type="0"><items /></layer></layers></plan>\n'
       '  <profile><layers><layer name="Base" type="0"><items /></layer></layers></profile>\n</csurvey>\n')


def _items(root):
    return {i.get("name"): (i.get("type"), i.text)
            for i in root.find("properties").find("designproperties").findall("item")}


def test_centerline_values_are_written_with_their_types_and_replace_existing():
    root = ET.fromstring(CSX)
    n = fixer.apply_centerline(root, {"PlotPenColor": -65536, "PlotPointColor": -65536,
                                      "PlotPenStyle": 1, "PlotPointSymbol": 7,
                                      "PlotSplayPenWidth": 0.8,
                                      "PlotCenterlineForceColor": 1})
    assert n == 6
    items = _items(root)
    assert items["PlotPenColor"] == ("color", "-65536")          # replaced, not duplicated
    assert items["PlotPointColor"] == ("color", "-65536")
    assert items["PlotPenStyle"] == ("integer", "1")             # Hatch
    assert items["PlotPointSymbol"] == ("integer", "7")          # Triangle
    assert items["PlotSplayPenWidth"] == ("single", "0.8")
    assert items["PlotCenterlineForceColor"] == ("integer", "1")
    assert sum(1 for i in root.iter("item") if i.get("name") == "PlotPenColor") == 1


def test_unknown_keys_are_skipped_and_missing_properties_is_tolerated(capsys):
    root = ET.fromstring(CSX)
    assert fixer.apply_centerline(root, {"NoSuchKey": 1}) == 0
    assert "NoSuchKey" in capsys.readouterr().err
    assert fixer.apply_centerline(ET.fromstring("<csurvey/>"), {"PlotPenColor": 1}) == 0
    assert fixer.apply_centerline(root, None) == 0


def test_the_shipped_mapping_carries_a_red_centerline():
    rules = json.loads((TOOLS / "tdx-mapping.json").read_text(encoding="utf-8"))["postimport"]
    cl = rules["centerline"]
    assert cl["PlotPointColor"] == -65536 and cl["PlotPenColor"] == -65536
    assert cl["PlotPenStyle"] == 1 and cl["PlotPointSymbol"] == 7
    assert set(cl) <= set(fixer.CENTERLINE_TYPES)


def test_a_designproperties_element_is_created_when_absent():
    root = ET.fromstring(CSX.replace(DP, ""))
    assert root.find("properties").find("designproperties") is None
    assert fixer.apply_centerline(root, {"PlotPenColor": -65536}) == 1
    assert _items(root)["PlotPenColor"] == ("color", "-65536")


def test_a_sign_size_the_operator_set_is_left_alone(tmp_path):
    src = tmp_path / "cave.csx"
    src.write_text(CSX.replace(
        '<plan><layers><layer name="Base" type="0"><items /></layer></layers></plan>',
        '<plan><layers><layer name="Signs" type="6"><items>'
        '<item layer="6" type="6" category="80" sign="263" signsize="4"><datarow>TopoDroid|x</datarow></item>'
        '<item layer="6" type="6" category="80" sign="263"><datarow>TopoDroid|x</datarow></item>'
        '</items></layer></layers></plan>'), encoding="utf-8")
    rules = tmp_path / "map.json"
    rules.write_text('{"postimport": {"sign_sizes": {"entrance": "small"}}}', encoding="utf-8")
    assert fixer.main([str(src), "--map", str(rules)]) == 0
    root = ET.parse(str(tmp_path / "cave_lt.csx")).getroot()
    sizes = [i.get("signsize") for i in root.iter("item") if i.get("sign") == "263"]
    assert sizes == ["4", "2"]           # the hand-set one kept, the bare one sized
