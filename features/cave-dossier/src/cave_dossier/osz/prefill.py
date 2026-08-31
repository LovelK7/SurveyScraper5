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
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cave_dossier import georef
from cave_dossier.core.config import FEATURE_ROOT, Settings
from cave_dossier.core.matching import SB_PREFIX
from cave_dossier.core.normalization import normalize_lookup_key, parse_optional_float
from cave_dossier.geo import elevation as elevation_mod
from cave_dossier.geo import locality as locality_mod
from cave_dossier.osz import pristupi
from cave_dossier.osz.addresses import KARTA_FRAME, TEMPLATE_VERSION, V10
from cave_dossier.osz.models import FieldValue, PrefillResult, SBUpdate
from cave_dossier.osz.writer import OszDocument
from cave_dossier.sb.loader import CaveRow, SBReader

TEMPLATE_PATH = FEATURE_ROOT / "osz-template" / "templates" / "Zapisnik_OSZ_v10.docx"
RUNS_DIR = FEATURE_ROOT / "runs" / "osz"

SB_UPDATES_CSV_COLUMNS = ("Redni broj", "Stupac", "Vrijednost", "Izvor", "Napomena")

# The LiDAR flag (user, 2026-08-30): a cave whose name or synonym carries
# "lidar" (which also covers "lidarka" and the "LiDAR Kristal N" convention
# every Liburnija-derived row gets) had its coordinates AND Z produced by
# the LiDAR analysis — so Izvor koordinata and Izvor kote ulaza are known in
# advance. "LiDAR" normalises to the CroSpeleo vocabulary's "LIDAR" option
# (osz_parser matches on normalize_lookup_key), so the friendly casing is
# downstream-safe.
LIDAR_SOURCE_LABEL = "LiDAR"
_LIDAR_KEY = "lidar"


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
    offline: bool = False,
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
                              debug=debug, force=force_karta, offline=offline,
                              has_coords=x_htrs is not None and y_htrs is not None)

    finding = None
    kota_finding = None
    if x_htrs is not None and y_htrs is not None:
        finding = locality_mod.build_finder(settings, offline=offline).locate(
            x_htrs,
            y_htrs,
            sb_lokalitet=_sb_text(cave, _field_column(settings, "locality")),
            sb_najblize_mjesto=_sb_text(cave, _field_column(settings, "nearest_place")),
        )
        result.notes.extend(finding.notes)
        kota_finding = elevation_mod.build_finder(settings, offline=offline).kota(x_htrs, y_htrs)
        result.notes.extend(kota_finding.notes)
    else:
        result.notes.append(
            "SB red nema upotrebljive X/Y HTRS koordinate — lokacija, kota i karta preskočeni."
        )

    _resolve_fields(settings, cave, result, x_htrs, y_htrs, finding, kota_finding)

    run_dir = RUNS_DIR / georef.padded_serial(serial)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Migration (user, 2026-08-30): an OSZ already in the cave's intake
    # leaf — an older prefill someone filled in, or a hand-made zapisnik in
    # the v10 layout — carries content forward into the fresh document; the
    # old file survives as a _stari backup for comparison.
    intake_folder = _existing_intake_folder(settings, serial)
    old_osz_path = _find_old_osz(intake_folder, result) if intake_folder else None
    old_content = None
    if old_osz_path is not None:
        old_content = _migrate_old_osz(old_osz_path, result, run_dir)

    docx_name = f"{_sb_prefix(serial)}_OSZ.docx"
    docx_path = run_dir / docx_name
    _write_docx(docx_path, result, png_bytes, serial)

    delivered_path = _deliver(settings, cave, serial, docx_path, docx_name, result,
                              intake_folder=intake_folder,
                              old_osz_path=old_osz_path,
                              unchanged=_content_unchanged(old_content, result))

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
    offline: bool,
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
        if offline:
            # Can't refresh without georef.hr — the stale excerpt is still
            # better than an empty frame; the note says why.
            result.notes.append(
                f"offline način: isječak karte je zastario ({reason}) — "
                "ugrađen postojeći, osvježi kad bude mreže."
            )
            result.karta_status = "reused"
            return paths.png.read_bytes()
        result.notes.append(f"Isječak karte je zastario ({reason}) — dohvaćam ponovno.")

    if offline:
        if paths.png.exists():  # --force-karta while offline: keep what exists
            result.notes.append(
                "offline način: --force-karta zanemaren, ugrađen postojeći isječak."
            )
            result.karta_status = "reused"
            return paths.png.read_bytes()
        result.notes.append(
            "offline način: isječak karte nije prikupljen, georef.hr tijek preskočen."
        )
        return None

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

    # Deliberately NOT filled (user, 2026-08-30): Katastarski broj — the
    # archivist assigns it manually at the very end, never a prefill;
    # Duljina/Dubina — supplied by the survey process (2.1a), not SB;
    # Datum istraživanja — SB only holds a year, the real date comes from
    # the field data.
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

    # Izvor koordinata (user, 2026-08-30): LiDAR-derived caves are known in
    # advance; everything else defaults to GPS — the most common source by
    # far. Both spellings are exact CroSpeleo vocabulary matches.
    lidar = _is_lidar_derived(cave, settings)
    if x_htrs is not None or y_htrs is not None:
        if lidar:
            fields["izvor_koordinata"] = FieldValue(value=LIDAR_SOURCE_LABEL, source="lidar-flag")
        else:
            fields["izvor_koordinata"] = FieldValue(value="GPS", source="default")

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

    _resolve_kota(settings, cave, result, kota_finding, lidar)
    _resolve_pristup(result)


