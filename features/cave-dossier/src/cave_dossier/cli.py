"""``cavedossier`` — CLI for SurveyScraper5 stage 2.

Commands: read-only SB inspection (`sb columns` / `sb inspect` / `sb stats`,
M1) and the per-cave dossier report (`report`, M2).  Every command starts with
a mode banner so it is always obvious whether the SANDBOX copy or the LIVE
workbook is being read.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from cave_dossier.core.config import ConfigError, Settings, load_settings
from cave_dossier.dossier import GateLevel, build_from_sb, evaluate, render
from cave_dossier.photos import (
    apply_renames,
    build_candidates,
    list_other_files,
    list_photos,
    match_photos,
    staged_photo_dir,
)
from cave_dossier.intake import (
    find_leaf_folders,
    liburnija,
    intake_root,
    match_leaves,
    old_queue_candidates,
    suggest,
)
from cave_dossier import georef
from cave_dossier.satellites import liburnija as sheet, resolver, sync
from cave_dossier.satellites.model import LinkStatus
from cave_dossier.sb.audit import AUTHOR_FLAG_HELP, audit_authors, audit_unclassified
from cave_dossier.sb.loader import SBReader
from cave_dossier.sb.safe_io import SBWorkbookUnreachable

# Exit-code convention (user, 2026-08-26): ready is the exceptional, actionable
# outcome, so it gets the non-zero code; errors are far away at 99 so a crashed
# run can never be mistaken for a verdict.
EXIT_NOT_READY = 0
EXIT_READY = 1
EXIT_ERROR = 99


def _print_banner(settings: Settings) -> None:
    print(f"SB mode: {settings.sb_mode} ({settings.sb_workbook_path})")
    if settings.sb_mode == "FALLBACK":
        print(f"⚠ {settings.sb_mode_reason} — čita se zadnja dobra lokalna kopija;")
        print("  podaci mogu kasniti za live SB. Ponovi kad SB bude slobodan.")
    print()


def _cell_display(value: object) -> str:
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() == "nan"


# ── Commands ───────────────────────────────────────────────────────


def cmd_sb_columns(settings: Settings) -> int:
    reader = SBReader(settings)
    header_row, columns = reader.describe_columns()
    print(f"Sheet:      {settings.sb_sheet_name}")
    print(f"Header row: {header_row} (1-based Excel row)")
    print(f"Columns ({len(columns)}, in sheet order):")
    for i, column in enumerate(columns, 1):
        print(f"  {i:3d}. {column}")
    return 0


def cmd_sb_inspect(settings: Settings, query: str) -> int:
    reader = SBReader(settings)
    matches = reader.find_caves(query)
    if not matches:
        print(f"No SB row matches {query!r} (tried object name, SUE number, plaque;")
        print("diacritic- and case-insensitive; then name substring).")
        return EXIT_ERROR
    if len(matches) > 1:
        print(f"{len(matches)} rows match {query!r} — showing all (refine with the exact name or SUE):")
        print()
    for cave in matches:
        print(f"=== Excel row {cave.row_number} — {cave.object_name or '<no name>'}"
              + (f" (SUE {cave.sue_number})" if cave.sue_number else ""))
        non_empty = [(k, v) for k, v in cave.values.items() if not _is_empty(v)]
        empty_count = len(cave.values) - len(non_empty)
        width = max((len(k) for k, _ in non_empty), default=0)
        for key, value in non_empty:
            print(f"  {key:<{width}}  {_cell_display(value)}")
        print(f"  ({empty_count} empty columns not shown)")
        print()
    return 0


def cmd_sb_stats(settings: Settings) -> int:
    reader = SBReader(settings)
    stats = reader.stats()
    print("Sheets in workbook:")
    for name in stats["sheet_names"]:
        marker = "  <- configured target" if name == stats["target_sheet"] else ""
        print(f"  - {name}{marker}")
    print()
    print(f"Target sheet: {stats['target_sheet']}")
    print(f"Header row:   {stats['header_row']}")
    print(f"Data rows:    {stats['data_rows']}")
    print()
    print("Non-empty cells in key columns:")
    for label, entry in stats["fill_counts"].items():
        if entry is None:
            print(f"  {label:<20} (column not configured / not found)")
        else:
            column, count = entry
            print(f"  {label:<20} {count:5d}   [{column}]")
    return 0


def cmd_report(settings: Settings, query: str, as_json: bool, gate: str) -> int:
    """Per-cave dossier report (M2).

    Both gates are always printed; ``--gate`` only picks which one the exit
    code reports on. Exit codes are the user's convention (2026-08-26):
    ``1`` ready, ``0`` not ready, ``99`` error.
    """
    reader = SBReader(settings)
    matches = reader.find_caves(query)
    if not matches:
        print(f"No SB row matches {query!r} (tried object name, SUE number, plaque).")
        return EXIT_ERROR
    if len(matches) > 1:
        print(f"{len(matches)} rows match {query!r} — refine the query:")
        for cave in matches:
            print(f"  row {cave.row_number}: {cave.object_name} (SUE {cave.sue_number or '—'})")
        return EXIT_ERROR

    dossier = build_from_sb(matches[0], settings)

    # Statement gathering: the izjave dir is shared (not per-cave), so it can
    # be scanned before archive intake exists. Unreachable Drive → the
    # statement gates honestly report "not checked yet".
    from cave_dossier.people.registry import PersonRegistry
    from cave_dossier.people.statements import enrich as enrich_statements

    registry = PersonRegistry.load(settings.people_registry_path)
    enrich_statements(dossier, settings, registry)

    report = evaluate(dossier)
    if as_json:
        print(dossier.model_dump_json(indent=2, exclude={"sb_record"}))
    else:
        print(render(dossier))

    level = GateLevel.CROSPELEO if gate == "crospeleo" else GateLevel.SUE
    return EXIT_READY if report.ready_for(level) else EXIT_NOT_READY


def cmd_sb_audit_authors(settings: Settings, limit: int) -> int:
    """Data-quality sweep over `Autori nacrta ili izvor` (M2, user request A5/4)."""
    findings = audit_authors(SBReader(settings), settings)
    if not findings:
        print("No suspicious author cells found.")
        return EXIT_READY

    counts: dict[str, int] = {}
    for finding in findings:
        for flag in finding.flags:
            counts[flag] = counts.get(flag, 0) + 1

    print(f"{len(findings)} rows worth a look (of the whole workbook).")
    print()
    print("By flag:")
    for flag, count in sorted(counts.items(), key=lambda item: -item[1]):
        print(f"  {flag:<14} {count:5d}   {AUTHOR_FLAG_HELP.get(flag, '')}")
    print()
    print(f"First {min(limit, len(findings))} rows (Excel row · Redni broj · cave · cell → parsed):")
    for finding in findings[:limit]:
        serial = finding.serial_number if finding.serial_number is not None else "—"
        print(f"  r{finding.row_number:<5} #{str(serial):<5} {(finding.object_name or '')[:28]:<28}"
              f" [{','.join(finding.flags)}]")
        print(f"        cell: {finding.raw!r}")
        if finding.parsed:
            print(f"        → {finding.parsed}"
                  + (f"   societies={finding.societies}" if finding.societies else ""))
    if len(findings) > limit:
        print(f"  … {len(findings) - limit} more (raise --limit to see them)")
    return EXIT_NOT_READY


def cmd_sb_unclassified(settings: Settings, limit: int) -> int:
    """Rows that appear in none of SB's three views (user request 5)."""
    rows = audit_unclassified(SBReader(settings), settings)
    if not rows:
        print("Every named row lands in one of Istraženi / Nesređeni / Za istražit.")
        return EXIT_READY

    print(f"{len(rows)} named rows have no SUE number and no Napomena flag of any kind,")
    print("so they show up in none of SB's views (and are not 'sudjelovanje' either):")
    print()
    for row in rows[:limit]:
        serial = row.serial_number if row.serial_number is not None else "—"
        print(f"  r{row.row_number:<5} #{str(serial):<5} {(row.object_name or '')[:32]:<32}"
              f" {(row.locality or '—')[:18]:<18} {row.exploration_period or '—'}")
        if row.note:
            print(f"        Napomena: {row.note}")
    if len(rows) > limit:
        print(f"  … {len(rows) - limit} more (raise --limit to see them)")
    return EXIT_NOT_READY


