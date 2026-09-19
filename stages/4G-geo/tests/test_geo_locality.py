"""geo/: RGI response parsing, vrsta screening, and the SB-wins synthesizer.

No network, no geodata files: the WFS parse runs on a fixture GeoJSON dict,
the finder gets duck-typed stubs for AdminLookup / RGIClient. Fuzzy matching
degrades to difflib when rapidfuzz is absent — the cases here use exact or
clearly-distant names so both scorers agree.
"""

from __future__ import annotations

import pytest

from cave_dossier.geo.locality import (
    LocalityFinder,
    is_topographic_locality_feature,
)
from cave_dossier.geo.models import AdminPlacement, NamedPlaceHit
from cave_dossier.geo.rgi_client import RGIClient, RGIClientConfig


# ── stubs ────────────────────────────────────────────────────────────
class StubAdmin:
    def __init__(self, naselje="Testno Selo", opcina="Lanišće", zupanija="Istarska",
                 nearby=("Testno Selo", "Gornje Testno"), available=True):
        self._placement = AdminPlacement(
            naselje=naselje, opcina=opcina, zupanija=zupanija,
            source="shapefile" if available else "unavailable",
        )
        self._nearby = list(nearby)

    def lookup(self, x, y):
        return self._placement

    def nearby_naselje_names(self, x, y, radius_m):
        return list(self._nearby)


class StubRGI:
    def __init__(self, hits=()):
        self._hits = sorted(
            hits, key=lambda h: h.distance_m if h.distance_m is not None else 1e9
        )
        self.used_offline_fallback = False

    def query_nearby(self, x, y):
        return list(self._hits)


def hit(name, vrsta, distance):
    return NamedPlaceHit(identifikator="x", geografskoime=name,
                         vrstaobiljezja=vrsta, distance_m=distance)


# ── vrsta screening ──────────────────────────────────────────────────
def test_vrsta_screening():
    assert is_topographic_locality_feature("vrh")
    assert is_topographic_locality_feature(None)  # conservative: keep unknowns
    assert not is_topographic_locality_feature("kapelica")   # object 525's lesson
    assert not is_topographic_locality_feature("naselje")
    assert not is_topographic_locality_feature("zaselak")    # hamlets are settlements
    assert not is_topographic_locality_feature("autocesta")
    # Diacritic folding: 'parkiralište' matches the folded 'parkiraliste' stem.
    assert not is_topographic_locality_feature("parkiralište")


def test_locate_sb_hamlet_recognised_when_admin_unavailable():
    """With DGU boundaries unavailable, SB's hamlet still validates via an
    RGI 'zaselak' point (silent keep) — the geo-admin override only applies
    when there IS an admin answer."""
    finder = LocalityFinder(
        rgi_client=StubRGI([hit("Pavletići", "zaselak", 400.0)]),
        admin_lookup=StubAdmin(naselje=None, opcina=None, zupanija=None,
                               nearby=(), available=False),
    )
    finding = finder.locate(0.0, 0.0, sb_najblize_mjesto="Pavletići")
    assert finding.najblize_mjesto == "Pavletići"
    assert finding.najblize_mjesto_source == "sb"
    assert not any("Pavletići" in note for note in finding.notes)
    # ...and a zaselak never fills an empty Lokalitet.
    finding = finder.locate(0.0, 0.0)
    assert finding.lokalitet is None


# ── RGI parsing (pure, no network) ───────────────────────────────────
def test_rgi_parse_response_distances_sorted():
    client = RGIClient(RGIClientConfig())
    data = {
        "features": [
            {"properties": {"identifikator": "2", "geografskoime": "Daleki vrh",
                            "vrstaobiljezja": "vrh"},
             "geometry": {"coordinates": [1000.0, 0.0]}},
            {"properties": {"identifikator": "1", "geografskoime": "Bliski dolac",
                            "vrstaobiljezja": "dolac"},
             "geometry": {"coordinates": [30.0, 40.0]}},
        ]
    }
    hits = client._parse_response(data, 0.0, 0.0)
    hits.sort(key=lambda h: h.distance_m)
    assert [h.geografskoime for h in hits] == ["Bliski dolac", "Daleki vrh"]
    assert hits[0].distance_m == pytest.approx(50.0)


