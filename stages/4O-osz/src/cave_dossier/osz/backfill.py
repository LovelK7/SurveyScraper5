"""KORAK 4 — write the survey's measurements into the cave's EXISTING zapisnik.

``cavedossier osz backfill <broj>`` is the Nacrt chain's last step (user,
2026-10-04; built as ``osz izmjera`` and renamed the same day — the former
``osz backfill``, the OSZ → SB review list, is now ``osz dopune``): after KORAK 3b has produced ``<ime>_dimenzije.json`` the operator
stays on the 3N page and this command carries the numbers into the OSZ that
``osz prefill`` delivered earlier — Duljina, Horizontalna duljina, Dubina,
Visinska razlika, and Broj / Širina / Visina-duljina ulaza (project 0005).
Nothing else in the document is touched: no SB lookup, no finders, no map
excerpt, no new document. The full prefill still writes the same cells when
the dimensions file exists, so a cave done in either order ends the same.

Rules, the same as the prefill's (``docs/design-decisions.md``):

- a measured value fills an empty cell and **wins** over a different recorded
  number (the note names both); a recorded number that is the same
  measurement (``18 m`` vs ``18``, ``0.55`` vs ``0,6``) stays as written;
- the pit / horizontal reading of the entrance follows the zapisnik's own
  ticked *Vrsta objekta*, the finisher's geometric guess otherwise;
- nothing to change → the document is left alone (no backup churn);
- a document open in Word (``~$`` lock) is not touched — close Word and rerun;
- the zapisnik is **overwritten in place** (user, 2026-10-04: Google Drive keeps
  the file's versions, and the step writes only measured cells); with
  ``keep_old`` (``--keep-old``) the previous file survives as
  ``<ime>_stari_<datum>.docx`` beside the new one instead. Either way the
  written copy also stays in ``runs/osz/<broj>/``.

A zapisnik the v10 reader cannot read (a legacy layout) is not edited in place:
``osz prefill`` migrates it first, and this command says so.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cave_dossier import georef
from cave_dossier.core.config import Settings
from cave_dossier.osz import prefill
from cave_dossier.osz.addresses import V10
from cave_dossier.osz.writer import OszDocument

#: The cells this step owns, in the order the report lists them.
MEASURED_KEYS: tuple[str, ...] = prefill.DIMENSION_FIELDS + prefill.ENTRANCE_FIELDS


class BackfillError(RuntimeError):
    """Nothing could be written; the message is CLI-ready (Croatian)."""


@dataclass
class BackfillResult:
    serial: int
    osz: str | None = None
    dimensions: str | None = None
    #: which entrance reading filled Širina/Visina: "pit" | "horizontal" | None
    entrance_kind: str | None = None
    #: cell -> the value written this run
    written: dict[str, str] = field(default_factory=dict)
    #: cell -> the recorded text that stays (same measurement, or nothing measured)
    kept: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    backup: str | None = None
    #: the OSZ's mtime before and after the write — the dashboard uses them to
    #: tell "KORAK 4 touched the OSZ" from "someone edited the OSZ" (the
    #: former must not make KORAK 3c stale: 3c reads the same numbers from
    #: the dimensions file already)
    osz_mtime_before: float | None = None
    osz_mtime_after: float | None = None


@dataclass(frozen=True)
class BackfillOutcome:
    result: BackfillResult
    osz_path: Path | None
    sidecar_path: Path


def measured_cells(dims: dict, ticked) -> tuple[dict[str, str], str | None, list[str]]:
    """(cell -> text, entrance reading used, notes) from a dimensions JSON and
    the zapisnik's ticked checkboxes — the prefill's own mapping, reused."""
    values = dict(prefill.dimension_values(dims))
    kind: str | None = None
    notes: list[str] = []
    block = dims.get("entrance_size")
    if isinstance(block, dict):
        evalues, kind, notes = prefill.entrance_values(block, prefill.entrance_kind_from_ticks(ticked))
        values.update(evalues)
    return values, kind, notes


def plan_changes(recorded: dict, measured: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """(cells to write, cells that stay). A recorded number that is the same
    measurement keeps the recorder's text; anything else yields to the survey."""
    written: dict[str, str] = {}
    kept: dict[str, str] = {}
    for key in MEASURED_KEYS:
        if key not in measured:
            continue
        value = measured[key]
        old = (recorded.get(key) or "").strip()
        if old and prefill._same_measurement(old, value):
            kept[key] = old
        else:
            written[key] = value
    return written, kept


def _fill(doc: OszDocument, key: str, value: str) -> None:
    addr = V10[key]
    if addr.kind == "sdt_cell":
        doc.fill_sdt_cell(addr.table, addr.row, addr.cell, [value])
    elif addr.kind == "sdt_inline":
        doc.fill_sdt_inline(addr.table, addr.row, addr.cell, [value])
    else:
        doc.fill_plain(addr.table, addr.row, addr.cell, value)


