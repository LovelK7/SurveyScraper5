"""Shared fixtures: settings pointed at the synthetic mini workbook.

Mirrors config.yaml (including ``sb.field_columns``) so the tests exercise the
same column names the real tool resolves — regenerate the workbook itself with
``python tests/fixtures/make_mini_sb.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cave_dossier.core.config import Settings
from cave_dossier.sb.loader import SBReader

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "mini_sb.xlsx"

FIELD_COLUMNS = {
    "synonyms": "Sinonimi",
    "locality": "Lokalitet",
    "nearest_place": "Najbliže mjesto",
    "length_m": "Duljina",
    "depth_m": "Dubina",
    "entrance_elevation_m": "Z",
    "last_exploration_year": "Godina zadnjeg istraživanja",
    "note": "Napomena",
    "entrance_photo_flag": "Fotografija ulaza",
    "pollution_flag": "Zagađenost",
    "ice_cave_flag": "Ledenica",
    "supplementary_record_flag": "Dopunski zapisnik?",
    "nacrt_link": "Link Nacrt",
    "zapisnik_link": "Link Zapisnik",
}


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        sb_workbook_path=FIXTURE,
        sb_mode="SANDBOX",
        sb_sheet_name="Svi objekti",
        sb_object_name_column="Ime objekta",
        sb_archive_reference_column="Katastarski broj SUE",
        sb_filter_column="CroSpeleo unos",
        sb_marker_column="Katastarski broj RH",
        sb_plaque_column="Broj pločice",
        sb_drawing_authors_column="Autori nacrta",
        sb_exploration_period_column="Godina ili period istraživanja",
        sb_x_htrs_column="X HTRS",
        sb_y_htrs_column="Y HTRS",
        local_drive_root=None,
        sb_field_columns=dict(FIELD_COLUMNS),
    )


@pytest.fixture()
def reader(settings: Settings) -> SBReader:
    return SBReader(settings)
