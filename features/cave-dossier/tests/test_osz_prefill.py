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
        elevation_m=680, source_label="DMV (DGU)", tile_name="RH_ELEV_7.tif"
    )
    monkeypatch.setattr(
        prefill.locality_mod, "build_finder",
        lambda settings: StubLocalityFinder(locality_finding),
    )
    monkeypatch.setattr(
        prefill.elevation_mod, "build_finder",
        lambda settings: StubElevationFinder(elevation_finding),
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
    png_path.write_bytes(make_png(50, 50))
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
    assert "izvor_kote" not in fields  # SB's Z has no recorded source
    # Always computed (SB has no columns for them).
    assert fields["zupanija"].value == "Istarska"
    assert fields["grad_opcina"].value == "Lanišće"
    # Straight SB data.
    assert fields["katastarski_broj"].value == "001"
    assert fields["broj_plocice"].value == "T-01"
    assert fields["x_htrs"].value == "450123"
    assert fields["y_htrs"].value == "5023456"
    assert fields["duljina"].value == "40"
    assert fields["dubina"].value == "12"
    assert fields["datum_istrazivanja"].value == "2015"

    # 680 vs 500 exceeds the 10 m tolerance → flagged, not overridden.
    assert any("Kota ulaza" in m for m in result.mismatches)
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
    assert result.fields["izvor_kote"].value == "DMV (DGU)"
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


def test_prefill_without_coordinates_degrades(settings, geo_stubs, run_dir, monkeypatch):
    _template_guard()
    monkeypatch.setattr(prefill.georef, "delivery_paths", lambda s, serial: None)
    outcome = prefill.run_prefill(settings, 4)  # the queue row: no coords, no Z
    result = outcome.result

    assert result.cave_name == "Đulin ponor mali"
    assert result.karta_status == "missing"
    assert "zupanija" not in result.fields
    assert "kota_ulaza" not in result.fields
    assert any("koordinate" in note.lower() for note in result.notes)
    assert outcome.docx_path.exists()  # the document is still produced


def test_prefill_unknown_serial_raises(settings, geo_stubs, run_dir):
    _template_guard()
    with pytest.raises(prefill.PrefillError):
        prefill.run_prefill(settings, 999)
