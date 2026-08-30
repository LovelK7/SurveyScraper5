"""Part 2.1c orchestration: SB row → georef.hr flow → shared Drive folder.

New code (the crospeleo counterpart, ``services/georef_worker.py``, feeds a
submission dossier — here the products are collected per cave instead):

- input comes from ONE thing, the SB **Redni broj** (the pre-SUE identity,
  user decision 2026-08-26);
- the map excerpt PNG is delivered into the shared ``!!Isječci karte`` Drive
  folder as ``SB_<zero-padded Redni broj>.png`` — the ``SB_`` marker keeps the
  number from reading as a katastarski broj (user, 2026-08-30);
- the georef record texts ("Georef zapis" in crospeleo's readiness terms)
  are collated into ONE ``!georef_zapisi.csv`` at the top of that folder,
  one row per cave, upserted by Redni broj — re-running a cave updates its
  row rather than appending a duplicate.
"""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import SB_PREFIX
from cave_dossier.core.normalization import parse_optional_float
from cave_dossier.georef.artifacts import build_georef_artifacts, persist_georef_result
from cave_dossier.georef.models import GeorefInput, GeorefResult, GeorefStatus
from cave_dossier.georef.selectors import load_selectors
from cave_dossier.sb.loader import CaveRow, SBReader

# Redni broj is 4 digits padded (currently 1..1438): unlike the 3-digit SUE
# photo prefixes, this folder is keyed by Redni broj, which is already past
# 1000, so 4 keeps Drive listings sorted for the registry's lifetime.
SERIAL_PAD = 4

# The `!` prefix floats the collation file above the numbered PNGs in Drive
# listings — same convention as the archive dirs themselves (user, 2026-08-29).
RECORDS_CSV_NAME = "!georef_zapisi.csv"
RECORDS_CSV_COLUMNS = ("Redni broj", "Ime objekta", "Georef zapis", "Datum")


def padded_serial(serial: int | str) -> str:
    return str(serial).strip().zfill(SERIAL_PAD)


def map_excerpts_dir(settings: Settings) -> Path | None:
    """The shared Drive folder the excerpts are collected in, or None if
    LOCAL_DRIVE_ROOT / archive.map_excerpts_dir is not configured."""
    subdir = settings.archive_dirs.get("map_excerpts_dir")
    if not settings.local_drive_root or not subdir:
        return None
    return settings.local_drive_root / subdir


@dataclass(frozen=True)
class DeliveryPaths:
    png: Path
    records_csv: Path


def delivery_paths(settings: Settings, serial: int | str) -> DeliveryPaths | None:
    directory = map_excerpts_dir(settings)
    if directory is None:
        return None
    return DeliveryPaths(
        png=directory / f"{SB_PREFIX}{padded_serial(serial)}.png",
        records_csv=directory / RECORDS_CSV_NAME,
    )


def find_by_serial(reader: SBReader, settings: Settings, serial: int) -> CaveRow | None:
    """Resolve a Redni broj to its SB row.

    ``SBReader.find_caves`` matches name / SUE / plaque — Redni broj is a
    different column (``sb.field_columns.serial_number``), scanned here.
    """
    column = settings.sb_field_columns.get("serial_number", "Redni broj")
    frame = reader.load_rows()
    if column not in frame.columns:
        return None
    for _index, row in frame.iterrows():
        record = {str(key).strip(): value for key, value in row.to_dict().items()}
        value = parse_optional_float(SBReader._cell_as_text(record, column))
        if value is not None and int(value) == serial:
            return reader._to_cave_row(record)
    return None


def build_input(cave: CaveRow, settings: Settings) -> GeorefInput:
    """GeorefInput from the SB row. Coordinates come from SB only — this
    tool is upstream of any OSZ, so crospeleo's OSZ/stored-georef fallbacks
    have nothing to fall back to here."""
    notes: list[str] = []
    x_htrs = _coordinate(cave, settings.sb_x_htrs_column)
    y_htrs = _coordinate(cave, settings.sb_y_htrs_column)
    if x_htrs is None or y_htrs is None:
        notes.append("No usable HTRS coordinates in the SB row.")
    serial = cave.values.get(settings.sb_field_columns.get("serial_number", "Redni broj"))
    serial_text = SBReader._cell_as_text({"c": serial}, "c") or "?"
    return GeorefInput(
        object_id=serial_text,
        object_name=cave.object_name or "",
        x_htrs=x_htrs,
        y_htrs=y_htrs,
        source="sb_htrs" if x_htrs is not None and y_htrs is not None else None,
        notes=notes,
    )


