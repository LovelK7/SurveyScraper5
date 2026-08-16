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

## Commands (M1)

```powershell
cavedossier sb columns                     # detected header row + all column names
cavedossier sb inspect --cave "Ponor X"    # dump a cave's row (name / SUE / plaque; substring OK)
cavedossier sb stats                       # sheets, row counts, fill counts of key columns
```

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
| `src/cave_dossier/sb/safe_io.py` | workbook preflight/backup/COM-write safety (ported) |
| `src/cave_dossier/sb/loader.py` | `SBReader`: header autodetect, canonicalized columns, `find_caves` (ported+trimmed) |
| `sessions/SESSIONS.md` | session journal (appended by `/wrap-up`) |
| `backlog/ideas.md` | dated idea capture |
| `example/` | **gitignored** — sandbox workbook + real cave data (PII, never committed) |
| `tests/` | pytest on tiny synthetic fixtures |

Planned modules: `dossier/` (M2 — model, intake, statement gating, readiness),
`georef/` (M3 — isječak karte), `osz/` (M4 — OSZ builder).

## Testing

```powershell
python -m pytest
```

Fixtures are synthetic (fake caves, fake names). Real-data checks run manually
via the CLI against the sandbox — see STATUS.md for the current checklist.
