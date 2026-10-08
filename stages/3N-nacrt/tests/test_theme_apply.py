"""theme_apply — symbol themes written into a post-import cSurvey file (project 0007, T3)."""

import base64
import hashlib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import nacrt_finish  # noqa: E402
import theme_apply as ta  # noqa: E402

FIX = Path(__file__).resolve().parents[1] / "example" / "finishing"
LT_FIN = FIX / "SB_1103_golobreska_lt_fin.csx"
TDX_RAW = FIX / "SB_1103_golobreska_tdx_raw.csx"

OLD_GLYPH = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M 0 0 L 1 1" fill="#000"/></svg>'
OLD_ID = nacrt_finish.clipart_hash(OLD_GLYPH)
THEME_SVG = ('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
             'xmlns:csurvey="http://www.csurvey.it" viewBox="0 0 2 2" csurvey:scale="1.2">'
             '<path d="M 0 0 L 2 0 L 2 2 Z" fill="#000000"/></svg>\n')

# A tiny post-import survey: two `blocks` signs (1290) - one imported (TopoDroid
# datarow, recoverable by name), one drawn in cSurvey (native, target fallback) -
# and an entrance (263) that no theme lists.
CSX = """<csurvey version="1.14" id="x">
  <properties name="t">
    <designproperties>
      <item name="PlotPenColor" type="color">-65536</item>
    </designproperties>
  </properties>
  <plan>
    <layers>
      <layer type="6">
        <items>
          <item layer="6" type="6" category="80" data="{old}" dataformat="2" sign="1290">
            <pen type="10" />
            <brush type="7" />
            <points data="1.00 2.00 " />
            <datarow>TopoDroid|x</datarow>
          </item>
          <item layer="6" type="6" category="80" data="{old}" dataformat="2" sign="1290">
            <pen type="10" />
            <brush type="7" />
            <points data="5.00 5.00 " />
          </item>
          <item layer="6" type="6" category="80" data="{old}" dataformat="2" sign="263">
            <pen type="10" />
            <brush type="7" />
            <points data="7.00 7.00 " />
            <datarow>TopoDroid|x</datarow>
          </item>
        </items>
      </layer>
    </layers>
  </plan>
  <signs>
    <cliparts>
      <clipart id="{old}" name="old.svg" data="{b64}" />
    </cliparts>
  </signs>
</csurvey>
""".format(old=OLD_ID, b64=base64.b64encode(OLD_GLYPH).decode())

PRE = """<csurvey><properties creatid="TopoDroid" /><plan>
  <item type="point" name="blocks"><points data="1.00 2.00 " /></item>
  <item type="point" name="entrance"><points data="7.00 7.00 " /></item>
</plan></csurvey>"""

GREY = -8882054        # #78787A


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "themes"
    (root / "t" / "signs").mkdir(parents=True)
    (root / "t" / "signs" / "blocks.svg").write_bytes(THEME_SVG.encode())
    (root / "t" / "theme.json").write_text(json.dumps(
        {"name": "T", "signs": {"blocks": {"svg": "signs/blocks.svg", "color": "#78787A"}}}))
    (root / "mono").mkdir()
    (root / "mono" / "theme.json").write_text(json.dumps(
        {"name": "M", "extends": "t", "monochrome": "#000000"}))
    (root / "line").mkdir()
    (root / "line" / "theme.json").write_text(json.dumps(
        {"name": "L", "extends": "t", "monochrome": "#000000",
         "signs": {"blocks": {"render": "outline", "size": 2}}}))
    csx = tmp_path / "in.csx"
    csx.write_text(CSX, encoding="utf-8")
    pre = tmp_path / "pre.csx"
    pre.write_text(PRE, encoding="utf-8")
    return tmp_path, root, csx, pre


def _run(env, src, theme, out_name, pre=True):
    tmp, root, _csx, prefile = env
    out = tmp / out_name
    rep = ta.theme_file(str(src), theme, str(prefile) if pre else None, str(out),
                        themes_root=str(root))
    return out, rep


def _signs(path):
    r = ET.parse(path).getroot()
    return [it for it in r.iter("item") if it.get("type") == "6"], r


def test_hash_is_csurvey_unpadded_sha1():
    blob = b"abc"
    digest = hashlib.sha1(blob).digest()
    assert nacrt_finish.clipart_hash(blob) == "".join("%X" % b for b in digest)
    # a byte < 0x10 shortens the id: cSurvey's {0:X1}
    assert any(b < 16 for b in digest) and len(nacrt_finish.clipart_hash(blob)) < 40


