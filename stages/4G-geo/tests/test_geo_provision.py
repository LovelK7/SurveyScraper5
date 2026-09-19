"""geo/provision.py pure helpers (the INSPIRE AU parse verified live 2026-08-30)."""

from __future__ import annotations

import pytest

lxml_etree = pytest.importorskip("lxml.etree")

from cave_dossier.geo.provision import _au_level, _pos_list_coords

_XLINK = "http://www.w3.org/1999/xlink"


def _element(xml: str):
    return lxml_etree.fromstring(xml)


def test_au_level_prefers_title_then_href():
    el = _element(
        f'<l xmlns:xlink="{_XLINK}" xlink:title="4thOrder" '
        f'xlink:href="http://inspire.ec.europa.eu/codelist/AdministrativeHierarchyLevel/4thOrder"/>'
    )
    assert _au_level(el) == "4thOrder"
    el = _element(
        f'<l xmlns:xlink="{_XLINK}" '
        f'xlink:href="http://inspire.ec.europa.eu/codelist/AdministrativeHierarchyLevel/2ndOrder"/>'
    )
    assert _au_level(el) == "2ndOrder"
    assert _au_level(None) is None


def test_pos_list_swaps_northing_first_pairs():
    el = _element("<p>2516834.5 4999295.4 2516865.6 4999184.1 2516939.7 4998977.5</p>")
    coords = _pos_list_coords(el)
    # GML pairs are (N, E); shapely wants (E, N).
    assert coords[0] == (4999295.4, 2516834.5)
    assert len(coords) == 3


def test_pos_list_rejects_garbage():
    assert _pos_list_coords(None) == []
    assert _pos_list_coords(_element("<p>1 2</p>")) == []
    assert _pos_list_coords(_element("<p>a b c d e f</p>")) == []
