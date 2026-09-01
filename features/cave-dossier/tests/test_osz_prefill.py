"""osz/prefill.py orchestration over the mini SB fixture.

Geo finders and the karta flow are monkeypatched — this file tests the
precedence rule (SB wins + mismatch flag), the review-CSV-only-for-empty-
cells rule, the embed path, and the no-coordinates degradation. Needs lxml
(the [osz] extra) because the writer fills the real committed template.
"""

from __future__ import annotations

import csv
import dataclasses
import zipfile

import pytest

pytest.importorskip("lxml")

from cave_dossier.geo.models import ElevationFinding, LocalityFinding
from cave_dossier.georef.worker import DeliveryPaths
from cave_dossier.osz import prefill
from cave_dossier.osz.writer import W

from test_osz_writer import TEMPLATE, make_png


class StubLocalityFinder:
    def __init__(self, finding: LocalityFinding):
        self._finding = finding

    def locate(self, x, y, sb_lokalitet=None, sb_najblize_mjesto=None):
        # Mimic the real finder's contract: Lokalitet is SB-wins, but
        # Najbliže mjesto is geo-admin-wins (user, 2026-09-01).
        f = self._finding.model_copy(deep=True)
        if sb_lokalitet:
            f.lokalitet, f.lokalitet_source = sb_lokalitet, "sb"
        return f


class StubElevationFinder:
    def __init__(self, finding: ElevationFinding):
        self._finding = finding

    def kota(self, x, y):
        return self._finding.model_copy(deep=True)


@pytest.fixture()
def geo_stubs(monkeypatch):
    locality_finding = LocalityFinding(
        zupanija="Istarska",
        grad_opcina="Lanišće",
        najblize_mjesto="Računato Selo",
        najblize_mjesto_source="geo-admin",
        lokalitet="Računati dolac",
        lokalitet_source="geo-rgi",
    )
    elevation_finding = ElevationFinding(
        elevation_m=680, source_label="DMV", tile_name="RH_ELEV_7.tif"
    )
    monkeypatch.setattr(
        prefill.locality_mod, "build_finder",
        lambda settings, **kwargs: StubLocalityFinder(locality_finding),
    )
    monkeypatch.setattr(
        prefill.elevation_mod, "build_finder",
        lambda settings, **kwargs: StubElevationFinder(elevation_finding),
    )


@pytest.fixture()
def run_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(prefill, "RUNS_DIR", tmp_path / "runs" / "osz")
    return tmp_path


@pytest.fixture()
def collected_karta(tmp_path, monkeypatch):
    """Pretend SB_0001.png is already delivered and current."""
    png_path = tmp_path / "excerpts" / "SB_0001.png"
    png_path.parent.mkdir(parents=True)
    png_path.write_bytes(make_png(50, 40))  # current 5:4 landscape format
    paths = DeliveryPaths(png=png_path, records_csv=png_path.parent / "!georef_zapisi.csv")
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: paths)
    monkeypatch.setattr(prefill.georef, "refresh_reason", lambda s, serial, name: None)
    return png_path


def _template_guard():
    if not TEMPLATE.exists():
        pytest.skip("v10 template not present")


def _docx_texts(path) -> str:
    from lxml import etree

    with zipfile.ZipFile(path) as zin:
        root = etree.fromstring(zin.read("word/document.xml"))
    return " ".join(t.text or "" for t in root.iter(W + "t"))


