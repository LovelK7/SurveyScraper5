"""Part 2.1b orchestrator: SB row → maximally prefilled OSZ DOCX.

``cavedossier osz prefill <Redni broj>``:

1. resolve the SB row (the Redni broj is the only input, as with ``karta``);
2. ensure the isječak karte exists — reuse the delivered ``SB_<broj>.png``
   when it is current, otherwise run the 2.1c georef flow (worker functions
   directly, never the CLI); a karta failure degrades to an empty frame;
3. run the locality + elevation finders (both fail-soft);
4. resolve every field under the precedence rule (user, 2026-08-30):
   **SB wins** — a computed value only fills an empty cell, a disagreement
   is a printed warning, never an override;
5. fill the v10 template, embed the PNG, deliver
   ``SB_<padded>_OSZ.docx`` into ``archive.osz_prefill_dir`` and keep run
   artifacts (DOCX copy, prefill.json, dopune-sb.csv) under
   ``runs/osz/<padded>/``.

The dopune-sb.csv review list is the ONLY route by which computed values
reach SB: a person pastes them (never-auto-write rule, ARCHITECTURE.md).
Nothing here marks dossier ``Source.OSZ`` gathered — that provenance means
"read back out of a FILLED zapisnik", and this tool writes a blank one.
"""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path

from cave_dossier import georef
from cave_dossier.core.config import FEATURE_ROOT, Settings
from cave_dossier.core.normalization import parse_optional_float
from cave_dossier.geo import elevation as elevation_mod
from cave_dossier.geo import locality as locality_mod
from cave_dossier.osz.addresses import KARTA_FRAME, TEMPLATE_VERSION, V10
from cave_dossier.osz.models import FieldValue, PrefillResult, SBUpdate
from cave_dossier.osz.writer import OszDocument
from cave_dossier.sb.loader import CaveRow, SBReader

TEMPLATE_PATH = FEATURE_ROOT / "osz-template" / "templates" / "Zapisnik_OSZ_v10.docx"
RUNS_DIR = FEATURE_ROOT / "runs" / "osz"

SB_UPDATES_CSV_COLUMNS = ("Redni broj", "Stupac", "Vrijednost", "Izvor", "Napomena")


class PrefillError(RuntimeError):
    """Hard failure — no document could be produced; message is CLI-ready."""


@dataclass(frozen=True)
class PrefillOutcome:
    result: PrefillResult
    docx_path: Path            # the run-dir copy (always exists on success)
    delivered_path: Path | None  # the Drive copy, when a dir is configured
    sidecar_path: Path
    sb_updates_path: Path | None


def run_prefill(
    settings: Settings,
    serial: int,
    *,
    debug: bool = False,
    force_karta: bool = False,
) -> PrefillOutcome:
    if not TEMPLATE_PATH.exists():
        raise PrefillError(f"OSZ template not found: {TEMPLATE_PATH}")

    reader = SBReader(settings)
    cave = georef.find_by_serial(reader, settings, serial)
    if cave is None:
        raise PrefillError(f"No SB row carries Redni broj {serial}.")

    result = PrefillResult(
        serial=serial,
        cave_name=cave.object_name or "",
        sue_number=cave.sue_number or None,
        template_version=TEMPLATE_VERSION,
    )

    x_htrs = _sb_float(cave, settings.sb_x_htrs_column)
    y_htrs = _sb_float(cave, settings.sb_y_htrs_column)

    png_bytes = _ensure_karta(settings, cave, serial, result,
                              debug=debug, force=force_karta,
                              has_coords=x_htrs is not None and y_htrs is not None)

    finding = None
    kota_finding = None
    if x_htrs is not None and y_htrs is not None:
        finding = locality_mod.build_finder(settings).locate(
            x_htrs,
            y_htrs,
            sb_lokalitet=_sb_text(cave, _field_column(settings, "locality")),
            sb_najblize_mjesto=_sb_text(cave, _field_column(settings, "nearest_place")),
        )
        result.notes.extend(finding.notes)
        kota_finding = elevation_mod.build_finder(settings).kota(x_htrs, y_htrs)
        result.notes.extend(kota_finding.notes)
    else:
        result.notes.append(
            "SB red nema upotrebljive X/Y HTRS koordinate — lokacija, kota i karta preskočeni."
        )

    _resolve_fields(settings, cave, result, x_htrs, y_htrs, finding, kota_finding)

    run_dir = RUNS_DIR / georef.padded_serial(serial)
    run_dir.mkdir(parents=True, exist_ok=True)
    docx_name = f"{_sb_prefix(serial)}_OSZ.docx"
    docx_path = run_dir / docx_name
    _write_docx(docx_path, result, png_bytes, serial)

    delivered_path = _deliver(settings, docx_path, docx_name)
    if delivered_path is None:
        result.notes.append(
            "Nije konfiguriran archive.osz_prefill_dir / LOCAL_DRIVE_ROOT — "
            "dokument je ostao samo lokalno."
        )

    sidecar_path = run_dir / "prefill.json"
    sidecar_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    sb_updates_path = None
    if result.sb_updates:
        sb_updates_path = run_dir / "dopune-sb.csv"
        _write_sb_updates(sb_updates_path, serial, result.sb_updates)

    return PrefillOutcome(
        result=result,
        docx_path=docx_path,
        delivered_path=delivered_path,
        sidecar_path=sidecar_path,
        sb_updates_path=sb_updates_path,
    )


