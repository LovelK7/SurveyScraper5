# 0P — Platform

**The shared spine.** Not a pipeline step: the code every other stage stands on.

## What lives here

| Module | What it is |
|---|---|
| `core/config.py` | `Settings` — `config.yaml` + `.env` resolved into one frozen object. Also the LIVE/FALLBACK/SANDBOX workbook switch. |
| `core/paths.py` | **The anchor.** `workspace_root()` finds the workspace by walking up for `.cavedossier-workspace`; `repo_root()` is dev-only and returns `None` in prod. |
| `core/normalization.py` | Diacritic folding, whitespace cleanup, optional-float parsing. Imported by 21 modules. |
| `core/matching.py` | The weighted-evidence matcher: a free-form folder or filename → an SB row. |
| `core/people.py`, `core/person_aliases.py` | Split an author cell into people; generate the abbreviation spellings (`L.Kukuljan` ↔ `Lovel Kukuljan`). |
| `cli/` | The single `argparse` entry point. Every `cavedossier` subcommand is parsed and dispatched here; the work happens in the stage modules. |
| `gui/` | The local dashboard, `cavedossier gui` — every stage's commands behind buttons, the current cave, "open SB". A mockup of the future GUI that already runs things. See [The dashboard](#the-dashboard--cavedossier-gui). |

## The dashboard — `cavedossier gui`

```powershell
cavedossier gui                 # starts http://127.0.0.1:8765/ and opens it in the browser
cavedossier gui --port 8800     # another port (the next free one up to +19 is taken)
cavedossier gui --no-browser    # just serve; open the URL yourself
```

One page, one tab per stage (1T … 6P) plus **Pregled**, in Croatian:

- **Otvori SB** in the top bar opens the live Speleo baza in Excel. Pregled also
  lists every `!Speleo_baza_SUE_v*.xlsm` on Drive and warns when a newer one
  exists than `config.yaml` points at.
- **Objekt**: pick the cave you are working on (Redni broj or name; the list is
  the `SB_<broj>_…` leaves under `!Za digitalizirat`). Every command on every
  tab then uses that number, and the 3N steps offer that cave's files
  (`_pp`, `_lt`, `_lt_fin`…), newest first. Pregled shows the cave's checklist:
  which Nacrt steps, OSZ, karta, photos and sastavnica already exist.
- **Pokreni** runs the command. Output streams into the **Ispis** panel at the
  bottom, and when a tool asks something (the 3N file menu, the layout menu) you
  answer in the box under the output. Every run is also logged to `runs/gui/`.
- Runs that only read go on one click. Anything that writes to Drive, to the
  cave's folder or to georef.hr asks first (orange **Pokreni…**). Ticking
  `--dry-run` / `--local` makes it a plain run again.
- **Kopiraj** gives the same command for the terminal. 3N commands use `$T`,
  as in the [3N README](../3N-nacrt/README.md).
- **cSurvey** buttons open a survey file in `C:\csurvey64\cSurveyPC.exe`
  (or `CSURVEY_DIR` from `.env`).

How it is built, for whoever turns it into the real GUI:

| File | Role |
|---|---|
| `gui/catalog.py` | **The table of every action**: stage, Croatian label, argv template (`{broj}`, `{file}`, `{query}`), options, what it writes. The page draws its buttons from this, and the server builds argv only from this. A new button is one `Action` entry. |
| `gui/state.py` | Read-only view of the machine: settings, SB versions, Drive dirs, caves in work, a cave's files classified by name. Fail-soft: a missing Drive is a note on the page. |
| `gui/jobs.py` | One subprocess per run, with stdin open for answers, output polled by offset, `taskkill /T` to stop it. |
| `gui/server.py` | `http.server` on 127.0.0.1 with a JSON API (`/api/state`, `/caves`, `/cave/<broj>`, `/catalog`, `/run`, `/job/<id>`, `/open`). Every API call needs the random token the page was served with. Opening is limited to paths under Drive, the workspace and the repo. |
| `gui/static/` | `index.html`, `app.css`, `app.js`: plain JS, no build step, light and dark theme. |

Only standard library, so it runs in the base install. Why it is built this way:
[design decisions §The dashboard](../../docs/design-decisions.md#the-dashboard--cavedossier-gui-2026-09-24).

## Why this stage exists

It is not a design preference — it is what the dependency graph says.
`core.config` is imported by 24 modules and `core.normalization` by 21, and
the CLI dispatches all eleven other stages. Forcing that into any one
substage would make that substage a hidden dependency of every other.

## The three roots, and why they are separate

`core/paths.py` exists because the old `FEATURE_ROOT = parents[3]` conflated
three different things and broke whenever the package moved:

- **workspace** — `config.yaml`, `.env`, `data/`, `runs/`, `sb-sync/`. The repo
  root in dev; `%LOCALAPPDATA%\CaveDossier\v<X>` in prod. One marker file finds
  both.
- **package assets** — the OSZ template, `selectors.yaml`, `pristupi.yaml`.
  These use neither root: each module resolves its own with
  `Path(__file__).parent`, so the asset travels with its code.
- **repo** — dev-only, for reaching `../crospeleo-automation`. `None` in prod,
  so callers must fail soft.

## Where things are

- Code: [`src/cave_dossier/core/`](src/cave_dossier/core/), [`src/cave_dossier/cli/`](src/cave_dossier/cli/), [`src/cave_dossier/gui/`](src/cave_dossier/gui/)
- Cross-cutting records: [`docs/PORTING.md`](docs/PORTING.md) (every file copied from
  `../crospeleo-automation`), [`docs/EXCEL_WORKBOOK_SAFETY.md`](docs/EXCEL_WORKBOOK_SAFETY.md)
  (why reads are openpyxl and writes are Excel COM only)
- Tests: [`tests/test_gui.py`](tests/test_gui.py); the repo-root [`conftest.py`](../../conftest.py) and [`tests/fixtures/`](../../tests/fixtures/)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)
