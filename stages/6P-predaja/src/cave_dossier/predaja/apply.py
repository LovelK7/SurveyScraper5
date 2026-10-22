"""Execute an approved delivery plan — the archivist's one click.

Order, and why (the principle from the design note: **a claimed-but-unfiled
number is cheap to repair, a duplicated number is not**):

1. **Stage** — the stamped OSZ and Nacrt are written into
   ``runs/predaja/<broj>/`` first. Everything that can fail on the documents
   (a locked OSZ, a PDF whose cell moved) fails here, before anything shared
   has changed.
2. **SB** — one Excel session writes the number, the Napomena and the photo
   flag (and fills an empty Duljina/Dubina). The guard re-reads the column
   inside that session: the row must still have no number, the number must
   still be free (and still ``max + 1`` when it was proposed), and the cells
   must still hold what the archivist saw. Anything else refuses the write.
   This *reserves* the number.
3. **File** — copies into ``!!Osnovni zapisnici``, ``!!Nacrti`` and
   ``!!Fotografije ulaza`` under the number. Copy, never move: the leaf stays
   whole until the last step. A target that appeared since the plan is a stop.
4. **Leaf** — its OSZ (and its Nacrt, unless that one is an Illustrator file
   whose editable original must survive) is replaced by the stamped copy, so
   the archived leaf says the same as the archive; then the whole leaf moves
   to ``Arhiva/<broj>_<Ime>/``.
5. **Manifest** — ``runs/predaja/<broj>/manifest.json`` after every step:
   each src → dst, each SB cell before → after, the backup name. A failure
   stops the rest, says what to do, and a re-run resumes from the manifest
   under the same number (``plan.build_plan`` sees the number in SB).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.predaja import stamp
from cave_dossier.predaja.plan import DeliveryPlan, previous_manifest, run_dir


class DeliveryError(RuntimeError):
    """Delivery stopped; message is CLI-ready and names the manifest."""


@dataclass
class ApplyOutcome:
    sue: int
    steps: list[dict] = field(default_factory=list)
    sb_backup: str | None = None
    manifest: str | None = None
    notes: list[str] = field(default_factory=list)


def sb_guard(plan: DeliveryPlan, settings: Settings):
    """The in-session check (see the module docstring, step 2)."""
    from cave_dossier.predaja.plan import _number, sequence_stats
    from cave_dossier.sb.safe_io import SBWriteRefused

    sue_col = settings.sb_archive_reference_column or "Katastarski broj SUE"

    def guard(session) -> None:
        current = _number(session.get(sue_col))
        if plan.sue_source != "existing":
            if current is not None:
                raise SBWriteRefused(f"Red već ima katastarski broj {int(current)} – netko ga je "
                                     "upravo dodijelio. Osvježi pregled.")
            stats = sequence_stats(session.column(sue_col))
            if plan.sue in stats["taken"]:
                raise SBWriteRefused(f"Broj {plan.sue} je u međuvremenu zauzet. Osvježi pregled.")
            if plan.sue_source == "proposed" and stats["max"] + 1 != plan.sue:
                raise SBWriteRefused(f"Sljedeći broj je sada {stats['max'] + 1}, ne {plan.sue}. "
                                     "Osvježi pregled.")
        elif current != plan.sue:
            raise SBWriteRefused(f"SB sada ima broj {current}, a pregled {plan.sue}. Osvježi pregled.")
        for change in plan.sb_changes:
            if change.column == sue_col:
                continue
            now = session.get(change.column)
            if _norm(now) != _norm(change.before):
                raise SBWriteRefused(f"'{change.column}' se promijenio od pregleda "
                                     f"('{change.before}' → '{now}'). Osvježi pregled.")

    return guard


def _norm(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())


def default_sb_writer(settings: Settings, plan: DeliveryPlan, cells: dict) -> tuple[dict, str | None]:
    from cave_dossier.sb.loader import SBReader
    from cave_dossier.sb.safe_io import write_row_via_excel_com

    reader = SBReader(settings)
    header_row, _columns = reader.describe_columns()
    _row, before, backup = write_row_via_excel_com(
        Path(settings.sb_workbook_path), settings.sb_sheet_name,
        header_row_1based=header_row,
        key_header=settings.sb_field_columns.get("serial_number", "Redni broj"),
        key_value=plan.serial, cells=cells, guard=sb_guard(plan, settings))
    return before, backup.name if backup else None


def apply_plan(settings: Settings, plan: DeliveryPlan, *, expected_sue: int,
               sb_writer=None, font_path: Path | None = None) -> ApplyOutcome:
    """Deliver. ``expected_sue`` is the number the archivist confirmed: if the
    plan now says otherwise, nothing happens."""
    if not plan.ready:
        raise DeliveryError("Predaja nije spremna:\n  " + "\n  ".join(plan.blockers or [plan.state]))
    if plan.sue != expected_sue:
        raise DeliveryError(f"Potvrđen je broj {expected_sue}, a plan sada daje {plan.sue} – "
                            "osvježi pregled i potvrdi ponovno.")
    if settings.sb_mode == "FALLBACK":
        raise DeliveryError("SB se čita iz lokalne kopije – predaja piše samo u živi SB.")

    sue = plan.sue
    out = ApplyOutcome(sue)
    work = run_dir(sue)
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = work / "manifest.json"
    previous = previous_manifest(sue)
    manifest = {
        "serial": plan.serial, "name": plan.name, "sue": sue,
        "started": datetime.now().isoformat(timespec="seconds"),
        "sb_mode": settings.sb_mode, "workbook": str(settings.sb_workbook_path),
        "steps": [], "done_dst": list(previous.get("done_dst", [])),
        "sb": previous.get("sb"),
    }
    out.manifest = str(manifest_path)

    def record(step: str, status: str, **extra) -> None:
        entry = {"step": step, "status": status, **extra}
        manifest["steps"].append(entry)
        out.steps.append(entry)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
                                 encoding="utf-8")

    def fail(step: str, exc: Exception, hint: str) -> DeliveryError:
        record(step, "failed", error=f"{type(exc).__name__}: {exc}")
        return DeliveryError(f"{step}: {exc}\n  {hint}\n  Zapis: {manifest_path}")

    # ── 1. stage the stamped documents ──────────────────────────────
    staged: dict[str, Path] = {}
    try:
        from cave_dossier.osz.prefill import _word_lock

        for move in plan.moves:
            if not move.stamp or move.done:
                continue
            src = Path(move.src)
            if move.kind == "osz" and _word_lock(src) is not None:
                raise stamp.StampError(f"{src.name} je otvoren u Wordu – zatvori ga.")
            target = work / Path(move.dst).name
            if move.kind == "osz":
                stamp.stamp_osz(src, target, sue)
            else:
                stamp.stamp_pdf(src, target, sue, font_path or _font(settings))
            staged[move.src] = target
        record("priprema", "ok", staged=[str(p) for p in staged.values()])
    except Exception as exc:  # noqa: BLE001
        raise fail("Upis broja u dokumente", exc, "Ništa nije promijenjeno (ni SB ni Drive).") from exc

    # ── 2. SB ───────────────────────────────────────────────────────
    cells = {c.column: c.after for c in plan.sb_changes}
    if cells:
        writer = sb_writer or default_sb_writer
        try:
            before, backup = writer(settings, plan, cells)
        except Exception as exc:  # noqa: BLE001
            raise fail("Upis u SB", exc, "SB nije promijenjen, Drive nije diran. Ispravi i pokreni "
                       "ponovno.") from exc
        out.sb_backup = backup
        manifest["sb"] = {"row_key": plan.serial, "before": before, "after": cells, "backup": backup}
        record("sb", "ok", cells=cells, before=before, backup=backup)
    else:
        record("sb", "skipped", reason="SB već ima sve vrijednosti")

    # ── 3. file into the archive dirs ───────────────────────────────
    for move in plan.moves:
        if move.kind == "leaf":
            continue
        dst = Path(move.dst)
        if move.done:
            continue
        try:
            if dst.exists():
                raise FileExistsError(f"{dst} se pojavio nakon pregleda")
            shutil.copy2(staged.get(move.src, Path(move.src)), dst)
            manifest["done_dst"].append(str(dst))
            record("arhiva", "ok", src=move.src, dst=str(dst))
        except Exception as exc:  # noqa: BLE001
            raise fail("Kopiranje u arhivu", exc,
                       f"Broj {stamp.number_text(sue)} je već upisan u SB (rezerviran). Ponovno pokretanje "
                       "nastavlja od ovog koraka; već kopirane datoteke se ne diraju.") from exc

    # ── 4. the leaf: stamped copies in, then into Arhiva ────────────
    for move in plan.moves:
        if move.kind not in ("osz", "nacrt") or move.src not in staged:
            continue
        src = Path(move.src)
        if move.kind == "nacrt" and plan.material.get("nacrt", {}).get("stamp", {}).get("illustrator"):
            out.notes.append(f"{src.name} je Illustratorov PDF – u mapi ostaje izvornik za uređivanje "
                             "(s 0000); broj je u !!Nacrti.")
            continue
        try:
            shutil.copyfile(staged[move.src], src)
        except OSError as exc:
            out.notes.append(f"{src.name} u mapi nije zamijenjen kopijom s brojem ({exc}).")
    leaf_move = next((m for m in plan.moves if m.kind == "leaf"), None)
    if leaf_move is not None:
        try:
            dst = Path(leaf_move.dst)
            if dst.exists():
                raise FileExistsError(f"{dst} već postoji")
            shutil.move(leaf_move.src, dst)
            record("mapa", "ok", src=leaf_move.src, dst=str(dst))
        except Exception as exc:  # noqa: BLE001
            raise fail("Premještanje mape u Arhivu", exc,
                       "SB i arhiva su gotovi; premjesti mapu ručno ili pokreni ponovno.") from exc
    manifest["finished"] = datetime.now().isoformat(timespec="seconds")
    record("gotovo", "ok")
    return out


def _font(settings: Settings) -> Path:
    from cave_dossier.sastavnica.fonts import resolve

    return resolve(settings.sastavnica_font_path).path


def outcome_json(outcome: ApplyOutcome) -> dict:
    return asdict(outcome)
