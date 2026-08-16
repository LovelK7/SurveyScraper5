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

## Open until M6

- Exact dimension column names + formats (integer meters? decimal?).
- Whether write-back happens automatically at delivery or as an explicit
  `cavedossier sb write --cave X` confirmation step (lean: explicit, with a
  preview of before→after values, mirroring crospeleo's `sb-mark` preview).