def test_pool_add_and_repoint(env):
    out, rep = _run(env, env[2], "t", "o.csx")
    items, root = _signs(out)
    new_id = nacrt_finish.clipart_hash(THEME_SVG.encode())
    pool = {c.get("id"): c for c in root.find("signs/cliparts")}
    assert new_id in pool and OLD_ID in pool                 # old entry left in place
    assert base64.b64decode(pool[new_id].get("data")) == THEME_SVG.encode()
    assert pool[new_id].get("name") == "tema-t_blocks.svg"   # not cSurvey's own blocks.svg
    assert [i.get("data") for i in items] == [new_id, new_id, OLD_ID]
    assert [i.get("sign") for i in items] == ["1290", "1290", "263"]   # sign= kept
    assert rep["glyph"] == 2 and rep["themed"] == 2


def test_fallback_lookup(env):
    _out, rep = _run(env, env[2], "t", "o.csx")
    assert rep["lookup"] == {"tdx (recovered)": 1, "target (native)": 1,
                             "none (recovered)": 1}
    _out, rep = _run(env, env[2], "t", "o2.csx", pre=False)
    assert rep["lookup"] == {"target (no-pre)": 2, "none (no-pre)": 1}


def test_colour_brush_and_pen_xml(env):
    out, _ = _run(env, env[2], "t", "o.csx")
    it = _signs(out)[0][0]
    assert it.find("brush").attrib == {"type": "99", "name": "tema:t", "color": str(GREY),
                                       "backgroundcolor": "0", "hatchtype": "1"}
    pen = it.find("pen")                                    # outline_pen off: style None
    assert pen.attrib == {"type": "99", "name": "tema:t", "color": str(GREY), "style": "98",
                          "width": "0.00", "decorationstyle": "0",
                          "decorationspacepercentage": "100.0", "decorationalignment": "0",
                          "decorationscale": "1.00"}
    assert pen.find("clipart").get("data") == ""


def test_outline_pen_true_keeps_the_tightpen_look(env):
    tmp, root, csx, _pre = env
    (root / "pen").mkdir()
    (root / "pen" / "theme.json").write_text(json.dumps(
        {"name": "P", "extends": "t", "signs": {"blocks": {"outline_pen": True}}}))
    (root / "monopen").mkdir()
    (root / "monopen" / "theme.json").write_text(json.dumps(
        {"name": "MP", "extends": "pen", "monochrome": "#000000"}))
    out, rep = _run(env, csx, "pen", "p.csx")
    pen = _signs(out)[0][0].find("pen")
    assert pen.get("style") == "0" and pen.get("color") == str(GREY)
    assert rep["pen_off"] == 0 and rep["colour"] == 2
    out, rep = _run(env, csx, "monopen", "mp.csx")
    it = _signs(out)[0][0]
    assert it.find("pen").attrib == {"type": "10"} and it.find("brush").attrib == {"type": "7"}
    assert rep["black_builtin"] == 2


def test_black_pen_off_and_centerline(env):
    out, rep = _run(env, env[2], "mono", "o.csx")
    items, root = _signs(out)
    pen = items[0].find("pen")
    assert pen.get("type") == "99" and pen.get("style") == "98"     # no built-in TightPen
    assert items[0].find("brush").attrib == {"type": "7"}           # black: built-in brush
    assert items[2].find("pen").attrib == {"type": "10"}            # entrance: not themed
    dp = {i.get("name"): i.text for i in root.find("properties/designproperties")}
    assert dp["PlotPenColor"] == "-16777216" and dp["CaveDossierTheme"] == "mono"
    assert rep["pen_off"] == 2 and rep["black_builtin"] == 0 and rep["colour"] == 0