def _resolve_pristup(result: PrefillResult) -> None:
    """Shared approach text when a config/pristupi.yaml rule matches the
    RESOLVED Najbliže mjesto + Lokalitet (post-precedence, so an SB value
    and a finder-filled one behave the same)."""
    najblize = result.fields.get("najblize_mjesto")
    lokalitet = result.fields.get("lokalitet")
    text = pristupi.find_pristup(
        najblize.value if najblize else None,
        lokalitet.value if lokalitet else None,
    )
    if text:
        result.fields["polozaj_pristup"] = FieldValue(value=text, source="pristup-template")


def _is_lidar_derived(cave: CaveRow, settings: Settings) -> bool:
    """True when the cave's name or a synonym carries the LiDAR marker."""
    synonyms = SBReader._cell_as_text(
        cave.values, settings.sb_field_columns.get("synonyms", "Sinonimi")
    )
    for text in (cave.object_name, synonyms):
        if text and _LIDAR_KEY in normalize_lookup_key(text):
            return True
    return False


def _resolve_kota(settings: Settings, cave: CaveRow, result: PrefillResult,
                  kota_finding, lidar: bool) -> None:
    sb_z = _sb_float(cave, _field_column(settings, "entrance_elevation_m"))
    computed = kota_finding.elevation_m if kota_finding is not None else None

    label = settings.geo_elevation_source_label

    if sb_z is not None:
        result.fields["kota_ulaza"] = FieldValue(value=_format_number(sb_z), source="sb")
        if lidar:
            # A LiDAR cave's SB Z came from the LiDAR analysis, whatever
            # the DMV grid says — the source is known in advance. A grid
            # disagreement is still worth a heads-up, but stays advisory.
            result.fields["izvor_kote"] = FieldValue(
                value=LIDAR_SOURCE_LABEL, source="lidar-flag"
            )
            if computed is not None and abs(computed - sb_z) > settings.geo_elevation_tolerance_m:
                result.mismatches.append(
                    f"Kota ulaza: SB (LiDAR) kaže {_format_number(sb_z)} m, "
                    f"{label} kaže {_format_number(computed)} m "
                    f"(razlika > {_format_number(settings.geo_elevation_tolerance_m)} m). "
                    "SB vrijednost je zadržana, Izvor kote je LiDAR."
                )
            return
        if computed is not None and abs(computed - sb_z) > settings.geo_elevation_tolerance_m:
            # Disagreement: SB's value stands, but claiming a DMV source
            # for a number the DMV grid contradicts would be false — leave
            # Izvor kote to the recorder and warn.
            result.mismatches.append(
                f"Kota ulaza: SB kaže {_format_number(sb_z)} m, "
                f"{label} kaže {_format_number(computed)} m "
                f"(razlika > {_format_number(settings.geo_elevation_tolerance_m)} m). "
                "SB vrijednost je zadržana, Izvor kote ostaje prazan."
            )
            return
        # The society's Z values are DMV/LiDAR-derived (user, 2026-08-30) —
        # Izvor kote gets the label whenever the kota goes in.
        result.fields["izvor_kote"] = FieldValue(value=label, source="sb")
        return

    if computed is not None:
        result.fields["kota_ulaza"] = FieldValue(
            value=_format_number(computed), source="dmv-dgu"
        )
        result.fields["izvor_kote"] = FieldValue(value=label, source="dmv-dgu")
        result.sb_updates.append(SBUpdate(
            column=_field_column(settings, "entrance_elevation_m") or "Z",
            value=_format_number(computed),
            source=label,
            note=kota_finding.tile_name or "",
        ))


