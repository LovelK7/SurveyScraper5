# Porting ledger — code copied from crospeleo-automation

Rule ([CLAUDE.md](../../../CLAUDE.md)): code may be COPIED from the read-only
`../crospeleo-automation` repo and adapted freely; every copy is logged here.
Source paths are under `crospeleo-automation/src/crospeleo_automation/`.

| Date | Source | Dest (`src/cave_dossier/`) | What changed |
|---|---|---|---|
| 2026-08-16 | `services/normalization.py` | `core/normalization.py` | Verbatim (diacritic-folding `normalize_lookup_key`, `cleanup_whitespace`, `split_semicolon_values`, `parse_optional_float`). |
| 2026-08-16 | `services/sb_safe_io.py` | `sb/safe_io.py` | Near-verbatim: kept lock-file preflight, `SBWorkbookUnreachable` + three-mode Drive-offline diagnosis, daily-rotated backups, xlwings COM single-cell write (dormant until M6 — xlwings not installed). Docstring paths adjusted; `[sb-write]` extra name kept. |
| 2026-08-16 | `services/sb_loader.py` | `sb/loader.py` | Kept: `_read_sheet` (header=None read + preflight), `_detect_header_row` scoring, `_canonicalize_columns`, `_header_text`, `_resolve_sheet_name`, `_cell_as_text`, `__excel_row_number`, openpyxl data-validation warning suppression. **Stripped:** queue/round logic (`load_queue`, `RoundProgress`, `_is_target_round`, `_is_marked_as_*`), `SubmissionLedger`, dossier seeding, `Georeference`. **New:** `SBReader` API — `sheet_names()`, `load_rows()`, `describe_columns()`, `find_caves(query)` (name/SUE/plaque, diacritic-insensitive exact + name-substring fallback), `stats()`, `CaveRow` dataclass. |
| 2026-08-16 | `docs/EXCEL_WORKBOOK_SAFETY.md` | `docs/EXCEL_WORKBOOK_SAFETY.md` | Copied with a provenance header; module paths in it refer to crospeleo-automation, principles apply verbatim to `sb/safe_io.py`. |

Planned ports (M2+): `models/dossier.py` (→ `CaveDossier`), `services/name_resolver.py`,
`services/statement_checker.py`, `services/drive_resolver.py`,
`services/readiness_validator.py`, `georef/` package (M3), OSZ FieldSpec tables from
`services/osz_parser.py` as output validator (M4).
