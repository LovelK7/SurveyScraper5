"""osz/backfill.py — KORAK 4: the survey's measurements written into the existing OSZ."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("lxml")

from cave_dossier.osz import backfill, prefill  # noqa: E402
from cave_dossier.osz.reader import read_osz_content  # noqa: E402
from cave_dossier.osz.writer import OszDocument  # noqa: E402

from test_osz_prefill import ENTRANCE_BLOCK, _leaf, _template_guard, intake_settings, run_dir  # noqa: E402,F401
from test_osz_writer import TEMPLATE  # noqa: E402


def _osz(folder, **cells):
    """A v10 zapisnik in the leaf with some cells typed in by hand."""
    _template_guard()
    folder.mkdir(parents=True, exist_ok=True)
    doc = OszDocument(TEMPLATE)
    for key, value in cells.items():
        backfill._fill(doc, key, value)
    path = folder / "SB_0001_OSZ.docx"
    doc.save(path)
    return path


def _dims(folder, **values):
    data = {"calculated": True, "l": 18.4, "pl": 16, "nvr_m": 5.0, "pvr_m": 5.5, "vr": 10,
            "entrance_size": ENTRANCE_BLOCK}
    data.update(values)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SB_1_test_dimenzije.json"
    path.write_text(json.dumps({k: v for k, v in data.items() if v is not None}), encoding="utf-8")
    return path


def test_measured_cells_follow_the_zapisnik_type():
    dims = {"l": 18, "pl": 16, "nvr": 5, "pvr": 1, "vr": 6, "entrance_size": ENTRANCE_BLOCK}
    values, kind, notes = backfill.measured_cells(dims, ("špilja",))
    assert kind == "horizontal" and values["sirina_ulaza"] == "0,6" and values["duljina"] == "18"
    values, kind, _ = backfill.measured_cells(dims, ("jama",))
    assert kind == "pit" and values["sirina_ulaza"] == "1,5" and values["visina_duljina_ulaza"] == "4,0"
    values, kind, _ = backfill.measured_cells({"l": 18}, ())
    assert kind is None and values == {"duljina": "18"}


def test_plan_changes_keeps_the_same_measurement_and_overrides_the_rest():
    recorded = {"duljina": "18 m", "dubina": "7", "sirina_ulaza": "0.55", "broj_ulaza": ""}
    measured = {"duljina": "18", "dubina": "5", "sirina_ulaza": "0,6", "broj_ulaza": "1"}
    written, kept = backfill.plan_changes(recorded, measured)
    assert kept == {"duljina": "18 m", "sirina_ulaza": "0.55"}
    assert written == {"dubina": "5", "broj_ulaza": "1"}


def test_izmjera_writes_the_cells_and_keeps_the_rest(intake_settings, run_dir):
    leaf = _leaf(intake_settings)
    path = _osz(leaf, ime_objekta="Špilja Testovka", opis="Ulaz je nizak.", dubina="7")
    _dims(leaf)
    outcome = backfill.run_backfill(intake_settings, 1)
    r = outcome.result
    assert r.written == {"duljina": "18", "horizontalna_duljina": "16", "dubina": "5",
                         "visinska_razlika": "10", "sirina_ulaza": "0,6",
                         "visina_duljina_ulaza": "1,4", "broj_ulaza": "1"}
    assert r.entrance_kind == "horizontal"   # no Vrsta objekta ticked -> the geometric guess
    assert r.backup is None                  # overwritten in place by default
    assert any("zapisano '7'" in n for n in r.notes)
    assert r.osz_mtime_before is not None and r.osz_mtime_after is not None
    content = read_osz_content(path)
    assert content.fields["dubina"] == "5" and content.fields["sirina_ulaza"] == "0,6"
    assert content.fields["ime_objekta"] == "Špilja Testovka" and content.fields["opis"] == "Ulaz je nizak."
    assert sorted(p.name for p in leaf.iterdir()) == ["SB_0001_OSZ.docx", "SB_1_test_dimenzije.json"]
    assert outcome.sidecar_path.exists() and backfill.last_write(1)["written"]["dubina"] == "5"


def test_keep_old_leaves_the_previous_zapisnik_beside_the_new_one(intake_settings, run_dir):
    leaf = _leaf(intake_settings)
    path = _osz(leaf, ime_objekta="X", dubina="7")
    _dims(leaf)
    r = backfill.run_backfill(intake_settings, 1, keep_old=True).result
    assert r.backup and r.backup.startswith("SB_0001_OSZ_stari_")
    assert read_osz_content(leaf / r.backup).fields["dubina"] == "7"
    assert read_osz_content(path).fields["dubina"] == "5"


def test_izmjera_second_run_changes_nothing(intake_settings, run_dir):
    leaf = _leaf(intake_settings)
    _osz(leaf, ime_objekta="X")
    _dims(leaf)
    backfill.run_backfill(intake_settings, 1)
    before = sorted(p.name for p in leaf.iterdir())
    outcome = backfill.run_backfill(intake_settings, 1)
    assert outcome.result.written == {} and outcome.result.backup is None
    assert any("ništa nije mijenjano" in n for n in outcome.result.notes)
    assert sorted(p.name for p in leaf.iterdir()) == before


def test_izmjera_takes_the_pit_reading_when_the_zapisnik_says_jama(intake_settings, run_dir):
    leaf = _leaf(intake_settings)
    path = _osz(leaf, ime_objekta="X")
    doc = OszDocument(path)
    assert doc.tick({"jama"}) == set()
    staged = leaf / "ticked.docx"
    doc.save(staged)
    staged.replace(path)
    _dims(leaf)
    r = backfill.run_backfill(intake_settings, 1).result
    assert r.entrance_kind == "pit"
    assert r.written["sirina_ulaza"] == "1,5" and r.written["visina_duljina_ulaza"] == "4,0"


def test_izmjera_refuses_without_osz_or_dimensions_or_when_word_holds_it(intake_settings, run_dir):
    leaf = _leaf(intake_settings)
    with pytest.raises(backfill.BackfillError, match="nema mapu"):
        backfill.run_backfill(intake_settings, 1)
    leaf.mkdir(parents=True)
    with pytest.raises(backfill.BackfillError, match="nema OSZ-a"):
        backfill.run_backfill(intake_settings, 1)
    path = _osz(leaf, ime_objekta="X")
    with pytest.raises(backfill.BackfillError, match="dimenzije.json"):
        backfill.run_backfill(intake_settings, 1)
    _dims(leaf)
    (leaf / "~$_0001_OSZ.docx").write_text("lock", encoding="utf-8")
    with pytest.raises(backfill.BackfillError, match="Wordu"):
        backfill.run_backfill(intake_settings, 1)
    assert read_osz_content(path).fields.get("duljina") in (None, "")