# ── migration of an older OSZ found in the intake leaf ───────────────
# Identity/location fields where the fresh prefill (SB + finders) wins and
# an older OSZ's differing value is only a note. Everything else — the
# narratives, team metadata, dimensions, dates — is content a person wrote
# and migrates verbatim into empty fields.
_PREFILL_WINS = {
    "ime_objekta", "sinonimi", "x_htrs", "y_htrs", "kota_ulaza", "izvor_kote",
    "izvor_koordinata", "zupanija", "grad_opcina", "najblize_mjesto",
    "lokalitet", "broj_plocice",
}


def _existing_intake_folder(settings: Settings, serial: int) -> Path | None:
    subdir = settings.archive_dirs.get("intake_dir")
    if not settings.local_drive_root or not subdir:
        return None
    intake_root = settings.local_drive_root / subdir
    if not intake_root.is_dir():
        return None
    return _find_intake_folder(intake_root, serial)


def _find_old_osz(folder: Path, result: PrefillResult) -> Path | None:
    """The OSZ document already in the leaf: the canonical
    ``SB_*_OSZ.docx`` when present, else a docx whose name says
    osz/zapisnik, else a lone docx. ``*_stari*`` backups and Word lock
    files never count; an ambiguous set is reported and skipped."""
    # Only OUR dated backups are excluded — a human's old file may well be
    # named "Zapisnik_stari.docx" and must still count as the old OSZ.
    backup_marker = re.compile(r"_stari_\d{4}-\d{2}-\d{2}(_\d+)?$", re.IGNORECASE)
    candidates = [
        f for f in sorted(folder.rglob("*.docx"))
        if not f.name.startswith("~$") and not backup_marker.search(f.stem)
    ]
    if not candidates:
        return None
    canonical = [f for f in candidates if re.fullmatch(r"SB_\d+_OSZ\.docx", f.name)]
    if len(canonical) == 1:
        return canonical[0]
    named = [f for f in candidates
             if "osz" in f.name.lower()
             or "zapisnik" in normalize_lookup_key(f.name)]
    pool = named or candidates
    if len(pool) == 1:
        return pool[0]
    result.notes.append(
        "Više OSZ kandidata u intake mapi — migracija preskočena: "
        + ", ".join(f.name for f in pool)
    )
    return None