def test_rotate_and_stroke_only_note(env):
    tmp, root, csx, _pre = env
    (root / "t" / "signs" / "blocks.svg").write_bytes(THEME_SVG.replace(
        '</svg>', '<path d="M 0 2 L 2 2" fill="none" stroke="#000000"/></svg>').encode())
    (root / "rot").mkdir()
    (root / "rot" / "theme.json").write_text(json.dumps(
        {"name": "R", "extends": "t", "signs": {"blocks": {"rotate": 90}}}))
    out, rep = _run(env, csx, "rot", "r.csx")
    items, r = _signs(out)
    pool = {c.get("id"): c for c in r.find("signs/cliparts")}
    svg = base64.b64decode(pool[items[0].get("data")].get("data"))
    assert b'd="M 2 0 L 2 2 L 0 2 Z"' in svg                 # turned 90 deg clockwise
    assert any("stroke-only" in n for n in rep["notes"])
    back, _ = _run(env, out, "t", "back.csx")
    plain, _ = _run(env, csx, "t", "plain.csx")
    assert back.read_bytes() == plain.read_bytes()           # undo leaves no trace


def test_outline_and_size(env):
    out, _ = _run(env, env[2], "line", "o.csx")
    items, root = _signs(out)
    it = items[0]
    assert it.find("brush").get("color") == "-1"            # white
    assert it.find("pen").get("color") == "-16777216"
    pool = {c.get("id"): c for c in root.find("signs/cliparts")}
    svg = base64.b64decode(pool[it.get("data")].get("data"))
    assert b'csurvey:scale="2.4"' in svg                    # 1.2 x size 2


def test_idempotent_and_switch(env):
    a, _ = _run(env, env[2], "t", "a.csx")
    a2, _ = _run(env, a, "t", "a2.csx")
    assert a.read_bytes() == a2.read_bytes()
    m, _ = _run(env, env[2], "mono", "m.csx")
    am, rep = _run(env, a, "mono", "am.csx")
    assert am.read_bytes() == m.read_bytes() and rep["previous_theme"] == "t"
    names = {c.get("name") for c in _signs(am)[1].find("signs/cliparts")}
    assert "tema-mono_blocks.svg" in names and "tema-t_blocks.svg" not in names   # renamed, not stacked
    ma, _ = _run(env, m, "t", "ma.csx")
    assert ma.read_bytes() == a.read_bytes()             # centerline restored too
    ol, _ = _run(env, env[2], "line", "l.csx")
    lt, rep = _run(env, ol, "t", "lt.csx")
    assert lt.read_bytes() == a.read_bytes()             # outline glyph removed from pool
    assert len(rep["pool_removed"]) == 1


def test_hand_customised_sign_is_left_alone(env):
    tmp, _root, csx, _pre = env
    src = tmp / "custom.csx"
    src.write_text(CSX.replace('<brush type="7" />',
                               '<brush type="99" color="-1" backgroundcolor="0" hatchtype="1" />', 1),
                   encoding="utf-8")
    out, rep = _run(env, src, "t", "o.csx")
    assert rep["skipped_custom"] == 1 and rep["themed"] == 1
    assert _signs(out)[0][0].get("data") == OLD_ID


def test_csz_writes_zip_entry(env):
    tmp, _root, csx, _pre = env
    data = CSX.replace('data="%s" />' % base64.b64encode(OLD_GLYPH).decode(),
                       'data="_data\\cliparts\\%s.svg" />' % OLD_ID)
    src = tmp / "in.csz"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("_data.xml", data)
        z.writestr("_data/cliparts/%s.svg" % OLD_ID, OLD_GLYPH)
    out, _ = _run(env, src, "t", "o.csz")
    new_id = nacrt_finish.clipart_hash(THEME_SVG.encode())
    with zipfile.ZipFile(out) as z:
        assert z.read("_data/cliparts/%s.svg" % new_id) == THEME_SVG.encode()
        assert ("_data\\cliparts\\%s.svg" % new_id).encode() in z.read("_data.xml")
    out2, _ = _run(env, out, "line", "o2.csz")
    out3, _ = _run(env, out2, "t", "o3.csz")
    with zipfile.ZipFile(out) as a, zipfile.ZipFile(out3) as b:
        assert sorted(a.namelist()) == sorted(b.namelist())
        assert all(a.read(n) == b.read(n) for n in a.namelist())


def test_default_out_replaces_theme_suffix(tmp_path):
    root = Path(TOOLS).parent / "themes"
    assert ta.default_out("x/SB_1_lt.csx", "boja", str(root)) == "x/SB_1_lt_boja.csx"
    assert ta.default_out("x/SB_1_lt_boja.csz", "crno-bijelo", str(root)) \
        == "x/SB_1_lt_crno-bijelo.csz"