def cmd_photos_match_queued(settings: Settings, limit: int, apply: bool) -> int:
    """Propose (and with --apply, perform) an SB_<Redni broj> prefix for staged photos (2.1d)."""
    directory = staged_photo_dir(settings)
    if directory is None:
        print("No staged-photo dir configured: set LOCAL_DRIVE_ROOT in .env and")
        print("`archive.queued_photos_dir` in config.yaml.", file=sys.stderr)
        return EXIT_ERROR
    photos = list_photos(directory)
    print(f"Staged photos: {len(photos)} in {directory}")
    if not photos:
        return EXIT_NOT_READY

    matches = match_photos(
        photos,
        build_candidates(SBReader(settings), settings),
        settings.photo_manual_matches,
    )
    matched = [m for m in matches if m.cave is not None and m.confidence != "conflict"]
    conflicts = [m for m in matches if m.confidence == "conflict"]
    renames = [m for m in matches if m.proposed_name]
    promotions = [m for m in matches if m.needs_promotion]
    print(f"Matched to an SB row: {len(matched)} / {len(matches)}"
          + (f"   ({len(conflicts)} conflicting)" if conflicts else ""))
    print(f"Rename proposals: {len(renames)}")
    if promotions:
        print(f"⚠ {len(promotions)} staged photo(s) belong to caves that ALREADY have a SUE "
              f"number — they should have been promoted into the main photo archive (or "
              f"deleted once newer photos replaced them). Listed below; never renamed here.")
    else:
        print("No staged photo belongs to an already-explored cave — nothing left behind.")
    print(
        "APPLYING — files will be renamed in place."
        if apply
        else "DRY RUN — nothing is renamed or moved; re-run with --apply to perform these."
    )
    print()
    for match in matches[:limit]:
        if match.cave is None:
            print(f"  ?    {match.path.name}")
            continue
        print(f"  {match.confidence[:4]:<4} {match.path.name}")
        if match.proposed_name:
            print(f"       → {match.proposed_name}")
        elif match.needs_promotion:
            print(f"       → PROMOTE or DELETE: cave now has SUE {match.cave.sue_number} — "
                  f"belongs in the main photo archive as {match.promoted_name}")
        elif match.already_correct:
            print("       → (already carries its Redni broj)")
        print(f"       {match.cave.object_name} · Redni broj "
              f"{match.cave.serial_number} · {match.evidence}")
    if len(matches) > limit:
        print(f"  … {len(matches) - limit} more (raise --limit to see them)")

    if apply:
        outcomes = apply_renames(matches)
        renamed = [o for o in outcomes if o.status == "renamed"]
        problems = [o for o in outcomes if o.status != "renamed"]
        print()
        print(f"Renamed {len(renamed)} file(s).")
        for outcome in problems:
            print(f"  {outcome.status}: {outcome.source.name} → "
                  f"{outcome.target.name if outcome.target else '?'}"
                  + (f"  ({outcome.detail})" if outcome.detail else ""))
        if problems:
            return EXIT_ERROR

    return EXIT_NOT_READY if len(matched) < len(matches) else EXIT_READY


def cmd_photos_check_flag(settings: Settings, limit: int) -> int:
    """Every staged photo's cave should say `Fotografija ulaza = DA` in SB (2.1d).

    The photo folder is the ground truth; the SB cell is a human-maintained
    claim about it. This reports the caves where the two disagree, which is the
    list to fix in Excel.
    """
    directory = staged_photo_dir(settings)
    if directory is None:
        print("No staged-photo dir configured (see config.yaml).", file=sys.stderr)
        return EXIT_ERROR

    photos = list_photos(directory)
    others = list_other_files(directory)
    matches = match_photos(
        photos, build_candidates(SBReader(settings), settings), settings.photo_manual_matches
    )

    by_cave: dict[int | None, list] = {}
    unmatched = []
    for match in matches:
        if match.cave is None:
            unmatched.append(match.path.name)
            continue
        by_cave.setdefault(match.cave.serial_number, []).append(match)

    missing = {
        serial: group
        for serial, group in by_cave.items()
        if (group[0].cave.entrance_photo_flag or "").strip().casefold() != "da"
    }

    print(f"Folder: {directory}")
    print(f"  {len(photos)} photo(s) covering {len(by_cave)} cave(s)"
          + (f", {len(unmatched)} unmatched" if unmatched else ""))
    if others:
        print(f"  {len(others)} non-photo file(s) in the same folder:")
        for path in others:
            print(f"      {path.name}")
    print()
    print(f"'Fotografija ulaza' = DA : {len(by_cave) - len(missing)} of {len(by_cave)} caves")

    if not missing:
        print("Every cave with a staged photo is flagged DA in SB. Nothing to fix.")
        return EXIT_READY

    print(f"NOT flagged DA          : {len(missing)} cave(s) — SB says no photo exists,")
    print("                          but these files are sitting in the folder:")
    print()
    for serial in sorted(missing, key=lambda value: (value is None, value)):
        group = missing[serial]
        cave = group[0].cave
        flag = cave.entrance_photo_flag or "(empty)"
        print(f"  Redni broj {str(serial):<5} {cave.object_name[:44]:<44} flag = {flag}")
        for match in group[:limit]:
            print(f"        {match.path.name}")
    for name in unmatched:
        print(f"  ?     unmatched file: {name}")
    return EXIT_NOT_READY


def cmd_photos_process(settings: Settings, serial: int, dry_run: bool,
                       from_dir: str | None, author_arg: str | None,
                       osz_path_arg: str | None, long_edge: int | None,
                       max_bytes: int | None, overwrite: bool) -> int:
    """Part 2.1d — archive-ready copies of ONE cave's entrance photos.

    Reads the raw photos from the cave's ``SB_<broj>_…`` intake leaf and writes
    ``SB_<broj>_<Ime objekta>_<Autor>_<n>.jpg`` copies beside them, downsized to
    the config's screen-size targets. The author is the OSZ cell "Autor
    fotografije ulaza"; the originals are never touched, and nothing is moved
    into `!!Fotografije ulaza` — that (and the SB→katastarski renumbering) is
    the later filing step.

    **Writes by default** (user, 2026-09-01): unlike every other `--apply`
    command in this tool, this one only ever ADDS files — the originals stay
    byte-for-byte, an existing copy is skipped rather than overwritten, and
    nothing leaves the folder. There is nothing for a dry run to protect, so
    requiring one was friction and no safety. `--dry-run` still prints the plan
    for anyone who wants to look first.
    """
    from cave_dossier.photos import process as process_mod

    cave = _find_serial_or_exit(settings, serial)
    if cave is None:
        return EXIT_ERROR

    job = process_mod.build_job(
        settings,
        serial,
        cave.object_name,
        folder=Path(from_dir).resolve() if from_dir else None,
        author_override=author_arg,
        osz_path=Path(osz_path_arg).resolve() if osz_path_arg else None,
    )
    config_long_edge, config_max_bytes = process_mod.resolve_targets(settings)
    long_edge_px = long_edge or config_long_edge
    budget_bytes = max_bytes or config_max_bytes

    print(f"Redni broj {serial}: {cave.object_name or '<no name>'}"
          + (f" (SUE {cave.sue_number})" if cave.sue_number else ""))
    for note in job.notes:
        print(f"  ! {note}")
    if job.folder is None:
        _print_staged_hint(job, serial)
        return EXIT_ERROR
    print(f"Mapa:  {job.folder}")
    if job.osz_path:
        print(f"OSZ:   {job.osz_path.name}")
    print(f"Autor: {job.author or '(prazno)'}"
          + (f"   ← '{job.author_source}'" if job.author_source else ""))
    print(f"Cilj:  duga stranica {long_edge_px} px, do "
          f"{budget_bytes / 1_000_000:.1f} MB po datoteci")

    for path in job.ignored:
        print(f"  – preskačem {path.name} (nije fotografija ulaza — "
              "photos.ignore_filenames)")
    if not job.plans:
        print("Nema neobrađenih fotografija u mapi "
              f"(datoteke koje već počinju s SB_{serial}_ su rezultat prijašnjeg "
              "pokretanja).")
        _print_staged_hint(job, serial)
        return EXIT_NOT_READY

    print(f"Fotografija za obradu: {len(job.plans)}")
    print(
        "PROBNI RUN — ništa se ne zapisuje (--dry-run)."
        if dry_run
        else "OBRAĐUJEM — kopije se zapisuju uz originale; originali ostaju netaknuti."
    )
    print()
    for plan in job.plans:
        marker = "!" if plan.unsupported else ("=" if plan.target_exists else " ")
        print(f"  {marker} {plan.source.name}")
        print(f"      → {plan.target.name}"
              + ("   (format traži pillow-heif)" if plan.unsupported else "")
              + ("   (postoji)" if plan.target_exists and not plan.unsupported else ""))

    if dry_run:
        return EXIT_NOT_READY

    print()
    outcomes = process_mod.process_job(
        job, long_edge_px=long_edge_px, max_bytes=budget_bytes, overwrite=overwrite
    )
    written = [o for o in outcomes if o.status == "written"]
    problems = [o for o in outcomes if o.status not in ("written", "exists")]
    for outcome in outcomes:
        if outcome.status == "written":
            print(f"  ✓ {outcome.plan.target.name}   "
                  f"{_mb(outcome.source_bytes)} → {_mb(outcome.target_bytes)}"
                  f"   {_px(outcome.source_px)} → {_px(outcome.target_px)}")
        else:
            print(f"  {outcome.status}: {outcome.plan.source.name}"
                  + (f"  ({outcome.detail})" if outcome.detail else ""))
    print()
    print(f"Zapisano {len(written)} kopija; originali su netaknuti.")
    oversized = [o for o in written
                 if o.target_bytes is not None and o.target_bytes > budget_bytes]
    if oversized:
        print(f"⚠ {len(oversized)} kopija je i dalje iznad budžeta na najnižoj "
              "kvaliteti — snizi --long-edge ako smeta.")
    _print_staged_hint(job, serial)
    return EXIT_ERROR if problems else EXIT_NOT_READY


