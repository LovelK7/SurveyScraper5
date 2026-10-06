"""tdx_name_recover — T8 spike: TopoDroid names back onto post-import items."""

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import tdx_name_recover as rec  # noqa: E402

RUNS = Path(__file__).resolve().parents[1] / "projects" / "0002-tdx-symbol-mapping" / "runs"

# A raw/KORAK 1 TopoDroid file: one sign, one renamed line (tdxpp), two walls,
# an area, a label; the profile repeats one geometry under another name.
PRE = """<?xml version="1.0" encoding="UTF-8"?>
<csurvey version="1.11"><properties creatid="TopoDroid" />
<plan>
 <item type="point" name="stalactite" options=""><points data="1.00 2.00 " /></item>
 <item type="line" name="overhang" reversed="0" closed="0" options="tdxpp:chimney">
  <points data="0.00 0.00 B 1.00 0.50 2.00 0.00 " /></item>
 <item type="line" name="wall" reversed="0" closed="0" options="">
  <points data="0.00 5.00 B 2.00 5.20 4.00 5.00 " /></item>
 <item type="line" name="wall" reversed="0" closed="0" options="tdxpp:wall:blocks">
  <points data="0.00 8.00 B 2.00 8.20 4.00 8.00 " /></item>
 <item type="area" name="clay" options="tdxpp:clay-area">
  <points data="5.00 5.00 B 6.00 5.00 6.00 6.00 5.00 6.00 " /></item>
 <item type="point" name="label" text="!" options="tdxpp:danger"><points data="3.00 3.00 " /></item>
</plan>
<profile>
 <item type="point" name="blocks" options=""><points data="1.00 2.00 " /></item>
</profile>
</csurvey>
"""

# What cSurvey makes of it: reversed point order, BS<guid>/S flags, other
# layers, and the two walls folded into ONE item (KORAK 2 merge), with the
# second stroke reversed back. Plus a native item drawn in cSurvey.
POST = """<?xml version="1.0" encoding="utf-8"?>
<csurvey version="1.14"><properties creatid="TopoDroid" creat_postprocessed="1" />
<plan><layers>
 <layer type="2" name="Water and floor morphologies"><items>
  <item layer="2" type="1" category="3"><pen type="12" />
   <points data="2.00 0.00 BSab-12 1.00 0.50 S 0.00 0.00 S " />
   <datarow>TopoDroid|2026-07-19T00:00:00</datarow></item>
  <item layer="2" type="1" category="3"><pen type="5" />
   <points data="9.00 9.00 B 9.50 9.50 " /></item>
 </items></layer>
 <layer type="5" name="Borders"><items>
  <item layer="5" type="4" category="1">
   <points data="4.00 5.00 BScd 2.00 5.20 S 0.00 5.00 S 0.00 8.00 BS 2.00 8.20 S 4.00 8.00 S " />
   <datarow>TopoDroid|2026-07-19T00:00:00</datarow></item>
 </items></layer>
 <layer type="1" name="Soil"><items>
  <item layer="1" type="3" category="48"><brush type="9" />
   <points data="5.00 6.00 BS1 6.00 6.00 S 6.00 5.00 S 5.00 5.00 S " />
   <datarow>TopoDroid|2026-07-19T00:00:00</datarow></item>
 </items></layer>
 <layer type="6" name="Signs"><items>
  <item layer="6" type="6" category="80" sign="12"><points data="1.00 2.00 S " />
   <datarow>TopoDroid|2026-07-19T00:00:00</datarow></item>
  <item layer="6" type="9" category="80" text="!"><points data="3.00 3.00 " />
   <datarow>TopoDroid|2026-07-19T00:00:00</datarow></item>
 </items></layer>
</layers></plan>
<profile><layers>
 <layer type="6" name="Signs"><items>
  <item layer="6" type="6" category="80" sign="40"><points data="1.00 2.00 " />
   <datarow>TopoDroid|2026-07-19T00:00:00</datarow></item>
 </items></layer>
</layers></profile>
</csurvey>
"""


def _files(tmp_path, pre=PRE, post=POST, csz=False):
    a = tmp_path / "x_prep.csx"
    a.write_text(pre, encoding="utf-8")
    if csz:
        b = tmp_path / "x_postp.csz"
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("_data/", "")
            z.writestr("_data.xml", post)
    else:
        b = tmp_path / "x_postp.csx"
        b.write_text(post, encoding="utf-8")
    return str(a), str(b)


def _by_layer(res):
    return {(it["design"], it["layer"], it["index"]): it for it in res["items"]}


def test_parse_sequences_reads_both_formats():
    assert rec.parse_sequences("0.00 0.00 B 1.00 0.50 2.00 0.00 ") == \
        [[(0.0, 0.0), (1.0, 0.5), (2.0, 0.0)]]
    seqs = rec.parse_sequences("4 5 BScd-1 2 5.2 S 0 5 S 0 8 BS 2 8.2 S 4 8 SLx ")
    assert [len(s) for s in seqs] == [3, 3]
    assert rec.parse_sequences("1.00 2.00 ") == [[(1.0, 2.0)]]
    assert rec.parse_sequences("") == []


