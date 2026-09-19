# 2B — Speleo baza

**The master registry of which caves exist**, and the satellite tables around it.
Everything upstream feeds it; everything downstream reads it.

## What it does

**SB** is `!Speleo_baza_SUE_v3.0.xlsm` — a live, macro-heavy, shared Excel
workbook on a Google Drive Desktop mount. It is ground truth for coordinates,
names, synonyms, dimensions and lifecycle state. This stage reads it safely and
never writes to it (write-back is 6P, at M6).

**Satellites** are the other tables holding cave data: the *Liburnija* Google
Sheet (the LiDAR Kristal table, edited live in the field), plus `Literatura` and
`Katastar RH` inside the workbook. None carries an SB row number, so they are
joined on shared keys — never on a local row id.

## Commands

```powershell
cavedossier sb stats               # sheet inventory + row/fill counts
cavedossier sb columns             # detected header row + all column names
cavedossier sb inspect --cave 1220 # dump one cave's SB row
cavedossier sb audit-authors       # author cells the name splitter cannot read
cavedossier sb unclassified        # named rows in none of SB's views

cavedossier sat sync               # satellite vs SB -> four review lists
```

## How it works

**The mode banner.** Every run prints `LIVE`, `FALLBACK` or `SANDBOX`. LIVE is
the real workbook; FALLBACK means it was unreachable or locked and a refreshed
copy was read instead, with the reason; SANDBOX means `SB_WORKBOOK_PATH` was set
explicitly. Reads are openpyxl (a save is physically impossible); the only safe
write path is Excel COM — see [`EXCEL_WORKBOOK_SAFETY.md`](../0P-platform/docs/EXCEL_WORKBOOK_SAFETY.md).

**`sat sync` never writes to either side.** It emits four review lists into
`sb-sync/<satellite>/<date>/` — new rows, synonyms, corrections, decisions — and
a person carries them out in Excel. SB is macro-heavy and the Liburnija sheet is
typed into in the field; neither tolerates an automatic write.

## Why join on shared keys, never a row id

Every satellite numbers its own rows, and those numbers leak into folder and
file names where three schemes collide. A measured test resolved **5 of 20**
field numbers to the *wrong* cave. The ranked key order is: Broj pločice →
`LiDAR Kristal N` synonym → Katastarski broj RH → HTRS coordinates (tight,
calibrated bands) → name (corroboration and duplicate-guard only).
Measurements: [`docs/sb-satellite-tables.md`](docs/sb-satellite-tables.md).

## Where things are

- Code: [`src/cave_dossier/sb/`](src/cave_dossier/sb/), [`src/cave_dossier/satellites/`](src/cave_dossier/satellites/)
- Tests: [`tests/`](tests/)
- Design: [`docs/sb-liburnija-hub.md`](docs/sb-liburnija-hub.md) · [`docs/sb-satellite-tables.md`](docs/sb-satellite-tables.md) · [`docs/sb-powerquery.md`](docs/sb-powerquery.md) · [`docs/sb-restructure-excel-prompt.md`](docs/sb-restructure-excel-prompt.md)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)

## Status

SB read-only operational (M1). Satellite sync operational — 126 rows entered SB
from Liburnija on 2026-08-29. Write-back is 6P, at M6.
