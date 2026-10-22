# SB write-back — design note (implementation deferred to M6)

## What gets written

After a survey is finished (2.1a done), the cave's SB row is updated with the new
survey-derived data — at minimum the **dimensions**. Confirmed against the real
workbook (`sb columns`, 2026-08-16): the columns are **`Duljina`** (length) and
**`Dubina`** (depth), plain meters (e.g. Konglomeratača: 18 / 11). Candidates for
the same write-back batch: `Godina zadnjeg istraživanja` (year of last
exploration), possibly `Link Nacrt` / `Link Zapisnik` (SUE-keyed links). Never
more than the agreed cells — SB is a shared operational workbook and its schema
is owned by the society, not by tools (inherited hard rule: **never add columns
to SB**).

## How (the only safe path)

Via `sb/safe_io.py: write_cell_via_excel_com` (already ported, dormant):

1. Preflight: workbook reachable (`check_workbook_present`) + not open in Excel
   (`check_excel_not_open`, `~$` lock file).
2. Daily-rotated timestamped backup beside the workbook (`create_backup`).
3. xlwings / Excel COM writes the cell(s) and **Excel itself saves** — the only
   path that preserves VBA macros, data validations, FuzzyLookup scratch sheets,
   conditional formats. openpyxl save would strip validations silently.
4. Log every write (sheet, R/C, value, backup name).

Requires `pip install -e ".[sb-write]"` (xlwings; Windows + Excel only).

## Rehearsal protocol (before touching the live workbook)

1. Run the write against the **sandbox copy** (`SB_WORKBOOK_PATH` set); verify in
   Excel that macros/validations/derived sheets survived and only the target cells
   changed.
2. Repeat on a **fresh sandbox copy** to prove idempotency (re-running must not
   duplicate or corrupt).
3. Only then unset `SB_WORKBOOK_PATH` and write live — with the automatic backup
   as rollback.

## Settled 2026-10-22 (built as `cavedossier deliver`)

- Write-back happens **at delivery**, after the archivist's explicit
  confirmation on the 6P page, which shows every cell before → after first.
- It is multi-cell, in one session: `safe_io.write_row_via_excel_com`. The row
  is re-found by Redni broj inside Excel, a guard callback runs before the
  write, and formula cells are refused. See
  [m6-delivery-design.md](m6-delivery-design.md#step-6--apply).
- Dimensions are plain numbers, decimals allowed (live SB: `18.5`, `21.5`), and
  are filled only when the SB cell is empty.
- `Link Nacrt`, `Link Zapisnik` and `Godina zadnjeg istraživanja` are formulas
  and are never written.
- Rehearsed on a sandbox **copy** 2026-10-22:
  - cells written;
  - formulas, the 3 data validations and all 18 VBA modules intact;
  - a second run refused.

## Open until M6 (as written 2026-08-16)

- Exact dimension column names + formats (integer meters? decimal?).
- Whether write-back happens automatically at delivery or as an explicit
  `cavedossier sb write --cave X` confirmation step (lean: explicit, with a
  preview of before→after values, mirroring crospeleo's `sb-mark` preview).