@pytest.mark.parametrize("csz", [False, True])
def test_every_item_gets_its_topodroid_name(tmp_path, csz):
    res = rec.recover(*_files(tmp_path, csz=csz))
    items = _by_layer(res)
    assert items[("plan", "2", 0)]["tdx_name"] == "chimney"      # tdxpp beats name
    assert items[("plan", "2", 0)]["sequences"][0]["source"]["prep_name"] == "overhang"
    assert items[("plan", "6", 0)]["tdx_name"] == "stalactite"   # unrenamed: name
    assert items[("plan", "6", 1)]["tdx_name"] == "danger"
    assert items[("plan", "1", 0)]["tdx_name"] == "clay-area"
    assert items[("profile", "6", 0)]["tdx_name"] == "blocks"    # design kept apart
    merged = items[("plan", "5", 0)]
    assert merged["status"] == "exact" and merged["tdx_names"] == ["wall", "wall:blocks"]
    assert merged["tdx_name"] is None                            # mixed names: per sequence
    assert [s["source"]["tdx_name"] for s in merged["sequences"]] == ["wall", "wall:blocks"]
    native = items[("plan", "2", 1)]
    assert native["status"] == "native" and native["tdx_name"] is None
    k = res["summary"]["by_kind"]
    assert k == {"point": {"total": 3, "recovered": 3},
                 "line": {"total": 3, "recovered": 3},
                 "area": {"total": 1, "recovered": 1}}
    assert res["unused_sources"] == []


def test_edited_geometry_matches_tolerantly(tmp_path):
    post = POST.replace("2.00 0.00 BSab-12 1.00 0.50 S 0.00 0.00 S",
                        "2.02 0.01 BSab-12 1.00 0.80 S 0.50 0.25 S 0.00 0.00 S")
    post = post.replace('<points data="1.00 2.00 S " />', '<points data="1.03 2.02 S " />')
    res = rec.recover(*_files(tmp_path, post=post))
    items = _by_layer(res)
    line = items[("plan", "2", 0)]["sequences"][0]
    assert line["status"] == "tolerant" and line["source"]["tdx_name"] == "chimney"
    pt = items[("plan", "6", 0)]["sequences"][0]
    assert pt["status"] == "tolerant" and pt["source"]["tdx_name"] == "stalactite"


def test_moved_and_deleted_items_are_reported_not_guessed(tmp_path):
    post = POST.replace('<points data="1.00 2.00 S " />', '<points data="1.50 2.00 S " />')
    post = post.replace("""  <item layer="6" type="9" category="80" text="!"><points data="3.00 3.00 " />
   <datarow>TopoDroid|2026-07-19T00:00:00</datarow></item>
""", "")
    res = rec.recover(*_files(tmp_path, post=post))
    pt = _by_layer(res)[("plan", "6", 0)]
    assert pt["status"] == "miss" and pt["tdx_name"] is None
    lost = {u["tdx_name"] for u in res["unused_sources"]}
    assert lost == {"stalactite", "danger"}
    assert res["summary"]["by_kind"]["point"] == {"total": 3, "recovered": 1}


def test_identical_geometry_with_different_names_is_ambiguous(tmp_path):
    pre = PRE.replace('</plan>', ' <item type="point" name="stalagmite" options="">'
                      '<points data="1.00 2.00 " /></item>\n</plan>')
    res = rec.recover(*_files(tmp_path, pre=pre))
    sq = _by_layer(res)[("plan", "6", 0)]["sequences"][0]
    assert sq["status"] == "ambiguous" and sq["source"] is None
    assert {c["tdx_name"] for c in sq["candidates"]} == {"stalactite", "stalagmite"}


def test_close_rivals_with_different_names_are_ambiguous(tmp_path):
    pre = PRE.replace('</plan>', ' <item type="point" name="stalagmite" options="">'
                      '<points data="1.04 2.00 " /></item>\n</plan>')
    post = POST.replace('<points data="1.00 2.00 S " />', '<points data="1.02 2.00 S " />')
    res = rec.recover(*_files(tmp_path, pre=pre, post=post))
    assert _by_layer(res)[("plan", "6", 0)]["status"] == "ambiguous"


def test_refuses_a_post_import_file_as_pre(tmp_path):
    a, b = _files(tmp_path)
    assert rec.main(["recover", b, b]) == 1


def test_cli_writes_json(tmp_path, capsys):
    a, b = _files(tmp_path)
    out = tmp_path / "r.json"
    assert rec.main(["recover", a, b, "--json", str(out), "--quiet"]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["summary"]["post_items"] == 7
    assert "recovered (100.0 %)" in capsys.readouterr().out


# ---- real pairs (survey files are gitignored: skip when absent) ----------

REAL_PAIRS = [
    ("2026-07-19-symbol-zoo/step-00-symbol-zoo.csx", "2026-07-19-symbol-zoo/step-01-after-import.csx"),
    ("2026-07-19-symbol-zoo/step-03-zoo-v3.csx", "2026-07-19-symbol-zoo/step-04-after-import.csx"),
    ("2026-07-19-rupe-acceptance/step-01b-preprocessed.csx", "2026-07-19-rupe-acceptance/step-02b-after-import.csx"),
    ("2026-07-19-rupe-acceptance/step-01d-preprocessed.csx", "2026-07-19-rupe-acceptance/step-03d-final.csx"),
]


@pytest.mark.parametrize("pre,post", REAL_PAIRS)
def test_real_pairs_recover_everything(pre, post):
    a, b = RUNS / pre, RUNS / post
    if not (a.exists() and b.exists()):
        pytest.skip("survey files not present (gitignored)")
    res = rec.recover(str(a), str(b))
    for kind, k in res["summary"]["by_kind"].items():
        assert k["recovered"] == k["total"], kind
    assert set(res["summary"]["sequence_status"]) == {"exact"}
