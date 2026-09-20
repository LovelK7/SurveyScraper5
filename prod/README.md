# prod — the outward-facing surface

**Everything here reaches someone who is not a developer.** Everything outside
this folder is internal. That is the whole rule.

If you are looking for "what do the society's people actually touch", it is the
two kits below and the Drive dirs in [`drive-layout.md`](drive-layout.md).

## The two kits

### 1. `cavedossier` launchers — for recorders and drafters

Double-clickable `.bat` files that live **on the Google Drive**, not in this
repo, at `!!!Digitalizacija/SurveyScraper5/`. Three commands ship today:
`osz prefill`, `photos process` and `sastavnica`.

| File | Role |
|---|---|
| [`build_prod.py`](build_prod.py) | Generates and publishes a version |
| [`prod_templates/launcher.bat.template`](prod_templates/launcher.bat.template) | The 14-line `.bat` stub the operator double-clicks |
| [`prod_templates/bootstrap.ps1.template`](prod_templates/bootstrap.ps1.template) | The real installer/runner (~380 lines) |
| [`prod_templates/PROCITAJ_ME.txt.template`](prod_templates/PROCITAJ_ME.txt.template) | The Croatian operator guide, ASCII-enforced at build time |
| `dist/` | Local staging of published versions (gitignored) |

```powershell
python prod\build_prod.py --version 1.5             # stage locally, no Drive writes
python prod\build_prod.py --version 1.5 --publish   # copy to the Drive
```

**What happens on the operator's machine.** The `.bat` calls `bootstrap.ps1`,
which probes upward from its own location for `!Speleo_baza_SUE_*.xlsm` to find
the Drive root, checks for Python 3.11+, extracts `bundle.zip` to
`%LOCALAPPDATA%\CaveDossier\v<X>`, creates a venv, `pip install -e .`,
installs Playwright Chromium, copies `podaci\geo` locally, and writes an `.env`
with `LOCAL_DRIVE_ROOT` derived from where the launcher itself sits. Every run
logs to `%LOCALAPPDATA%\CaveDossier\logs\` for remote debugging.

**Adding a command to prod is two edits**: `PROD_COMMANDS` in `build_prod.py`,
and a `switch ($Command)` branch in `bootstrap.ps1.template`.

**The bundle is flattened.** In the repo each stage owns its own
`src/cave_dossier/<sub>/`; `build_prod.py` rewrites them all into a single
`src/cave_dossier/` tree and ships a generated single-root `pyproject.toml`.
That is deliberate: `bootstrap.ps1` runs `pip install -e .` unattended, on a
machine with no developer present, with whatever setuptools pip downloads that
day. The repo's multi-root `package-dir` map works, but it has no business
being on that path.

### 2. The `csurvey` TDX kit — for people processing TopoDroid surveys

Drag-and-drop `.bat` files plus the Python tools they drive, published together
into `!!!Digitalizacija/` — the digitalization folder itself, beside the surveys
(user decision 2026-09-20; before that they sat in a `Share/TDX` handoff folder).
The `csurvey_` prefix keeps them legible in a folder they share with the
society's own documents, the way `cavedossier_*` does one level down.

| File | Step |
|---|---|
| [`csx_templates/csurvey_recover_tdx.bat.template`](csx_templates/csurvey_recover_tdx.bat.template) | 1b — rebuild a broken `.csx` from the TopoDroid project `.zip` |
| [`csx_templates/csurvey_preprocess_tdx.bat.template`](csx_templates/csurvey_preprocess_tdx.bat.template) | 2 — raw `.csx` → import-ready `_pp.csx` |
| [`csx_templates/csurvey_fix_tdx.bat.template`](csx_templates/csurvey_fix_tdx.bat.template) | 4 — after cSurvey "Save As", before drawing |
| [`csx_templates/csurvey_READ ME FIRST - process a survey.txt`](csx_templates/csurvey_READ%20ME%20FIRST%20-%20process%20a%20survey.txt) | The jargon-free operator checklist |
| [`build_csx_kit.py`](build_csx_kit.py) | Generates and publishes the kit (`--publish`); `csurvey_alati/` carries the Python tools |

```powershell
python prod\build_csx_kit.py                  # stage into prod/dist/csx-kit
python prod\build_csx_kit.py --publish        # + copy to !!!Digitalizacija
```

A double-click scans `!Za digitalizirat` (from `config.yaml`'s `intake_dir`),
which is where the per-cave folders are; dragging files onto a launcher works
from anywhere. Step 3 is manual: open the `_pp.csx` in cSurvey and Save As. The
protocol is
[`stages/3N-nacrt/production/tdx-processing-protocol.md`](../stages/3N-nacrt/production/tdx-processing-protocol.md);
the Python tools live in
[`stages/3N-nacrt/production/tools/`](../stages/3N-nacrt/production/tools/) and
are copied into `csurvey_alati/` at publish time — edit them in the repo, never
on the Drive.

## Why these are templates and not just files

Both kits are **generated**, never hand-edited in place, because both used to
carry a hardcoded absolute path to one developer's machine. The TDX `.bat` files
were the worse case: their own headers said they were copies handed to
operators, and every such copy was inert on any machine but that one. Generating
them makes the developer path a build-time value and the *last* fallback rung —
the launchers find their tools in `csurvey_alati/` beside themselves first, so a
published kit works anywhere.

## The standing portability rules

These are what make productionization cheap, and they apply to every new tool:

- **One command per tool, no repo knowledge required to run it.** Every
  capability is a `cavedossier` subcommand with the Redni broj as its only input.
- **Per-machine facts live only in `.env`**, never in code or committed config.
- **Every local dataset is regenerable from open services by one command**
  (`geo fetch-data` is the model), so a prod machine can be provisioned by
  running it once or by copying a ready-made bundle.
- **Outputs land in prod and tolerate hand management there** — fail-soft
  delivery, self-healing collections, review lists instead of writes. That
  contract is the prod interface and must survive any packaging.

## Still open

A fully bundled runtime (no Python install step), prod coverage for more
commands as they stabilize, and update notification beyond "a newer launcher
appeared in the folder". Tracked in [`journal/backlog.md`](../journal/backlog.md).