def _migrate_old_osz(old_path: Path, result: PrefillResult, run_dir: Path):
    """Lift the old document's content into the result; returns the
    extracted ``OszContent`` (None when the file is not a v10 document)."""
    from cave_dossier.osz import reader as reader_mod

    try:
        content = reader_mod.read_osz_content(old_path)
    except reader_mod.OszReadError as exc:
        result.notes.append(
            f"Postojeći OSZ ({old_path.name}) nije čitljiv v10 dokument — "
            f"migracija preskočena ({exc}). Migriraj ručno."
        )
        return None

    result.migrated_from = old_path.name
    (run_dir / "stari_osz.json").write_text(
        json.dumps({"file": str(old_path), "fields": content.fields,
                    "ticked": list(content.ticked)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    carried = 0
    for key, value in content.fields.items():
        if not value:
            continue
        existing = result.fields.get(key)
        if existing is None or not existing.value:
            result.fields[key] = FieldValue(value=value, source="stari-osz")
            carried += 1
        elif _old_osz_wins(key, existing):
            # Recorded content beats what the fresh prefill merely assumed:
            # the GPS default, the shared pristup template, and the inferred
            # Izvor kote / Izvor koordinata labels.
            if _canon(existing.value) != _canon(value):
                result.fields[key] = FieldValue(value=value, source="stari-osz")
                carried += 1
        elif _canon(existing.value) != _canon(value):
            preview = " ".join(value.split())
            if len(preview) > 60:
                preview = preview[:57] + "…"
            result.notes.append(
                f"Stari OSZ ({key}): '{preview}' ≠ nova vrijednost "
                f"'{existing.value}' — zadržana nova."
                if key in _PREFILL_WINS else
                f"Stari OSZ ({key}) se razlikuje: '{preview}' — zadržana nova vrijednost."
            )
    result.ticked_checkboxes = sorted(content.ticked)
    result.notes.append(
        f"Migrirano iz {old_path.name}: {carried} polja + "
        f"{len(content.ticked)} kućica."
    )
    return content


def _old_osz_wins(key: str, existing: FieldValue) -> bool:
    """Whether a recorded old-OSZ value outranks the fresh prefill's.

    SB + finder facts stand (``_PREFILL_WINS`` semantics), but a value the
    prefill only ASSUMED — the GPS default, the pristupi template text, an
    inferred source label — yields to what a person actually recorded.
    The exception is the LiDAR flag: 'known in advance' (user, 2026-08-30)
    stays authoritative even against an older document.
    """
    if existing.source in ("default", "pristup-template"):
        return True
    return key in ("izvor_kote", "izvor_koordinata") and existing.source != "lidar-flag"


def _content_unchanged(old_content, result: PrefillResult) -> bool:
    """True when the freshly assembled document says exactly what the old
    one already says — then the old file stays as-is (idempotent re-runs
    must not grow a _stari backup each time)."""
    if old_content is None:
        return False
    for key, field_value in result.fields.items():
        if field_value.value is None:
            continue
        if _canon(old_content.fields.get(key) or "") != _canon(field_value.value):
            return False
    if set(result.ticked_checkboxes) != set(old_content.ticked):
        return False
    return True


def _canon(text: str) -> str:
    return " ".join(text.replace(";", " ").replace("\n", " ").split()).lower()


# ── outputs ──────────────────────────────────────────────────────────
def _write_docx(target: Path, result: PrefillResult, png_bytes: bytes | None,
                serial: int) -> None:
    doc = OszDocument(TEMPLATE_PATH)
    for key, field_value in result.fields.items():
        addr = V10.get(key)
        if addr is None or field_value.value is None:
            continue
        if addr.kind == "sdt_cell":
            # Multi-line values become <w:br/>-separated lines — a control
            # must stay single-paragraph (see osz/writer.py).
            doc.fill_sdt_cell(addr.table, addr.row, addr.cell,
                              field_value.value.split("\n"))
        elif addr.kind == "sdt_inline":
            doc.fill_sdt_inline(addr.table, addr.row, addr.cell,
                                field_value.value.split("\n"))
        else:
            doc.fill_plain(addr.table, addr.row, addr.cell,
                           field_value.value.replace("\n", "; "))
    if result.ticked_checkboxes:
        missing = doc.tick(set(result.ticked_checkboxes))
        for label in sorted(missing):
            result.notes.append(f"Kućica iz starog OSZ-a nije nađena u v10: '{label}'")
    if png_bytes is not None:
        doc.embed_png(KARTA_FRAME.table, KARTA_FRAME.row, KARTA_FRAME.cell,
                      png_bytes, f"{_sb_prefix(serial)}.png")
    doc.save(target)


def _deliver(settings: Settings, cave: CaveRow, serial: int, docx_path: Path,
             docx_name: str, result: PrefillResult, *,
             intake_folder: Path | None = None,
             old_osz_path: Path | None = None,
             unchanged: bool = False) -> Path | None:
    """Copy into the cave's per-cave INTAKE folder (user, 2026-08-30).

    The intake leaf under ``!Za digitalizirat`` is where the cave's survey
    files, photos and OSZ live together — so the prefill lands there, and
    CREATES the folder when the cave has none yet (named
    ``SB_<broj>_<Ime>[_<Sinonimi>][_<Autori>]``, the existing intake
    convention with the identity components the user listed). An existing
    ``SB_<broj>_…`` leaf anywhere in the tree is reused — leaves may sit
    inside hand-made container folders (!!Mune, Tin, …).

    Migration handshake: when an old OSZ was lifted into this document, the
    old file is RENAMED to a ``…_stari_<datum>`` backup first; when the new
    document says nothing the old one doesn't, the old file simply stays
    (idempotent re-runs must not pile up backups).

    Fail-soft — the run-dir copy is always the fallback (folder open,
    Drive mount offline, …).
    """
    subdir = settings.archive_dirs.get("intake_dir")
    if not settings.local_drive_root or not subdir:
        result.notes.append(
            "Nije konfiguriran archive.intake_dir / LOCAL_DRIVE_ROOT — "
            "dokument je ostao samo lokalno."
        )
        return None
    intake_root = settings.local_drive_root / subdir
    try:
        if not intake_root.is_dir():
            result.notes.append(
                f"Intake mapa nije dostupna ({intake_root}) — dokument je ostao lokalno."
            )
            return None
        folder = intake_folder or _find_intake_folder(intake_root, serial)
        if folder is None:
            folder = intake_root / _intake_folder_name(cave, serial, settings)
            folder.mkdir(parents=True, exist_ok=True)
            result.notes.append(f"Stvorena intake mapa: {folder.name}")
        target = folder / docx_name

        if old_osz_path is not None and unchanged:
            result.notes.append(
                f"{old_osz_path.name} već sadrži sve što i novi dokument — "
                "ostavljen netaknut."
            )
            return old_osz_path
        if old_osz_path is not None and old_osz_path.exists():
            backup = _backup_path(old_osz_path)
            old_osz_path.rename(backup)
            result.notes.append(f"Stari OSZ sačuvan kao: {backup.name}")

        shutil.copy2(docx_path, target)
    except OSError as exc:
        result.notes.append(
            f"Isporuka na Drive nije uspjela ({exc.__class__.__name__}: {exc}) — "
            f"dokument je ostao lokalno; zatvori {docx_name} u Wordu / pričekaj "
            "mrežu i ponovi."
        )
        return None
    return target


def _backup_path(old_path: Path) -> Path:
    """``<ime>_stari_<datum>.docx`` beside the original, counter on clash."""
    base = f"{old_path.stem}_stari_{date.today().isoformat()}"
    candidate = old_path.with_name(f"{base}{old_path.suffix}")
    counter = 2
    while candidate.exists():
        candidate = old_path.with_name(f"{base}_{counter}{old_path.suffix}")
        counter += 1
    return candidate


def _find_intake_folder(intake_root: Path, serial: int) -> Path | None:
    """The cave's existing ``SB_<broj>_…`` leaf, padded or not, anywhere in
    the intake tree; None when the cave has no folder yet."""
    pattern = re.compile(rf"^SB_0*{serial}(_|$)")
    for candidate in sorted(intake_root.rglob("SB_*")):
        if candidate.is_dir() and pattern.match(candidate.name):
            return candidate
    return None


def _intake_folder_name(cave: CaveRow, serial: int, settings: Settings) -> str:
    """``SB_<broj>_<Ime>[_<Sinonimi>][_<Autori>]`` — the components the user
    listed (2026-08-30), sanitized for Windows/Drive, empties skipped.
    Serial stays unpadded, matching the existing intake folders."""
    parts = [f"{SB_PREFIX}{serial}", cave.object_name or ""]
    parts.append(_sb_text(cave, _field_column(settings, "synonyms")) or "")
    parts.append(_sb_text(cave, settings.sb_drawing_authors_column) or "")
    cleaned = [_sanitize_component(part) for part in parts]
    name = "_".join(part for part in cleaned if part)
    return name[:120].rstrip("._ ")


def _sanitize_component(text: str) -> str:
    text = re.sub(r'[<>:"/\\|?*]', " ", text)
    text = text.replace(";", ",")
    return " ".join(text.split()).strip("._ ")


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
    return f"{SB_PREFIX}{georef.padded_serial(serial)}"


def _format_number(value: float) -> str:
    """Croatian rendering: integers bare, decimals with a comma."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}".replace(".", ",")
