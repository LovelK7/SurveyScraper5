"""`Izjava za katastar` filename semantics (user's convention, 2026-08-26).

The hard case is that one shape — an underscore after the surname — carries
three different meanings: a locality scope, a single-cave scope, and a double
surname. The convention resolves it by joining double surnames with a hyphen;
the pre-existing exception is listed explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cave_dossier.archive import Izjava, covers, is_izjava_file, parse_izjava


@pytest.mark.parametrize(
    ("filename", "person", "scope"),
    [
        ("Izjava_ABahović.pdf", "ABahović", None),                 # universal
        ("Izjava_ACiceran_Šverda.pdf", "ACiceran", "Šverda"),      # locality scope
        ("Izjava_MMarić_Kaverna-Učka.pdf", "MMarić", "Kaverna-Učka"),  # single cave
        ("Izjava_IIvić_Kotluša.pdf", "IIvić", "Kotluša"),          # single cave
        # Hyphen keeps a double surname together.
        ("Izjava_SKapidžić-Antolič.pdf", "SKapidžić-Antolič", None),
    ],
)
def test_parse_person_and_scope(filename: str, person: str, scope: str | None) -> None:
    izjava = parse_izjava(Path(filename))
    assert izjava is not None
    assert izjava.person == person
    assert izjava.scope == scope


def test_legacy_underscore_double_surname_is_still_one_person() -> None:
    """Until the file is renamed, the old form must not read as a scope."""
    izjava = parse_izjava(Path("Izjava_SKapidžić_Antolič.pdf"))
    assert izjava is not None
    assert izjava.scope is None
    assert izjava.person == "SKapidžić-Antolič"


@pytest.mark.parametrize(
    "filename",
    [
        "!!Izjava_SUE_član_2021_prazna.pdf",   # blank template
        "!!!Fale_Brane.txt",                   # the society's missing-izjave list
        "!!!Traženje izjava.txt",
        "CroSpeleo_upute.pdf",                 # not an izjava at all
    ],
)
def test_notes_and_templates_are_not_izjave(filename: str) -> None:
    assert is_izjava_file(Path(filename)) is False
    assert parse_izjava(Path(filename)) is None


# ── Scope resolution ──────────────────────────────────────────────────


def test_universal_izjava_covers_every_cave() -> None:
    izjava = parse_izjava(Path("Izjava_ABahović.pdf"))
    assert covers(izjava, locality="Šverda", object_name="Konglomeratača") is True
    assert covers(izjava, locality="Učka", object_name="Bilo koja jama") is True


def test_locality_scope_covers_only_that_locality() -> None:
    izjava = parse_izjava(Path("Izjava_ACiceran_Šverda.pdf"))
    assert covers(izjava, locality="Šverda", object_name="Konglomeratača") is True
    # Same author, cave elsewhere → a new izjava is required.
    assert covers(izjava, locality="Učka", object_name="Konglomeratača") is False


def test_locality_scope_is_diacritic_insensitive() -> None:
    izjava = Izjava(path=Path("Izjava_X_Sverda.pdf"), person="X", scope="Sverda")
    assert covers(izjava, locality="Šverda", object_name=None) is True


def test_single_object_scope_matches_the_cave_or_a_synonym() -> None:
    izjava = parse_izjava(Path("Izjava_MMarić_Kaverna-Učka.pdf"))
    assert covers(izjava, locality="Učka", object_name="Kaverna-Učka") is True
    assert covers(izjava, locality="Učka", object_name="Neka druga",
                  synonyms=("Kaverna-Učka",)) is True
    assert covers(izjava, locality="Učka", object_name="Neka druga") is False
