# SurveyScraper5

Turns raw cave-exploration data into the two things the society actually files:
the **OSZ** (osnovni speleološki zapisnik) and the **Nacrt** (the survey map),
delivered into the shared Google Drive archive of *Speleološki odsjek HPD
Estavela*.

## Where to look

| If you want… | Go to |
|---|---|
| What one part of the pipeline does | the stage's own README under [`stages/`](stages/) |
| The whole pipeline, with its bridges | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Where development currently stands | [STATUS.md](STATUS.md) |
| Every command in one place | [docs/commands.md](docs/commands.md) |
| Why something is the way it is | [docs/design-decisions.md](docs/design-decisions.md) |
| What non-developers actually run | [prod/README.md](prod/README.md) |
| Croatian domain terms | [shared/glossary.md](shared/glossary.md) |

## The stages

The label is `<digit><letter>` — the digit is the position in the pipeline, the
letter is the Croatian name of the thing. So the folders sort in the order data
flows through them, and `4O` tells you "OSZ" without a lookup.

```
stages/
  0P-platform/      shared spine: config, the workspace anchor, the CLI
  1T-teren/         field capture (PARKED) + the intake-dir contract
  2B-baza/          SB master workbook + the satellite tables
  3N-nacrt/         TopoDroid -> Nacrt PDF (route A, cSurvey)
  4G-geo/           locality + kota finders
  4I-isjecak/       isječak karte via georef.hr
  4O-osz/           the OSZ builder (prefill + backfill)
  4F-fotografije/   entrance-photo processing
  4S-sastavnica/    the Nacrt title block (route B, Illustrator)
  5O-osobe/         registar osoba + izjave
  5D-dosje/         the dossier model, the two gates, report
  6P-predaja/       delivery + SB write-back (designed only)
```

Everything each stage needs is inside its folder: its README, its code
(`src/cave_dossier/<subpackage>/`), its tests, its docs and its templates.

## The rest of the tree

```
prod/            the outward-facing surface -- Drive launchers, the TDX kit
docs/            cross-cutting records
journal/         SESSIONS.md + backlog.md, the active log
config.yaml      committed config      .env  per-machine facts (gitignored)
data/ runs/      workspace state (gitignored except the people registry)
pipeline.yaml    the machine-readable stage list the doctor checks against
tools/           pipeline_doctor.py
```

## Setup

Requires Python 3.11+, and a Google Drive Desktop mount for anything touching
real data.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev,osz,photos,geo,karta,sastavnica]"
copy .env.example .env      # then set LOCAL_DRIVE_ROOT and the georef.hr login
.venv\Scripts\python -m pytest -q
```

Then, once per machine, provision the open geodata:

```powershell
.venv\Scripts\cavedossier geo fetch-data
```

Every command takes the cave's **Redni broj** as its only required input:

```powershell
cavedossier report --cave 1220      # what is present, missing, blocking
cavedossier osz prefill 1220        # the prefilled zapisnik
cavedossier sastavnica 1220         # the Nacrt title block
```

Full reference: [docs/commands.md](docs/commands.md).

## Health check

```powershell
.venv\Scripts\python tools\pipeline_doctor.py
```

Checks that the tree, the stage manifest and the prose still agree: broken
links, undocumented commands, unclaimed subpackages, orphaned docs, stale status
claims. It is the closing step of `/feature-dev` and a gate in `/wrap-up`.

## Related repos

`../cSurvey` and `../crospeleo-automation` are **read-only reference material** —
see [CLAUDE.md](CLAUDE.md). Open
[SurveyScraper5.code-workspace](SurveyScraper5.code-workspace) for all three in
one window.
