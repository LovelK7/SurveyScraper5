"""The fetcher direction: person aliases, year cropping, reader round-trip,
and the SB backfill rules (empty cells get proposals, conflicts get notes,
authors merge across the full-name/shorthand conventions)."""

from __future__ import annotations

import pytest

from cave_dossier.core.person_aliases import same_person, to_sb_shorthand, variants_for
from cave_dossier.osz.backfill import build_backfill, extract_year_period
from cave_dossier.sb.loader import SBReader


# ── person aliases ───────────────────────────────────────────────────
def test_variants_for_core_forms():
    variants = variants_for("Lovel Kukuljan")
    assert variants[0] == "L.Kukuljan"  # the SB convention leads
    assert "L. Kukuljan" in variants and "LK" in variants
    assert variants_for("Ana") == []              # single token
    assert variants_for("Ana Marija Horvat") == []  # 3 tokens — skipped, as in crospeleo


def test_to_sb_shorthand():
    assert to_sb_shorthand("Lovel Kukuljan") == "L.Kukuljan"
    assert to_sb_shorthand("L.Kukuljan") == "L.Kukuljan"   # passthrough
    assert to_sb_shorthand("Ana Marija Horvat") == "Ana Marija Horvat"


def test_same_person_across_conventions():
    assert same_person("Lovel Kukuljan", "L.Kukuljan")
    assert same_person("L.Kukuljan", "Lovel Kukuljan")
    assert same_person("L. Kukuljan", "L.Kukuljan")
    assert not same_person("Nina Grozić", "Dino Grozić")
    # Surname alone stays ambiguous — singletons are deliberately excluded.
    assert not same_person("Kukuljan", "Lovel Kukuljan")


# ── year / period cropping ───────────────────────────────────────────
def test_extract_year_period():
    assert extract_year_period("10.05.2025.") == "2025"
    assert extract_year_period("10.5.2014 – 17.5.2025") == "2014-2025"
    assert extract_year_period("2019") == "2019"
    assert extract_year_period("svibanj, bez godine") is None
    assert extract_year_period(None) is None


# ── reader round-trip (real template) ────────────────────────────────
def test_reader_roundtrip(tmp_path):
    pytest.importorskip("lxml")
    from cave_dossier.osz.reader import read_osz
    from cave_dossier.osz.writer import OszDocument
    from test_osz_writer import TEMPLATE

    if not TEMPLATE.exists():
        pytest.skip("v10 template not present")
    doc = OszDocument(TEMPLATE)
    doc.fill_plain(0, 1, 1, "051-999")            # broj_plocice
    doc.fill_plain(1, 0, 1, "Jama Proba")         # ime_objekta
    doc.fill_plain(1, 1, 1, "Stara Proba")        # sinonimi
    doc.fill_sdt_cell(2, 2, 2, ["333001"])        # x_htrs — a filled control
    doc.fill_plain(4, 3, 0, "12,5")               # duljina
    doc.fill_plain(6, 8, 1, "10.05.2025.")        # datum
    doc.fill_plain(6, 14, 1, "Lovel Kukuljan, Ivana Dujmović")  # crtali
    out = tmp_path / "filled.docx"
    doc.save(out)

    values = read_osz(out)
    assert values["broj_plocice"] == "051-999"
    assert values["ime_objekta"] == "Jama Proba"
    assert values["x_htrs"] == "333001"
    assert values["duljina"] == "12,5"
    assert values["datum_istrazivanja"] == "10.05.2025."
    assert values["crtali"] == "Lovel Kukuljan, Ivana Dujmović"
    # Untouched control (grey placeholder) and untouched plain cell → None.
    assert values["y_htrs"] is None
    assert values["dubina"] is None


# ── filled-OSZ discovery in the intake tree ──────────────────────────
def _intake_settings(settings, tmp_path):
    import dataclasses

    return dataclasses.replace(
        settings,
        local_drive_root=tmp_path,
        archive_dirs={"intake_dir": "!Za digitalizirat",
                      "osz_prefill_dir": "OSZ prefill"},
    )


def test_locate_filled_osz_in_intake_dir(settings, tmp_path):
    from cave_dossier.osz.backfill import locate_filled_osz

    cave_dir = tmp_path / "!Za digitalizirat" / "Veprinac" / "SB_764_Piccolo_orig"
    cave_dir.mkdir(parents=True)
    (cave_dir / "opis terena.txt").write_text("x", encoding="utf-8")
    target = cave_dir / "SB_0764_OSZ.docx"
    target.write_bytes(b"docx")
    (cave_dir / "~$SB_0764_OSZ.docx").write_bytes(b"lock")  # Word lock file

    location = locate_filled_osz(_intake_settings(settings, tmp_path), 764)
    assert location.path == target


def test_locate_filled_osz_prefers_osz_named_docx(settings, tmp_path):
    from cave_dossier.osz.backfill import locate_filled_osz

    cave_dir = tmp_path / "!Za digitalizirat" / "SB_15_Volarova"
    cave_dir.mkdir(parents=True)
    (cave_dir / "biljeske.docx").write_bytes(b"x")
    target = cave_dir / "zapisnik Volarova.docx"
    target.write_bytes(b"x")
    location = locate_filled_osz(_intake_settings(settings, tmp_path), 15)
    assert location.path == target


