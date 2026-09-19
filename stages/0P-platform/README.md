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

- Code: [`src/cave_dossier/core/`](src/cave_dossier/core/), [`src/cave_dossier/cli/`](src/cave_dossier/cli/)
- Cross-cutting records: [`docs/PORTING.md`](docs/PORTING.md) (every file copied from
  `../crospeleo-automation`), [`docs/EXCEL_WORKBOOK_SAFETY.md`](docs/EXCEL_WORKBOOK_SAFETY.md)
  (why reads are openpyxl and writes are Excel COM only)
- Tests: the repo-root [`conftest.py`](../../conftest.py) and [`tests/fixtures/`](../../tests/fixtures/)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)
