"""``cavedossier`` — CLI for SurveyScraper5 stage 2.

Commands: read-only SB inspection (`sb columns` / `sb inspect` / `sb stats`,
M1) and the per-cave dossier report (`report`, M2).  Every command starts with
a mode banner so it is always obvious whether the SANDBOX copy or the LIVE
workbook is being read.
"""

from __future__ import annotations

import argparse
import sys

from cave_dossier.core.config import ConfigError, Settings, load_settings
from cave_dossier.dossier import build_from_sb, evaluate, render
from cave_dossier.sb.loader import SBReader
from cave_dossier.sb.safe_io import SBWorkbookUnreachable


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
        return 1
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


def cmd_report(settings: Settings, query: str, as_json: bool) -> int:
    """Per-cave dossier report (M2).

    Only SB is gathered so far, so most Tablica 2 rules come back as
    "not checked yet" rather than as blockers — see dossier/gating.py.
    """
    reader = SBReader(settings)
    matches = reader.find_caves(query)
    if not matches:
        print(f"No SB row matches {query!r} (tried object name, SUE number, plaque).")
        return 2
    if len(matches) > 1:
        print(f"{len(matches)} rows match {query!r} — refine the query:")
        for cave in matches:
            print(f"  row {cave.row_number}: {cave.object_name} (SUE {cave.sue_number or '—'})")
        return 2

    dossier = build_from_sb(matches[0], settings)
    evaluate(dossier)
    if as_json:
        print(dossier.model_dump_json(indent=2, exclude={"sb_record"}))
    else:
        print(render(dossier))
    return 0 if dossier.readiness.ready else 1


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
        if args.command == "report":
            return cmd_report(settings, args.cave, args.as_json)
        return 2
    except (ConfigError, SBWorkbookUnreachable) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
