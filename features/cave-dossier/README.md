# cave-dossier — SB communication + cave dossier builder

Pipeline parts **2.1 / 2.1b / 2.1c / 2.1d / 2.2** ([ARCHITECTURE.md](../../ARCHITECTURE.md)):
talk to **SB** (Speleo baza, the society's cave-registry Excel workbook), build a
per-cave **dossier** with warning/blocker gating, prefill the **OSZ**, produce the
**isječak karte**, process the **fotografije ulaza**. Python package
`cave_dossier`, CLI `cavedossier`. Run from VS Code — no GUI yet, function over
form.

This page is the **operator's view**: what the tools are, every command you can
run, and how to set a machine up. Design rationale and settled decisions live in
[docs/design-decisions.md](docs/design-decisions.md); the module/docs map for
agents and developers is [_INDEX.md](_INDEX.md).

## Contents

- [Where to look next](#where-to-look-next)
- [What this does (orientation)](#what-this-does-orientation)
- [Milestones — what M1-M6 mean](#milestones--what-m1-m6-mean)
- [Commands](#commands)
- [Quick checks](#quick-checks)
- [Setup (once)](#setup-once)
  - [.env — per-machine facts](#env--per-machine-facts)
  - [The SB mode banner](#the-sb-mode-banner)
  - [Dev vs prod — this setup is the DEV half](#dev-vs-prod--this-setup-is-the-dev-half)
  - [Two venvs exist](#two-venvs-exist)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)

## Where to look next

| Goal | Read this |
|---|---|
| Run any tool, look up a command and its flags | [Commands](#commands) (this page, below) |
| Set up a fresh machine | [Setup](#setup-once) (this page) |
| Understand **why** a rule / verdict / heuristic behaves as it does | [docs/design-decisions.md](docs/design-decisions.md) |
| Find a Python module, doc, or data location | [_INDEX.md](_INDEX.md) |
| See where the dev cycle stands right now | [../../STATUS.md](../../STATUS.md) (milestone ladder + checklists) |
| What an "M-number" (M1…M6) means | [Milestones](#milestones--what-m1-m6-mean) (this page) |
| The pipeline map + part numbering (2.1a/b/c…) | [../../ARCHITECTURE.md](../../ARCHITECTURE.md) |
| **Which command connects part A to part B** (nodes, bridges, chains) | [ARCHITECTURE §Bridges](../../ARCHITECTURE.md#bridges--the-scripts-between-the-nodes) |
| Where a ported file came from | [docs/PORTING.md](docs/PORTING.md) |
| Why SB reads are openpyxl and writes Excel-COM only | [docs/EXCEL_WORKBOOK_SAFETY.md](docs/EXCEL_WORKBOOK_SAFETY.md) |
| The OSZ v10 template workbench (audits, mockups, conformance) | [osz-template/README.md](osz-template/README.md) |
| What happened in past sessions / captured ideas | [sessions/SESSIONS.md](sessions/SESSIONS.md) · [backlog/ideas.md](backlog/ideas.md) |
| Work as an AI agent in this repo | [../../CLAUDE.md](../../CLAUDE.md) → [_INDEX.md](_INDEX.md) |

## What this does (orientation)

A **dossier** is one cave's folder — except it lives in memory instead of on
Drive. The tool walks up to each source in turn (the SB row, the files on
Drive, the processed survey, the filled zapisnik, the isječak karte, the
photos), copies what that source knows into one object, and asks a fixed list
of rules: *is anything mandatory still missing?* That answer is what
`cavedossier report` prints — and the same object is what later stages use to
prefill the OSZ and (at M6) update SB.

There are **two gates**: gate 1 is the society's own acceptance step (Nacrt +
OSZ + foto + pločica + izjave), and passing it *earns* the cave its SUE number;
gate 2 is the stricter CroSpeleo/Protokol-v6 bar that crospeleo-automation
submits against. Everything that is not *Istraženi* is the queue. A verdict is
three-tier — blocker / warning / *not checked yet* — so "missing" is never
confused with "nobody looked". The full design (state derivation from SB's own
Power Query, the rule table, §5.1 year exemptions, identity numbering) is in
[docs/design-decisions.md](docs/design-decisions.md).

People go through the **registar osoba** (`data/people/registry.json`): one
entry per author, aliases derived automatically, so SB's `L.Kukuljan`, an
OSZ's `Lovel Kukuljan` and the file `Izjava_LKukuljan.pdf` count as one
person. At gate 1 a missing (or wrongly scoped) izjava **per author** blocks;
at gate 2 any named person without an izjava on file — recorder and team
members included — gets a warning. `cavedossier people check` runs the same
audit over the whole registry and workbook.

## Milestones — what M1-M6 mean

The M-numbers this repo's docs and comments use everywhere are stage-2 build
steps (canonical definitions: [ARCHITECTURE.md §Milestones](../../ARCHITECTURE.md#milestones-stage-2);
current state per milestone: [STATUS.md](../../STATUS.md#milestone-ladder)):

| M | In one line |
|---|---|
| M0 | docs scaffold |
| M1 | read SB (the live workbook) safely |
| M2 | the dossier object + `report` (+ archive intake, still open) |
| M3 | isječak karte (`karta`) |
| M4 | OSZ both ways: `osz prefill` + `osz fetch` (+ the CroSpeleo-field fetcher, still open) |
| M5 | consume the 2.1a survey artifacts (Nacrt + dimensions) |
| M6 | the only WRITE step: SB write-back + archive delivery (+ 2.1d photo processing) |

Until M6, every tool that "changes" SB really emits a **review list** a person
carries into Excel — that is why so many outputs are `dopune-*.csv` files.

## Commands

This is the full reference. If you are asking *"what do I run to get from
here to there?"*, start from the pipeline's bridge maps instead —
[ARCHITECTURE §Bridges](../../ARCHITECTURE.md#bridges--the-scripts-between-the-nodes)
— and come back here for the flags.

Exit codes: **1** = ready, **0** = not ready, **99** = error. `--gate` only
chooses which gate the exit code reports on — both are always printed.
First time on a machine? [Setup](#setup-once) below.

```powershell
# ── Read-only SB inspection (part 2.2a) ────────────────────────────────
cavedossier sb columns                     # detected header row + all column names
cavedossier sb inspect --cave "Ponor X"    # dump a cave's row (name / SUE / plaque; substring OK)
cavedossier sb stats                       # sheets, row counts, fill counts of key columns

# ── Per-cave dossier report (part 2.1) ─────────────────────────────────
cavedossier report --cave "Konglomeratača"      # both gates, text
cavedossier report --cave 570 --json            # the dossier as data
cavedossier report --cave 570 --gate crospeleo  # exit code follows gate 2 instead

# ── Workbook-wide audits (read-only worklists for an Excel cleanup pass) ─
cavedossier sb audit-authors --limit 40    # author cells the splitter cannot read
cavedossier sb unclassified                # rows in none of SB's views

# ── Registar osoba — authors, aliases, izjave (part 2.1) ───────────────
cavedossier people list                    # every registry person + aliases + linked izjave
cavedossier people check                   # audit: people without an izjava · izjave whose
                                           #   signer is not in the registry · SB author names
                                           #   the registry cannot resolve; also writes the
                                           #   person↔izjava JSON to runs/people/
# Author vs finder: in `Autori nacrta ili izvor` only names written N.Prezime
# (L.Kukuljan) are survey authors and get statement-checked; everything else
# (bare first names, full names) is a cave finder/source — no izjava needed,
# so they are exempt from the gates and from the section-3 sweep.
# The registry is data/people/registry.json (committed, hand-curated). Full
# "First Last" names derive their aliases automatically (L.Kukuljan,
# LKukuljan, Lovel K., …); entries still in token form (ABahović) match SB
# shorthand + izjava files — upgrade them to full names as you learn them.
# Odd spellings that derive to nothing get a manual "aliases": [...] entry.

# ── Field-data intake (folders under !!!Digitalizacija/!Za digitalizirat) ─
cavedossier intake map                     # DRY RUN: map each leaf folder to its SB row
cavedossier intake map --unmatched-only    # just the ones that need a human
cavedossier intake map --apply             # rename the folders in place

# ── Satellite tables (part 2.2b) ───────────────────────────────────────
cavedossier sat sync                       # Liburnija sheet vs SB: four review lists (read-only)
cavedossier sat sync --coords --out        # + coordinate proximity, lists written to sb-sync/

# ── Staged entrance photos (part 2.1d) ─────────────────────────────────
cavedossier photos match-queued            # DRY RUN: propose SB_<Redni broj>_… per staged photo
cavedossier photos match-queued --apply    # perform the proposed renames in place
cavedossier photos check-flag              # staged photos vs SB's "Fotografija ulaza = DA"

# ── Isječak karte (part 2.1c — WRITES to georef.hr: creates the point) ──
cavedossier karta 1234                     # fetch the map excerpt for Redni broj 1234
cavedossier karta 1234 --debug             # watch the browser do it (headed + screenshots)
cavedossier karta 1234 --force             # refresh an excerpt already collected
# Re-running an already-collected cave skips — UNLESS something makes the
# collection stale, which auto-triggers a fresh run instead of needing --force
# or hand-deleting files (the delivery dir is managed by hand too):
#   · SB renamed the cave (the name is typed into the point and embedded in
#     the georef zapis — e.g. "LiDAR Kristal 31" becoming a synonym later);
#   · the PNG is in an outdated excerpt format (pre-2026-08-30 1:1 squares;
#     current format is landscape 5:4, ~1.5 km above/below the entrance);
#   · the PNG exists without its !georef_zapisi.csv row (or is unreadable).
# The CSV survives Excel edits: unpadded brojevi, local dates and blank rows
# are tolerated, and the next upsert repairs that row's formatting.

# ── Locality + elevation finders (part 2.1b — open DGU services) ────────
cavedossier geo fetch-data                 # one-time: boundary GeoPackages + RGI gazetteer
cavedossier geo fetch-data --no-inspire-au # skip the ~209 MB INSPIRE AU download path
cavedossier geo locate 1234                # županija / grad-općina / najbliže mjesto /
                                           #   lokalitet from the row's X/Y, vs what SB says
cavedossier geo kota 1234                  # Kota ulaza from the DGU DMV grid vs SB's Z
cavedossier geo locate 1234 --offline      # no network: local RGI gpkg + cached data only
cavedossier geo kota 1234 --offline        #   (elevation needs the cave's DEM tile cached)

# ── OSZ prefill (part 2.1b — fills the v10 template, embeds the karta,
#    delivers SB_<broj>_OSZ.docx into the cave's per-cave INTAKE folder under
#    !!!Digitalizacija/!Za digitalizirat: reuses the existing SB_<broj>_… leaf
#    wherever it sits, else creates SB_<broj>_<Ime>[_<Sinonimi>][_<Autori>]) ─
cavedossier osz prefill 1234               # SB + finders -> prefilled DOCX + prefill.json
                                           #   + dopune-sb.csv (empty SB cells a finder filled)
cavedossier osz prefill 1234 --force-karta # re-fetch the excerpt first (server-side save)
cavedossier osz prefill 1234 --offline     # never touch the network; an already-collected
                                           #   excerpt is still embedded, georef.hr is skipped
# Precedence: SB wins — computed values only fill EMPTY cells; disagreements
# (e.g. kota vs the DMV grid beyond 10 m) are warnings, never overrides.
# LiDAR flag: a cave whose name or synonym carries "lidar" (Lidarka, the
# "LiDAR Kristal N" Liburnija convention, …) had its coordinates and Z
# produced by the LiDAR analysis, so Izvor koordinata AND Izvor kote ulaza
# are prefilled as "LiDAR" — known in advance, even when the DMV grid
# disagrees (the warning then stays advisory).
# Migration: an OSZ already in the cave's intake leaf is read first and its
# content carries into the fresh document (dump: runs/osz/<broj>/stari_osz.json).
# TWO readers, tried in order: the v10 address reader (an older prefill someone
# filled in), then the LEGACY parser ported from crospeleo's OSZParser
# (osz/legacy.py) — it reads every pre-v10 zapisnik generation in the archive
# (the 2019 Gauss-Krüger layout, the 2025 "kamp" layout), including the choice
# fields whose selection lives in BOLD formatting, and maps everything onto the
# v10 template + checkbox ticks. Recorded content beats prefill ASSUMPTIONS
# (GPS default, pristup template, inferred source labels); SB + finder FACTS
# still win, differences become notes. The old file survives as
# <ime>_stari_<datum>.docx beside the new one; a re-run that changes nothing
# leaves everything untouched. Only a binary .doc needs a manual save-as-docx
# first — the tool says so.
# Pristup prefill: caves around one trailhead share the approach road, so
# config/pristupi.yaml maps a (Najbliže mjesto, Lokalitet) pair to a shared
# "Položaj i pristup objektu" text the recorder continues from "Od tuda
# nastaviti…" (first rule: Veprinac + Ćićarija). Add rules by editing the
# YAML — no code change; the geographic/clustering successor is a backlog idea. Any other cave with
# coordinates gets Izvor koordinata = "GPS", the most common source —
# the recorder corrects the rare exception by hand.
# Never prefilled by design: Katastarski broj (the archivist's manual final
# step), Duljina/Dubina (come from the survey), Datum istraživanja (SB only
# holds a year). dopune-sb.csv is a review list a person carries into Excel —
# nothing writes to SB automatically.

# ── OSZ fetch → SB backfill (part 2.1b — reads a FILLED zapisnik back) ──
cavedossier osz fetch 1234                 # find the cave's SB_<broj>_… dir in the intake
                                           #   tree (!Za digitalizirat), read the OSZ DOCX
                                           #   inside it (prefers osz/zapisnik-named files;
                                           #   falls back to the prefill copy) and propose
                                           #   the SB backfill
cavedossier osz fetch 1234 --osz-dir DIR   # search a different root for the SB_<broj>_… dir
cavedossier osz fetch 1234 --osz FILE      # point at an exact filled v10 DOCX instead
# Proposes for EMPTY SB cells: Broj pločice, Duljina, Dubina, Godina/period
# (cropped out of the OSZ's free-form Datum: "10.05.2025." -> "2025",
# two visits -> "2025-2026"), Autori nacrta (OSZ full names -> SB shorthand,
# "Lovel Kukuljan" -> "L.Kukuljan"; spellings matched so an author already
# in SB is never duplicated, and new authors MERGE, never replace).
# A NEW name in the OSZ replaces SB's Ime objekta and the old name moves
# into Sinonimi. Non-empty conflicting cells are printed as differences —
# SB kept, human decides. Output: dopune-sb-iz-osz.csv under runs/osz/<broj>/,
# carried into Excel by hand (write-back is M6). Exit 1 = something to carry.
```

## Quick checks

```powershell
cavedossier sb columns                      # what the tool sees in the workbook
cavedossier report --cave "Konglomeratača"  # one cave, end to end, both gates
cavedossier report --cave 570 --json        # the same dossier as data
cavedossier geo locate 570                  # the locality finders vs the SB row
cavedossier geo kota 570                    # DMV elevation vs the SB row's Z
cavedossier osz prefill 570                 # the whole 2.1b chain for one cave
```

## Setup (once)

```powershell
cd features/cave-dossier
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env     # then fill in (see below)
```

Optional extras per tool: `[karta]` (playwright + Pillow; then run
`playwright install chromium` once) for the isječak karte, `[osz]` (lxml) for
the OSZ prefill, `[geo]` (requests, geopandas, shapely, pyproj, rapidfuzz,
rasterio) for the locality/elevation finders — then a one-time
`cavedossier geo fetch-data` to provision the geodata. `[sb-write]` (xlwings)
stays dormant until M6.

### .env — per-machine facts

`.env` (gitignored, per-machine):

- `LOCAL_DRIVE_ROOT` — the Drive Desktop mount of the society archive. The
  **live workbook** resolves as `<LOCAL_DRIVE_ROOT>/<sb.workbook_filename>`
  and is the default read target (user, 2026-08-30); the archive dirs
  (nacrti, izjave, photos, isječci) resolve against it too.
- `SB_SANDBOX_PATH` — local **fallback copy**, read automatically when the live
  workbook is unreachable (Drive offline), open in someone's Excel, or
  unreadable. While live is healthy the copy is auto-refreshed to match it, so
  a fallback always reads the *last good* live state.
- `SB_WORKBOOK_PATH` — optional override that **forces** a sandbox copy
  (development / offline work); relative paths resolve against this feature's
  root, e.g. `example/sb-sandbox/!Speleo_baza_SUE_v3.0.xlsm`.
- `GEOREF_BASE_URL` / `GEOREF_USERNAME` / `GEOREF_PASSWORD` — georef.hr login
  for the `karta` flow.

### The SB mode banner

Every command prints the mode first — `SB mode: LIVE (...)`,
`SB mode: FALLBACK (...)` (with the conflict reason), or
`SB mode: SANDBOX (...)` (forced) — always check the banner.

> **A manual sandbox copy goes stale the moment SB is edited.** On 2026-08-29 a
> run against one reported a cave as missing that had just been added live
> (row 1311), because the copy still ended at 1301. The LIVE-first default with
> auto-refreshed fallback (2026-08-30) exists precisely to close that hole; a
> FALLBACK banner still means "data may lag — retry when SB is free".

### Dev vs prod — this setup is the DEV half

Everything on this page assumes the developer's PC. **Prod is the registry
Drive** (see [ARCHITECTURE.md](../../ARCHITECTURE.md) §Dev vs prod): the
people who will eventually run these tools work in the shared Drive folders,
not in a repo clone. Productionizing (a distributable entry point, cloud
copies of `data/geo/` and the template, a non-developer setup guide) is
noted but unscheduled — until then, keep the portability rules: one
subcommand per tool, per-machine facts only in `.env`, every local dataset
regenerable by one command, outputs delivered fail-soft into the hand-managed
Drive dirs.

### Two venvs exist

| Venv | What it holds | Use it for |
|---|---|---|
| `SurveyScraper5/.venv` (repo root) | this package **plus every optional extra** (playwright, lxml, geopandas, xlwings, …) + pytest | day-to-day work across features |
| `features/cave-dossier/.venv` | this package + `[dev]` only | isolated feature work / the setup above |

Both provide the `cavedossier` command, so either is fine — just don't expect
the optional extras in the feature-local one.

## Troubleshooting

- **Console shows `?` instead of š/č/ž** — `$env:PYTHONIOENCODING="utf-8"`
  (the CLI also self-reconfigures its output streams, so this is rarely needed).
- **`uv trampoline failed to canonicalize script path`** (or pip/pytest
  suddenly "vanish") — the venv was created under an older absolute path;
  moving or renaming the repo folder breaks every `.exe` shim and editable
  install inside it. Recreate the venv
  (`uv venv .venv --python "C:/Program Files/Python311/python.exe"`, reinstall
  from a `pip freeze` taken beforehand) and re-run
  `uv pip install -e features/cave-dossier`. Happened once already, after the
  SurveyScraper4 → SurveyScraper5 rename.
- **`SB mode: FALLBACK` banner** — someone has SB open in Excel or Drive is
  offline; the run reads the last good local copy. Data may lag — retry when
  SB is free before trusting numbers.
- **Drive delivery "nije uspjela (PermissionError…)"** — the target file is
  open in Word (or the mount is offline). The run-dir copy under `runs/…` is
  always produced; close the file / wait for network and re-run.

## Testing

```powershell
python -m pytest
```

Fixtures are synthetic (fake caves, fake names) — `tests/fixtures/mini_sb.xlsx`
is regenerated by `python tests/fixtures/make_mini_sb.py` and deliberately
reproduces the live workbook's traps (metadata row above the header, header
spelling variants, a queue row with no SUE, a surname-first author cell). Real
data checks run manually via the CLI against the sandbox — see
[STATUS.md](../../STATUS.md) for the current checklist.