def _newest_dimensions(folder: Path) -> Path | None:
    try:
        found = sorted(folder.glob("*_dimenzije.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    return found[0] if found else None


def run_backfill(settings: Settings, serial: int, *, keep_old: bool = False) -> BackfillOutcome:
    """Write the measured cells into the cave's OSZ; see the module docstring."""
    from cave_dossier.osz import reader as reader_mod
    from cave_dossier.osz.dopune import pick_osz_docx

    result = BackfillResult(serial=serial)
    run_dir = prefill.RUNS_DIR / georef.padded_serial(serial)
    run_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = run_dir / "backfill.json"

    folder = prefill._existing_intake_folder(settings, serial)
    if folder is None:
        raise BackfillError(
            f"Objekt {serial} nema mapu pod !Za digitalizirat – prvo `cavedossier osz prefill {serial}`."
        )
    osz_path, pool = pick_osz_docx(folder)
    if osz_path is None:
        raise BackfillError(
            f"U mapi {folder.name} nema OSZ-a – prvo `cavedossier osz prefill {serial}`, pa KORAK 4."
        )
    if pool:
        result.notes.append("Više OSZ kandidata u mapi – uzet " + osz_path.name
                            + " (ostali: " + ", ".join(p.name for p in pool) + ").")
    result.osz = osz_path.name

    dims_path = _newest_dimensions(folder)
    if dims_path is None:
        raise BackfillError(
            f"U mapi {folder.name} nema <ime>_dimenzije.json – prvo KORAK 3b (ispis iz cSurveya)."
        )
    try:
        data = json.loads(dims_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BackfillError(f"Ne mogu pročitati {dims_path.name} ({exc.__class__.__name__}).") from exc
    if not isinstance(data, dict):
        raise BackfillError(f"{dims_path.name} nije JSON objekt.")
    result.dimensions = dims_path.name
    if not data.get("calculated"):
        result.notes.append(f"{dims_path.name}: survey nije izračunat – provjeri duljine.")

    try:
        content = reader_mod.read_osz_content(osz_path)
    except reader_mod.OszReadError as exc:
        raise BackfillError(
            f"{osz_path.name} nije v10 zapisnik ({exc}) – pokreni `cavedossier osz prefill {serial}`, "
            "koji ga migrira, pa KORAK 4."
        ) from exc

    measured, kind, enotes = measured_cells(data, content.ticked)
    result.entrance_kind = kind
    result.notes.extend(enotes)
    if not measured:
        result.notes.append(f"{dims_path.name} nema izmjerenih vrijednosti (sve 0) – ništa za upisati.")
    written, kept = plan_changes(content.fields, measured)
    result.written, result.kept = written, kept
    for key, value in written.items():
        old = (content.fields.get(key) or "").strip()
        if old:
            result.notes.append(f"{key}: zapisano '{old}' ≠ izmjera '{value}' – upisana izmjera.")
    if not written:
        result.notes.append("OSZ već sadrži izmjeru – ništa nije mijenjano.")
        _write_sidecar(sidecar_path, result)
        return BackfillOutcome(result, osz_path, sidecar_path)

    lock = prefill._word_lock(osz_path)
    if lock is not None:
        raise BackfillError(f"{prefill._LOCKED_NOTE} ({lock.name}). Ništa nije upisano.")

    result.osz_mtime_before = osz_path.stat().st_mtime
    doc = OszDocument(osz_path)
    for key, value in written.items():
        _fill(doc, key, value)
    staged = run_dir / osz_path.name
    doc.save(staged)

    if keep_old:
        backup = prefill._backup_path(osz_path)
        osz_path.rename(backup)
        try:
            shutil.copy2(staged, osz_path)
        except OSError:
            try:
                backup.rename(osz_path)          # never leave the leaf with only a backup
            except OSError:
                result.notes.append(f"Stari OSZ je ostao preimenovan u {backup.name} – vrati ime ručno.")
            raise
        result.backup = backup.name
        result.notes.append(f"Stari OSZ sačuvan kao: {backup.name}")
    else:
        try:
            shutil.copyfile(staged, osz_path)    # same file, a new version on Drive
        except OSError:
            result.notes.append(f"Upis nije uspio – zapisana kopija je u {staged}; "
                                "prethodna verzija je u povijesti verzija na Driveu.")
            raise
        result.notes.append(f"Upisano u postojeći {osz_path.name} (prethodna verzija ostaje u "
                            "povijesti verzija na Driveu; --keep-old čuva i _stari kopiju).")
    result.osz_mtime_after = osz_path.stat().st_mtime
    _write_sidecar(sidecar_path, result)
    return BackfillOutcome(result, osz_path, sidecar_path)


def _write_sidecar(path: Path, result: BackfillResult) -> None:
    path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")


def last_write(serial: int) -> dict | None:
    """The last run's sidecar for the dashboard (None when KORAK 4 never ran)."""
    path = prefill.RUNS_DIR / georef.padded_serial(serial) / "backfill.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None