@pytest.mark.skipif(not (LT_FIN.exists() and TDX_RAW.exists()), reason="SB 1103 fixture absent")
def test_real_fixture_both_themes(tmp_path):
    outs = {}
    for t in ("boja", "crno-bijelo"):
        out = tmp_path / ("%s.csx" % t)
        rep = ta.theme_file(str(LT_FIN), t, str(TDX_RAW), str(out))
        assert rep["themed"] == 2 and rep["glyph"] == 2      # the two profile blocks
        outs[t] = out
    again = tmp_path / "again.csx"
    ta.theme_file(str(outs["boja"]), "crno-bijelo", str(TDX_RAW), str(again))
    assert again.read_bytes() == outs["crno-bijelo"].read_bytes()


# --------------------------------------------------------------------------
# phase 2: lines (library pens) and areas (library brushes)

UNIT = ('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 2 3">\n  <title>u</title>\n  <path d="M 0 3 L 1 0 L 2 3 Z" fill="#000000"/>\n'
        '</svg>\n')
TILE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4">'
        '<path d="M 0 0 L 4 0 L 4 4 Z" fill="#000000"/></svg>\n')

CSX2 = """<csurvey version="1.14" id="x">
  <properties name="t">
    <designproperties>
      <item name="BaseMediumLinesScaleFactor" type="single">2.5</item>
    </designproperties>
  </properties>
  <pens />
  <brushes />
  <plan>
    <layers>
      <layer type="2">
        <items>
          <item layer="2" type="1" category="3" linetype="1">
            <pen type="12" />
            <points data="0.00 0.00 B 3.00 0.00 S 3.00 3.00 S " />
            <datarow>TopoDroid|x</datarow>
          </item>
          <item layer="2" type="1" category="2" linetype="1">
            <pen type="2" />
            <points data="10.00 0.00 B 13.00 0.00 S " />
            <datarow>TopoDroid|x</datarow>
          </item>
          <item layer="2" type="1" category="3" linetype="1">
            <pen type="21" />
            <points data="20.00 0.00 B 23.00 0.00 S " />
            <datarow>TopoDroid|x</datarow>
          </item>
        </items>
      </layer>
      <layer type="1">
        <items>
          <item layer="1" type="3" category="48">
            <pen type="0" />
            <brush type="4">
              <seed base="82.00" increment="12.00" />
            </brush>
            <points data="0.00 10.00 B 2.00 10.00 S 2.00 12.00 S 0.00 12.00 S " />
            <datarow>TopoDroid|x</datarow>
          </item>
          <item layer="1" type="3" category="64">
            <pen type="2" />
            <brush type="6" />
            <points data="5.00 10.00 B 7.00 10.00 S 7.00 12.00 S 5.00 12.00 S " />
            <datarow>TopoDroid|x</datarow>
          </item>
        </items>
      </layer>
    </layers>
  </plan>
  <signs>
    <cliparts />
  </signs>
</csurvey>
"""

PRE2 = """<csurvey><properties creatid="TopoDroid" /><plan>
  <item type="line" name="overhang"><points data="3.00 3.00 3.00 0.00 0.00 0.00 " /></item>
  <item type="line" name="rope"><points data="13.00 0.00 10.00 0.00 " /></item>
  <item type="line" name="floor-meander"><points data="23.00 0.00 20.00 0.00 " /></item>
  <item type="area" name="pebbles"><points data="0.00 12.00 2.00 12.00 2.00 10.00 0.00 10.00 " /></item>
  <item type="area" name="water"><points data="5.00 12.00 7.00 12.00 7.00 10.00 5.00 10.00 " /></item>
</plan></csurvey>"""


@pytest.fixture
def env2(tmp_path):
    root = tmp_path / "themes"
    (root / "c" / "lines").mkdir(parents=True)
    (root / "c" / "areas").mkdir()
    (root / "c" / "lines" / "u.svg").write_text(UNIT)
    (root / "c" / "areas" / "t.svg").write_text(TILE)
    (root / "c" / "theme.json").write_text(json.dumps({"name": "C", "lines": {
        "overhang": {"svg": "lines/u.svg", "color": "#000000", "decoration": {"scale": 2}},
        "floor-meander": {"svg": "lines/u.svg", "style": "none",
                          "decoration": {"alignment": "center", "spacing_pct": 0}},
        "rope": {"color": "#EF5553", "width": 0.1}},
        "areas": {"pebbles": {"svg": "areas/t.svg", "color": "#AD7E2F", "density": 0.6,
                              "zoom": 0.05}}}))
    (root / "bw").mkdir()
    (root / "bw" / "theme.json").write_text(json.dumps(
        {"name": "BW", "extends": "c", "monochrome": "#000000",
         "areas": {"water": {"pattern": {"type": "lines", "angle": 45}}}}))
    csx = tmp_path / "in2.csx"
    csx.write_text(CSX2, encoding="utf-8")
    pre = tmp_path / "pre2.csx"
    pre.write_text(PRE2, encoding="utf-8")
    return tmp_path, root, csx, pre


