# prod — the outward-facing surface

**Everything here reaches someone who is not a developer.** Everything outside
this folder is internal. That is the whole rule.

If you are looking for "what do the society's people actually touch", it is the
two kits below and the Drive dirs in [`drive-layout.md`](drive-layout.md).

**Publishing either kit goes through `/publish`**
([`.claude/skills/publish/SKILL.md`](../.claude/skills/publish/SKILL.md)):
doctor and tests first, then the version bump and a commit, so the stamped
commit matches what ships. The kit is built and deployed after that, and the
Drive copy is checked. The builder commands below are what that skill runs.

## The two kits

### 1. `cavedossier` launchers — for recorders and drafters

Double-clickable `.bat` files that live **on the Google Drive**, not in this
repo, at `!!!Digitalizacija/SurveyScraper5/`. Four commands ship today:
`osz prefill`, `photos process`, `sastavnica` and `nacrt`. The last one is also
called by the csurvey kit's KORAK 3 launcher (below), which is why it has to be
published into that folder and not only run from a repo clone.

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
into `!!!Digitalizacija/SurveyScraper5/` — the same prod folder as the
`cavedossier_*` launchers, so everything an operator double-clicks is in one
place (user decision 2026-09-20; before that they sat in a `Share/TDX` handoff
folder). The `csurvey_` prefix is what keeps the two kits apart in that listing,
and `_archive_old()` in `build_prod.py` only ever sweeps `cavedossier_*`.

The **digit in each filename is the running order** — named after their tools
they sorted alphabetically into the wrong sequence (user, 2026-09-20). The
launchers, the guide and the protocol all speak the same KORAK numbers. The
order is **1 → 2 → 3**; the zip rescue carries **9** because it is a repair and
not a step (user, 2026-09-20, settling the clash with the finisher's KORAK 3),
so it sorts to the bottom of the listing and of the guide.

| File | KORAK |
|---|---|
| [`csx_templates/csurvey_0_PROCITAJ_ME.txt.template`](csx_templates/csurvey_0_PROCITAJ_ME.txt.template) | 0 — the Croatian operator guide (diacritics, UTF-8 BOM) |
| [`csx_templates/csurvey_1_pripremi_csx.bat.template`](csx_templates/csurvey_1_pripremi_csx.bat.template) | 1 — raw `.csx` → import-ready `_pp.csx` |
| [`csx_templates/csurvey_2_dovrsi_uvoz.bat.template`](csx_templates/csurvey_2_dovrsi_uvoz.bat.template) | 2 — after cSurvey "Save As", before drawing |
| [`csx_templates/csurvey_3_dovrsi_nacrt.bat.template`](csx_templates/csurvey_3_dovrsi_nacrt.bat.template) | 3 — corrected `_lt` → the finished `SB_<broj>_nacrt.pdf` |
| [`csx_templates/csurvey_9_oporavi_iz_zipa.bat.template`](csx_templates/csurvey_9_oporavi_iz_zipa.bat.template) | 9 — rescue: rebuild a broken `.csx` from the TopoDroid project `.zip` |
| [`build_csx_kit.py`](build_csx_kit.py) | Generates and publishes the kit (`--publish`); `csurvey_alati/` carries the Python tools |

**Operator-facing text is Croatian.** The `.txt` guide keeps real diacritics and
is written UTF-8 with a BOM; the `.bat` consoles are Croatian *without* them,
because a cp852 console cannot print them. `build_csx_kit.py` enforces both.

```powershell
python prod\build_csx_kit.py                  # stage into prod/dist/csx-kit
python prod\build_csx_kit.py --publish        # + copy to the prod folder
```

A double-click **asks which caves to process** — Redni broj (SB), several at a
time, `SVE` for everything, Enter to cancel — and resolves each number to that
cave's `SB_<broj>_…` leaf under `..\!Za digitalizirat` (the intake tree one level
up, derived at build time from `config.yaml`'s `intake_dir` and kept relative).
Sweeping the whole tree is now opt-in, not the default (user, 2026-09-20).
KORAK 2 and KORAK 3 go one step further and ask *which file* in that cave's
folder to work on, annotating each with how far through the chain it is.
Dragging files onto a launcher skips both prompts and works from anywhere. The
two manual steps between the launchers are cSurvey's own: open the `_pp.csx` and
Save As (between 1 and 2), then correct the sketch in the `_lt` file (between 2
and 3).

**KORAK 3 spans both kits.** Its first two steps are kit tools (`nacrt_finish.py`
then `csurvey_driver.py finish`, both in `csurvey_alati/`); its third is
`cavedossier nacrt`, a prod-bundle command. The launcher finds
`cavedossier_nacrt_v*.bat` beside itself in this same folder and, when it is
missing or fails, says so and stops with the PDFs already delivered. The one
step that needs cSurvey installed is the headless print; without it the launcher
stops cleanly and prints the two-click manual recipe instead of a traceback. The
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
