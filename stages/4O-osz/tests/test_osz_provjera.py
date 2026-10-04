"""osz/provjera.py — the obligatory zapisnik fields still empty, before 3N."""

from __future__ import annotations

import pytest

pytest.importorskip("lxml")

from cave_dossier.osz import backfill, provjera  # noqa: E402
from cave_dossier.osz.writer import OszDocument  # noqa: E402

from test_osz_prefill import _leaf, _template_guard, intake_settings, run_dir  # noqa: E402,F401
from test_osz_writer import TEMPLATE  # noqa: E402

#: Every non-survey requirement answered — the baseline the tests take away from.
COMPLETE = {
    "nacrt_uredio": "Tomislav Tepavac", "crtali": "Lovel Kukuljan", "mjerili_2": "Ana Anić",
    "clanovi_ekipe": "Lovel Kukuljan, Ana Anić", "datum_istrazivanja": "10.12.2023.",
    "istrazile_udruge": "SO PDS Velebit", "ime_objekta": "Špilja Testovka",
    "x_htrs": "450000", "izvor_koordinata": "GPS", "polozaj_pristup": "Uz put.",
    "opis": "Ulaz je nizak.", "zapisnicar": "Lovel Kukuljan",
}
TICKED = ("špilja", "preuzeto kao lokalni naziv", "suh", "nema", "nije poznato")


def _labels(gaps):
    return [g.label for g in gaps]


def test_complete_zapisnik_has_no_gaps_and_survey_cells_are_deferred():
    check = provjera.check_content(COMPLETE, TICKED)
    assert check.missing == []
    assert check.filled == check.total
    assert _labels(check.deferred) == ["Duljina", "Horizontalna duljina", "Dubina",
                                       "Visinska razlika", "Širina ulaza", "Visina/duljina ulaza"]


def test_missing_nacrt_uredio_is_flagged_for_3n():
    fields = dict(COMPLETE, nacrt_uredio=None)
    check = provjera.check_content(fields, TICKED)
    assert _labels(check.missing_for_3n) == ["Nacrt uredio"]
    assert check.to_json()["missing_for_3n"] == ["Nacrt uredio"]
    assert provjera.describe(check.missing[0]).startswith("Nacrt uredio – 3N sastavnica")


def test_placeholders_count_as_empty_and_any_cell_of_a_group_counts():
    fields = dict(COMPLETE, crtali="?", mjerili_2=None, mjerili="Ana Anić")
    assert _labels(provjera.check_content(fields, TICKED).missing) == ["Crtali"]


def test_checkbox_groups_need_a_tick_and_match_without_diacritics():
    check = provjera.check_content(COMPLETE, ())
    assert {"Vrsta objekta", "Podrijetlo imena", "Hidrološka karakteristika",
            "Hidrogeološka funkcija"} <= set(_labels(check.missing))
    # Perspektiva is satisfied by its text alone.
    assert "Perspektiva daljnjeg istraživanja" in _labels(check.missing)
    check = provjera.check_content(dict(COMPLETE, perspektiva="Suženje na -5 m."),
                                   ("spilja", "preuzeto kao lokalni naziv", "suh", "nema"))
    assert check.missing == []


def test_survey_cells_once_filled_are_neither_missing_nor_deferred():
    fields = dict(COMPLETE, duljina="18", dubina="5")
    check = provjera.check_content(fields, TICKED)
    assert "Duljina" not in _labels(check.deferred) and "Dubina" not in _labels(check.deferred)


def test_run_check_reads_the_leaf_zapisnik(intake_settings, run_dir):
    _template_guard()
    leaf = _leaf(intake_settings)
    leaf.mkdir(parents=True, exist_ok=True)
    doc = OszDocument(TEMPLATE)
    for key, value in COMPLETE.items():
        if key != "nacrt_uredio":
            backfill._fill(doc, key, value)
    doc.tick(set(TICKED))
    doc.save(leaf / "SB_0001_OSZ.docx")

    check, path = provjera.run_check(intake_settings, 1)
    assert path.name == "SB_0001_OSZ.docx" and check.osz == path.name
    assert _labels(check.missing) == ["Nacrt uredio"]


def test_run_check_without_a_leaf_is_a_clear_error(intake_settings, run_dir):
    with pytest.raises(provjera.ProvjeraError, match="osz prefill"):
        provjera.run_check(intake_settings, 1)