def _items(path):
    r = ET.parse(path).getroot()
    return [it for it in r.iter("item") if it.get("type") in ("1", "3")], r


def test_line_library_pen_xml(env2):
    out, rep = _run(env2, env2[2], "c", "o.csx")
    items, r = _items(out)
    pens = {p.get("id"): p for p in r.find("pens")}
    oh = pens["tema-c-line-overhang-12"]
    assert list(oh.attrib.items())[:5] == [("type", "98"), ("id", "tema-c-line-overhang-12"),
                                           ("name", "tema:c:overhang/12"),
                                           ("color", "-16777216"), ("style", "0")]
    assert oh.get("width") == "2.50"                     # the file's BaseMediumLinesScaleFactor
    assert oh.get("decorationstyle") == "99" and oh.get("decorationscale") == "2.00"
    assert oh.get("decorationalignment") == "2"          # OverhangDownPen is Inner ...
    data = oh.find("clipart").get("data")
    assert data.startswith("<svg ") and 'd="M 0 0 L 1 3 L 2 0 Z"' in data   # ... so flipped
    assert oh.get("clipartpenmode") == "1" and oh.get("clipartpenstyle") == "98"
    assert "clipartbrushmode" not in oh.attrib            # decoration colour = line colour
    rope = pens["tema-c-line-rope-2"]
    assert rope.get("color") == str(-1092269) and rope.get("width") == "0.10"
    assert rope.get("decorationstyle") == "0" and rope.find("clipart").get("data") == ""
    md = pens["tema-c-line-floor-meander-21"]
    assert md.get("style") == "98" and md.get("decorationalignment") == "1"
    assert md.get("decorationspacepercentage") == "0.1"   # 0 would read back as 100
    assert [it.find("pen").attrib for it in items[:3]] == [
        {"type": "98", "id": "tema-c-line-overhang-12"}, {"type": "98", "id": "tema-c-line-rope-2"},
        {"type": "98", "id": "tema-c-line-floor-meander-21"}]
    assert sum(rep["lines"]["themed"].values()) == 3


def test_area_library_brushes_tile_and_pattern(env2):
    out, rep = _run(env2, env2[2], "bw", "o.csx")
    items, r = _items(out)
    br = {b.get("id"): b for b in r.find("brushes")}
    tile = br["tema-bw-area-pebbles-4"]
    assert tile.get("hatchtype") == "2" and tile.get("clipartdensity") == "0.60"
    assert tile.get("clipartzoomfactor") == "0.0500" and tile.get("clipartcrop") == "2"
    assert tile.get("color") == "-16777216"                       # monochrome
    assert tile.find("clipart").get("data").startswith("<svg ")
    pat = br["tema-bw-area-water-6"]
    assert {k: pat.get(k) for k in ("hatchtype", "patterntype", "patternpenstyle", "patterndensity",
                                    "patternzoomfactor", "patternanglemode", "patternangle")} == {
        "hatchtype": "3", "patterntype": "0", "patternpenstyle": "0", "patterndensity": "1.00",
        "patternzoomfactor": "1.0000", "patternanglemode": "0", "patternangle": "45.00"}
    assert pat.find("parameters") is not None and len(pat.find("parameters")) == 0
    peb = items[3].find("brush")
    assert peb.attrib == {"type": "98", "id": "tema-bw-area-pebbles-4"}
    assert peb.find("seed").get("base") == "82.00"               # the item seed is kept
    assert items[3].find("pen").attrib == {"type": "0"}          # area outline untouched