def test_prefill_full_row_sb_wins(settings, geo_stubs, run_dir, collected_karta):
    _template_guard()
    outcome = prefill.run_prefill(settings, 1)
    result = outcome.result

    assert result.cave_name == "Špilja Testovka"
    assert result.karta_status == "reused"

    fields = result.fields
    # SB supplies these; the stubs' computed values must NOT override them —
    # EXCEPT Najbliže mjesto, where geo-admin wins (user, 2026-09-01).
    assert fields["kota_ulaza"].value == "500" and fields["kota_ulaza"].source == "sb"
    assert fields["najblize_mjesto"].value == "Računato Selo"
    assert fields["najblize_mjesto"].source == "geo-admin"
    assert fields["lokalitet"].value == "Testni kras"
    # 680 vs 500 exceeds the 10 m tolerance → flagged, not overridden; a
    # hand-entered Z that contradicts the grid is most likely GPS-measured
    # (user, 2026-09-01, SB 1255) — assumed, and overridable by an old OSZ.
    assert fields["izvor_kote"].value == "GPS"
    assert fields["izvor_kote"].source == "default"
    assert any("Kota ulaza" in m for m in result.mismatches)
    # The differing SB Najbliže mjesto becomes a CORRECTION proposal.
    corrections = [u for u in result.sb_updates if "ispravak" in u.note]
    assert len(corrections) == 1
    assert corrections[0].value == "Računato Selo"
    assert "Testno Selo" in corrections[0].note
    # Always computed (SB has no columns for them).
    assert fields["zupanija"].value == "Istarska"
    assert fields["grad_opcina"].value == "Lanišće"
    # Straight SB data.
    assert fields["broj_plocice"].value == "T-01"
    assert fields["x_htrs"].value == "450123"
    assert fields["y_htrs"].value == "5023456"
    # Not LiDAR-derived → Izvor koordinata defaults to GPS.
    assert fields["izvor_koordinata"].value == "GPS"
    assert fields["izvor_koordinata"].source == "default"
    # NEVER prefilled (user, 2026-08-30): the archivist's manual final step
    # and the fields other processes supply.
    for never in ("katastarski_broj", "duljina", "dubina", "datum_istrazivanja"):
        assert never not in fields, never
    # Every SB cell was filled → the only proposal is the correction above.
    assert len(result.sb_updates) == 1
    assert outcome.sb_updates_path is not None

    # The document really carries the values + the embedded excerpt.
    text = _docx_texts(outcome.docx_path)
    for expected in ("Špilja Testovka", "Istarska", "Računato Selo", "500", "450123"):
        assert expected in text
    with zipfile.ZipFile(outcome.docx_path) as zin:
        assert "word/media/SB_0001.png" in zin.namelist()

    # No Drive root in test settings → local only, with a note saying so.
    assert outcome.delivered_path is None
    assert outcome.sidecar_path.exists()


def test_prefill_empty_cells_become_sb_updates(settings, geo_stubs, run_dir, monkeypatch):
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    # Point the Z / locality / nearest-place lookups at columns the fixture
    # row does not fill, simulating a row the finders can complete.
    empty_cols = {**settings.sb_field_columns,
                  "entrance_elevation_m": "NEMA_Z",
                  "locality": "NEMA_LOK",
                  "nearest_place": "NEMA_NM"}
    settings = dataclasses.replace(settings, sb_field_columns=empty_cols)

    outcome = prefill.run_prefill(settings, 1)
    result = outcome.result

    assert result.fields["kota_ulaza"].value == "680"
    assert result.fields["kota_ulaza"].source == "dmv-dgu"
    assert result.fields["izvor_kote"].value == "DMV"
    assert result.fields["najblize_mjesto"].source == "geo-admin"
    assert result.fields["lokalitet"].source == "geo-rgi"
    assert result.mismatches == []

    assert len(result.sb_updates) == 3  # Z + Najbliže mjesto + Lokalitet
    proposed = {u.column: u.value for u in result.sb_updates}
    assert proposed == {
        "NEMA_Z": "680",
        "NEMA_NM": "Računato Selo",
        "NEMA_LOK": "Računati dolac",
    }

    assert outcome.sb_updates_path is not None
    with outcome.sb_updates_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == list(prefill.SB_UPDATES_CSV_COLUMNS)
    assert len(rows) == 4
    assert all(row[0] == "1" for row in rows[1:])


