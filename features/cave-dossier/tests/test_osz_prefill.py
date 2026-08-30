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
        # Mimic the real finder's SB-wins contract for the fields SB supplies.
        f = self._finding.model_copy(deep=True)
        if sb_najblize_mjesto:
            f.najblize_mjesto, f.najblize_mjesto_source = sb_najblize_mjesto, "sb"
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
    # SB supplies these; the stubs' computed values must NOT override them.
    assert fields["kota_ulaza"].value == "500" and fields["kota_ulaza"].source == "sb"
    assert fields["najblize_mjesto"].value == "Testno Selo"
    assert fields["lokalitet"].value == "Testni kras"
    # 680 vs 500 exceeds the 10 m tolerance → flagged, not overridden, and
    # claiming a DMV source for a contradicted number would be false.
    assert "izvor_kote" not in fields
    assert any("Kota ulaza" in m for m in result.mismatches)
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
    # Every SB cell was filled → nothing to propose back.
    assert result.sb_updates == []
    assert outcome.sb_updates_path is None

    # The document really carries the values + the embedded excerpt.
    text = _docx_texts(outcome.docx_path)
    for expected in ("Špilja Testovka", "Istarska", "Testno Selo", "500", "450123"):
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


def test_prefill_unknown_serial_raises(settings, geo_stubs, run_dir):
    _template_guard()
    with pytest.raises(prefill.PrefillError):
        prefill.run_prefill(settings, 999)
