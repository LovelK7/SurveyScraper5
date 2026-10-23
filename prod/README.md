# prod — the outward-facing surface

**Everything here reaches someone who is not a developer.** Everything outside
this folder is internal. That is the whole rule.

If you are looking for "what do the society's people actually touch", it is
**one file**, `SurveyScraper5.bat`, in `!!!Digitalizacija/SurveyScraper5/`, and
the Drive dirs in [`drive-layout.md`](drive-layout.md).

**Publishing goes through `/publish`**
([`.claude/skills/publish/SKILL.md`](../.claude/skills/publish/SKILL.md)):
doctor and tests first, then the version bump and a commit, so the stamped
commit matches what ships. The bundle is built and deployed after that, and
the Drive copy is checked. The builder command below is what that skill runs.

## The dashboard launcher — for everyone

One double-clickable `.bat` on the Drive opens the dashboard
([`cavedossier gui`](../stages/0P-platform/README.md#the-dashboard--cavedossier-gui))
in the browser. Every operator command is a button there: OSZ, karta, the 3N
KORAK 0–4 and 9, sastavnica, photos, people, dossier, predaja. That replaced
the per-command `cavedossier_*_v<X>.bat` launchers and the `csurvey_*`
drag-and-drop kit (user, 2026-10-22). The rationale is
[The dashboard on the Drive](../docs/design-decisions.md#the-dashboard-on-the-drive-one-launcher-every-bat-retired-2026-10-22).

```text
!!!Digitalizacija/SurveyScraper5/
├─ SurveyScraper5.bat      ← the one thing operators double-click (no version in the name)
├─ PROCITAJ_ME.txt         ← the Croatian operator guide
├─ VERZIJE.txt             ← publish log, one line per release
├─ v<X>/                   ← bootstrap.ps1 + bundle.zip
├─ podaci/geo/             ← cloud copy of data/geo (~280 MB)
└─ _arhiva/                ← superseded v-dirs + every retired .bat and csurvey_alati/
```

| File | Role |
|---|---|
| [`build_prod.py`](build_prod.py) | Generates and publishes a version |
| [`prod_templates/launcher.bat.template`](prod_templates/launcher.bat.template) | The `.bat` stub the operator double-clicks |
| [`prod_templates/bootstrap.ps1.template`](prod_templates/bootstrap.ps1.template) | The real installer and server starter |
| [`prod_templates/PROCITAJ_ME.txt.template`](prod_templates/PROCITAJ_ME.txt.template) | The Croatian operator guide (UTF-8 with BOM, real diacritics) |
| `dist/` | Local staging of published versions (gitignored) |

```powershell
python prod\build_prod.py --version 2.0             # stage locally, no Drive writes
python prod\build_prod.py --version 2.0 --publish   # copy to the Drive (via /publish)
```

**What a double-click does.** The `.bat` calls `v<X>\bootstrap.ps1`, which:

1. probes upward from its own location for `!Speleo_baza_SUE_*.xlsm` to find
   the Drive root;
2. on the first run, or when `bundle.zip` is newer than the install, installs to
   `%LOCALAPPDATA%\CaveDossier\v<X>`. That means: a Python 3.11+ check (with
   install instructions when it is missing), extract, venv, `pip install -e
   .[osz,photos,geo,karta,sastavnica,sb-write]`, Playwright Chromium, a local copy of
   `podaci\geo`, and an `.env` with `LOCAL_DRIVE_ROOT` derived from the
   launcher's location plus the shared georef.hr login. Then **3N KORAK 0**
   runs: cSurvey's app settings into the registry, and a local cSurvey copy
   with a desktop shortcut. It is fail-soft: a cSurvey left open only leaves
   a warning;
3. reads `%LOCALAPPDATA%\CaveDossier\gui.json`. If this version's dashboard
   is already running, it opens the browser on it and the window closes. An
   older version's dashboard is asked to stop first, unless a job is
   running, in which case it is left and opened instead;
4. otherwise starts `cavedossier gui --no-browser --state-file … --idle-minutes 10`
   **with no window** (output to `logs\gui_v<X>_*.log`), waits until it
   answers, and opens the browser.

The dashboard stops itself 10 minutes after its last page closes (the page
pings every minute). It never stops while a job runs, and its **Zatvori**
button stops it at once. The setup steps log to
`%LOCALAPPDATA%\CaveDossier\logs\nadzorna_ploca_*.log`, the server to
`gui_*.log`, and each job to the install's `runs/gui/`.

**The bundle is flattened.** In the repo each stage owns its own
`src/cave_dossier/<sub>/`; `build_prod.py` rewrites them all into a single
`src/cave_dossier/` tree and ships a generated single-root `pyproject.toml`.
That is deliberate: `bootstrap.ps1` runs `pip install -e .` unattended, on a
machine with no developer present, with whatever setuptools pip downloads that
day. The repo's multi-root `package-dir` map works, but it has no business
being on that path.

**The 3N tools ride in the bundle** as `csx-alati/`. They are the kit's
`TOOLS` list from [`build_csx_kit.py`](build_csx_kit.py), plus the tools only
the dashboard calls (`DASHBOARD_ONLY_TOOLS`), plus the symbol themes as
`csx-alati/teme/`. A test fails when a catalog action names a tool the bundle
lacks. Edit them in
[`stages/3N-nacrt/production/tools/`](../stages/3N-nacrt/production/tools/),
never on the Drive.

**Adding a command to prod** is adding it to the dashboard's catalog
(`gui/catalog.py`). The launcher has no per-command code anymore.

**Publishing sweeps the old surface away.** `_archive_old()` moves superseded
`v<X>/` dirs, every `cavedossier_*_v*.bat`, every `csurvey_*.bat|.txt` and
`csurvey_alati/` into `_arhiva/`. An archived launcher still works from there,
because its v-dir moves with it.

### The retired `csurvey` TDX kit

Until 2026-10-22 the 3N steps were drag-and-drop `csurvey_<n>_*.bat` files
(KORAK 0–4, 9) plus `csurvey_alati/`, published beside the `cavedossier_*`
launchers by [`build_csx_kit.py`](build_csx_kit.py) from
[`csx_templates/`](csx_templates/). The dashboard runs every one of those
steps, so `build_csx_kit.py --publish` now refuses. `--publish-to DIR` still
builds a private drag-and-drop copy for someone who wants one, and the
builder's `TOOLS` list and `theme_files()` remain the source of truth for what
the bundle's `csx-alati/` carries. The step-by-step protocol is
[`stages/3N-nacrt/production/tdx-processing-protocol.md`](../stages/3N-nacrt/production/tdx-processing-protocol.md).

## Why these are templates and not just files

Everything on the Drive is **generated**, never hand-edited in place. The
first launchers carried a hardcoded absolute path to one developer's
machine. The TDX `.bat` files were the worse case: their own headers said they
were copies handed to operators, and every such copy was inert on any machine
but that one. Generating them made the developer path a build-time value. Now
nothing on the operator's side refers to a developer path at all: the
launcher finds the Drive by probing upward, and the tools ride in the bundle.

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

A fully bundled runtime (no Python install step), and the prod version shown
on the dashboard itself. A newer version is picked up by the next
double-click, but an open dashboard does not say one exists. Tracked in
[`journal/backlog.md`](../journal/backlog.md).