# ── karta ────────────────────────────────────────────────────────────
def _ensure_karta(
    settings: Settings,
    cave: CaveRow,
    serial: int,
    result: PrefillResult,
    *,
    debug: bool,
    force: bool,
    has_coords: bool,
) -> bytes | None:
    paths = georef.delivery_paths(settings, serial)
    if paths is None:
        result.notes.append(
            "Nije konfiguriran archive.map_excerpts_dir / LOCAL_DRIVE_ROOT — "
            "isječak karte preskočen."
        )
        return None

    if paths.png.exists() and not force:
        reason = georef.refresh_reason(settings, serial, cave.object_name or "")
        if reason is None:
            result.karta_status = "reused"
            return paths.png.read_bytes()
        result.notes.append(f"Isječak karte je zastario ({reason}) — dohvaćam ponovno.")

    if not has_coords:
        return None

    print("Isječak karte nedostaje — pokrećem georef.hr tijek (2.1c) …")
    try:
        georef_input = georef.build_input(cave, settings)
        flow_result = georef.run_for_cave(settings, georef_input, debug=debug)
    except Exception as exc:  # noqa: BLE001 — karta failure must not kill the prefill
        result.notes.append(f"Georef tijek se srušio: {exc} — okvir karte ostaje prazan.")
        return None
    if not flow_result.success:
        message = flow_result.error_message or str(flow_result.georef_status)
        result.notes.append(f"Georef tijek NIJE uspio ({message}) — okvir karte ostaje prazan.")
        result.notes.extend(f"georef: {w}" for w in flow_result.warnings)
        return None
    delivered = georef.deliver(settings, cave.object_name or "", serial, flow_result)
    result.karta_status = "fetched"
    return delivered.png.read_bytes()


# ── field resolution (SB wins) ───────────────────────────────────────
def _resolve_fields(
    settings: Settings,
    cave: CaveRow,
    result: PrefillResult,
    x_htrs: float | None,
    y_htrs: float | None,
    finding,
    kota_finding,
) -> None:
    fields = result.fields

    if cave.sue_number:
        fields["katastarski_broj"] = FieldValue(value=str(cave.sue_number), source="sb")
    plaque = _sb_text(cave, settings.sb_plaque_column)
    if plaque:
        fields["broj_plocice"] = FieldValue(value=plaque, source="sb")
    if cave.object_name:
        fields["ime_objekta"] = FieldValue(value=cave.object_name, source="sb")
    synonyms = _sb_text(cave, _field_column(settings, "synonyms"))
    if synonyms:
        fields["sinonimi"] = FieldValue(value=synonyms, source="sb")

    # Integer metres: SB carries them that way and the georef form demands it.
    if x_htrs is not None:
        fields["x_htrs"] = FieldValue(value=str(int(round(x_htrs))), source="sb")
    if y_htrs is not None:
        fields["y_htrs"] = FieldValue(value=str(int(round(y_htrs))), source="sb")

    if finding is not None:
        if finding.zupanija:
            fields["zupanija"] = FieldValue(value=finding.zupanija, source="geo-admin")
        if finding.grad_opcina:
            fields["grad_opcina"] = FieldValue(value=finding.grad_opcina, source="geo-admin")
        if finding.najblize_mjesto:
            fields["najblize_mjesto"] = FieldValue(
                value=finding.najblize_mjesto, source=finding.najblize_mjesto_source
            )
            if finding.najblize_mjesto_source == "geo-admin":
                result.sb_updates.append(SBUpdate(
                    column=_field_column(settings, "nearest_place") or "Najbliže mjesto",
                    value=finding.najblize_mjesto,
                    source="DGU naselja (točka ulaza)",
                ))
        if finding.lokalitet:
            fields["lokalitet"] = FieldValue(
                value=finding.lokalitet, source=finding.lokalitet_source
            )
            if finding.lokalitet_source == "geo-rgi":
                result.sb_updates.append(SBUpdate(
                    column=_field_column(settings, "locality") or "Lokalitet",
                    value=finding.lokalitet,
                    source="RGI (najbliži toponim)",
                ))

    _resolve_kota(settings, cave, result, kota_finding)

    for key in ("length_m", "depth_m"):
        value = _sb_float(cave, _field_column(settings, key))
        if value is not None:
            fields["duljina" if key == "length_m" else "dubina"] = FieldValue(
                value=_format_number(value), source="sb"
            )

    period = _sb_text(cave, settings.sb_exploration_period_column)
    if period:
        fields["datum_istrazivanja"] = FieldValue(value=period, source="sb")