def test_locate_filled_osz_ambiguous_reports_candidates(settings, tmp_path):
    from cave_dossier.osz.backfill import locate_filled_osz

    cave_dir = tmp_path / "!Za digitalizirat" / "SB_20_Blazici"
    cave_dir.mkdir(parents=True)
    (cave_dir / "prva.docx").write_bytes(b"x")
    (cave_dir / "druga.docx").write_bytes(b"x")
    location = locate_filled_osz(_intake_settings(settings, tmp_path), 20)
    assert location.path is None
    assert any("kandidata" in note for note in location.notes)


def test_locate_filled_osz_falls_back_to_prefill_dir(settings, tmp_path):
    from cave_dossier.osz.backfill import locate_filled_osz

    (tmp_path / "!Za digitalizirat").mkdir()
    prefill_dir = tmp_path / "OSZ prefill"
    prefill_dir.mkdir()
    target = prefill_dir / "SB_0764_OSZ.docx"
    target.write_bytes(b"docx")
    location = locate_filled_osz(_intake_settings(settings, tmp_path), 764)
    assert location.path == target
    assert any("prefill" in note for note in location.notes)


def test_locate_filled_osz_override_dir(settings, tmp_path):
    from cave_dossier.osz.backfill import locate_filled_osz

    cave_dir = tmp_path / "negdje" / "SB_99_Proba"
    cave_dir.mkdir(parents=True)
    target = cave_dir / "SB_99_OSZ.docx"
    target.write_bytes(b"docx")
    # Pointing at the parent...
    location = locate_filled_osz(_intake_settings(settings, tmp_path), 99,
                                 override_dir=tmp_path / "negdje")
    assert location.path == target
    # ...or straight at the cave's own dir both work.
    location = locate_filled_osz(_intake_settings(settings, tmp_path), 99,
                                 override_dir=cave_dir)
    assert location.path == target


# ── backfill rules over the mini SB fixture ──────────────────────────
def _cave(reader: SBReader, settings, serial: int):
    from cave_dossier.georef.worker import find_by_serial

    cave = find_by_serial(reader, settings, serial)
    assert cave is not None
    return cave


def test_backfill_fills_empty_queue_row(reader, settings):
    cave = _cave(reader, settings, 4)  # Đulin ponor mali: everything empty, "/" author
    osz = {
        "broj_plocice": "051-777",
        "ime_objekta": "Đulin ponor mali",
        "sinonimi": None,
        "duljina": "22",
        "dubina": "7,5",
        "datum_istrazivanja": "3.3.2024. i 4.4.2025.",
        "crtali": "Lovel Kukuljan i Ivana Dujmović",
    }
    result = build_backfill(cave, osz, settings)
    proposed = {p.column: p.proposed for p in result.proposals}
    assert proposed["Broj pločice"] == "051-777"
    assert proposed["Duljina"] == "22"
    assert proposed["Dubina"] == "7,5"
    assert proposed["Godina ili period istraživanja"] == "2024-2025"
    assert proposed["Autori nacrta ili izvor"] == "L.Kukuljan, I.Dujmović"
    assert result.differences == []


def test_backfill_new_name_moves_old_to_synonyms(reader, settings):
    cave = _cave(reader, settings, 1)  # Špilja Testovka, synonym "Testovka mala"
    osz = {"ime_objekta": "Jama Prekrasna", "sinonimi": "Treće ime"}
    result = build_backfill(cave, osz, settings)
    proposed = {p.column: p.proposed for p in result.proposals}
    assert proposed["Ime objekta"] == "Jama Prekrasna"
    # Old SB name + old synonyms + OSZ synonyms, new name excluded.
    assert proposed["Sinonimi"] == "Testovka mala, Špilja Testovka, Treće ime"


def test_backfill_full_match_proposes_nothing(reader, settings):
    cave = _cave(reader, settings, 1)  # plaque T-01, 40/12, 2015, Ana Anić
    osz = {
        "broj_plocice": "T-01",
        "ime_objekta": "Špilja Testovka",
        "sinonimi": "Testovka mala",
        "duljina": "40",
        "dubina": "12",
        "datum_istrazivanja": "15.07.2015.",
        "crtali": "Ana Anić",
    }
    result = build_backfill(cave, osz, settings)
    assert result.proposals == []
    assert result.differences == []
    assert len(result.matches) >= 6


def test_backfill_authors_merge_never_drop(reader, settings):
    cave = _cave(reader, settings, 2)  # Jama Čavlić: "Ivo Ivić; Ana Anić"
    osz = {"ime_objekta": "Jama Čavlić",
           "crtali": "Ivo Ivić, Luka Peloza"}
    result = build_backfill(cave, osz, settings)
    proposed = {p.column: p.proposed for p in result.proposals}
    # Luka is new → merged in as shorthand; Ana stays (note, not a drop).
    assert proposed["Autori nacrta ili izvor"] == "Ivo Ivić, Ana Anić, L.Peloza"
    assert any("Ana Anić" in note for note in result.notes)


def test_backfill_conflict_is_a_difference_not_a_proposal(reader, settings):
    cave = _cave(reader, settings, 1)  # Duljina 40 in SB
    osz = {"ime_objekta": "Špilja Testovka", "duljina": "55"}
    result = build_backfill(cave, osz, settings)
    assert not any(p.column == "Duljina" for p in result.proposals)
    assert any("Duljina" in d for d in result.differences)
