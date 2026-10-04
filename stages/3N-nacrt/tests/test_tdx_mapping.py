"""tdx_mapping — the shared default plus a cave's own override.

The dashboard writes `tdx-mapping-objekt.json` into a cave's SB_ leaf; KORAK 1
and KORAK 2 must pick it up for that cave's files and for no other.
"""

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import fix_imported_linetypes as fixer  # noqa: E402
import preprocess_tdx_csx as pp  # noqa: E402
import tdx_mapping as tm  # noqa: E402

DEFAULT = {
    "points": {"clay": {"to": "sand"}, "danger": {"label": "!"}},
    "lines": {"pit": {"to": "pit"}},
    "areas": {},
    "generic": {"strip_line_subtypes": True},
    "postimport": {
        "spline_linetypes": True,
        "centerline": {"PlotPenColor": -65536, "PlotPenWidth": 2},
        "sign_sizes": {"entrance": "default"},
        "designproperties": {"_readme": "comment"},
    },
}


def test_merge_replaces_removes_and_merges_postimport():
    over = {
        "_readme": "x",
        "points": {"clay": None, "mud": {"to": "clay"}},
        "postimport": {"centerline": {"PlotPenColor": -16776961},
                       "sign_sizes": {"entrance": None}},
    }
    eff = tm.merge(DEFAULT, over)
    assert eff["points"] == {"danger": {"label": "!"}, "mud": {"to": "clay"}}
    assert eff["postimport"]["centerline"] == {"PlotPenColor": -16776961, "PlotPenWidth": 2}
    assert eff["postimport"]["sign_sizes"] == {}
    assert "_readme" not in eff
    assert DEFAULT["points"]["clay"] == {"to": "sand"}  # input untouched


@pytest.mark.parametrize("edit", [
    lambda m: m["points"].pop("clay"),
    lambda m: m["points"].__setitem__("mud", {"to": "clay", "orientation": 90}),
    lambda m: m["lines"].__setitem__("pit", {"to": "pit", "reverse": True}),
    lambda m: m["postimport"]["centerline"].__setitem__("PlotPenColor", -16711936),
    lambda m: m["postimport"].__setitem__("spline_linetypes", False),
    lambda m: m["postimport"]["sign_sizes"].__setitem__("stalactite", "medium"),
])
def test_diff_round_trips(edit):
    eff = json.loads(json.dumps(DEFAULT))
    edit(eff)
    over = tm.diff(DEFAULT, eff)
    assert over
    merged = tm.merge(DEFAULT, over)
    merged["postimport"]["designproperties"] = eff["postimport"]["designproperties"]
    assert merged == eff


def test_no_change_means_no_override():
    assert tm.diff(DEFAULT, json.loads(json.dumps(DEFAULT))) == {}


@pytest.fixture
def intake(tmp_path):
    default = tmp_path / "tdx-mapping.json"
    default.write_text(json.dumps(DEFAULT), encoding="utf-8")
    a = tmp_path / "SB_811_Nozata jama" / "topodroid"
    b = tmp_path / "SB_908_Druga spilja"
    a.mkdir(parents=True)
    b.mkdir()
    return tmp_path, default, a, b


def test_find_override_walks_up_to_the_leaf_only(intake):
    root, default, a, b = intake
    leaf = a.parent
    assert tm.find_override(str(a / "x.csx")) is None
    tm.write_override(str(leaf), DEFAULT, {**DEFAULT, "points": {}})
    assert tm.find_override(str(a / "x.csx")) == str(leaf / tm.OVERRIDE_NAME)
    assert tm.find_override(str(b / "y.csx")) is None
    # an override above the leaf is not the cave's - never picked up
    (root / tm.OVERRIDE_NAME).write_text("{}", encoding="utf-8")
    assert tm.find_override(str(b / "y.csx")) is None


def test_write_override_removes_the_file_when_back_to_default(intake):
    _, _, a, _ = intake
    leaf = str(a.parent)
    path = tm.write_override(leaf, DEFAULT, {**DEFAULT, "points": {}})
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data["points"] == {"clay": None, "danger": None}
    assert "_readme" in data
    assert tm.write_override(leaf, DEFAULT, DEFAULT) is None
    assert not Path(path).exists()


def test_broken_override_falls_back_to_default(intake, capsys):
    _, default, a, _ = intake
    (a.parent / tm.OVERRIDE_NAME).write_text("{ broken", encoding="utf-8")
    cfg, over = tm.effective_for(str(a / "x.csx"), str(default))
    assert over is None and cfg == DEFAULT
    assert "WARNING" in capsys.readouterr().out


def test_korak1_tables_do_not_leak_between_caves(intake):
    _, default, a, b = intake
    tm.write_override(str(a.parent), DEFAULT,
                      tm.merge(DEFAULT, {"points": {"clay": {"to": "clay"},
                                                    "mud": {"label": "M"}}}))
    pp.apply_mapping(tm.effective_for(str(a / "x.csx"), str(default))[0])
    assert pp.POINT_RENAMES["clay"] == "clay" and pp.POINT_TO_LABEL["mud"] == "M"
    pp.apply_mapping(tm.effective_for(str(b / "y.csx"), str(default))[0])
    assert pp.POINT_RENAMES["clay"] == "sand" and "mud" not in pp.POINT_TO_LABEL
    pp.load_mapping(pp.DEFAULT_MAP)  # leave the module as other tests expect


def test_korak2_rules_follow_the_cave(intake):
    _, default, a, b = intake
    tm.write_override(str(a.parent), DEFAULT, tm.merge(DEFAULT, {
        "postimport": {"centerline": {"PlotPenColor": -16776961},
                       "sign_sizes": {"stalactite": "large"}}}))
    rules, signs, _, over = fixer.load_rules(str(a / "x_postp.csx"), str(default))
    assert over and rules["centerline"]["PlotPenColor"] == -16776961
    assert signs[str(fixer.SIGN_VALUES["stalactite"])] == fixer.SIZES["large"]
    rules, _, _, over = fixer.load_rules(str(b / "y.csx"), str(default))
    assert over is None and rules["centerline"]["PlotPenColor"] == -65536
