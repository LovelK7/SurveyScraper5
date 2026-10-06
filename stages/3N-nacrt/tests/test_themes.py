"""themes — symbol-theme format, loader and validator (project 0007, T2)."""

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import themes as th  # noqa: E402

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><path d="M 0 0 L 1 1"/></svg>'
RED = -65536
BLACK = -16777216


def _theme(root, tid, data, files=()):
    d = root / tid
    d.mkdir(parents=True, exist_ok=True)
    (d / "theme.json").write_text(json.dumps(data), encoding="utf-8")
    for rel in files:
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(SVG, encoding="utf-8")
    return d


def _index(theme_dir, kind, mapping):
    (theme_dir / kind).mkdir(parents=True, exist_ok=True)
    (theme_dir / kind / "index.json").write_text(json.dumps(mapping), encoding="utf-8")


# --- colours ---------------------------------------------------------------

@pytest.mark.parametrize("value, want", [
    ("#FF0000", RED), ("#ff0000", RED), ("#FFFF0000", RED), (RED, RED),
    (0xFFFF0000, RED), ("#000000", BLACK), ("#00000000", 0),
])
def test_to_argb(value, want):
    assert th.to_argb(value) == want


@pytest.mark.parametrize("bad", ["red", "#F00", True, 1.5, "#GG0000"])
def test_to_argb_rejects(bad):
    with pytest.raises(ValueError):
        th.to_argb(bad)


# --- extends ---------------------------------------------------------------

def test_extends_deep_merge_child_wins(tmp_path):
    base = _theme(tmp_path, "base", {
        "name": "Base", "default_color": "#00FF00",
        "signs": {"bones": {"color": "#FF0000", "size": 1.5}, "danger": {}},
        "lines": {"slope": {"color": "#0000FF", "decoration": {"scale": 2}}},
        "centerline": {"PlotPenWidth": 3, "PlotPenColor": "#FF0000"},
    }, files=["signs/bones.svg", "lines/slope.svg"])
    _index(base, "signs", {"bones": "bones.svg"})
    _index(base, "lines", {"slope": "slope.svg"})
    _theme(tmp_path, "child", {
        "name": "Child", "extends": "base",
        "signs": {"bones": {"color": "#0000FF"}, "danger": None, "plus": {"svg": "own/plus.svg"}},
        "lines": {"slope": {"decoration": {"spacing_pct": 50}}},
        "centerline": {"PlotPenWidth": 1},
    }, files=["own/plus.svg"])
    t = th.load_theme("child", tmp_path)
    assert t.name == "Child" and t.chain == ["base", "child"]
    bones = t.signs["bones"]
    assert bones["color"] == th.to_argb("#0000FF")          # child wins
    assert bones["size"] == 1.5                             # inherited field kept
    assert Path(bones["svg"]) == base / "signs" / "bones.svg"   # resolved in the parent's dir
    assert "danger" not in t.signs                          # null drops the inherited entry
    assert Path(t.signs["plus"]["svg"]) == tmp_path / "child" / "own" / "plus.svg"
    assert t.signs["plus"]["color"] == th.to_argb("#00FF00")    # inherited default_color
    deco = t.lines["slope"]["decoration"]
    assert deco["scale"] == 2 and deco["spacing_pct"] == 50     # nested merge
    assert t.centerline == {"PlotPenWidth": 1, "PlotPenColor": RED}


def test_extends_cycle_rejected(tmp_path):
    _theme(tmp_path, "a", {"name": "A", "extends": "b"})
    _theme(tmp_path, "b", {"name": "B", "extends": "a"})
    with pytest.raises(th.ThemeError) as e:
        th.load_theme("a", tmp_path)
    assert any("cycle" in x for x in e.value.errors)
    _theme(tmp_path, "self", {"name": "S", "extends": "self"})
    assert any("cycle" in x for x in th.validate("self", tmp_path))


