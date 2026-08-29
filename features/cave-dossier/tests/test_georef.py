"""Part 2.1c unit tests — everything that runs WITHOUT a browser: serial
lookup, input building, delivery naming, the !georef_zapisi.csv upsert, and
the selectors-file parser. The Playwright flow itself is exercised live
(one cave per attended run), never from tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from cave_dossier.core.config import Settings
from cave_dossier.georef import worker
from cave_dossier.georef.models import GeorefInput
from cave_dossier.georef.selectors import load_selectors
from cave_dossier.sb.loader import SBReader


# ── Serial lookup + input building (synthetic mini workbook) ───────


def test_find_by_serial_resolves_the_row(reader: SBReader, settings: Settings) -> None:
    cave = worker.find_by_serial(reader, settings, 1)
    assert cave is not None
    assert cave.object_name == "Špilja Testovka"


def test_find_by_serial_unknown_number(reader: SBReader, settings: Settings) -> None:
    assert worker.find_by_serial(reader, settings, 99) is None


def test_build_input_reads_sb_coordinates(reader: SBReader, settings: Settings) -> None:
    cave = worker.find_by_serial(reader, settings, 1)
    georef_input = worker.build_input(cave, settings)
    assert georef_input.object_id == "1"
    assert georef_input.object_name == "Špilja Testovka"
    assert georef_input.x_htrs == 450123.0
    assert georef_input.y_htrs == 5023456.0
    assert georef_input.source == "sb_htrs"
    assert georef_input.notes == []


def test_build_input_flags_missing_coordinates(reader: SBReader, settings: Settings) -> None:
    cave = worker.find_by_serial(reader, settings, 4)  # queue row, no coords
    georef_input = worker.build_input(cave, settings)
    assert georef_input.x_htrs is None
    assert georef_input.source is None
    assert georef_input.notes


def test_coordinate_variants_round_to_integer_metres() -> None:
    # The Georef form silently rejects decimals (crospeleo, SUE 960 lesson).
    assert GeorefInput.coordinate_variants(361433.72) == ["361434"]
    assert GeorefInput.coordinate_variants(None) == []


# ── Delivery naming ────────────────────────────────────────────────


def test_delivery_paths_use_padded_serial(settings: Settings, tmp_path: Path) -> None:
    configured = dataclasses.replace(
        settings,
        local_drive_root=tmp_path,
        archive_dirs={"map_excerpts_dir": "!!Isječci karte"},
    )
    paths = worker.delivery_paths(configured, 17)
    assert paths.png == tmp_path / "!!Isječci karte" / "0017.png"
    assert paths.records_csv == tmp_path / "!!Isječci karte" / "!georef_zapisi.csv"


def test_delivery_paths_need_drive_root(settings: Settings) -> None:
    assert worker.delivery_paths(settings, 17) is None  # fixture has no drive root


# ── !georef_zapisi.csv upsert ───────────────────────────────────────


def test_upsert_record_creates_then_updates(tmp_path: Path) -> None:
    csv_path = tmp_path / "!georef_zapisi.csv"
    worker.upsert_record(csv_path, "0002", "Jama Čavlić", "zapis; star", "2026-08-29")
    worker.upsert_record(csv_path, "0001", "Špilja Testovka", "zapis; jedan", "2026-08-29")
    # Re-running cave 0002 must REPLACE its row, not append a duplicate.
    worker.upsert_record(csv_path, "0002", "Jama Čavlić", "zapis;\nnov", "2026-08-30")

    raw = csv_path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM, as Excel expects of a .csv
    assert b"\r\n" in raw

    lines = csv_path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0].split(",")[:2] == ["Redni broj", "Ime objekta"]
    assert len(lines) == 3  # header + two caves
    assert lines[1].startswith("0001")  # sorted by padded serial
    assert "zapis; nov" in lines[2]  # updated + flattened to one line
    assert "star" not in lines[2]


# ── Excerpt size budget ────────────────────────────────────────────


def test_save_png_under_limit_downscales_to_fit(tmp_path: Path) -> None:
    # Random noise defeats PNG compression, forcing the downscale loop.
    pytest.importorskip("PIL")
    pytest.importorskip("playwright")  # flows.py imports it at module scope
    import numpy
    from PIL import Image

    from cave_dossier.georef.flows import save_png_under_limit

    noise = numpy.random.default_rng(7).integers(0, 256, (1400, 1400, 3), dtype="uint8")
    image = Image.fromarray(noise, "RGB")
    target = tmp_path / "excerpt.png"
    save_png_under_limit(image, target, max_bytes=1_000_000)
    assert target.stat().st_size <= 1_000_000
    assert min(Image.open(target).size) >= 512  # floor respected


# ── Selectors parser ───────────────────────────────────────────────


def test_load_selectors_keeps_css_ids_and_strips_comments(tmp_path: Path) -> None:
    path = tmp_path / "selectors.yaml"
    path.write_text(
        "# a comment line\n"
        "georef_save_button: \"#uncertCoordSave\"\n"
        "georef_record_value: \"\"  # cleared — see log\n"
        "georef_point_tool: \"text=Točka\"\n",
        encoding="utf-8",
    )
    selectors = load_selectors(path)
    assert selectors["georef_save_button"] == "#uncertCoordSave"
    assert "georef_record_value" not in selectors  # empty stays absent
    assert selectors["georef_point_tool"] == "text=Točka"


def test_shipped_selectors_file_parses() -> None:
    shipped = Path(__file__).resolve().parents[1] / "config" / "selectors.yaml"
    selectors = load_selectors(shipped)
    # The three the flow cannot run without:
    assert selectors["georef_x_htrs_input"] == "#uncertCoordX"
    assert selectors["georef_y_htrs_input"] == "#uncertCoordY"
    assert selectors["georef_save_button"] == "#uncertCoordSave"
