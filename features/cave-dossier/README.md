# cave-dossier — SB communication + cave dossier builder

Pipeline parts **2.1 / 2.1b / 2.1c / 2.2** ([ARCHITECTURE.md](../../ARCHITECTURE.md)):
talk to **SB** (Speleo baza, the society's cave-registry Excel workbook), build a
per-cave **dossier** with warning/blocker gating, create the **OSZ**, produce the
**isječak karte**. Python package `cave_dossier`, CLI `cavedossier`. Run from
VS Code — no GUI yet, function over form.

Much of the machinery is ported from the read-only `../crospeleo-automation`
repo (the downstream cadastre-submission tool) — every copy is logged in
[docs/PORTING.md](docs/PORTING.md). Excel safety rules:
[docs/EXCEL_WORKBOOK_SAFETY.md](docs/EXCEL_WORKBOOK_SAFETY.md).

## Setup (once)

```powershell
cd features/cave-dossier
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env     # then fill in (see below)
```

`.env` (gitignored, per-machine):
- `SB_WORKBOOK_PATH` — absolute path to a **sandbox copy** of the SB workbook
  (recommended during development; e.g. `...\example\sb-sandbox\!Speleo_baza_SUE_v2.4.xlsm`).
- `LOCAL_DRIVE_ROOT` — the Drive Desktop mount of the society archive; used for
  LIVE mode (workbook resolves as `<LOCAL_DRIVE_ROOT>/<sb.workbook_filename>`)
  and, from M2 on, the archive dirs (nacrti, izjave, photos).

Every command prints `SB mode: SANDBOX (...)` or `SB mode: LIVE (...)` first —
always check the banner.

## Commands

```powershell
# M1 — read-only SB inspection
cavedossier sb columns                     # detected header row + all column names
cavedossier sb inspect --cave "Ponor X"    # dump a cave's row (name / SUE / plaque; substring OK)
cavedossier sb stats                       # sheets, row counts, fill counts of key columns

# M2 — per-cave dossier
cavedossier report --cave "Konglomeratača" # what is present / missing / blocking
cavedossier report --cave 570 --json       # same dossier as JSON (raw SB row omitted)
```

`report` exits **0** when the dossier is ready, **1** when it is not, **2** on a
lookup/config error. Only SB is gathered today, so most Tablica 2 rules come back
as *not checked yet* — see the gating section below.

Reads are openpyxl-only — saving through this path is physically impossible.
Writes to SB (M6) go exclusively through `sb/safe_io.py`'s xlwings/Excel-COM
path with automatic backups; see [docs/sb-write-back-design.md](docs/sb-write-back-design.md).

Console shows `?` instead of š/č/ž? `$env:PYTHONIOENCODING="utf-8"` (the CLI
also self-reconfigures its output streams, so this is rarely needed).

## Module map

| Path | What |
|---|---|
| `src/cave_dossier/cli.py` | `cavedossier` entry point (argparse) |
| `src/cave_dossier/core/config.py` | config.yaml + .env → `Settings`; SANDBOX/LIVE resolution |
| `src/cave_dossier/core/normalization.py` | diacritic-insensitive matching keys (ported) |
| `src/cave_dossier/core/people.py` | split a free-text author cell into people (ported+adapted) |
| `src/cave_dossier/sb/safe_io.py` | workbook preflight/backup/COM-write safety (ported) |
| `src/cave_dossier/sb/loader.py` | `SBReader`: header autodetect, canonicalized columns, `find_caves` (ported+trimmed) |
| `src/cave_dossier/dossier/model.py` | `CaveDossier` + `Source` provenance, files, issues, readiness |
| `src/cave_dossier/dossier/sb_mapper.py` | SB row -> dossier; parses the `za istražit` queue flag |
| `src/cave_dossier/dossier/gating.py` | Protokol v6 Tablica 2 rules -> warnings / blockers / unchecked |
| `src/cave_dossier/dossier/report.py` | the text rendering behind `cavedossier report` |
| `sessions/SESSIONS.md` | session journal (appended by `/wrap-up`) |
| `backlog/ideas.md` | dated idea capture |
| `example/` | **gitignored** — sandbox workbook + real cave data (PII, never committed) |
| `tests/` | pytest on tiny synthetic fixtures |

Planned modules: `dossier/intake.py` (rest of M2 — resolve a cave's files on
Drive), `georef/` (M3 — isječak karte), `osz/` (M4 — OSZ builder).

## Gating: warnings, blockers, and "not checked yet"

The dossier is assembled milestone by milestone, so `dossier/gating.py` labels
every rule with the **source** that feeds it (`SB`, `ARCHIVE`, `SURVEY`, `OSZ`,
`MAP`). A rule whose source has not been gathered is reported as *unchecked* —
never as a failure — and a dossier counts as ready only when there are no
blockers **and** nothing blocking is left unchecked. The rules themselves encode
Protokol v6: Tablica 2 mandatory fields, the §5.1 year-conditional GPS /
fotografija ulaza / pločica trio (mandatory from 2015 on, warnings before that),
the §5 kaverna plaque exemption, and per-author `Izjava za katastar` checks.

## Testing

```powershell
python -m pytest
```

Fixtures are synthetic (fake caves, fake names). Real-data checks run manually
via the CLI against the sandbox — see STATUS.md for the current checklist.