def test_phase2_undo_switch_idempotent(env2):
    tmp, _root, csx, _pre = env2
    a, _ = _run(env2, csx, "c", "a.csx")
    a2, _ = _run(env2, a, "c", "a2.csx")
    assert a.read_bytes() == a2.read_bytes()
    b, _ = _run(env2, csx, "bw", "b.csx")
    ab, rep = _run(env2, a, "bw", "ab.csx")
    assert ab.read_bytes() == b.read_bytes() and rep["previous_theme"] == "c"
    ba, _ = _run(env2, b, "c", "ba.csx")
    assert ba.read_bytes() == a.read_bytes()
    # undoing everything restores the original items and the empty libraries
    root = ET.parse(a).getroot()
    _, state = ta.read_state(root)
    ta.undo(root, state)
    orig = ET.parse(csx).getroot()
    assert ET.tostring(root.find("plan")) == ET.tostring(orig.find("plan"))
    assert len(root.find("pens")) == 0 and len(root.find("brushes")) == 0


def test_libraries_created_when_absent_and_removed_on_undo(env2):
    tmp, _root, csx, _pre = env2
    src = tmp / "nolib.csx"
    src.write_text(CSX2.replace("  <pens />\n  <brushes />\n", ""), encoding="utf-8")
    a, _ = _run(env2, src, "c", "a.csx")
    r = ET.parse(a).getroot()
    tags = [c.tag for c in r]
    assert tags.index("pens") < tags.index("brushes") < tags.index("plan")
    back, _ = _run(env2, a, "bw", "back.csx")
    direct, _ = _run(env2, src, "bw", "direct.csx")
    assert back.read_bytes() == direct.read_bytes()
    root = ET.parse(a).getroot()
    ta.undo(root, ta.read_state(root)[1])
    assert root.find("pens") is None and root.find("brushes") is None


def test_hand_set_line_pen_left_alone(env2):
    tmp, _root, csx, _pre = env2
    src = tmp / "hand.csx"
    src.write_text(CSX2.replace('<pen type="12" />',
                                '<pen type="99" color="-1" style="0" width="1.00" />'),
                   encoding="utf-8")
    out, rep = _run(env2, src, "c", "o.csx")
    assert any("own pen" in s for s in rep["lines"]["skipped"])
    assert _items(out)[0][0].find("pen").get("type") == "99"


def test_importer_turn_and_auto_outline_pen():
    assert ta.importer_turn("water-flow", "777") == 90 and ta.importer_turn("waterflow", "777") == 0
    assert ta.importer_turn(None, "774") == 90 and ta.importer_turn(None, "1290") == 0
    blob = b'<svg><path d="M 0 0 L 1 1" fill="none" stroke="#000000"/></svg>'
    assert ta.stroke_only_paths(blob) == 1 and ta.filled_paths(blob) == 0


def test_stroke_only_sign_gets_the_pen(env):
    tmp, root, csx, _pre = env
    (root / "t" / "signs" / "blocks.svg").write_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2 2">'
        b'<path d="M 0 0 L 2 2" fill="none" stroke="#000000"/></svg>')
    out, rep = _run(env, csx, "t", "s.csx")
    pen = _signs(out)[0][0].find("pen")
    assert pen.get("style") == "0" and pen.get("color") == str(GREY)     # pen on, sign colour
    assert any("outline pen turned on" in n for n in rep["notes"])


def test_majority_name_of_merged_item():
    def seq(n):
        return {"status": "exact", "source": {"tdx_name": n, "kind": "line", "prep_name": n}}
    assert ta._majority([seq("wall"), seq("wall"), seq("pit")])[0] == "wall"
    name, _k, _p, note = ta._majority([seq("wall"), seq("pit")])
    assert name is None and "tie" in note
    assert ta._majority([seq("pit")])[3] is None


# ── KORAK 2's theme step (T5) ────────────────────────────────────────

def test_find_pre_prefers_the_prep_over_the_raw_export(env):
    tmp, _root, csx, pre = env
    import os
    import shutil
    raw = tmp / "spilja.csx"
    shutil.copy(pre, raw)
    prep = tmp / "spilja_prep.csx"
    shutil.copy(pre, prep)
    os.utime(prep, (1, 1))                       # older than the raw one, still preferred
    shutil.copy(csx, tmp / "spilja_backup.csx")  # cSurvey's safety copy: never a pre
    assert ta.find_pre(str(csx)) == str(prep)
    prep.unlink()
    assert ta.find_pre(str(csx)) in (str(raw), str(pre))