def test_prefill_sb_kota_with_agreeing_grid_gets_dmv(settings, geo_stubs, run_dir, monkeypatch):
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    # Widen the tolerance so the stub's 680 "agrees" with SB's 500 —
    # an agreeing (or absent) grid means the SB kota is DMV-sourced too.
    settings = dataclasses.replace(settings, geo_elevation_tolerance_m=500.0)
    result = prefill.run_prefill(settings, 1).result
    assert result.fields["kota_ulaza"].value == "500"
    assert result.fields["izvor_kote"].value == "DMV"
    assert result.mismatches == []


def test_prefill_without_coordinates_degrades(settings, geo_stubs, run_dir, monkeypatch):
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    outcome = prefill.run_prefill(settings, 4)  # the queue row: no coords, no Z
    result = outcome.result

    assert result.cave_name == "Đulin ponor mali"
    assert result.karta_status == "missing"
    assert "zupanija" not in result.fields
    assert "kota_ulaza" not in result.fields
    assert "izvor_koordinata" not in result.fields  # no coords → no GPS guess
    assert any("koordinate" in note.lower() for note in result.notes)
    assert outcome.docx_path.exists()  # the document is still produced


def test_is_lidar_derived_matches_name_and_synonyms(settings):
    from cave_dossier.osz.prefill import _is_lidar_derived
    from cave_dossier.sb.loader import CaveRow

    def row(name, synonyms=None):
        return CaveRow(row_number=1, object_name=name, sue_number=None,
                       values={"Sinonimi": synonyms})

    assert _is_lidar_derived(row("LiDAR Kristal 31"), settings)
    assert _is_lidar_derived(row("Jama X", synonyms="Lidarka mala; drugo"), settings)
    assert _is_lidar_derived(row("LIDAR 7"), settings)
    assert not _is_lidar_derived(row("Špilja Testovka"), settings)
    assert not _is_lidar_derived(row("Jama X", synonyms="Kristalka"), settings)


def test_prefill_lidar_flag_sets_both_sources(settings, geo_stubs, run_dir, monkeypatch):
    """A LiDAR-derived cave (user, 2026-08-30): Izvor koordinata AND Izvor
    kote ulaza are known in advance — 'LiDAR' — even when the DMV grid
    disagrees with the SB Z (the warning stays advisory)."""
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    monkeypatch.setattr(prefill, "_is_lidar_derived", lambda cave, s: True)

    result = prefill.run_prefill(settings, 1).result  # SB Z=500, stub DMV=680
    assert result.fields["izvor_koordinata"].value == "LiDAR"
    assert result.fields["kota_ulaza"].value == "500"
    assert result.fields["izvor_kote"].value == "LiDAR"
    assert any("LiDAR" in m for m in result.mismatches)  # advisory, not blank


def test_prefill_pristup_rule_fills_the_narrative(settings, geo_stubs, run_dir, monkeypatch):
    """Resolved Veprinac + Ćićarija triggers the shared-approach text into
    the Položaj i pristup control, <w:br/>-joined (single paragraph)."""
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    monkeypatch.setattr(
        prefill.pristupi, "find_pristup",
        lambda nm, lok, path=None: ("Položaj:\nPristup:\nZajednički pristup."
                                    if (nm, lok) == ("Računato Selo", "Testni kras") else None),
    )
    outcome = prefill.run_prefill(settings, 1)  # SB row: Testno Selo / Testni kras
    fv = outcome.result.fields["polozaj_pristup"]
    assert fv.source == "pristup-template"
    assert _docx_texts(outcome.docx_path).count("Zajednički pristup.") == 1

    from lxml import etree

    with zipfile.ZipFile(outcome.docx_path) as zin:
        root = etree.fromstring(zin.read("word/document.xml"))
    tbl = root.find(W + "body").findall(W + "tbl")[3]
    tr = tbl.findall(W + "tr")[0]
    sdt = [n for n in tr if n.tag in (W + "tc", W + "sdt")][1]
    holder = sdt.find(W + "sdtContent").find(W + "tc")
    assert len(holder.findall(W + "p")) == 1  # the single-paragraph invariant
    assert len(holder.findall(".//" + W + "br")) == 2  # three lines