def _print_staged_hint(job, serial: int, limit: int = 8) -> None:
    """The cave's photos may not be in its leaf at all — they may still be
    queued in `…za istražit`, which is invisible from the leaf alone and is
    exactly how a cave gets processed with half its photos missing.

    Printed on every exit of `photos process`, including the ones that found
    nothing to do: "no photos here" plus "four are sitting in the queue" is the
    single most useful thing the command can say.
    """
    if not job.staged:
        return
    print()
    print(f"⚠ {len(job.staged)} fotografija ove jame još stoji u redu čekanja "
          "(!!Fotografije ulaza za istražit):")
    for path in job.staged[:limit]:
        print(f"      {path.name}")
    if len(job.staged) > limit:
        print(f"      … još {len(job.staged) - limit}")
    print("  Prebaci ih u intake mapu pa ponovno pokreni obradu:")
    print(f"      cavedossier photos pull-staged {serial} --apply")


def cmd_photos_pull_staged(settings: Settings, serial: int, apply: bool) -> int:
    """Move a cave's queued photos out of `…za istražit` into its intake leaf.

    Dry run by default — unlike `photos process`, this one MOVES files and
    creates a folder, so it follows the same `--apply` guard as `photos
    match-queued` and `intake map`. The `SB_<broj>_` prefix is dropped on the
    way in: inside the cave's own leaf it is redundant, and `photos process`
    reads that prefix as "already processed output".
    """
    from cave_dossier.photos import process as process_mod

    cave = _find_serial_or_exit(settings, serial)
    if cave is None:
        return EXIT_ERROR

    plan = process_mod.plan_pull(settings, cave, serial)
    print(f"Redni broj {serial}: {cave.object_name or '<no name>'}")
    for note in plan.notes:
        print(f"  ! {note}")
    if plan.folder is None:
        return EXIT_ERROR
    if not plan.moves:
        print("Nema fotografija ove jame u redu čekanja "
              "(!!Fotografije ulaza za istražit) — nema što prebaciti.")
        return EXIT_NOT_READY

    print(f"Odredište: {plan.folder}"
          + ("" if plan.folder_exists else "   (bit će stvorena)"))
    print(f"Fotografija za prebacivanje: {len(plan.moves)}")
    print(
        "PREBACUJEM — datoteke se MIČU iz reda čekanja."
        if apply
        else "PROBNI RUN — ništa se ne miče; ponovi s --apply."
    )
    print()
    for move in plan.moves:
        print(f"  {move.source.name}")
        print(f"      → {move.target.name}"
              + ("   (postoji)" if move.target.exists() else ""))

    if not apply:
        return EXIT_NOT_READY

    outcomes = process_mod.apply_pull(plan)
    moved = [o for o in outcomes if o.status == "moved"]
    problems = [o for o in outcomes if o.status == "error"]
    print()
    for outcome in problems:
        print(f"  {outcome.status}: {outcome.move.source.name}  ({outcome.detail})")
    print(f"Prebačeno {len(moved)} fotografija.")
    if moved:
        print("  Sad ih obradi:")
        print(f"      cavedossier photos process {serial}")
    return EXIT_ERROR if problems else EXIT_NOT_READY


def _mb(size_bytes: int | None) -> str:
    return "?" if size_bytes is None else f"{size_bytes / 1_000_000:.2f} MB"


def _px(size: tuple[int, int] | None) -> str:
    return "?" if size is None else f"{size[0]}×{size[1]}"


def cmd_intake_map(settings: Settings, limit: int, apply: bool, unmatched_only: bool) -> int:
    """Map each field-data leaf folder to its SB row (M2, field-data intake).

    Read-only unless --apply. Leading numbers in these folders are local ids
    (LIDAR point, expedition sequence), so they are deliberately not read as SB
    numbers — see cave_dossier/intake/scanner.py.
    """
    root = intake_root(settings)
    if root is None:
        print("No intake dir configured: set LOCAL_DRIVE_ROOT in .env and")
        print("`archive.intake_dir` in config.yaml.", file=sys.stderr)
        return EXIT_ERROR

    leaves = find_leaf_folders(root)
    if not leaves:
        print(f"No leaf folders under {root}")
        return EXIT_NOT_READY
    candidates = build_candidates(SBReader(settings), settings)
    sheet_csv = liburnija.sheet_path(settings)
    sheet_rows = liburnija.load_rows(sheet_csv) if sheet_csv else {}
    if sheet_rows:
        print(f"Liburnija sheet: {len(sheet_rows)} numbered rows from {sheet_csv.name}")
    matches = match_leaves(leaves, candidates, settings.intake_manual_matches,
                           settings.intake_new_entries, sheet_rows)
    by_path = {leaf.path: leaf for leaf in leaves}

    matched = [m for m in matches if m.cave is not None and m.confidence != "conflict"]
    conflicts = [m for m in matches if m.confidence == "conflict"]
    new_entries = [m for m in matches if m.is_new_entry]
    unmatched = [m for m in matches if m.cave is None and not m.is_new_entry]

    print(f"Intake root: {root}")
    print(f"  {len(leaves)} leaf folder(s) — mapped to an SB row: {len(matched)}"
          + (f", conflicting {len(conflicts)}" if conflicts else ""))
    print(f"  {len(new_entries) + len(unmatched)} with no SB row — new caves that need"
          f" a row before they can be numbered")
    print(
        "APPLYING — folders will be renamed in place."
        if apply
        else "DRY RUN — nothing is renamed; re-run with --apply once the mapping looks right."
    )

    group = None
    shown = 0
    for match in matches:
        if unmatched_only and match.cave is not None:
            continue
        if shown >= limit:
            break
        shown += 1
        leaf = by_path[match.path]
        if leaf.group != group:
            group = leaf.group
            print()
            print(f"  [{group or '(top level)'}]")
        mark = "NEW" if match.is_new_entry else ("?" if match.cave is None else match.confidence[:4])
        print(f"    {mark:<4} {leaf.relative.name}   ({leaf.file_count} files)")
        if match.is_new_entry:
            print("         → NEW: confirmed absent from SB (overrides a lookalike match)")
            continue
        if match.cave is None:
            print("         → NEW: no SB row resolves; create one, then re-run")
            for token, cave in old_queue_candidates(leaf.relative.name, candidates):
                print(f"         ? stari broj {token} → {cave.object_name} "
                      f"(Redni broj {cave.serial_number})")
            for cave, score in suggest(leaf.relative.name, candidates):
                if score < 0.45:
                    break
                print(f"         ~ {score:.2f}  {cave.object_name} (Redni broj {cave.serial_number})")
            continue
        if match.proposed_name:
            print(f"         → {match.proposed_name}")
        elif match.already_correct:
            print("         → (already prefixed with its Redni broj)")
        print(f"         {match.cave.object_name} · Redni broj {match.cave.serial_number}"
              f" · SUE {match.cave.sue_number or '—'} · {match.evidence}")

    remaining = (len(unmatched) if unmatched_only else len(matches)) - shown
    if remaining > 0:
        print(f"\n  … {remaining} more (raise --limit)")

    if apply:
        outcomes = apply_renames(matches)
        renamed = [o for o in outcomes if o.status == "renamed"]
        problems = [o for o in outcomes if o.status != "renamed"]
        print()
        print(f"Renamed {len(renamed)} folder(s).")
        for outcome in problems:
            print(f"  {outcome.status}: {outcome.source.name}"
                  + (f"  ({outcome.detail})" if outcome.detail else ""))
        if problems:
            return EXIT_ERROR

    return EXIT_READY if not unmatched and not conflicts else EXIT_NOT_READY