def test_korak2_step_themes_in_place_and_fails_soft(env, tmp_path):
    import io
    _tmp, root, csx, _pre = env
    before = csx.read_bytes()
    log = io.StringIO()
    assert not ta.korak2_step(str(csx), "nema", out=log, themes_root=str(root))
    assert "ne postoji" in log.getvalue() and csx.read_bytes() == before
    log = io.StringIO()
    assert ta.korak2_step(str(csx), "t", out=log, themes_root=str(root))
    assert "tema t:" in log.getvalue() and "imena iz: pre.csx" in log.getvalue()
    assert ta.read_state(ET.parse(csx).getroot())[0] == "t"


def test_korak2_applies_the_caves_theme_from_its_mapping(tmp_path):
    """fix_imported_linetypes: the override's "theme" themes the _postp; --no-theme skips it."""
    import fix_imported_linetypes as fixer
    leaf = tmp_path / "SB_1_test"
    leaf.mkdir()
    (leaf / "spilja.csx").write_text(CSX, encoding="utf-8")
    (leaf / "spilja_prep.csx").write_text(PRE, encoding="utf-8")
    (leaf / "tdx-mapping-objekt.json").write_text('{"theme": "boja"}', encoding="utf-8")
    assert fixer.main([str(leaf / "spilja.csx"), "--force"]) == 0
    out = leaf / "spilja_postp.csx"
    assert ta.read_state(ET.parse(out).getroot())[0] == "boja"
    assert fixer.main([str(leaf / "spilja.csx"), "--force", "--no-theme"]) == 0
    assert ta.read_state(ET.parse(out).getroot())[0] is None


# ── T9: KORAK 1 labels -> theme glyphs ───────────────────────────────

LABELS = """
          <item layer="6" type="8" category="81" text="!" textrotatemode="1">
            <brush type="7" />
            <points data="9.00 9.00 " />
            <datarow>TopoDroid|x</datarow>
            <font type="0" />
          </item>
          <item layer="6" type="8" category="81" text="f" textrotatemode="1">
            <brush type="7" />
            <points data="3.00 3.00 " />
            <datarow>TopoDroid|x</datarow>
            <font type="0" />
          </item>"""
PRE_LABELS = PRE.replace("</plan>", """  <item type="point" name="label" text="!" options="tdxpp:danger"><points data="9.00 9.00 " /></item>
  <item type="point" name="label" text="f" options="tdxpp:anchor"><points data="3.00 3.00 " /></item>
</plan>""")


def test_labels_become_theme_signs_and_come_back(env):
    tmp, root_dir, _csx, _pre = env
    (root_dir / "t" / "signs" / "danger.svg").write_bytes(THEME_SVG.encode())
    (root_dir / "t" / "signs" / "anchor.svg").write_bytes(THEME_SVG.encode())
    (root_dir / "t" / "theme.json").write_text(json.dumps(
        {"name": "T", "signs": {"blocks": {"svg": "signs/blocks.svg", "color": "#78787A"},
                                "danger": {"svg": "signs/danger.svg"},
                                "anchor": {"svg": "signs/anchor.svg"}}}))
    csx = tmp / "lab.csx"
    csx.write_text(CSX.replace("        </items>", LABELS.lstrip("\n") + "\n        </items>"),
                   encoding="utf-8")
    pre = tmp / "lab_pre.csx"
    pre.write_text(PRE_LABELS, encoding="utf-8")
    out = tmp / "lab_t.csx"
    rep = ta.theme_file(str(csx), "t", str(pre), str(out), themes_root=str(root_dir))
    assert rep["labels"] == 1
    r = ET.parse(out).getroot()
    texts = [it.get("text") for it in r.iter("item") if it.get("type") == "8"]
    assert texts == ["f"]                                   # anchor is never themed
    sign = next(it for it in r.iter("item")
                if it.find("points") is not None and it.find("points").get("data") == "9.00 9.00 ")
    assert sign.get("type") == "6" and sign.get("category") == "80" and sign.get("sign") is None
    assert sign.get("data") == nacrt_finish.clipart_hash(THEME_SVG.encode())
    assert [c.tag for c in sign] == ["pen", "brush", "points", "datarow"]
    # undo (a re-run with another theme undoes first) restores the label byte for byte
    root, _is_csz, style = nacrt_finish.load_root(str(out))
    ta.undo(root, ta.read_state(root)[1])
    plain_root, _c, plain_style = nacrt_finish.load_root(str(csx))
    assert style.render(root) == plain_style.render(plain_root)