def test_prefill_no_pristup_rule_leaves_placeholder(settings, geo_stubs, run_dir, monkeypatch):
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    outcome = prefill.run_prefill(settings, 1)  # Testno Selo matches no real rule
    assert "polozaj_pristup" not in outcome.result.fields


def test_prefill_offline_reuses_karta_and_skips_flow(settings, geo_stubs, run_dir,
                                                    collected_karta, monkeypatch):
    _template_guard()

    def boom(*args, **kwargs):
        raise AssertionError("offline mode must not run the georef flow")

    monkeypatch.setattr(prefill.georef, "run_for_cave", boom)
    outcome = prefill.run_prefill(settings, 1, offline=True)
    assert outcome.result.karta_status == "reused"
    with zipfile.ZipFile(outcome.docx_path) as zin:
        assert "word/media/SB_0001.png" in zin.namelist()


def test_prefill_offline_without_karta_degrades(settings, geo_stubs, run_dir, monkeypatch):
    _template_guard()
    from cave_dossier.georef.worker import DeliveryPaths as DP

    missing = DP(png=run_dir / "nema.png", records_csv=run_dir / "nema.csv")
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: missing)
    monkeypatch.setattr(
        prefill.georef, "run_for_cave",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    outcome = prefill.run_prefill(settings, 1, offline=True)
    assert outcome.result.karta_status == "missing"
    assert any("offline" in note for note in outcome.result.notes)
    assert outcome.docx_path.exists()


def test_intake_folder_name_components_and_sanitization(settings):
    from cave_dossier.osz.prefill import _intake_folder_name
    from cave_dossier.sb.loader import CaveRow

    cave = CaveRow(row_number=1, object_name="Špilja Testovka", sue_number="001",
                   values={"Sinonimi": "Testovka mala; druga",
                           "Autori nacrta ili izvor": "Ana Anić"})
    name = _intake_folder_name(cave, 1, settings)
    assert name == "SB_1_Špilja Testovka_Testovka mala, druga_Ana Anić"

    # Illegal filesystem characters are stripped, empties skipped.
    cave = CaveRow(row_number=1, object_name='Jama "X/Y"?', sue_number=None,
                   values={})
    assert _intake_folder_name(cave, 42, settings) == "SB_42_Jama X Y"


def test_find_intake_folder_matches_nested_and_padded(tmp_path):
    from cave_dossier.osz.prefill import _find_intake_folder

    (tmp_path / "!!Container" / "SB_0001_stara mapa").mkdir(parents=True)
    (tmp_path / "SB_12_druga").mkdir()
    found = _find_intake_folder(tmp_path, 1)
    assert found is not None and found.name == "SB_0001_stara mapa"
    assert _find_intake_folder(tmp_path, 2) is None       # SB_12 must not match 2
    assert _find_intake_folder(tmp_path, 12).name == "SB_12_druga"


def test_prefill_delivers_into_intake_folder(settings, geo_stubs, run_dir,
                                             collected_karta, tmp_path):
    _template_guard()
    intake_root = tmp_path / "drive" / "!Za digitalizirat"
    intake_root.mkdir(parents=True)
    settings = dataclasses.replace(
        settings,
        local_drive_root=tmp_path / "drive",
        archive_dirs={"intake_dir": "!Za digitalizirat"},
    )

    # First run: no folder for cave 1 → created with the identity components.
    outcome = prefill.run_prefill(settings, 1)
    assert outcome.delivered_path is not None
    folder = outcome.delivered_path.parent
    assert folder.parent == intake_root
    assert folder.name.startswith("SB_1_Špilja Testovka")
    assert outcome.delivered_path.name == "SB_0001_OSZ.docx"
    assert any("Stvorena intake mapa" in note for note in outcome.result.notes)

    # Second run: the existing folder is reused, no sibling appears.
    outcome2 = prefill.run_prefill(settings, 1)
    assert outcome2.delivered_path.parent == folder
    assert len([d for d in intake_root.iterdir() if d.is_dir()]) == 1


# ── migration of an older OSZ found in the intake leaf ───────────────
def _make_old_osz(path):
    """A 'previously filled' v10 document with human content the fresh
    prefill cannot know."""
    from cave_dossier.osz.writer import OszDocument

    doc = OszDocument(TEMPLATE)
    doc.fill_plain(1, 0, 1, "Špilja Testovka")                # same name as SB
    doc.fill_sdt_cell(4, 7, 0, ["Prvi red opisa.", "Drugi red opisa."])  # opis
    doc.fill_sdt_inline(6, 4, 0, ["Istraženo davne 1987."])   # povijest
    doc.fill_plain(6, 14, 1, "Ana Anić")                      # crtali
    doc.fill_plain(4, 3, 0, "40")                             # duljina
    doc.fill_plain(6, 8, 1, "10.05.2015.")                    # datum
    doc.tick({"špilja"})
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)


