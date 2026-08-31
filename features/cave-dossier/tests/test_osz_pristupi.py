"""osz/pristupi.py — the shared-approach rule engine and its committed rules."""

from __future__ import annotations

import pytest

from cave_dossier.osz import pristupi


def test_committed_rules_load_and_match_veprinac():
    rules = pristupi.load_rules()
    assert rules, "config/pristupi.yaml must carry at least the Veprinac rule"
    text = pristupi.find_pristup("Veprinac", "Ćićarija")
    assert text is not None
    assert text.startswith("Položaj:")
    assert "Veprinačku cestu" in text
    assert text.endswith("Od tuda nastaviti...")


def test_matching_is_folded_and_tokenised(tmp_path):
    path = tmp_path / "pristupi.yaml"
    path.write_text(
        "- match:\n"
        "    najblize_mjesto: \"Veprinac\"\n"
        "    lokalitet: \"Ćićarija\"\n"
        "  text: \"Zajednički pristup.\"\n",
        encoding="utf-8",
    )
    # Diacritic/case folding on both sides.
    assert pristupi.find_pristup("VEPRINAC", "cicarija", path) == "Zajednički pristup."
    # Lokalitet matches any comma/semicolon token.
    assert pristupi.find_pristup("Veprinac", "Ćićarija, Slum", path) is not None
    assert pristupi.find_pristup("Veprinac", "Slum; Ćićarija", path) is not None
    # Both halves must match.
    assert pristupi.find_pristup("Breza", "Ćićarija", path) is None
    assert pristupi.find_pristup("Veprinac", "Učka", path) is None
    assert pristupi.find_pristup(None, "Ćićarija", path) is None


def test_missing_or_malformed_file_is_failsoft(tmp_path):
    assert pristupi.load_rules(tmp_path / "nema.yaml") == []
    bad = tmp_path / "bad.yaml"
    bad.write_text("]:not yaml at [all", encoding="utf-8")
    assert pristupi.load_rules(bad) == []
    incomplete = tmp_path / "incomplete.yaml"
    incomplete.write_text("- match:\n    najblize_mjesto: X\n", encoding="utf-8")
    assert pristupi.load_rules(incomplete) == []  # no lokalitet, no text