def cmd_sat_sync(
    settings: Settings,
    satellite: str,
    limit: int,
    use_coordinates: bool,
    out_dir: str | None,
) -> int:
    """Compare the Liburnija sheet against SB and print the three review lists.

    Read-only against both sides — the sheet is a live Google Sheet people type
    into, and nothing here writes to it or to SB. `--out` only saves the three
    lists to files: list 1 as a block to paste into `Svi objekti`, the other two
    as worksheets to tick off by hand.
    """
    rows, path = sheet.load_from_settings(settings)
    if not rows:
        print("No Liburnija export cached. Set `intake.sheet_csv` in config.yaml and")
        print("re-export the sheet (Drive MCP) to that path.", file=sys.stderr)
        return EXIT_ERROR

    reader = SBReader(settings)
    records = resolver.build_sb_index(reader, settings)
    next_serial = resolver.next_serial_number(reader, settings)
    # The block has to paste into `Svi objekti`, so it carries the workbook's
    # own header in the workbook's own order — never a subset of our choosing.
    _header_row, sb_columns = reader.describe_columns()

    overrides = settings.satellites.get(satellite, {})
    resolutions = resolver.resolve_rows(
        rows,
        records,
        use_coordinates=use_coordinates,
        manual={str(k): int(v) for k, v in (overrides.get("manual_matches") or {}).items()},
        out_of_scope=set(overrides.get("out_of_scope") or []),
        confirmed_new=set(overrides.get("confirmed_new") or []),
    )
    result = sync.build(
        resolutions,
        next_serial=next_serial,
        row_defaults={
            str(k): str(v) for k, v in (overrides.get("row_defaults") or {}).items()
        },
    )
    counts = result.counts

    print(f"Liburnija: {len(rows)} row(s) from {path.name}")
    print(f"SB: {len(records)} named row(s), next Redni broj {next_serial}")
    print(
        f"  linked {counts[LinkStatus.LINKED.value]}"
        f" · za SB {counts[LinkStatus.CANDIDATE.value]}"
        f" · nije objekt {counts[LinkStatus.NOT_A_CAVE.value]}"
        f" · neprovjereno {counts[LinkStatus.UNCHECKED.value]}"
        f" · druga udruga {counts[LinkStatus.OUT_OF_SCOPE.value]}"
        f" · sporno {counts[LinkStatus.CONFLICT.value]}"
    )
    if not use_coordinates:
        print("  (coordinate key off — add --coords to propose links by proximity)")
    print("READ ONLY — every change below is carried out by hand.")

    print()
    print(f"1 · ZA SB — {len(result.to_sb)} potvrđen(a) objekt(a) bez retka u SB")
    if result.to_sb:
        print(f"     Redni broj {result.to_sb[0].values['Redni broj']}"
              f" – {result.to_sb[-1].values['Redni broj']}")
        # A missing year is not worth a line each, but it is worth knowing.
        undated = [
            new_row
            for new_row in result.to_sb
            if not new_row.values.get("Godina ili period istraživanja")
        ]
        if undated:
            print(f"     {len(undated)} bez godine — tablica nema datum provjere")
    for new_row in result.to_sb[:limit]:
        values = new_row.values
        print(f"    {values['Redni broj']:>5}  {values['Ime objekta']}"
              + (f"   [sinonim: {values['Sinonimi']}]" if values["Sinonimi"] else ""))
        print(f"           red {new_row.row_id} · {values['X HTRS']}/{values['Y HTRS']}"
              f" · {values['Napomena'] or '—'}")
        if new_row.warning:
            print(f"           ! {new_row.warning}")
    if len(result.to_sb) > limit:
        print(f"    … {len(result.to_sb) - limit} more (raise --limit)")

    print()
    print(f"2 · DOPUNE SB — {len(result.to_sb_edits)} postojeć(ih) redaka bez sinonima")
    for edit in result.to_sb_edits[:limit]:
        print(f"    Redni broj {edit.serial_number:<6} {edit.column}: "
              f"{edit.current} → {edit.proposed}")
        print(f"           ({edit.reason})")
    if len(result.to_sb_edits) > limit:
        print(f"    … {len(result.to_sb_edits) - limit} more (raise --limit)")

    print()
    print(f"3 · ZA TABLICU — {len(result.to_sheet)} ćelij(a) koje SB zna bolje")
    for difference in result.to_sheet[:limit]:
        print(f"    red {difference.row_id:<6} {difference.column:<12}"
              f" {difference.current} → {difference.proposed}")
        print(f"           ({difference.reason})")
    if len(result.to_sheet) > limit:
        print(f"    … {len(result.to_sheet) - limit} more (raise --limit)")

    print()
    print(f"4 · ZA ODLUKU — {len(result.to_decide)}")
    for decision in result.to_decide[:limit]:
        print(f"    red {decision.row_id:<6} {decision.issue}")
        if decision.detail:
            print(f"           {decision.detail}")
    if len(result.to_decide) > limit:
        print(f"    … {len(result.to_decide) - limit} more (raise --limit)")

    if out_dir is not None:
        # `--out` with no path means the conventional spot: one dated folder
        # per run under sb-sync/, grouped by satellite (see sb-sync/README.md).
        target = (
            Path(out_dir)
            if out_dir
            else sync.default_out_dir(satellite, date.today())
        )
        written = sync.write_lists(result, target, tuple(sb_columns))
        print()
        print(f"Written to {target}:")
        for label, path in written.items():
            print(f"  {path.name:<20} {label}")
        print(f"  1-za-sb.csv carries all {len(sb_columns)} SB columns in the")
        print("  workbook's own order: open it in Excel, select the rows under")
        print("  the header, copy, and paste below the last row of `Svi objekti`.")
        print("  Check Redni broj first — it assumes nobody added a row since")
        print("  this run.")

    actionable = result.to_sb or result.to_sb_edits or result.to_sheet
    return EXIT_READY if actionable else EXIT_NOT_READY


def cmd_karta(settings: Settings, serial: int, debug: bool, force: bool) -> int:
    """Part 2.1c: fetch the georef.hr map excerpt for ONE cave by Redni broj.

    Delivers ``SB_<padded Redni broj>.png`` into the shared ``!!Isječci karte``
    Drive folder and upserts the cave's row in ``!georef_zapisi.csv`` there.
    NOTE this WRITES to georef.hr (creates/validates the point server-side)
    — same operation crospeleo-automation performs, one cave per run.
    """
    paths = georef.delivery_paths(settings, serial)
    if paths is None:
        print("No delivery dir configured: set LOCAL_DRIVE_ROOT in .env and", file=sys.stderr)
        print("`archive.map_excerpts_dir` in config.yaml.", file=sys.stderr)
        return EXIT_ERROR

    if settings.sb_mode != "LIVE":
        print(f"⚠ {settings.sb_mode} workbook: Redni broj and coordinates come from a local copy,")
        print("  which may lag the live SB. Verify before trusting the excerpt.")
        print()

    cave = georef.find_by_serial(SBReader(settings), settings, serial)
    if cave is None:
        print(f"No SB row carries Redni broj {serial}.", file=sys.stderr)
        return EXIT_ERROR
    print(f"Redni broj {serial}: {cave.object_name or '<no name>'}"
          + (f" (SUE {cave.sue_number})" if cave.sue_number else ""))

    if paths.png.exists() and not force:
        # A rename invalidates the collection: the name is typed into the
        # georef point and embedded in the zapis, so a stale name means the
        # point itself must be re-made — not just the CSV row edited.
        reason = georef.refresh_reason(settings, serial, cave.object_name or "")
        if reason is None:
            print(f"Already collected: {paths.png}")
            print("Re-run with --force to refresh it (e.g. after a coordinate fix).")
            return 0
        print(f"Collected excerpt is STALE: {reason}")
        print("Re-running the georef flow to refresh the point, excerpt and record …")

    georef_input = georef.build_input(cave, settings)
    if georef_input.x_htrs is None or georef_input.y_htrs is None:
        print("SB row has no usable X HTRS / Y HTRS — nothing to georeference.", file=sys.stderr)
        return EXIT_ERROR
    print(f"HTRS96: X {georef_input.x_htrs} · Y {georef_input.y_htrs}")
    print("Opening georef.hr" + (" (headed, --debug)" if debug else " (headless; --debug shows the browser)")
          + " — this creates/validates the point server-side …")

    result = georef.run_for_cave(settings, georef_input, debug=debug)
    if not result.success:
        print()
        print(f"Georef flow FAILED ({result.georef_status})"
              + (f": {result.error_message}" if result.error_message else ""), file=sys.stderr)
        for warning in result.warnings:
            print(f"  ! {warning}", file=sys.stderr)
        if result.trace_path:
            print(f"  Playwright trace: {result.trace_path}", file=sys.stderr)
        return EXIT_ERROR

    delivered = georef.deliver(settings, cave.object_name or "", serial, result)
    print()
    print(f"Georef zapis: {result.georef_record}")
    print(f"Delivered:")
    print(f"  {delivered.png}")
    print(f"  {delivered.records_csv}  (row {georef.padded_serial(serial)} upserted)")
    for warning in result.warnings:
        print(f"  ! {warning}")
    return 0