@pytest.fixture()
def intake_settings(settings, tmp_path):
    (tmp_path / "drive" / "!Za digitalizirat").mkdir(parents=True)
    return dataclasses.replace(
        settings,
        local_drive_root=tmp_path / "drive",
        archive_dirs={"intake_dir": "!Za digitalizirat"},
    )


def test_prefill_migrates_old_osz(intake_settings, geo_stubs, run_dir, monkeypatch):
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    intake_root = intake_settings.local_drive_root / "!Za digitalizirat"
    old_path = intake_root / "SB_1_Špilja Testovka_stara" / "Zapisnik_stari.docx"
    _make_old_osz(old_path)

    outcome = prefill.run_prefill(intake_settings, 1)
    result = outcome.result

    assert result.migrated_from == "Zapisnik_stari.docx"
    # Human content carried into fields the fresh prefill leaves empty.
    assert result.fields["opis"].source == "stari-osz"
    assert "Prvi red opisa." in result.fields["opis"].value
    assert result.fields["povijest"].value == "Istraženo davne 1987."
    assert result.fields["crtali"].value == "Ana Anić"
    assert result.fields["duljina"].value == "40"
    assert result.fields["datum_istrazivanja"].value == "10.05.2015."
    assert result.ticked_checkboxes == ["špilja"]
    # SB still wins identity fields.
    assert result.fields["ime_objekta"].value == "Špilja Testovka"

    # Delivered as the canonical name; the old file became a _stari backup.
    assert outcome.delivered_path.name == "SB_0001_OSZ.docx"
    folder = old_path.parent
    backups = list(folder.glob("Zapisnik_stari_stari_*.docx"))
    assert len(backups) == 1
    assert not old_path.exists()
    assert (run_dir / "runs" / "osz" / "0001" / "stari_osz.json").exists()

    # The new document really carries the content, ticks included.
    from cave_dossier.osz.reader import read_osz_content

    content = read_osz_content(outcome.delivered_path)
    assert content.fields["opis"] == "Prvi red opisa.\nDrugi red opisa."
    assert content.fields["povijest"] == "Istraženo davne 1987."
    assert "špilja" in content.ticked


def test_prefill_migration_is_idempotent(intake_settings, geo_stubs, run_dir, monkeypatch):
    """Re-running on an already-migrated document must not grow backups."""
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    intake_root = intake_settings.local_drive_root / "!Za digitalizirat"
    old_path = intake_root / "SB_1_Špilja Testovka_stara" / "Zapisnik_stari.docx"
    _make_old_osz(old_path)

    first = prefill.run_prefill(intake_settings, 1)
    second = prefill.run_prefill(intake_settings, 1)

    folder = old_path.parent
    assert len(list(folder.glob("*_stari_*.docx"))) == 1  # only the first backup
    assert second.delivered_path == first.delivered_path
    assert any("ostavljen netaknut" in note for note in second.result.notes)


