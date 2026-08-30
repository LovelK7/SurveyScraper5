# SurveyScraper5 — pipeline architecture

The canonical map of the app. Part numbers below are **the** reference vocabulary —
use them in docs, STATUS.md, session logs, and conversation ("2.1b" always means
the OSZ builder). This is an early-stage plan: parts get built step by step, details
firm up as real usage accumulates.

## What the app produces

From raw cave-exploration data to two final products per cave:

- **OSZ** — *osnovni speleološki zapisnik*, the common cave file (DOCX). Aggregates
  everything known about the cave: primary data from SB, survey results, field
  descriptions/photos, isječak karte.
- **Nacrt** — the survey map (vector PDF), produced from the TopoDroid survey.

Delivered (with entrance photos) into dedicated Google Drive archive dirs — the same
dirs the separate crospeleo-automation tool later consumes to submit the cave to the
national CroSpeleo cadastre. **SurveyScraper5 is the upstream producer; crospeleo-
automation is the downstream submitter.** Design every delivery format for that
continuity (SUE-prefixed filenames, OSZ labels its parser recognizes).

## The two main parts

```
 PART 1 — FIELD (mobile, PARKED)          PART 2 — STATIONARY (VS Code, PRIORITY)
┌──────────────────────────────┐         ┌───────────────────────────────────────────────┐
│ voice → text cave description│         │        2.1 DOSSIER BUILDER (per cave)         │
│ photos of cave/entrance      │  Drive  │  ┌─────────────────────────────────────────┐  │
│ TopoDroid .csx (via BT from  │ ─queue→ │  │ 2.1a csx-to-survey ─→ Nacrt PDF + dims  │  │
│   the survey phone)          │  dirs   │  │ 2.1b OSZ builder   ─→ OSZ DOCX          │  │
└──────────────────────────────┘         │  │ 2.1c isječak karte ─→ map excerpt PNG   │  │
                                         │  │ 2.1d foto ulaza    ─→ resized + renamed │  │
        (manual for now: user            │  └───────────┬────────────────▲────────────┘  │
         copies files by hand)           │              │ dims           │ coords, year  │
                                         │              ▼                │               │
                                         │        2.2 REGISTRY ──────────┘               │
                                         │  ┌─────────────────────────────────────────┐  │
                                         │  │ 2.2a SB · Svi objekti — THE MASTER      │  │
                                         │  │      read basic data · write back new   │  │
                                         │  │      ▲                ▼                 │  │
                                         │  │      │ new rows       │ names, status,  │  │
                                         │  │      │ + synonyms     │ deliverables    │  │
                                         │  │ 2.2b satellite tables                   │  │
                                         │  │      Liburnija gdoc (LiDAR Kristal) ·   │  │
                                         │  │      Literatura · Katastar RH           │  │
                                         │  │      joined on shared keys, never on a  │  │
                                         │  │      local row id · review lists a      │  │
                                         │  │      person carries out, never an       │  │
                                         │  │      automatic write                    │  │
                                         │  └─────────────────────────────────────────┘  │
                                         └───────────────────────┬───────────────────────┘
                                                                 ▼
                                          Drive archive dirs: OSZ · Nacrt · entrance photos
                                                                 ▼
                                          (downstream: crospeleo-automation → CroSpeleo cadastre)
```

## Part map