def _find_serial_or_exit(settings: Settings, serial: int):
    """The SB row for a Redni broj, or None after printing the error."""
    cave = georef.find_by_serial(SBReader(settings), settings, serial)
    if cave is None:
        print(f"No SB row carries Redni broj {serial}.", file=sys.stderr)
    return cave


def cmd_geo_fetch_data(settings: Settings, include_au: bool) -> int:
    """Provision the gitignored geo data dir (boundaries, RGI, DEM index)."""
    from cave_dossier.geo import provision

    return provision.fetch_data(settings, include_au=include_au)


def cmd_geo_locate(settings: Settings, serial: int, offline: bool = False) -> int:
    """Part 2.1b debug harness: the locality finder for one cave, verbose."""
    from cave_dossier.geo import locality as locality_mod
    from cave_dossier.georef.worker import _coordinate

    cave = _find_serial_or_exit(settings, serial)
    if cave is None:
        return EXIT_ERROR
    x = _coordinate(cave, settings.sb_x_htrs_column)
    y = _coordinate(cave, settings.sb_y_htrs_column)
    if x is None or y is None:
        print("SB row has no usable X HTRS / Y HTRS.", file=sys.stderr)
        return EXIT_ERROR
    sb_lokalitet = cave.values.get(settings.sb_field_columns.get("locality", "Lokalitet"))
    sb_najblize = cave.values.get(settings.sb_field_columns.get("nearest_place", "Najbliže mjesto"))
    sb_lokalitet = None if _is_empty(sb_lokalitet) else str(sb_lokalitet).strip()
    sb_najblize = None if _is_empty(sb_najblize) else str(sb_najblize).strip()

    print(f"Redni broj {serial}: {cave.object_name or '<no name>'}  (X {x:.0f} · Y {y:.0f})")
    finding = locality_mod.build_finder(settings, offline=offline).locate(
        x, y, sb_lokalitet=sb_lokalitet, sb_najblize_mjesto=sb_najblize
    )
    print(f"  Županija:        {finding.zupanija or '—'}")
    print(f"  Grad/općina:     {finding.grad_opcina or '—'}")
    print(f"  Najbliže mjesto: {finding.najblize_mjesto or '—'}"
          + (f"  [{finding.najblize_mjesto_source}]" if finding.najblize_mjesto_source else ""))
    print(f"  Lokalitet:       {finding.lokalitet or '—'}"
          + (f"  [{finding.lokalitet_source}]" if finding.lokalitet_source else ""))
    if finding.rgi_hits:
        label = "offline fallback" if finding.rgi_offline_fallback else "WFS"
        print(f"  RGI ({label}, {len(finding.rgi_hits)} pogodaka ≤ "
              f"{settings.geo_rgi_radius_m:.0f} m):")
        for hit in finding.rgi_hits[:12]:
            distance = f"{hit.distance_m:.0f} m" if hit.distance_m is not None else "?"
            print(f"    {distance:>7}  {hit.geografskoime}  ({hit.vrstaobiljezja or '—'})")
    for note in finding.notes:
        print(f"  ! {note}")
    return 0


def cmd_geo_kota(settings: Settings, serial: int, offline: bool = False) -> int:
    """Part 2.1b debug harness: the elevation finder vs SB's Z, verbose."""
    from cave_dossier.core.normalization import parse_optional_float
    from cave_dossier.geo import elevation as elevation_mod
    from cave_dossier.georef.worker import _coordinate

    cave = _find_serial_or_exit(settings, serial)
    if cave is None:
        return EXIT_ERROR
    x = _coordinate(cave, settings.sb_x_htrs_column)
    y = _coordinate(cave, settings.sb_y_htrs_column)
    if x is None or y is None:
        print("SB row has no usable X HTRS / Y HTRS.", file=sys.stderr)
        return EXIT_ERROR
    print(f"Redni broj {serial}: {cave.object_name or '<no name>'}  (X {x:.0f} · Y {y:.0f})")
    finding = elevation_mod.build_finder(settings, offline=offline).kota(x, y)
    z_column = settings.sb_field_columns.get("entrance_elevation_m", "Z")
    sb_z = parse_optional_float(SBReader._cell_as_text(cave.values, z_column))
    if finding.elevation_m is not None:
        print(f"  Kota ({finding.source_label}): {finding.elevation_m:.0f} m"
              + (f"  [pločica {finding.tile_name}]" if finding.tile_name else ""))
    if sb_z is not None:
        print(f"  SB {z_column}: {sb_z:g} m")
        if finding.elevation_m is not None:
            delta = abs(finding.elevation_m - sb_z)
            verdict = ("OK" if delta <= settings.geo_elevation_tolerance_m
                       else f"NESLAGANJE (> {settings.geo_elevation_tolerance_m:g} m)")
            print(f"  Razlika: {delta:.0f} m — {verdict}")
    elif finding.elevation_m is not None:
        print(f"  SB {z_column}: prazan — kandidat za dopunu (dopune-sb.csv kod `osz prefill`)")
    for note in finding.notes:
        print(f"  ! {note}")
    return 0


def cmd_osz_prefill(settings: Settings, serial: int, debug: bool, force_karta: bool,
                    offline: bool = False) -> int:
    """Part 2.1b: SB row -> prefilled OSZ DOCX with the map excerpt embedded."""
    from cave_dossier.osz import prefill

    if settings.sb_mode != "LIVE":
        print(f"⚠ {settings.sb_mode} workbook: SB data comes from a local copy,")
        print("  which may lag the live SB. Verify before distributing the zapisnik.")
        print()
    try:
        outcome = prefill.run_prefill(settings, serial, debug=debug,
                                      force_karta=force_karta, offline=offline)
    except prefill.PrefillError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    result = outcome.result
    print(f"Redni broj {serial}: {result.cave_name or '<no name>'}"
          + (f" (SUE {result.sue_number})" if result.sue_number else ""))
    filled = {k: v for k, v in result.fields.items() if v.value is not None}
    print(f"Popunjeno {len(filled)} polja; isječak karte: {result.karta_status}")
    for key, fv in filled.items():
        value = " ".join(fv.value.split())  # narrative fields span lines
        if len(value) > 70:
            value = value[:67] + "…"
        print(f"  {key:<18} {value}" + (f"  [{fv.source}]" if fv.source and fv.source != "sb" else ""))
    for mismatch in result.mismatches:
        print(f"  ⚠ {mismatch}")
    for note in result.notes:
        print(f"  ! {note}")
    print()
    if outcome.delivered_path is not None:
        print(f"Delivered: {outcome.delivered_path}")
    print(f"Run dir:   {outcome.docx_path.parent}")
    if outcome.sb_updates_path is not None:
        print(f"Dopune za SB ({len(result.sb_updates)}): {outcome.sb_updates_path}")
        print("  (upiši ručno u Svi objekti — alat nikad ne piše u SB)")
    return 0