def test_rgi_offline_without_gpkg_returns_empty(tmp_path):
    client = RGIClient(RGIClientConfig(offline_dir=tmp_path))
    assert client._query_offline(0.0, 0.0) == []


def test_rgi_forced_offline_never_touches_wfs(tmp_path, monkeypatch):
    client = RGIClient(RGIClientConfig(offline_dir=tmp_path, offline=True))

    def boom(*args, **kwargs):
        raise AssertionError("WFS must not be called in offline mode")

    monkeypatch.setattr(client, "_query_wfs", boom)
    assert client.query_nearby(0.0, 0.0) == []  # empty gpkg dir → just empty


# ── synthesizer: empty SB row gets filled ────────────────────────────
def test_locate_fills_empty_sb_row():
    finder = LocalityFinder(
        rgi_client=StubRGI([
            hit("Autobusna postaja", "postaja", 100.0),   # screened out
            hit("Veliki dolac", "dolac", 300.0),          # the topographic pick
        ]),
        admin_lookup=StubAdmin(),
    )
    finding = finder.locate(450000.0, 5020000.0)
    assert finding.zupanija == "Istarska"
    assert finding.grad_opcina == "Lanišće"
    assert finding.najblize_mjesto == "Testno Selo"
    assert finding.najblize_mjesto_source == "geo-admin"
    assert finding.lokalitet == "Veliki dolac"
    assert finding.lokalitet_source == "geo-rgi"


def test_locate_lokalitet_respects_append_radius():
    finder = LocalityFinder(
        rgi_client=StubRGI([hit("Predaleki vrh", "vrh", 2500.0)]),  # > 1500 m
        admin_lookup=StubAdmin(),
    )
    finding = finder.locate(0.0, 0.0)
    assert finding.lokalitet is None


# ── synthesizer: SB wins ─────────────────────────────────────────────
def test_locate_keeps_matching_sb_values_silently():
    finder = LocalityFinder(rgi_client=StubRGI(), admin_lookup=StubAdmin())
    finding = finder.locate(
        0.0, 0.0, sb_lokalitet="Testni kras", sb_najblize_mjesto="Testno Selo"
    )
    # Najbliže mjesto is geo-admin's answer; SB agreeing means no note.
    assert finding.najblize_mjesto == "Testno Selo"
    assert finding.najblize_mjesto_source == "geo-admin"
    assert finding.lokalitet == "Testni kras"
    assert finding.lokalitet_source == "sb"
    assert finding.notes == []


def test_locate_geo_admin_overrides_sb_nearest_place():
    """Geo-admin WINS Najbliže mjesto (user, 2026-09-01, SB 1220): the DGU
    naselje of the entrance point replaces a differing hand-entered value,
    with a note naming both."""
    finder = LocalityFinder(rgi_client=StubRGI(), admin_lookup=StubAdmin())
    finding = finder.locate(0.0, 0.0, sb_najblize_mjesto="Mali Platak")
    assert finding.najblize_mjesto == "Testno Selo"  # the containing naselje
    assert finding.najblize_mjesto_source == "geo-admin"
    assert any("Mali Platak" in note and "Testno Selo" in note
               for note in finding.notes)


def test_locate_flags_settlement_inside_sb_lokalitet():
    finder = LocalityFinder(rgi_client=StubRGI(), admin_lookup=StubAdmin())
    finding = finder.locate(0.0, 0.0, sb_lokalitet="Kuk, Testno Selo")
    assert finding.lokalitet == "Kuk, Testno Selo"  # kept verbatim
    assert any("Testno Selo" in note for note in finding.notes)


def test_locate_everything_unavailable_is_quietly_empty():
    finder = LocalityFinder(
        rgi_client=StubRGI(),
        admin_lookup=StubAdmin(naselje=None, opcina=None, zupanija=None,
                               nearby=(), available=False),
    )
    finding = finder.locate(0.0, 0.0)
    assert finding.zupanija is None
    assert finding.najblize_mjesto is None
    assert finding.lokalitet is None
    assert not finding.admin_available
    assert any("fetch-data" in note for note in finding.notes)
