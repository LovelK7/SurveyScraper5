"""fix_imported_linetypes — the KORAK 2 post-import fixer: the centerline rule."""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

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
    root = ET.parse(str(tmp_path / "cave_postp.csx")).getroot()
    sizes = [i.get("signsize") for i in root.iter("item") if i.get("sign") == "263"]
    assert sizes == ["4", "2"]           # the hand-set one kept, the bare one sized


def test_border_lines_are_not_clipped_unless_the_operator_chose(tmp_path):
    src = tmp_path / "cave.csx"
    src.write_text(CSX.replace(
        '<plan><layers><layer name="Base" type="0"><items /></layer></layers></plan>',
        '<plan><layers><layer name="Borders" type="5"><items>'
        '<item layer="5" type="1" category="2"><pen type="2" /><datarow>TopoDroid|x</datarow></item>'
        '<item layer="5" type="1" category="2" clippingtype="2"><pen type="2" /><datarow>TopoDroid|x</datarow></item>'
        '<item layer="2" type="1" category="3"><pen type="12" /><datarow>TopoDroid|x</datarow></item>'
        '</items></layer></layers></plan>'), encoding="utf-8")
    assert fixer.main([str(src), "--no-theme"]) == 0
    root = ET.parse(str(tmp_path / "cave_postp.csx")).getroot()
    assert [i.get("clippingtype") for i in root.iter("item") if i.get("type") == "1"] == ["1", "2", None]


def test_long_labels_are_broken_into_lines_and_short_or_hand_broken_ones_kept(tmp_path):
    long = "ide al je usko, a tu je jos neki dugi tekst koji mozda prelazi granice"
    src = tmp_path / "cave.csx"
    src.write_text(CSX.replace(
        '<plan><layers><layer name="Base" type="0"><items /></layer></layers></plan>',
        '<plan><layers><layer name="Signs" type="6"><items>'
        '<item layer="6" type="8" category="81" text="%s"><datarow>TopoDroid|x</datarow></item>'
        '<item layer="6" type="8" category="81" text="MES"><datarow>TopoDroid|x</datarow></item>'
        '<item layer="6" type="8" category="81" text="vec&#10;prelomljeno, ostaje kako je napisano">'
        '<datarow>TopoDroid|x</datarow></item>'
        '</items></layer></layers></plan>' % long), encoding="utf-8")
    assert fixer.main([str(src), "--no-theme"]) == 0
    texts = [i.get("text") for i in ET.parse(str(tmp_path / "cave_postp.csx")).getroot().iter("item")
             if i.get("type") == "8"]
    assert texts[0] == "ide al je usko, a tu je\njos neki dugi tekst koji\nmozda prelazi granice"
    assert texts[1] == "MES"
    assert texts[2] == "vec\nprelomljeno, ostaje kako je napisano"


ABYSS_POST = CSX.replace(
    '<plan><layers><layer name="Base" type="0"><items /></layer></layers></plan>',
    '<plan><layers><layer name="Floor" type="2"><items>'
    '<item layer="2" type="1" category="3" linetype="1"><pen type="12" />'
    '<points data="0.00 0.00 B 3.00 0.00 S 3.00 3.00 S " /><datarow>TopoDroid|x</datarow></item>'
    '<item layer="2" type="1" category="3" linetype="1"><pen type="12" />'
    '<points data="10.00 0.00 B 13.00 0.00 S " /><datarow>TopoDroid|x</datarow></item>'
    '</items></layer></layers></plan>')
ABYSS_PRE = ('<csurvey><properties creatid="TopoDroid" /><plan>'
             '<item type="line" name="overhang" options="tdxpp:abyss-entrance">'
             '<points data="3.00 3.00 3.00 0.00 0.00 0.00 " /></item>'
             '<item type="line" name="overhang"><points data="13.00 0.00 10.00 0.00 " /></item>'
             '</plan></csurvey>')


def test_abyss_entrance_is_not_clipped_when_its_name_is_recovered(tmp_path, capsys):
    (tmp_path / "cave.csx").write_text(ABYSS_POST, encoding="utf-8")
    (tmp_path / "cave_prep.csx").write_text(ABYSS_PRE, encoding="utf-8")
    assert fixer.main([str(tmp_path / "cave.csx"), "-o", str(tmp_path / "out.csx"),
                       "--no-theme"]) == 0
    clip = [i.get("clippingtype") for i in ET.parse(str(tmp_path / "out.csx")).getroot().iter("item")
            if i.get("type") == "1"]
    assert clip == ["1", None]            # the abyss-entrance ring only; overhang keeps its cut
    assert "abyss-entrance) bez rezanja: 1" in capsys.readouterr().out