def cmd_osz_fetch(settings: Settings, serial: int, osz_path_arg: str | None,
                  osz_dir_arg: str | None) -> int:
    """Part 2.1b fetcher: read a FILLED OSZ and propose the SB backfill.

    The zapisnik is found in the cave's SB_<broj>_… intake dir by default
    (user, 2026-08-30); --osz-dir overrides the search root, --osz points
    at an exact file. Never writes SB — proposals land in
    dopune-sb-iz-osz.csv for a person to carry into Excel (write-back is
    M6). Exit 1 when there is something to carry over, 0 when SB already
    holds everything, 99 on errors.
    """
    from cave_dossier.osz import backfill as backfill_mod
    from cave_dossier.osz import prefill as prefill_mod
    from cave_dossier.osz.reader import OszReadError, read_osz

    cave = _find_serial_or_exit(settings, serial)
    if cave is None:
        return EXIT_ERROR

    if osz_path_arg:
        osz_path = Path(osz_path_arg).resolve()
        if not osz_path.exists():
            print(f"Filled OSZ not found: {osz_path}", file=sys.stderr)
            return EXIT_ERROR
    else:
        override = Path(osz_dir_arg).resolve() if osz_dir_arg else None
        location = backfill_mod.locate_filled_osz(settings, serial, override_dir=override)
        for note in location.notes:
            print(f"  ! {note}")
        if location.path is None:
            print(f"Nema ispunjenog OSZ-a za Redni broj {serial} — "
                  "predaj ga u SB_<broj>_… mapu ili pokaži s --osz / --osz-dir.",
                  file=sys.stderr)
            return EXIT_ERROR
        osz_path = location.path

    print(f"Redni broj {serial}: {cave.object_name or '<no name>'}"
          + (f" (SUE {cave.sue_number})" if cave.sue_number else ""))
    print(f"Čitam: {osz_path}")
    try:
        osz_values = read_osz(osz_path)
    except OszReadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR

    result = backfill_mod.build_backfill(cave, osz_values, settings)
    print()
    if result.matches:
        print(f"Slaže se ({len(result.matches)}):")
        for match in result.matches:
            print(f"  ✓ {match}")
    if result.proposals:
        print(f"\nPRIJEDLOZI za SB ({len(result.proposals)}):")
        for p in result.proposals:
            arrow = f"'{p.current}' -> " if p.current else ""
            print(f"  + {p.column}: {arrow}'{p.proposed}'  [{p.reason}]")
    if result.differences:
        print(f"\nRazlike — SB zadržan, provjeri ručno ({len(result.differences)}):")
        for diff in result.differences:
            print(f"  ⚠ {diff}")
    for note in result.notes:
        print(f"  ! {note}")

    if result.proposals:
        run_dir = prefill_mod.RUNS_DIR / georef.padded_serial(serial)
        run_dir.mkdir(parents=True, exist_ok=True)
        csv_path = run_dir / "dopune-sb-iz-osz.csv"
        backfill_mod.write_backfill_csv(csv_path, serial, result)
        print(f"\nDopune za SB: {csv_path}")
        print("  (upiši ručno u Svi objekti — alat nikad ne piše u SB)")
        return EXIT_READY
    print("\nSB već sadrži sve što ovaj OSZ nudi.")
    return EXIT_NOT_READY


def cmd_people_list(settings: Settings) -> int:
    """The people registry, each person with their aliases and linked izjave."""
    from cave_dossier.people.registry import PersonRegistry
    from cave_dossier.people.statements import StatementIndex, scan_izjave, statements_dir

    registry = PersonRegistry.load(settings.people_registry_path)
    print(f"Registar osoba: {settings.people_registry_path}")
    print(f"  {len(registry)} osoba · {len(registry.key_map)} ključeva "
          f"({registry.stats.keys_derived} izvedenih, {registry.stats.keys_curated} ručnih)")
    if registry.stats.collisions:
        print(f"  ⚠ kolizije (ključ ne razrješava nikoga): {', '.join(registry.stats.collisions)}")
    if not registry:
        print("  (prazan — dodaj osobe u registry.json; `people check` predlaže koga)")
        return EXIT_NOT_READY

    directory = statements_dir(settings)
    index = None
    if directory is not None and directory.exists():
        index = StatementIndex(scan_izjave(directory), registry)
        print(f"Izjave: {len(index.izjave)} u {directory}")
    else:
        print("Izjave: mapa nedostupna (Drive?) — prikaz bez poveznica")
    print()

    for person in sorted(registry.people, key=lambda p: p.name.casefold()):
        linked = index.statements_for(person.name) if index else []
        mark = "✓" if linked else ("·" if index is None else "✗")
        extras = []
        if person.deceased:
            extras.append("† (izjava nije potrebna)")
        if person.aliases:
            extras.append(f"alias: {', '.join(person.aliases)}")
        if person.society:
            extras.append(f"[{person.society}]")
        files = ", ".join(izjava.path.name for izjava in linked)
        line = f"  {mark} {person.name:<26}"
        if extras:
            line += f" {'  '.join(extras)}"
        if files:
            line += f"  {files}"
        print(line)
    return 0


def cmd_people_check(settings: Settings, limit: int) -> int:
    """Registry-wide audit: aliases used anywhere + who is missing an izjava.

    The registry-level face of the statement gates: (1) registry people with
    no izjava on file, (2) izjava files whose person resolves to nobody,
    (3) alias-key collisions, (4) every SB author cell swept through the
    registry — names that resolve to no one. Writes the person↔izjava JSON
    snapshot under runs/people/.
    """
    from cave_dossier.core.config import FEATURE_ROOT
    from cave_dossier.people.registry import PersonRegistry
    from cave_dossier.people.statements import (
        StatementIndex,
        scan_izjave,
        statements_dir,
        write_index_json,
    )
    from cave_dossier.sb.audit import iter_author_names

    registry = PersonRegistry.load(settings.people_registry_path)
    directory = statements_dir(settings)
    if directory is None or not directory.exists():
        print("Statements dir unreachable: set LOCAL_DRIVE_ROOT in .env and", file=sys.stderr)
        print("`archive.statements_dir` in config.yaml (and mount Drive).", file=sys.stderr)
        return EXIT_ERROR

    izjave = scan_izjave(directory)
    index = StatementIndex(izjave, registry)
    print(f"Registar: {len(registry)} osoba ({settings.people_registry_path.name})")
    print(f"Izjave:   {len(izjave)} u {directory}")

    findings = False

    if registry.stats.collisions:
        findings = True
        print()
        print(f"⚠ Kolizije ključeva ({len(registry.stats.collisions)}) — ni jedna strana se ne razrješava:")
        for key in registry.stats.collisions:
            print(f"    {key}")

    # SB sweep runs FIRST so both people-lists can carry the caves and their
    # exploration years — an old year is the signal a statement will be hard to
    # get (user, 2026-08-30). Deduped on the normalized key so "R.Reš" and
    # "R. Reš" are one row (first-seen spelling kept).
    from cave_dossier.core.normalization import normalize_lookup_key

    year_pattern = re.compile(r"(?:19|20)\d{2}")

    def cave_year(cave) -> int | None:
        raw = cave.values.get(settings.sb_exploration_period_column)
        if raw is None or _is_empty(raw):
            return None
        years = year_pattern.findall(str(raw))
        return min(int(year) for year in years) if years else None

    unresolved: dict[str, list[tuple[str, int | None]]] = {}
    authored: dict[str, list[tuple[str, int | None]]] = {}  # registry name -> caves
    spelling: dict[str, str] = {}
    row_count = 0
    for cave, names in iter_author_names(SBReader(settings), settings):
        row_count += 1
        entry = (cave.object_name or f"r{cave.row_number}", cave_year(cave))
        for name in names:
            person = registry.resolve(name)
            if person is None:
                key = normalize_lookup_key(name)
                spelling.setdefault(key, name)
                unresolved.setdefault(spelling[key], []).append(entry)
            else:
                authored.setdefault(person.name, []).append(entry)

    def year_span(caves: list[tuple[str, int | None]]) -> str:
        years = sorted({year for _label, year in caves if year is not None})
        if not years:
            return "god. ?"
        return str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"

    def latest_year(caves: list[tuple[str, int | None]]) -> int:
        years = [year for _label, year in caves if year is not None]
        return max(years) if years else 0

    def cave_list(caves: list[tuple[str, int | None]], shown: int = 3) -> str:
        parts = [f"{label} ({year or '?'})" for label, year in caves[:shown]]
        return ", ".join(parts) + (" …" if len(caves) > shown else "")

    missing = index.missing_statement_people()
    # Newest activity first: a recent author is chase-able, an old one is the
    # hard case — and pokojni (deceased: true) are exempt and not listed at all.
    missing.sort(key=lambda person: -latest_year(authored.get(person.name, [])))
    print()
    print(f"1 · BEZ IZJAVE — {len(missing)} osoba iz registra nema nijednu izjavu")
    for person in missing[:limit]:
        caves = authored.get(person.name, [])
        if caves:
            print(f"    ✗ {person.name:<26} {len(caves)}× autor, {year_span(caves):<10} "
                  f"({cave_list(caves)})")
        else:
            print(f"    ✗ {person.name:<26} (nije autor nijednog SB retka)")
    if len(missing) > limit:
        print(f"    … {len(missing) - limit} more (raise --limit)")
    findings = findings or bool(missing)

    orphans = index.orphan_izjave()
    print()
    print(f"2 · IZJAVE BEZ OSOBE — {len(orphans)} datoteka čiji potpisnik nije u registru")
    for izjava in orphans[:limit]:
        print(f"    ? {izjava.path.name}   → dodaj {{\"name\": \"{izjava.person}\"}} u registry.json")
    findings = findings or bool(orphans)

    print()
    print(f"3 · SB AUTORI IZVAN REGISTRA — {len(unresolved)} imena "
          f"(pregledano {row_count} redaka; broje se samo autori u obliku "
          f"N.Prezime — sve ostalo su pronalazači, bez obveze izjave)")
    ordered = sorted(
        unresolved.items(),
        key=lambda item: (-latest_year(item[1]), -len(item[1])),
    )
    for name, caves in ordered[:limit]:
        print(f"    ? {name:<26} {len(caves)}×  {year_span(caves):<10} ({cave_list(caves)})")
    if len(unresolved) > limit:
        print(f"    … {len(unresolved) - limit} more (raise --limit)")
    findings = findings or bool(unresolved)

    out_path = FEATURE_ROOT / "runs" / "people" / "statements-index.json"
    write_index_json(index, out_path, source_dir=directory)
    print()
    print(f"Poveznice osoba ↔ izjava: {out_path}")

    if not findings:
        print("Sve se slaže: svaka osoba ima izjavu, svaka izjava osobu, svi SB autori poznati.")
        return EXIT_READY
    return EXIT_NOT_READY