def test_prefill_migration_recorded_source_beats_default(intake_settings, geo_stubs,
                                                         run_dir, monkeypatch):
    """The GPS default and inferred source labels yield to what the old
    OSZ actually recorded (the 764/811 live lesson, 2026-08-31)."""
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    from cave_dossier.osz.writer import OszDocument

    intake_root = intake_settings.local_drive_root / "!Za digitalizirat"
    old_path = intake_root / "SB_1_x" / "Zapisnik ispunjen.docx"
    old_path.parent.mkdir(parents=True)
    doc = OszDocument(TEMPLATE)
    doc.fill_plain(2, 5, 4, "LIDAR")   # izvor_koordinata, recorded
    doc.fill_plain(2, 4, 4, "HOK")     # izvor_kote, recorded
    doc.save(old_path)

    result = prefill.run_prefill(intake_settings, 1).result
    assert result.fields["izvor_koordinata"].value == "LIDAR"
    assert result.fields["izvor_koordinata"].source == "stari-osz"
    assert result.fields["izvor_kote"].value == "HOK"
    assert result.fields["izvor_kote"].source == "stari-osz"


def test_merge_locality_sb_first_dedup():
    from cave_dossier.osz.prefill import merge_locality

    assert merge_locality("Ćićarija", "Ćićarija, Mela sapca, PP Učka") == \
        "Ćićarija, Mela sapca, PP Učka"
    assert merge_locality("Učka", "Ćićarija, Mela sapca") == "Učka, Ćićarija, Mela sapca"
    assert merge_locality("Ćićarija", "CICARIJA") == "Ćićarija"  # fold-dedup


def test_prefill_migration_merges_localities(intake_settings, geo_stubs, run_dir, monkeypatch):
    """SB holds ONE locality by convention; the old OSZ's extra localities
    must survive into the new document (user, 2026-09-01, SB 1252)."""
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    from cave_dossier.osz.writer import OszDocument

    intake_root = intake_settings.local_drive_root / "!Za digitalizirat"
    old_path = intake_root / "SB_1_x" / "Zapisnik_star.docx"
    old_path.parent.mkdir(parents=True)
    doc = OszDocument(TEMPLATE)
    doc.fill_plain(1, 6, 1, "Testni kras, Mela sapca, PP Učka")  # lokalitet
    doc.save(old_path)

    result = prefill.run_prefill(intake_settings, 1).result  # SB: "Testni kras"
    assert result.fields["lokalitet"].value == "Testni kras, Mela sapca, PP Učka"
    assert result.fields["lokalitet"].source == "sb+stari-osz"


def test_prefill_migration_conflict_keeps_new_value(intake_settings, geo_stubs,
                                                    run_dir, monkeypatch):
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    from cave_dossier.osz.writer import OszDocument

    intake_root = intake_settings.local_drive_root / "!Za digitalizirat"
    old_path = intake_root / "SB_1_x" / "Zapisnik_stari.docx"
    old_path.parent.mkdir(parents=True)
    doc = OszDocument(TEMPLATE)
    doc.fill_plain(1, 0, 1, "Sasvim drugo ime")  # conflicts with SB's name
    doc.save(old_path)

    result = prefill.run_prefill(intake_settings, 1).result
    assert result.fields["ime_objekta"].value == "Špilja Testovka"  # SB wins
    assert any("Sasvim drugo ime" in note and "zadržana nova" in note
               for note in result.notes)


def test_prefill_unknown_serial_raises(settings, geo_stubs, run_dir):
    _template_guard()
    with pytest.raises(prefill.PrefillError):
        prefill.run_prefill(settings, 999)
