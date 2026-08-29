"""``cavedossier`` — CLI for SurveyScraper5 stage 2.

Commands: read-only SB inspection (`sb columns` / `sb inspect` / `sb stats`,
M1) and the per-cave dossier report (`report`, M2).  Every command starts with
a mode banner so it is always obvious whether the SANDBOX copy or the LIVE
workbook is being read.
"""

from __future__ import annotations

import argparse
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
    """Propose (and with --apply, perform) a Redni broj prefix for staged photos (2.1d)."""
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

    resolutions = resolver.resolve_rows(rows, records, use_coordinates=use_coordinates)
    result = sync.build(resolutions, next_serial=next_serial)
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
    print(f"2 · ZA TABLICU — {len(result.to_sheet)} ćelij(a) koje SB zna bolje")
    for difference in result.to_sheet[:limit]:
        print(f"    red {difference.row_id:<6} {difference.column:<12}"
              f" {difference.current} → {difference.proposed}")
        print(f"           ({difference.reason})")
    if len(result.to_sheet) > limit:
        print(f"    … {len(result.to_sheet) - limit} more (raise --limit)")

    print()
    print(f"3 · ZA ODLUKU — {len(result.to_decide)}")
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
        written = sync.write_lists(result, target)
        print()
        print(f"Written to {target}:")
        for label, path in written.items():
            print(f"  {path.name:<20} {label}")
        print("  1-za-sb.tsv: open it, select the rows under the header, copy, and")
        print("  paste below the last row of `Svi objekti`. Check Redni broj first —")
        print("  it assumes nobody added a row since this run.")

    return EXIT_READY if (result.to_sb or result.to_sheet) else EXIT_NOT_READY


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
        help="Map each leaf folder to its SB row and propose a Redni broj prefix",
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
        help="Write all three lists — 1-za-sb.tsv (paste into Svi objekti), "
             "2-za-tablicu.txt, 3-za-odluku.txt. Bare --out uses "
             "sb-sync/<satellite>/<today>/; pass DIR to put them elsewhere",
    )

    photos = subparsers.add_parser(
        "photos",
        help="Part 2.1d — entrance-photo processing (read-only for now)",
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
        if args.command == "photos":
            if args.photos_command == "match-queued":
                return cmd_photos_match_queued(settings, args.limit, args.apply)
            if args.photos_command == "check-flag":
                return cmd_photos_check_flag(settings, args.limit)
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
        if args.command == "report":
            return cmd_report(settings, args.cave, args.as_json, args.gate)
        return EXIT_ERROR
    except (ConfigError, SBWorkbookUnreachable) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