# ── Entry point ────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cavedossier",
        description="SurveyScraper5 stage 2: SB communication + cave dossier builder.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sb = subparsers.add_parser("sb", help="Read-only SB (Speleo baza) inspection")
    sb_sub = sb.add_subparsers(dest="sb_command", required=True)

    sb_sub.add_parser("columns", help="Detected header row + all column names")

    inspect = sb_sub.add_parser("inspect", help="Dump a cave's SB row")
    inspect.add_argument(
        "--cave",
        required=True,
        help="Object name, SUE number, or plaque number (diacritic-insensitive; name substring works)",
    )

    sb_sub.add_parser("stats", help="Sheet inventory + row/fill counts")

    audit = sb_sub.add_parser(
        "audit-authors",
        help="List 'Autori nacrta ili izvor' cells the name splitter cannot read confidently",
    )
    audit.add_argument("--limit", type=int, default=40, help="How many rows to print (default 40)")

    unclassified = sb_sub.add_parser(
        "unclassified",
        help="Named rows with no SUE number and no Napomena flag (in none of SB's views)",
    )
    unclassified.add_argument("--limit", type=int, default=60, help="How many rows to print")

    report = subparsers.add_parser(
        "report",
        help="Per-cave dossier: what is present, what is missing, what blocks",
    )
    report.add_argument(
        "--cave",
        required=True,
        help="Object name, SUE number, or plaque number (must resolve to ONE row)",
    )
    report.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit the dossier as JSON (raw SB row omitted) instead of the text report",
    )
    report.add_argument(
        "--gate",
        choices=["sue", "crospeleo"],
        default="sue",
        help="Which gate the EXIT CODE reports on (both are always printed): "
             "sue = society katastarski broj (default), crospeleo = national cadastre",
    )

    intake = subparsers.add_parser(
        "intake",
        help="Field-data intake folders (!!!Digitalizacija/!Za digitalizirat)",
    )
    intake_sub = intake.add_subparsers(dest="intake_command", required=True)
    intake_map = intake_sub.add_parser(
        "map",
        help="Map each leaf folder to its SB row and propose an SB_<Redni broj> prefix",
    )
    intake_map.add_argument("--limit", type=int, default=80, help="How many folders to print")
    intake_map.add_argument(
        "--unmatched-only", action="store_true", dest="unmatched_only",
        help="Print only the folders that could not be resolved",
    )
    intake_map.add_argument(
        "--apply", action="store_true",
        help="Rename the folders in place (default is a dry run)",
    )

    sat = subparsers.add_parser(
        "sat",
        help="Satellite tables around SB (Liburnija / LiDAR Kristal sheet, …)",
    )
    sat_sub = sat.add_subparsers(dest="sat_command", required=True)
    sat_sync = sat_sub.add_parser(
        "sync",
        help="Difference lists between a satellite table and SB (read-only)",
    )
    sat_sync.add_argument(
        "satellite",
        nargs="?",
        default="liburnija",
        choices=["liburnija"],
        help="Which satellite to compare (default: liburnija)",
    )
    sat_sync.add_argument("--limit", type=int, default=40, help="Rows printed per list")
    sat_sync.add_argument(
        "--coords",
        action="store_true",
        dest="use_coordinates",
        help="Also propose links by coordinate proximity (auto only under "
             f"{resolver.AUTO_LINK_M:.0f} m and unambiguous; everything else is "
             "listed for a decision)",
    )
    sat_sync.add_argument(
        "--out",
        dest="out_dir",
        nargs="?",
        const="",
        metavar="DIR",
        help="Write the review lists — 1-za-sb.csv (paste into Svi objekti), "
             "2-dopune-sb.txt, 3-za-tablicu.txt, 4-za-odluku.txt. Bare --out uses "
             "sb-sync/<satellite>/<today>/; pass DIR to put them elsewhere",
    )

    karta = subparsers.add_parser(
        "karta",
        help="Part 2.1c — isječak karte: fetch the georef.hr map excerpt for one cave",
    )
    karta.add_argument(
        "redni_broj",
        type=int,
        help="SB Redni broj of the cave (the only input; coordinates come from its SB row)",
    )
    karta.add_argument(
        "--debug",
        action="store_true",
        help="Run the browser headed with step screenshots (default is headless)",
    )
    karta.add_argument(
        "--force",
        action="store_true",
        help="Refresh an excerpt that is already in !!Isječci karte (default skips it)",
    )

    geo = subparsers.add_parser(
        "geo",
        help="Part 2.1b — locality + elevation finders over HTRS96 coordinates",
    )
    geo_sub = geo.add_subparsers(dest="geo_command", required=True)
    fetch_data = geo_sub.add_parser(
        "fetch-data",
        help="Provision data/geo: DGU boundary GeoPackages + RGI gazetteer (open data)",
    )
    fetch_data.add_argument(
        "--no-inspire-au",
        action="store_false",
        dest="include_au",
        help="Skip the ~209 MB INSPIRE AU download when boundary files are missing",
    )
    offline_help = ("Never touch the network: RGI answers from the local "
                    "rgi_named_places.gpkg, elevation only from cached DEM tiles")
    geo_locate = geo_sub.add_parser(
        "locate",
        help="Županija / grad-općina / najbliže mjesto / lokalitet for one cave (debug)",
    )
    geo_locate.add_argument("redni_broj", type=int, help="SB Redni broj of the cave")
    geo_locate.add_argument("--offline", action="store_true", help=offline_help)
    geo_kota = geo_sub.add_parser(
        "kota",
        help="Kota ulaza from the DGU elevation grid vs SB's Z for one cave (debug)",
    )
    geo_kota.add_argument("redni_broj", type=int, help="SB Redni broj of the cave")
    geo_kota.add_argument("--offline", action="store_true", help=offline_help)

    osz = subparsers.add_parser(
        "osz",
        help="Part 2.1b — OSZ builder (v10 template)",
    )
    osz_sub = osz.add_subparsers(dest="osz_command", required=True)
    osz_prefill = osz_sub.add_parser(
        "prefill",
        help="Prefill the OSZ template from SB + finders, embed the isječak karte, "
             "deliver SB_<broj>_OSZ.docx",
    )
    osz_prefill.add_argument(
        "redni_broj",
        type=int,
        help="SB Redni broj of the cave (the only input; everything else is derived)",
    )
    osz_prefill.add_argument(
        "--debug",
        action="store_true",
        help="If the karta flow runs, run its browser headed (default is headless)",
    )
    osz_prefill.add_argument(
        "--force-karta",
        action="store_true",
        help="Re-fetch the map excerpt even when one is already collected",
    )
    osz_prefill.add_argument(
        "--offline",
        action="store_true",
        help="Never touch the network: local RGI gpkg + cached DEM tiles only, "
             "and the georef.hr flow is skipped (an already-collected excerpt "
             "is still embedded)",
    )
    osz_fetch = osz_sub.add_parser(
        "fetch",
        help="Read a FILLED OSZ and propose the SB backfill (pločica, ime/sinonimi, "
             "duljina/dubina, godina, autori) — review CSV, never writes SB",
    )
    osz_fetch.add_argument(
        "redni_broj",
        type=int,
        help="SB Redni broj of the cave the zapisnik belongs to",
    )
    osz_fetch.add_argument(
        "--osz-dir",
        dest="osz_dir",
        metavar="DIR",
        help="Where to look for the cave's SB_<broj>_… dir holding the filled "
             "OSZ (default: the intake dir, !!!Digitalizacija/!Za digitalizirat)",
    )
    osz_fetch.add_argument(
        "--osz",
        dest="osz_path",
        metavar="FILE",
        help="Exact filled OSZ DOCX, skipping the dir search entirely",
    )

    people = subparsers.add_parser(
        "people",
        help="Registar osoba — authors, their aliases, and their izjave",
    )
    people_sub = people.add_subparsers(dest="people_command", required=True)
    people_sub.add_parser(
        "list",
        help="Every registry person with derived/curated aliases and linked izjave",
    )
    people_check = people_sub.add_parser(
        "check",
        help="Audit: people without an izjava, izjave without a person, SB author "
             "names outside the registry; writes runs/people/statements-index.json",
    )
    people_check.add_argument("--limit", type=int, default=40, help="Rows printed per list")

    photos = subparsers.add_parser(
        "photos",
        help="Part 2.1d — entrance-photo processing (rename + downsize)",
    )
    photos_sub = photos.add_subparsers(dest="photos_command", required=True)
    match_queued = photos_sub.add_parser(
        "match-queued",
        help="Propose a 'Redni broj' prefix for each photo in the za-istražit staging folder",
    )
    match_queued.add_argument("--limit", type=int, default=80, help="How many files to print")
    check_flag = photos_sub.add_parser(
        "check-flag",
        help="Confirm every cave with a staged photo says 'Fotografija ulaza = DA' in SB",
    )
    check_flag.add_argument("--limit", type=int, default=20, help="Files listed per cave")

    match_queued.add_argument(
        "--apply",
        action="store_true",
        help="Perform the proposed renames in place (default is a dry run). "
             "Conflicts, unmatched files and already-correct names are never touched, "
             "and an existing target is never overwritten.",
    )

    photos_process = photos_sub.add_parser(
        "process",
        help="Archive-ready copies of one cave's entrance photos: downsize to "
             "screen size and name them SB_<broj>_<Ime>_<Autor>_<n>.jpg",
    )
    photos_process.add_argument(
        "redni_broj",
        type=int,
        help="The cave's Redni broj — its SB_<broj>_… intake folder holds the raw photos",
    )
    photos_process.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the plan. The command writes by default — it never "
             "touches the originals, so there is nothing to guard against.",
    )
    # Accepted silently so an --apply still in someone's shell history keeps
    # working; writing is the default now, so it is a no-op.
    photos_process.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)

    pull_staged = photos_sub.add_parser(
        "pull-staged",
        help="Move a cave's photos out of the za-istražit queue into its "
             "SB_<broj>_… intake folder (creating it if needed)",
    )
    pull_staged.add_argument("redni_broj", type=int, help="The cave's Redni broj")
    pull_staged.add_argument(
        "--apply",
        action="store_true",
        help="Perform the moves (default is a dry run). Unlike `photos "
             "process`, this MOVES files out of the queue and may create a "
             "folder, so it is guarded. An existing target is never overwritten.",
    )
    photos_process.add_argument(
        "--from",
        dest="from_dir",
        metavar="DIR",
        help="Read the raw photos from this folder instead of the cave's intake leaf",
    )
    photos_process.add_argument(
        "--author",
        metavar="NAME",
        help="Use this photo author instead of the OSZ's 'Autor fotografije ulaza' "
             "(a full name is abbreviated the archive's way: Lovel Kukuljan -> LKukuljan)",
    )
    photos_process.add_argument(
        "--osz",
        dest="osz_path",
        metavar="FILE",
        help="Read the author from this exact OSZ DOCX, skipping the folder search",
    )
    photos_process.add_argument(
        "--long-edge",
        type=int,
        metavar="PX",
        help="Long-edge target in pixels (default: photos.target_long_edge_px in config.yaml)",
    )
    photos_process.add_argument(
        "--max-bytes",
        type=int,
        metavar="N",
        help="Per-file size budget (default: photos.target_max_bytes in config.yaml)",
    )
    photos_process.add_argument(
        "--overwrite",
        action="store_true",
        help="Rewrite copies that already exist (default is to skip them) — use "
             "after changing --long-edge",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252, which cannot print Croatian
    # diacritics — reconfigure instead of crashing on the first š/č/ž.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)

    try:
        settings = load_settings()
        _print_banner(settings)
        if args.command == "sb":
            if args.sb_command == "columns":
                return cmd_sb_columns(settings)
            if args.sb_command == "inspect":
                return cmd_sb_inspect(settings, args.cave)
            if args.sb_command == "stats":
                return cmd_sb_stats(settings)
            if args.sb_command == "audit-authors":
                return cmd_sb_audit_authors(settings, args.limit)
            if args.sb_command == "unclassified":
                return cmd_sb_unclassified(settings, args.limit)
        if args.command == "people":
            if args.people_command == "list":
                return cmd_people_list(settings)
            if args.people_command == "check":
                return cmd_people_check(settings, args.limit)
        if args.command == "photos":
            if args.photos_command == "match-queued":
                return cmd_photos_match_queued(settings, args.limit, args.apply)
            if args.photos_command == "check-flag":
                return cmd_photos_check_flag(settings, args.limit)
            if args.photos_command == "pull-staged":
                return cmd_photos_pull_staged(settings, args.redni_broj, args.apply)
            if args.photos_command == "process":
                return cmd_photos_process(
                    settings, args.redni_broj, args.dry_run, args.from_dir,
                    args.author, args.osz_path, args.long_edge, args.max_bytes,
                    args.overwrite,
                )
        if args.command == "sat":
            if args.sat_command == "sync":
                return cmd_sat_sync(
                    settings,
                    args.satellite,
                    args.limit,
                    args.use_coordinates,
                    args.out_dir,
                )
        if args.command == "intake":
            if args.intake_command == "map":
                return cmd_intake_map(settings, args.limit, args.apply, args.unmatched_only)
        if args.command == "karta":
            return cmd_karta(settings, args.redni_broj, args.debug, args.force)
        if args.command == "geo":
            if args.geo_command == "fetch-data":
                return cmd_geo_fetch_data(settings, args.include_au)
            if args.geo_command == "locate":
                return cmd_geo_locate(settings, args.redni_broj, args.offline)
            if args.geo_command == "kota":
                return cmd_geo_kota(settings, args.redni_broj, args.offline)
        if args.command == "osz":
            if args.osz_command == "prefill":
                return cmd_osz_prefill(settings, args.redni_broj, args.debug,
                                       args.force_karta, args.offline)
            if args.osz_command == "fetch":
                return cmd_osz_fetch(settings, args.redni_broj, args.osz_path, args.osz_dir)
        if args.command == "report":
            return cmd_report(settings, args.cave, args.as_json, args.gate)
        return EXIT_ERROR
    except (ConfigError, SBWorkbookUnreachable) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