def _coordinate(cave: CaveRow, column: str | None) -> float | None:
    if not column:
        return None
    return parse_optional_float(SBReader._cell_as_text(cave.values, column))


def run_for_cave(settings: Settings, georef_input: GeorefInput, *, debug: bool = False) -> GeorefResult:
    """Login → point flow → close; artifacts under runs/georef/<padded>/.

    Deliberately mirrors crospeleo's ``GeorefAutomationWorker.run_for_dossier``
    minus the dossier bookkeeping.  Imports Playwright lazily so every
    non-karta CLI command works without the ``[karta]`` extra installed.
    """
    from cave_dossier.georef.client import GeorefClient
    from cave_dossier.georef.flows import run_point_georef_flow

    artifacts = build_georef_artifacts(padded_serial(georef_input.object_id))

    if georef_input.x_htrs is None or georef_input.y_htrs is None:
        result = GeorefResult(
            success=False,
            georef_status=GeorefStatus.WARNING,
            warnings=[*georef_input.notes, "Missing coordinates; Georef flow skipped."],
        )
        return persist_georef_result(artifacts, result)

    selectors = load_selectors(settings.georef_selectors_path)
    client = GeorefClient(settings, selectors, debug=debug)

    login_result, session = client.login(artifacts)
    if not login_result.success or session is None:
        result = GeorefResult(
            success=False,
            georef_status=login_result.georef_status,
            warnings=login_result.warnings,
            trace_path=login_result.trace_path,
            browser_log_path=login_result.browser_log_path,
            error_message=login_result.error_message,
        )
        return persist_georef_result(artifacts, result)

    result = GeorefResult(success=False, georef_status=GeorefStatus.ERROR)
    try:
        result = run_point_georef_flow(client, session, georef_input, selectors, artifacts)
    finally:
        trace_path = client.close_session(session)
        if not result.trace_path:
            result.trace_path = trace_path

    return persist_georef_result(artifacts, result)


def deliver(settings: Settings, cave_name: str, serial: int | str, result: GeorefResult,
            *, today: date | None = None) -> DeliveryPaths:
    """Copy the excerpt PNG to the shared folder and upsert the record CSV."""
    paths = delivery_paths(settings, serial)
    if paths is None:
        raise RuntimeError(
            "No delivery dir configured: set LOCAL_DRIVE_ROOT in .env and "
            "`archive.map_excerpts_dir` in config.yaml."
        )
    if not result.map_screenshot_path:
        raise RuntimeError("Georef result carries no map screenshot to deliver.")
    paths.png.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(result.map_screenshot_path, paths.png)
    if result.georef_record:
        stamp = (today or date.today()).isoformat()
        upsert_record(paths.records_csv, padded_serial(serial), cave_name,
                      result.georef_record, stamp)
    return paths


def upsert_record(csv_path: Path, serial_label: str, cave_name: str,
                  record: str, date_text: str) -> None:
    """One row per cave in !georef_zapisi.csv, keyed by (padded) Redni broj.

    Same CSV dialect as `satellites/sync.to_csv`: comma separator (Excel picks
    it from the machine's list separator, checked 2026-08-29), CRLF, BOM.
    The record itself is semicolon-joined, so commas/quoting stay safe, and
    it is flattened to one line — a cell spanning lines is miserable in Excel.
    """
    rows: dict[str, list[str]] = {}
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            for row in reader:
                if not row or row[0] == RECORDS_CSV_COLUMNS[0]:
                    continue
                rows[row[0]] = (row + [""] * len(RECORDS_CSV_COLUMNS))[: len(RECORDS_CSV_COLUMNS)]

    flat = " ".join(record.split())
    rows[serial_label] = [serial_label, cave_name, flat, date_text]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(RECORDS_CSV_COLUMNS)
        for key in sorted(rows):
            writer.writerow(rows[key])
