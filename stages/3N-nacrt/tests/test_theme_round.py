"""theme_round — the pure parts: split diff, theme.json diff, cache key, RUNLOG, seeds."""

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import make_theme_mockup as mm  # noqa: E402
import theme_round as tr  # noqa: E402


# ---------------------------------------------------------------- theme.json diff

def test_diff_theme_json_paths_and_comments():
    old = {"name": "Boja", "_readme": "x",
           "lines": {"ceiling-step": {"_note": "a", "style": "custom", "dash": [4, 2],
                                      "decoration": {"scale": 2, "spacing_pct": 4500}},
                     "pit": {"color": "#000000"}},
           "areas": {"blocks": {"density": 0.9}}}
    new = {"name": "Boja", "_readme": "changed comment",
           "lines": {"ceiling-step": {"_note": "b", "style": "none",
                                      "decoration": {"scale": 1.5, "spacing_pct": 4500}},
                     "pit": {"color": "#000000"},
                     "rope": {"color": "#EF5553"}},
           "areas": {}}
    rows = tr.diff_theme_json(old, new)
    got = {(op, p) for op, p, _o, _n in rows}
    assert ("~", "lines.ceiling-step.style") in got
    assert ("-", "lines.ceiling-step.dash") in got
    assert ("~", "lines.ceiling-step.decoration.scale") in got
    assert ("+", "lines.rope") in got
    assert ("-", "areas.blocks") in got
    assert not any("_note" in p or "_readme" in p or "spacing_pct" in p for _, p in got)
    assert tr.changed_keys(rows) == {("lines", "ceiling-step"), ("lines", "rope"),
                                     ("areas", "blocks")}
    assert tr.diff_theme_json(None, new) == []
    assert tr.diff_theme_json(new, json.loads(json.dumps(new))) == []


# ---------------------------------------------------------------- cache key

def test_cache_key_stable_and_sensitive():
    lists = {"signs": [["blocks", ["boja"]]], "lines": [], "areas": []}
    v = {"make_theme_mockup.py": "aa"}
    k = tr.cache_key(lists, v)
    assert len(k) == 12 and k == tr.cache_key(json.loads(json.dumps(lists)), dict(v))
    assert k != tr.cache_key({"signs": [["blocks", ["boja"]], ["bones", ["boja"]]],
                              "lines": [], "areas": []}, v)
    assert k != tr.cache_key(lists, {"make_theme_mockup.py": "ab"})


# ---------------------------------------------------------------- split diff

def _write(folder, kind, files):
    d = folder / kind
    d.mkdir(parents=True, exist_ok=True)
    idx = {}
    for key, body in files.items():
        fn = key.replace(":", "@") + ".svg"
        (d / fn).write_text(body, encoding="utf-8")
        idx[key] = fn
    (d / "index.json").write_text(json.dumps(idx), encoding="utf-8")


def test_split_diff_summary(tmp_path):
    theme, split = tmp_path / "theme", tmp_path / "split"
    _write(theme, "signs", {"bones": "<svg>1</svg>", "plus": "<svg>p</svg>"})
    _write(theme, "lines", {"pit": "<svg>pit</svg>", "slope:steep": "<svg>s</svg>"})
    _write(split, "signs", {"bones": "<svg>2</svg>", "plus": "<svg>p</svg>",
                            "tree-trunk": "<svg>t</svg>"})
    _write(split, "lines", {"pit": "<svg>pit</svg>"})
    _write(split, "areas", {"ice": "<svg>i</svg>"})
    report = {"pieces": [
        {"kind": "signs", "key": "tree-trunk", "id": "tree-trunk",
         "colours_flattened": ["#453625", "#FFFFFF"], "warnings": []},
        {"kind": "areas", "key": "ice", "id": "ice", "strokes": [{"stroke_width": 1}],
         "paths_out": 1, "warnings": []},
        {"kind": "signs", "key": "bones", "id": "_x3C_Group_x3E_-2", "warnings": []}],
        "unnamed": [{"layer": "Znakovi", "element": "g", "id": "_x3C_Group_x3E_"}],
        "duplicates": [{"kind": "signs", "key": "plus", "id": "plus-2", "kept": "plus"}]}
    theme_raw = {"signs": {"bones": {}, "plus": {}, "_rotate": "c"}, "lines": {"pit": {}},
                 "areas": {}}
    d = tr.split_diff(str(theme), str(split), report, theme_raw)
    assert d["signs"]["changed"] == ["bones"] and d["signs"]["added"] == ["tree-trunk"]
    assert d["signs"]["unchanged"] == 1
    assert d["lines"]["removed"] == ["slope:steep"] and d["areas"]["added"] == ["ice"]
    assert ("signs", "tree-trunk") in d["no_entry"] and ("areas", "ice") in d["no_entry"]
    assert d["colours"][("signs", "tree-trunk")] == ["#453625"]
    assert d["stroked"] == [("areas", "ice", 1, True)]
    text = "\n".join(tr.format_split_summary(d))
    assert "+ signs/tree-trunk  colour #453625" in text
    assert "- lines/slope:steep" in text and "theme file kept" in text
    assert "STROKE-ONLY" in text
    loud = [ln for ln in tr.format_split_summary(d) if ln.startswith("!!")]
    assert any("UNNAMED" in ln for ln in loud)
    assert any("DUPLICATE" in ln for ln in loud)
    assert sum("Illustrator default id" in ln for ln in loud) == 2