def _resolve_kota(settings: Settings, cave: CaveRow, result: PrefillResult, kota_finding) -> None:
    sb_z = _sb_float(cave, _field_column(settings, "entrance_elevation_m"))
    computed = kota_finding.elevation_m if kota_finding is not None else None

    if sb_z is not None:
        result.fields["kota_ulaza"] = FieldValue(value=_format_number(sb_z), source="sb")
        # SB does not record where its Z came from — the recorder fills
        # Izvor kote by hand for an SB-supplied elevation.
        if computed is not None and abs(computed - sb_z) > settings.geo_elevation_tolerance_m:
            result.mismatches.append(
                f"Kota ulaza: SB kaže {_format_number(sb_z)} m, "
                f"{kota_finding.source_label} kaže {_format_number(computed)} m "
                f"(razlika > {_format_number(settings.geo_elevation_tolerance_m)} m). "
                "SB vrijednost je zadržana."
            )
        return

    if computed is not None:
        result.fields["kota_ulaza"] = FieldValue(
            value=_format_number(computed), source="dmv-dgu"
        )
        result.fields["izvor_kote"] = FieldValue(
            value=kota_finding.source_label, source="dmv-dgu"
        )
        result.sb_updates.append(SBUpdate(
            column=_field_column(settings, "entrance_elevation_m") or "Z",
            value=_format_number(computed),
            source=kota_finding.source_label or "DMV (DGU)",
            note=kota_finding.tile_name or "",
        ))


# ── outputs ──────────────────────────────────────────────────────────
def _write_docx(target: Path, result: PrefillResult, png_bytes: bytes | None,
                serial: int) -> None:
    doc = OszDocument(TEMPLATE_PATH)
    for key, field_value in result.fields.items():
        addr = V10.get(key)
        if addr is None or field_value.value is None:
            continue
        if addr.kind == "sdt_cell":
            doc.fill_sdt_cell(addr.table, addr.row, addr.cell, [field_value.value])
        else:
            doc.fill_plain(addr.table, addr.row, addr.cell, field_value.value,
                           style_from=addr.style_from)
    if png_bytes is not None:
        doc.embed_png(KARTA_FRAME.table, KARTA_FRAME.row, KARTA_FRAME.cell,
                      png_bytes, f"{_sb_prefix(serial)}.png")
    doc.save(target)


def _deliver(settings: Settings, docx_path: Path, docx_name: str) -> Path | None:
    subdir = settings.archive_dirs.get("osz_prefill_dir")
    if not settings.local_drive_root or not subdir:
        return None
    target = settings.local_drive_root / subdir / docx_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(docx_path, target)
    return target


def _write_sb_updates(path: Path, serial: int, updates: list[SBUpdate]) -> None:
    # Same CSV dialect as satellites/sync and !georef_zapisi.csv: comma,
    # CRLF, BOM — Excel opens it right on this machine's list separator.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(SB_UPDATES_CSV_COLUMNS)
        for update in updates:
            writer.writerow([serial, update.column, update.value, update.source, update.note])


# ── SB cell helpers ──────────────────────────────────────────────────
def _field_column(settings: Settings, key: str) -> str | None:
    return settings.sb_field_columns.get(key)


def _sb_text(cave: CaveRow, column: str | None) -> str | None:
    if not column:
        return None
    return SBReader._cell_as_text(cave.values, column) or None


def _sb_float(cave: CaveRow, column: str | None) -> float | None:
    return parse_optional_float(_sb_text(cave, column))


def _sb_prefix(serial: int) -> str:
    from cave_dossier.core.matching import SB_PREFIX

    return f"{SB_PREFIX}{georef.padded_serial(serial)}"


def _format_number(value: float) -> str:
    """Croatian rendering: integers bare, decimals with a comma."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}".replace(".", ",")
