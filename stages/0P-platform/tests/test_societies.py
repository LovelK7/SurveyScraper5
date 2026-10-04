"""Registar udruga: the shipped data, the lookup, the fit ladder, the builder."""

from __future__ import annotations

import json

import pytest

from cave_dossier.core import societies
from cave_dossier.core.societies import (
    Society,
    SocietyRegistry,
    fit_societies,
    society_ladder,
    split_canonical,
    split_export_cell,
)


@pytest.fixture(scope="module")
def shipped():
    return societies.load()


# ── the shipped data stays consistent ────────────────────────────────

def test_the_shipped_registry_has_no_key_conflicts(shipped):
    assert shipped.conflicts == {}


def test_no_two_societies_share_a_short_form(shipped):
    shorts = [s.short for s in shipped.societies if s.short]
    assert len(shorts) == len(set(shorts))


def test_every_curated_canonical_is_a_crospeleo_organisation(shipped):
    """CroSpeleo is the ground truth (user, 2026-10-04): a curated canonical
    CroSpeleo does not know is a typo, not a new society."""
    stray = [s.canonical for s in shipped.societies
             if s.curated and s.canonical and not s.in_crospeleo]
    assert stray == []


def test_crospeleo_organisations_without_an_overlay_entry_are_still_found(shipped):
    society = shipped.find('Speleološko društvo "Pauk", Fužine')
    assert society is not None and not society.curated
    assert society.name == "SD Pauk" and society.place == "Fužine"


# ── lookup ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, name", [
    ("SKOL", "SK Ozren Lukić"),
    ("Speleološki klub Ozren Lukić, Zagreb", "SK Ozren Lukić"),
    ('Speleološka udruga "Estavela", Kastav', "SU Estavela"),
    ("speleoloska udruga estavela", "SU Estavela"),
    ("SUE", "SU Estavela"),
    ("Speleološki odsjek Mosor", "SO HPD Mosor"),     # derived spelling
    ("SOŽ", "SO HPD Željezničar"),                      # the Zagreb section, curated
    # SB 1328's OSZ calls the Bitelić Speleo sekcija an "SO" (user, 2026-10-04)
    ("SO Sv. Jakov Bitelić", "SS PD Sv. Jakov"),
    ("Speleo sekcija PD Sv. Jakov Bitelić", "SS PD Sv. Jakov"),
    ('Speleološka sekcija PD "Sv. Jakov", Gornji Bitelić', "SS PD Sv. Jakov"),
    ("Speleo 8", "Osmica"),          # the HPS name of CroSpeleo's Osmica (user, 2026-10-04)
    ("SKH", "SK Had"),
    ("SD Had", "SK Had"),
])
def test_a_written_form_resolves_to_its_society(shipped, text, name):
    found = shipped.find(text)
    assert found is not None and found.name == name


@pytest.mark.parametrize("text", ["", None, "Nekakva grupa", "SO", "Jakov"])
def test_lookup_never_guesses(shipped, text):
    assert shipped.find(text) is None


def test_a_derived_key_two_societies_share_resolves_to_neither():
    registry = SocietyRegistry([
        Society(name="SO HPD Mosor", place="Split"),
        Society(name="SO PD Mosor", place="Omiš"),
    ])
    assert registry.find("SO Mosor") is None             # both would derive it
    assert registry.find("SO HPD Mosor").place == "Split"


def test_a_canonical_comma_is_not_a_list_separator(shipped):
    pairs = shipped.split('Speleološka udruga "Estavela", Kastav, SKOL')
    assert [s.name for _part, s in pairs] == ["SU Estavela", "SK Ozren Lukić"]


# ── fitting a list into a tight space ────────────────────────────────

def test_the_ladder_for_sb_1328(shipped):
    assert society_ladder("SKOL, SO Sv. Jakov Bitelić", shipped) == [
        "SKOL, SO Sv. Jakov Bitelić",
        "SKOL, SS PD Sv. Jakov",
        "SKOL, SS Sv. JB",
    ]


def test_the_ladder_never_lengthens_a_part(shipped):
    # "SUE" is shorter than the name "SU Estavela" — it stays SUE
    assert society_ladder("SUE, SO Sv. Jakov Bitelić", shipped)[1] == "SUE, SS PD Sv. Jakov"


def test_an_unlisted_society_falls_back_to_the_rule_and_noise_is_kept(shipped):
    assert society_ladder("SO Nepoznati, HPS Zagreb", shipped)[-1] == "SON, HPS Zagreb"


def test_fit_takes_the_longest_candidate_that_fits(shipped):
    raw = 'Speleološka udruga "Estavela", Kastav'
    assert fit_societies(raw, lambda t: len(t) <= 12, shipped) == "SU Estavela"
    assert fit_societies(raw, lambda t: True, shipped) == raw
    assert fit_societies(raw, lambda t: False, shipped) == "SUE"


# ── building the ground truth from an export ─────────────────────────

def test_split_canonical():
    assert split_canonical('Speleološki odsjek HPD "Mosor", Split') == ("SO HPD Mosor", "Split")
    assert split_canonical('Hrvatsko planinarsko društvo "Mosor", Split') == ("HPD Mosor", "Split")
    assert split_canonical("Speleološko društvo ''Zelena brda'' (Trebinje, BIH)")[1] is None


def test_split_export_cell():
    cell = ('"Osmica" društvo za planinarenje, istraživanje i očuvanje prirodoslovnih '
            'vrijednosti, Karlovac, Speleološki klub Ozren Lukić, Zagreb, Breganja, Bregana')
    assert split_export_cell(cell, known={"Breganja, Bregana"}) == [
        '"Osmica" društvo za planinarenje, istraživanje i očuvanje prirodoslovnih '
        'vrijednosti, Karlovac',
        "Speleološki klub Ozren Lukić, Zagreb",
        "Breganja, Bregana",
    ]


def test_build_from_export(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Ime objekta", "Predala udruga", "Istražile udruge"])
    sheet.append(["A", "Speleološka udruga \"Estavela\", Kastav",
                  "Speleološka udruga \"Estavela\", Kastav, Speleološki klub Ozren Lukić, Zagreb"])
    sheet.append(["B", "Breganja, Bregana", None])
    path = tmp_path / "objekti.xlsx"
    book.save(path)

    payload = societies.build_from_export(path)
    uses = {o["canonical"]: o["uses"] for o in payload["organizations"]}
    assert uses == {'Speleološka udruga "Estavela", Kastav': 2,
                    "Speleološki klub Ozren Lukić, Zagreb": 1,
                    "Breganja, Bregana": 1}

    out = tmp_path / "crospeleo.json"
    societies.write_crospeleo(payload, out)
    registry = societies.load(crospeleo_path=out)
    assert registry.find("Breganja").in_crospeleo
    json.loads(out.read_text(encoding="utf-8"))