| Part | What it is | Where it lives | Status |
|---|---|---|---|
| **1** | Field mobile app (Android): voice→text description, photos→cloud, receive TopoDroid `.csx`, upload everything to Drive queue dirs | not started — to be built in Android Studio (via Gemini); user has a prior app to reuse as context | **PARKED** (manual workflow suffices; its only design interface is the intake dir contract, settled at 2.1's M2) |
| **2** | Stationary local app for postprocessing, run from VS Code (no GUI yet — function over form) | `features/` below | **ACTIVE** |
| **2.1** | Dossier builder — gathers all available data per cave, with warning/blocker gating (e.g. missing author izjava) | [features/cave-dossier/](features/cave-dossier/README.md) | in development |
| **2.1a** | csx-to-survey: TopoDroid TDX/CSX → processed survey → Nacrt (PDF/vector). Also yields cave dimensions → SB | [features/csx-to-survey-pipeline/](features/csx-to-survey-pipeline/README.md) — its own feature; integration via artifacts (Nacrt PDF + dimensions), never imports | operational (semi-manual pipeline) |
| **2.1b** | OSZ builder: fills the society's blank OSZ template (SB primary data + 2.1a results + part-1 field data + 2.1c excerpt) | `features/cave-dossier/` (module `osz/`) | waiting on template DOCX |
| **2.1c** | Isječak karte: map excerpt from georef.hr (HTRS96 coords → marker-centered PNG + record text). `cavedossier karta <Redni broj>` delivers `SB_<padded broj>.png` + a `!georef_zapisi.csv` row into the shared `!!Isječci karte` Drive dir | `features/cave-dossier/` (module `georef/`, ported from crospeleo-automation 2026-08-29) | **operational** (M3 done) |
| **2.1d** | Entrance-photo processing: field photos come off the camera at full resolution, so they are downsized (~1920 px / ~1.5 MB) and renamed to the archive convention (`<padded SUE>_<ime>_…_<autor>.jpg`) before being filed into `!!Fotografije ulaza`. Queued caves' photos live in the `!!Fotografije ulaza za istražit` staging folder keyed by **Redni broj**, and move across when the cave earns its SUE number. That move is manual today and routinely forgotten, so the tool also **flags staged photos whose cave already has a SUE number** — the leak that leaves old photos in the queue forever | `features/cave-dossier/` (module `photos/`) | matcher + staleness guard done 2026-08-28; downsizing not started |
| **2.2** | **Registry communication** — everything the app knows about *which caves exist*. Not a side channel: 2.1 cannot start a dossier without it, and every finished dossier ends by writing back into it | `features/cave-dossier/` | in development |
| **2.2a** | **SB (Speleo baza)** — the master registry of all caves (discovered + to-be-explored), an `.xlsm` on the Drive mount. Source of coordinates/year/etc. for the OSZ; updated with new data (dimensions) once a survey is finished. Everything else in the app treats it as ground truth | `features/cave-dossier/` (module `sb/`) | **M1 ✅**; write-back at M6 |
| **2.2b** | **Satellite tables** — SB is the master but not the only table holding cave data. The *Liburnija* Google Sheet (the LiDAR Kristal table, live and edited in the field), plus `Literatura` and `Katastar RH` inside the workbook. None carries an SB row number, so they are joined on shared keys (pločica → `LiDAR Kristal N` synonym → coordinates), **never on a local row id**. `sat sync` compares a satellite against SB and emits four review lists a person carries out — it never writes to either side. This is how a LIDAR candidate becomes an SB row, and how the field sheet learns what happened to it | `features/cave-dossier/` (module `satellites/`), design in [docs/sb-liburnija-hub.md](features/cave-dossier/docs/sb-liburnija-hub.md) | **operational** — 126 rows entered SB from Liburnija 2026-08-29 |

## Key facts that shape the design

- **SB is an Excel workbook**, `!Speleo_baza_SUE_v3.0.xlsm` — live, macro-heavy, shared,
  on a Google Drive Desktop mount. No Google API anywhere: all cloud access is
  locally-synced paths (`LOCAL_DRIVE_ROOT`). Reads are openpyxl (save physically
  impossible); the only safe write path is xlwings/Excel COM (Excel itself saves).
  See `features/cave-dossier/docs/EXCEL_WORKBOOK_SAFETY.md`.
- **Gating discipline** (inherited from crospeleo-automation): two tiers — *warnings*
  (advisory) vs *blockers* (hard gate on the final action). Statements ("Izjava za
  katastar") are checked **per author**, drawing and photo authors separately;
  statements live in their own Drive dir.
- **Two gates, not one** (user, 2026-08-26). Gate 1 is the society's own step:
  Nacrt + OSZ + fotografije ulaza + pločica + izjave earn the cave its
  **katastarski broj SUE**, which is what moves its SB row into *Istraženi*.
  Gate 2 is the stricter CroSpeleo bar (Protokol v6) — a superset, and holding a
  SUE number makes it "almost a certain go". A cave's SB lifecycle is therefore
  *Za istražit* → *Nesređeni* → *Istraženi*, and everything short of Istraženi is
  a queue item.
- **Croatian terms are domain identity** (OSZ, Nacrt, SB, SUE, izjava, isječak karte) —
  see [shared/glossary.md](shared/glossary.md). The codebase itself is English.
- **Never join a satellite on its own row number** (2.2b). Every satellite
  numbers its own rows, and those numbers leak into folder and file names where
  three schemes collide; a measured test resolved 5 of 20 field numbers to the
  *wrong* cave. Join on a shared key, ranked: Broj pločice → `LiDAR Kristal N`
  synonym → Katastarski broj RH → HTRS coordinates (tight, calibrated bands) →
  name (corroboration and duplicate-guard only). Details and the measurements:
  [sb-satellite-tables.md](features/cave-dossier/docs/sb-satellite-tables.md).
- **A LIDAR table carries a stage SB does not model**: *probable* caves — points
  nobody has yet checked are caves at all (`provjereno` / `speleo_obj`). A row
  crosses into SB only once it is confirmed a cave, entering as *Za istražit* or
  *Istraženi*; SB gets no "za provjeriti" sheet for now. So the satellite owns
  the pre-SB stage and SB owns everything after the crossing — that split is what
  makes the traffic safely two-way.
- **Nothing writes to a live shared source automatically.** SB is a macro-heavy
  workbook and Liburnija is a Google Sheet people type into in the field, so
  `sat sync` produces review lists (a paste-able CSV for SB, worksheets for the
  rest) and a person carries them out. Same reasoning as the Excel safety rules:
  [sb-liburnija-hub.md](features/cave-dossier/docs/sb-liburnija-hub.md) §7.
- **Real data from day one**: development and testing run against real dirs (photos,
  csx, descriptions) under gitignored `example/` zones; committed test fixtures are
  tiny and synthetic.
- **Reuse by porting**: code is COPIED from read-only `../crospeleo-automation` and
  adapted; every copy is logged in `features/cave-dossier/docs/PORTING.md`.

## Dev vs prod — a duality to design for (noted 2026-08-30, unscheduled)

Today everything runs in **dev**: this repo on the developer's PC (VS Code,
local Python venvs, a Google Drive Desktop mount, GitHub as backup). But
**prod is the registry Drive itself** — the shared `Speleo baza SUE` folder is
where the society's real work lives, and the people who will eventually run
these tools (recorders, the archivist) work *there*, not in a cloned repo.
Anything a tool needs must therefore one day be available FROM the Drive side:
not just entry-point scripts, but everything they stand on —

- the Python package + its optional extras (or a packaged/self-contained form);
- per-machine config (`.env`: `LOCAL_DRIVE_ROOT`, georef credentials) with a
  setup story a non-developer can follow;
- the regenerable local data (`data/geo/` GeoPackages + DEM tiles — or cloud
  copies of them on the Drive so `fetch-data` becomes a copy, not a download);
- the committed inputs tools read at runtime (OSZ v10 template,
  `config/selectors.yaml`, `config.yaml`).

Nothing is productionized yet and no milestone schedules it. What we do NOW is
keep the code prod-portable so that step stays cheap. Standing rules:

- **One command per tool, no repo knowledge required to run it** — every
  capability is a `cavedossier` subcommand with the Redni broj as the only
  input; keep it that way.
- **Per-machine facts live only in `.env`**, never in code or committed config.
- **Every local dataset must be regenerable from open services by one command**
  (`geo fetch-data` is the model) — a prod machine can then be provisioned
  by running it once, or by copying a ready-made bundle to/from the Drive.
- **Outputs already land in prod** (the `!!`-prefixed Drive dirs) and tolerate
  hand management there — that contract (fail-soft delivery, self-healing
  collections, review lists instead of writes) is the prod interface and must
  survive any packaging.

When productionization becomes real, expect: a distributable entry point
(installer, bundled runtime, or thin launcher scripts beside the Drive dirs),
cloud copies of `data/geo/` and the template on the Drive, and a documented
non-developer setup. Track it as its own work item when its time comes.

## Milestones (stage 2)

M0 docs scaffold ✅ → **M1 SB read-only (sandbox → live)** ✅ → M2 dossier skeleton +
`report` command → M3 isječak karte port / M4 OSZ builder (order flexible; M4 gated on
template) → M5 2.1a artifact handoff → M6 SB write-back + delivery to archive dirs
(2.1d entrance-photo processing rides along with M6: resizing + renaming is a
delivery action, and the SUE number it renames to only exists at that point).
Current state: [STATUS.md](STATUS.md).