def test_extends_missing_parent(tmp_path):
    _theme(tmp_path, "orphan", {"name": "O", "extends": "nowhere"})
    errs = th.validate("orphan", tmp_path)
    assert any("nowhere" in x for x in errs)


# --- monochrome ------------------------------------------------------------

def test_monochrome_forces_every_colour_and_the_centerline(tmp_path):
    _theme(tmp_path, "colour", {
        "name": "C",
        "signs": {"bones": {"color": "#FF0000"}},
        "lines": {"slope": {"svg": "lines/slope.svg", "color": "#00FF00",
                            "decoration_color": "#0000FF"},
                  "rope": {"color": "#EF5553", "width": 0.1}},
        "areas": {"water": {"solid": True, "color": "#0000FF"},
                  "clay": {"svg": "areas/clay.svg", "color": "#AC7E2E"}},
        "centerline": {"PlotPenColor": "#FF0000", "PlotPenWidth": 2},
    }, files=["lines/slope.svg", "areas/clay.svg"])
    _theme(tmp_path, "bw", {"name": "BW", "extends": "colour", "monochrome": "#000000"})
    t = th.load_theme("bw", tmp_path)
    assert t.monochrome == BLACK and t.default_color == BLACK
    for kind in th.KINDS:
        for spec in t.section(kind).values():
            assert spec["color"] == BLACK
            if "decoration_color" in spec:
                assert spec["decoration_color"] == BLACK
    types = th._centerline_types()
    colour_keys = {k for k, v in types.items() if v == "color"}
    assert colour_keys and all(t.centerline[k] == BLACK for k in colour_keys)
    assert t.centerline["PlotPenWidth"] == 2               # non-colours untouched
    merged = t.centerline_over({"PlotTextColor": RED, "PlotPointSize": 2})
    assert merged["PlotTextColor"] == BLACK and merged["PlotPointSize"] == 2
    # the parent stays in colour
    assert th.load_theme("colour", tmp_path).signs["bones"]["color"] == RED


# --- lookup ----------------------------------------------------------------

def test_resolve_lookup_order(tmp_path):
    _theme(tmp_path, "t", {
        "name": "T",
        "lines": {"slope:steep": {"color": "#FF0000"}, "slope": {"color": "#00FF00"}},
        "signs": {"waterflow": {"color": "#0000FF"}},
    })
    t = th.load_theme("t", tmp_path)
    assert th.resolve(t, "lines", "slope:steep", "slope")["key"] == "slope:steep"   # TopoDroid wins
    assert th.resolve(t, "lines", "slope:sheer", "slope")["key"] == "slope"         # target fallback
    assert th.resolve(t, "lines", None, "slope")["key"] == "slope"                  # name not recovered
    assert th.resolve(t, "lines", "wall", "border") is None                         # built-in look
    assert th.resolve(t, "areas", "slope", "slope") is None                         # kinds are separate
    # point targets are compared without dashes ('water-flow' in the mapping == 'waterflow')
    assert th.resolve(t, "point", "water-drip", "water-flow")["key"] == "waterflow"


# --- validation ------------------------------------------------------------

def test_unknown_key_is_an_error(tmp_path):
    _theme(tmp_path, "t", {"name": "T", "signs": {"no-such-sign": {}},
                           "areas": {"overhang": {}}})          # a line name, not an area
    errs = th.validate("t", tmp_path)
    assert any("signs.no-such-sign" in x and "unknown key" in x for x in errs)
    assert any("areas.overhang" in x for x in errs)
    with pytest.raises(th.ThemeError):
        th.load_theme("t", tmp_path)


def test_missing_svg_is_an_error(tmp_path):
    d = _theme(tmp_path, "t", {"name": "T",
                               "signs": {"bones": {"svg": "signs/bones.svg"}, "plus": {}}})
    _index(d, "signs", {"plus": "plus.svg"})
    errs = th.validate("t", tmp_path)
    assert sum("svg not found" in x for x in errs) == 2
    _theme(tmp_path, "esc", {"name": "E", "signs": {"bones": {"svg": "../t/theme.json"}}})
    assert any("outside the theme folder" in x for x in th.validate("esc", tmp_path))