# ---------------------------------------------------------------- focus, previous run

def test_focus_matching():
    slots = [{"tag": "P49", "kind": "signs", "name": "water", "themes": []},
             {"tag": "L19", "kind": "lines", "name": "water", "themes": []},
             {"tag": "A09", "kind": "areas", "name": "water", "themes": ["boja"]},
             {"tag": "L04", "kind": "lines", "name": "ceiling-step", "themes": ["boja"]}]
    f = tr.parse_focus("ceiling-step, water,lines/water,P49")
    assert f == [(None, "ceiling-step"), (None, "water"), ("lines", "water"), (None, "P49")]
    tags = [s["tag"] for s in tr.match_focus(f, slots)]
    assert tags == ["L04", "A09", "L19", "P49"]


def test_previous_run(tmp_path):
    for name, t in (("2026-10-06-r8", 100), ("2026-10-06-r9", 200), ("2026-10-07-x", 300)):
        d = tmp_path / name / "themes"
        d.mkdir(parents=True)
        p = d / "boja.theme.json"
        p.write_text("{}", encoding="utf-8")
        os.utime(p, (t, t))
    (tmp_path / "2026-10-07-mockup-r7").mkdir()        # no copies: never a baseline
    assert tr.previous_run(str(tmp_path), "2026-10-07-x", ["boja"]) == "2026-10-06-r9"
    assert tr.previous_run(str(tmp_path), "new", ["boja"]) == "2026-10-07-x"
    assert tr.previous_run(str(tmp_path), "new", ["other"]) is None


# ---------------------------------------------------------------- RUNLOG

def test_render_runlog():
    rep = {"themed": 14, "signs": 47, "lookup": {"tdx (recovered)": 13, "target": 1},
           "notes": ["vegetable-debris: strokes"],
           "lines": {"themed": {"pit (tdx)": 2, "rope (target)": 1}, "skipped": []},
           "areas": {"themed": {"clay (tdx, tile)": 1}, "skipped": ["ice: own brush"]}}
    s = tr.report_summary(rep, {"lines": {"pit", "rope", "slope"}, "areas": {"clay", "ice"}})
    assert s["lines"] == {"pit": 2, "rope": 1}
    assert s["unthemed"] == ["lines/slope", "areas/ice"]
    assert "lines/rope (target)" in s["fallbacks"] and "signs/target: 1" in s["fallbacks"]
    info = {"label": "r9-test", "date": "2026-10-08", "command": "python theme_round.py r9-test",
            "inputs": [("drawing", "x.svg")], "previous_run": "2026-10-07-r8",
            "theme_diffs": {"boja": [("~", "lines.pit.decoration.scale", 2, 1.5)],
                            "crno-bijelo": []},
            "split": ["signs: 1 changed", "!! UNNAMED g"], "reports": {"boja": s},
            "ink": {"cols": ["izvorno", "boja s0"],
                    "rows": [("A01", "clay", {"izvorno": (0.078, 0), "boja s0": (0.15, 2)})]},
            "details": [("d.png", "focus")], "sheets": [("s.png", "sheet")],
            "files": [("pregled.png", "overview")], "timings": [("a", 1.0), ("b", 2.5)],
            "warnings": ["UNNAMED g"]}
    md = tr.render_runlog(info)
    assert md.startswith("# Theme round r9-test, 2026-10-08")
    assert "| ~ | `lines.pit.decoration.scale` | 2 | 1.5 |" in md
    assert "`crno-bijelo`: no change" in md
    assert "| A01 | clay | 7.8 % | 15.0 % (2 empty) |" in md
    assert "| **total** | **3.5** |" in md
    assert "## Feedback → change" in md and "[`d.png`](d.png)" in md
    assert "lines/slope" in md and "signs: 1 changed" in md
    base = dict(info, previous_run=None)
    assert "this round is the baseline" in tr.render_runlog(base)


# ---------------------------------------------------------------- fixed seeds

IMPORTED = """<csurvey>
  <plan><items>
          <item layer="1" type="3" linetype="0">
            <pen type="10" />
            <brush type="1" />
            <points data="0 0" />
          </item>
          <item layer="1" type="6" linetype="3">
            <brush type="7" />
          </item>
          <item layer="1" type="3" linetype="1">
            <pen type="0" />
            <brush type="4">
              <seed base="23.00" increment="19.00" />
            </brush>
          </item>
  </items></plan>
</csurvey>
"""


def test_seed_areas_fixed_and_variant():
    out, n = mm.seed_areas(IMPORTED)
    assert n == 2
    root = ET.fromstring(out)
    items = list(root.iter("item"))
    seeds = [it.find("brush").find("seed") for it in items]
    assert seeds[1] is None                                 # a sign is left alone
    want = [mm.area_seed(0), mm.area_seed(1)]
    got = [(float(s.get("base")), float(s.get("increment"))) for s in (seeds[0], seeds[2])]
    assert got == want
    assert items[0].find("brush").get("type") == "1"
    assert mm.seed_areas(out)[0] == out                     # idempotent
    alt, _ = mm.seed_areas(IMPORTED, variant=1)
    assert alt != out
    for i in range(20):
        for v in range(4):
            b, inc = mm.area_seed(i, v)
            assert 0 <= b < 100 and 1 <= inc <= 29