def test_abyss_entrance_without_a_pre_file_stays_clipped_and_says_so(tmp_path, capsys):
    (tmp_path / "cave.csx").write_text(ABYSS_POST, encoding="utf-8")
    assert fixer.main([str(tmp_path / "cave.csx"), "--no-theme"]) == 0
    root = ET.parse(str(tmp_path / "cave_postp.csx")).getroot()
    assert all(i.get("clippingtype") is None for i in root.iter("item"))
    assert "nema izvornog TopoDroid" in capsys.readouterr().out


@pytest.mark.parametrize("given", ["cave_prep.csx", "cave_pp.csx"])
def test_the_output_replaces_prep_with_postp(tmp_path, given):
    (tmp_path / given).write_text(CSX, encoding="utf-8")
    assert fixer.main([str(tmp_path / given)]) == 0
    assert (tmp_path / "cave_postp.csx").exists()


def test_designproperties_write_any_typed_key_and_skip_bad_ones():
    root = ET.fromstring("<csurvey><properties><designproperties>"
                         "<item name='PlotTextScaleFactor' type='single'>1</item>"
                         "</designproperties></properties></csurvey>")
    n = fixer.apply_design_properties(root, {
        "_readme": "ignored",
        "PlotTextScaleFactor": {"type": "single", "value": 0.5},
        "SomeFlag": {"type": "boolean", "value": True},
        "NoType": {"value": 1},
        "Font": {"type": "citemfont", "value": "Arial"},
    })
    assert n == 2
    items = {i.get("name"): i for i in root.find("properties/designproperties")}
    assert (items["PlotTextScaleFactor"].get("type"), items["PlotTextScaleFactor"].text) == ("single", "0.5")
    assert (items["SomeFlag"].get("type"), items["SomeFlag"].text) == ("boolean", "True")
    assert "NoType" not in items and "Font" not in items
    assert fixer.apply_design_properties(root, None) == 0


def test_the_shipped_designproperties_section_is_valid():
    rules = json.loads(Path(fixer.DEFAULT_MAP).read_text(encoding="utf-8"))["postimport"]
    root = ET.fromstring("<csurvey><properties/></csurvey>")
    real = {k: v for k, v in rules.get("designproperties", {}).items() if not k.startswith("_")}
    assert fixer.apply_design_properties(root, real) == len(real)


def test_viewoptions_set_attributes_on_the_named_views_only():
    root = ET.fromstring("<csurvey><options>"
                         "<_design.plan drawsplay='0' splaystyle='0'/>"
                         "<_export.plan drawsplay='1' splaystyle='0'/>"
                         "</options></csurvey>")
    n = fixer.apply_view_options(root, {
        "_readme": "ignored",
        "design.plan": {"drawsplay": 1, "splaystyle": 2},
        "design.profile": {"splaystyle": 2},  # not in the file: skipped
    })
    assert n == 2
    plan = root.find("options/_design.plan")
    assert (plan.get("drawsplay"), plan.get("splaystyle")) == ("1", "2")
    assert root.find("options/_export.plan").get("splaystyle") == "0"
    assert fixer.apply_view_options(ET.fromstring("<csurvey/>"), {"design.plan": {"drawsplay": 1}}) == 0
    assert fixer.apply_view_options(root, None) == 0


def test_the_shipped_viewoptions_show_splays_as_rays_in_combined_style():
    rules = json.loads(Path(fixer.DEFAULT_MAP).read_text(encoding="utf-8"))["postimport"]
    vo = rules["viewoptions"]
    for view in ("design.plan", "design.profile"):
        assert vo[view] == {"drawsplay": 1, "splaystyle": 2, "designstyle": 2}
    assert all(k in fixer.VIEW_NAMES for k in vo if not k.startswith("_"))


def test_the_abyss_ring_becomes_the_hidden_cave_area_once_even_when_re_run(tmp_path, capsys):
    # findings/walls-and-clipping.md §4: what lies inside a pit's entrance ring is cave
    post = ABYSS_POST.replace('</items></layer></layers></plan>',
                              '</items></layer><layer name="Borders" type="5"><items /></layer></layers></plan>')
    (tmp_path / "cave.csx").write_text(post, encoding="utf-8")
    (tmp_path / "cave_prep.csx").write_text(ABYSS_PRE, encoding="utf-8")
    assert fixer.main([str(tmp_path / "cave.csx"), "-o", str(tmp_path / "a.csx"), "--no-theme"]) == 0
    assert "unutrasnjost ruba ulaza u jamu: 1" in capsys.readouterr().out
    assert fixer.main([str(tmp_path / "a.csx"), "-o", str(tmp_path / "b.csx"), "--no-theme"]) == 0
    root = ET.parse(str(tmp_path / "b.csx")).getroot()
    hidden = [i for i in root.iter("item") if fixer.wall_orient.is_cave_area(i)]
    assert len(hidden) == 1 and hidden[0].find("pen").get("type") == "0"
    assert hidden[0].find("points").get("data").startswith("0.00 0.00 B 3.00 0.00")
    ring = root.find("plan/layers/layer/items/item")
    assert (ring.get("type"), ring.get("clippingtype")) == ("1", "1")