def test_field_validation(tmp_path):
    _theme(tmp_path, "t", {
        "name": "T", "bogus": 1,
        "lines": {"pit": {"style": "custom"},
                  "slope": {"style": "dash", "dash": [4, 2]},
                  "wall": {"style": "none"},
                  "border": {"decoration": {"scale": 2}},
                  "chimney": {"style": "wavy", "colour": "#FF0000"}},
        "areas": {"water": {"solid": True, "color": "#00F", "density": 2}},
        "centerline": {"NoSuchKey": 1, "PlotPointSymbol": 1.5},
        "scale_rules": {"150": {"DesignSoilScaleFactor": 1},
                        "200": {"DesignFoo": 1, "DesignSignScaleFactor": 0}},
    })
    errs = "\n".join(th.validate("t", tmp_path))
    for needle in ["unknown top-level field 'bogus'",
                   "lines.pit.dash: style custom needs",
                   "lines.slope.dash: only allowed with style custom",
                   "lines.wall: style none with no decoration svg",
                   "lines.border.decoration: set but the line has no svg",
                   "lines.chimney.style: 'wavy'",
                   "unknown field 'colour'",
                   "areas.water.color",
                   "a solid area takes only color",
                   "centerline.NoSuchKey: unknown key",
                   "centerline.PlotPointSymbol: must be an integer",
                   "scale_rules.150: scale must be one of",
                   "scale_rules.200.DesignFoo",
                   "scale_rules.200.DesignSignScaleFactor: must be a number > 0"]:
        assert needle in errs, needle


def test_custom_dash_and_scale_rules_resolve(tmp_path):
    _theme(tmp_path, "t", {"name": "T",
                           "lines": {"wall:presumed": {"style": "custom", "dash": [4, 2]}},
                           "scale_rules": {"500": {"DesignSoilScaleFactor": 0.7}}})
    t = th.load_theme("t", tmp_path)
    assert t.lines["wall:presumed"]["dash"] == [4.0, 2.0]
    assert t.lines["wall:presumed"]["decoration"] is None
    assert t.scale_rules == {500: {"DesignSoilScaleFactor": 0.7}}


def test_list_themes(tmp_path):
    _theme(tmp_path, "b", {"name": "B"})
    _theme(tmp_path, "a", {"name": "A"})
    (tmp_path / "not-a-theme").mkdir()
    assert th.list_themes(tmp_path) == ["a", "b"]
    assert th.list_themes(tmp_path / "missing") == []


# --- the shipped starter themes --------------------------------------------

@pytest.mark.parametrize("tid", ["boja", "crno-bijelo"])
def test_starter_themes_validate_clean(tid):
    assert tid in th.list_themes()
    assert th.validate(tid) == []


def test_starter_themes_content():
    boja = th.load_theme("boja")
    bw = th.load_theme("crno-bijelo")
    assert boja.lines["rope"]["svg"] is None and boja.lines["rope"]["width"] == 0.1
    assert boja.lines["rope"]["color"] == th.to_argb("#EF5553")
    meander = boja.lines["floor-meander"]
    assert meander["style"] == "none" and meander["decoration"]["alignment"] == "center"
    assert meander["decoration"]["spacing_pct"] == 0
    assert set(bw.signs) == set(boja.signs) and set(bw.areas) == set(boja.areas)
    assert all(s["color"] == BLACK for s in bw.lines.values())
    assert bw.centerline["PlotPenColor"] == BLACK
    assert th.unused_svgs(boja) == []


def test_cli_check_and_show(capsys):
    assert th.main(["check"]) == 0
    assert th.main(["show", "crno-bijelo", "--kind", "centerline"]) == 0
    out = capsys.readouterr().out
    assert '"PlotPenColor": "#FF000000"' in out
