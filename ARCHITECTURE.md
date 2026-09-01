# SurveyScraper5 — pipeline architecture

The canonical map of the app. Part numbers below are **the** reference vocabulary —
use them in docs, STATUS.md, session logs, and conversation ("2.1b" always means
the OSZ builder). This is an early-stage plan: parts get built step by step, details
firm up as real usage accumulates.

## Contents

- [What the app produces](#what-the-app-produces)
- [The two main parts](#the-two-main-parts)
- [Part map](#part-map)
- [Bridges — the scripts between the nodes](#bridges--the-scripts-between-the-nodes)
  - [Map 1 — everything that flows INTO SB](#map-1--everything-that-flows-into-sb)
  - [Map 2 — producing the field kit (SB → prefilled zapisnik)](#map-2--producing-the-field-kit-sb--prefilled-zapisnik)
  - [Map 3 — identity, photos, readiness](#map-3--identity-photos-readiness)
  - [Bridge catalog](#bridge-catalog)
  - [Chains — whole journeys, bridge by bridge](#chains--whole-journeys-bridge-by-bridge)
- [Key facts that shape the design](#key-facts-that-shape-the-design)
- [Dev vs prod — a duality to design for](#dev-vs-prod--a-duality-to-design-for-noted-2026-08-30-unscheduled)
- [Milestones (stage 2)](#milestones-stage-2)

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

<pre>
 PART 1 — FIELD (mobile, PARKED)          PART 2 — STATIONARY (VS Code, PRIORITY)
┌──────────────────────────────┐         ┌───────────────────────────────────────────────┐
│ voice → text cave description│         │      <a href="#part-21">2.1</a> DOSSIER BUILDER (per cave) [<a href="#b9">B9</a>]      │
│ photos of cave/entrance      │  Drive  │  ┌─────────────────────────────────────────┐  │
│ TopoDroid .csx (via BT from  │ ─queue→ │  │ <a href="#part-21a">2.1a</a> csx-to-survey ─→ Nacrt PDF + dims  │  │
│   the survey phone)          │  dirs   │  │ <a href="#part-21b">2.1b</a> OSZ builder   ─→ OSZ DOCX [<a href="#b6">B6</a>·<a href="#b7">B7</a>]  │  │
└──────────────────────────────┘         │  │ <a href="#part-21c">2.1c</a> isječak karte ─→ excerpt PNG  [<a href="#b3">B3</a>] │  │
                                         │  │ <a href="#part-21d">2.1d</a> foto ulaza    ─→ renamed foto [<a href="#b8">B8</a>] │  │
        (manual for now: user            │  └───────────┬────────────────▲────────────┘  │
         copies files by hand)           │   [<a href="#b10">B10</a>] dims │   coords, year │ [<a href="#b6">B6</a>·<a href="#b9">B9</a>]       │
                                         │              ▼                │               │
                                         │        <a href="#part-22">2.2</a> REGISTRY ──────────┘               │
                                         │  ┌─────────────────────────────────────────┐  │
                                         │  │ <a href="#part-22a">2.2a</a> SB · Svi objekti — THE MASTER      │  │
                                         │  │      read basic data · write back [<a href="#b11">B11</a>] │  │
                                         │  │      ▲ [<a href="#b1">B1</a>+<a href="#h1">H1</a>]         ▼ [<a href="#b1">B1</a> lists]     │  │
                                         │  │      │ new rows        │ names, status, │  │
                                         │  │      │ + synonyms      │ deliverables   │  │
                                         │  │ <a href="#part-22b">2.2b</a> satellite tables                   │  │
                                         │  │      Liburnija gdoc (LiDAR Kristal) ·   │  │
                                         │  │      Literatura · Katastar RH           │  │
                                         │  │      joined on shared keys, never on a  │  │
                                         │  │      local row id · review lists [<a href="#h1">H1</a>]   │  │
                                         │  │      a person carries out, never an     │  │
                                         │  │      automatic write                    │  │
                                         │  └─────────────────────────────────────────┘  │
                                         └───────────────────────┬───────────────────────┘
                                                                 ▼  [<a href="#b11">B11</a>, M6]
                                          Drive archive dirs: OSZ · Nacrt · entrance photos
                                                                 ▼
                                          (downstream: crospeleo-automation → CroSpeleo cadastre)
</pre>

*Every part number and every `[B#]`/`[H#]` label above is a link — parts jump to their
[part-map](#part-map) row, bridge labels to the [bridge catalog](#bridge-catalog) row that
names the exact command.*

## Part map

| Part | What it is | Where it lives | Status |
|---|---|---|---|
| <a name="part-1"></a>**1** | Field mobile app (Android): voice→text description, photos→cloud, receive TopoDroid `.csx`, upload everything to Drive queue dirs | not started — to be built in Android Studio (via Gemini); user has a prior app to reuse as context | **PARKED** (manual workflow suffices; its only design interface is the intake dir contract, settled at 2.1's M2) |
| <a name="part-2"></a>**2** | Stationary local app for postprocessing, run from VS Code (no GUI yet — function over form) | `features/` below | **ACTIVE** |
| <a name="part-21"></a>**2.1** | Dossier builder — gathers all available data per cave, with warning/blocker gating (e.g. missing author izjava) | [features/cave-dossier/](features/cave-dossier/README.md) | in development |
| <a name="part-21a"></a>**2.1a** | csx-to-survey: TopoDroid TDX/CSX → processed survey → Nacrt (PDF/vector). Also yields cave dimensions → SB | [features/csx-to-survey-pipeline/](features/csx-to-survey-pipeline/README.md) — its own feature; integration via artifacts (Nacrt PDF + dimensions), never imports | operational (semi-manual pipeline) |
| <a name="part-21b"></a>**2.1b** | OSZ builder: fills the society's blank OSZ template (SB primary data + 2.1a results + part-1 field data + 2.1c excerpt). `cavedossier osz prefill <Redni broj>` delivers `SB_<broj>_OSZ.docx` prefilled from SB + the `geo/` finders (locality via DGU/RGI, kota via the open DMV grid) with the excerpt embedded; `cavedossier osz fetch` reads a FILLED zapisnik back and proposes the SB backfill (pločica, ime→sinonimi, duljina/dubina, godina, autori via the alias registry) as a review CSV | `features/cave-dossier/` (modules `osz/` + `geo/`) | **prefill + fetch operational** (2026-08-30); real-zapisnik validation + the CroSpeleo-field fetcher pending |
| <a name="part-21c"></a>**2.1c** | Isječak karte: map excerpt from georef.hr (HTRS96 coords → marker-centered PNG + record text). `cavedossier karta <Redni broj>` delivers `SB_<padded broj>.png` + a `!georef_zapisi.csv` row into the shared `!!Isječci karte` Drive dir | `features/cave-dossier/` (module `georef/`, ported from crospeleo-automation 2026-08-29) | **operational** (M3 done) |
| <a name="part-21d"></a>**2.1d** | Entrance-photo processing: field photos come off the camera at full resolution, so they are downsized (~1920 px / ~1.5 MB) and renamed to the archive convention (`<padded SUE>_<ime>_…_<autor>.jpg`) before being filed into `!!Fotografije ulaza`. Queued caves' photos live in the `!!Fotografije ulaza za istražit` staging folder keyed by **Redni broj**, and move across when the cave earns its SUE number. That move is manual today and routinely forgotten, so the tool also **flags staged photos whose cave already has a SUE number** — the leak that leaves old photos in the queue forever | `features/cave-dossier/` (module `photos/`) | matcher + staleness guard done 2026-08-28 (that staging sweep is finished and no longer run); **per-cave downsize + rename done 2026-09-01** (`photos process`, copies only); the mover into `!!Fotografije ulaza` under the katastarski broj is the remaining step |
| <a name="part-22"></a>**2.2** | **Registry communication** — everything the app knows about *which caves exist*. Not a side channel: 2.1 cannot start a dossier without it, and every finished dossier ends by writing back into it | `features/cave-dossier/` | in development |
| <a name="part-22a"></a>**2.2a** | **SB (Speleo baza)** — the master registry of all caves (discovered + to-be-explored), an `.xlsm` on the Drive mount. Source of coordinates/year/etc. for the OSZ; updated with new data (dimensions) once a survey is finished. Everything else in the app treats it as ground truth | `features/cave-dossier/` (module `sb/`) | **M1 ✅**; write-back at M6 |
| <a name="part-22b"></a>**2.2b** | **Satellite tables** — SB is the master but not the only table holding cave data. The *Liburnija* Google Sheet (the LiDAR Kristal table, live and edited in the field), plus `Literatura` and `Katastar RH` inside the workbook. None carries an SB row number, so they are joined on shared keys (pločica → `LiDAR Kristal N` synonym → coordinates), **never on a local row id**. `sat sync` compares a satellite against SB and emits four review lists a person carries out — it never writes to either side. This is how a LIDAR candidate becomes an SB row, and how the field sheet learns what happened to it | `features/cave-dossier/` (module `satellites/`), design in [docs/sb-liburnija-hub.md](features/cave-dossier/docs/sb-liburnija-hub.md) | **operational** — 126 rows entered SB from Liburnija 2026-08-29 |

> Picking a part tells you WHAT; the [Bridges section](#bridges--the-scripts-between-the-nodes)
> right below tells you what to RUN — find your part in its per-part table,
> follow the bridge labels through the maps, and each label resolves to its
> command in the [catalog](#bridge-catalog).

## Bridges — the scripts between the nodes

The part map above says what exists; THIS section says **what runs to get from
one node to another**. A *node* is where data lives (SB, a Drive dir, an
external service, a local cache); a *bridge* is the script or human step that
moves data between two nodes. Every scripted bridge is labeled **[B#]** and
every human step **[H#]**; the [catalog below](#bridge-catalog) resolves each
label to its exact command. Deep flags live in the feature README's
[command reference](features/cave-dossier/README.md#commands) — start from the
bridge, not from the command list.

**Which bridges do I need for part X?**

| Part | Its bridges |
|---|---|
| [2.1](#part-21) dossier builder | [**B9**](#b9) (report); intake tail of M2 pending |
| [2.1a](#part-21a) csx-to-survey | [**B10**](#b10) (M5, planned) — until then its own feature's pipeline |
| [2.1b](#part-21b) OSZ builder | [**B4**](#b4) (once) → [**B6**](#b6) (prefill) → [**H2**](#h2) (field) → [**B7**](#b7) (fetch) → [**H1**](#h1); [**B5**](#b5) to verify the finders |
| [2.1c](#part-21c) isječak karte | [**B3**](#b3) (standalone; B6 runs it for you) |
| [2.1d](#part-21d) fotografije ulaza | [**B8**](#b8) (downsize + rename, done); the *mover* into `!!Fotografije ulaza` rides with [**B11**](#b11) (M6) |
| [2.2a](#part-22a) SB master | destination of [**H1**](#h1); source of [B3](#b3)/[B6](#b6)/[B9](#b9); [**B11**](#b11) (M6) will write it |
| [2.2b](#part-22b) satellites | [**B1**](#b1) → [**H1**](#h1) |

### Map 1 — everything that flows INTO SB

Nothing writes to SB automatically before M6 — every inbound edge converges on
[**H1**](#h1), a person pasting a review list into Excel. That is the design,
not a gap ([key facts](#key-facts-that-shape-the-design)).

<pre>
  Liburnija LIDAR sheet          filled OSZ zapisnik            empty SB cells a geo
  (satellites, 2.2b)             (in the cave's intake dir,     finder could fill
        │                         arrived there via [<a href="#h2">H2</a>])       (found during prefill)
        │ [<a href="#b1">B1</a>] sat sync                │ [<a href="#b7">B7</a>] osz fetch              │ [<a href="#b6">B6</a>] osz prefill
        ▼                              ▼                             ▼
  4 review lists                dopune-sb-iz-osz.csv           dopune-sb.csv
  (new rows · synonyms ·        (pločica · ime→sinonimi ·      (Z · Najbliže mjesto ·
   corrections · decisions)      duljina/dubina · godina ·      Lokalitet)
        │                        autori)                            │
        └───────────────────────────────┴───────────────────────────┘
                                        │
                        [<a href="#h1">H1</a>] a person pastes into Svi objekti
                                        ▼
                     ┌─────────────────────────────────────┐
                     │   SB — Svi objekti  (THE MASTER)    │
                     │   !Speleo_baza_SUE_v3.0.xlsm, Drive │
                     └─────────────────────────────────────┘
</pre>

### Map 2 — producing the field kit (SB → prefilled zapisnik)

The 2.1b forward direction: from a bare SB row (name, synonym, X/Y) to a
zapisnik a recorder takes to the cave.

<pre>
                  ┌────────────────────────────────────┐
                  │ SB row: ime · sinonimi · X/Y HTRS  │
                  └───────┬─────────────────────┬──────┘
                          │                     │
              [<a href="#b3">B3</a>] karta  │                     │  [<a href="#b6">B6</a>] osz prefill
       (georef.hr, one    │                     │  (runs B3 itself when the
        server-side save) │                     │   excerpt is missing/stale)
                          ▼                     │
                  ┌───────────────┐             │
   georef.hr ───► │ !!Isječci     │────────────►│◄──────── data/geo cache
   (external)     │ karte:        │   excerpt   │          (RGI gazetteer · DGU
                  │ SB_&lt;broj&gt;.png │   embedded  │           granice · DMV tiles)
                  │ !georef_zapisi│             │                ▲
                  └───────────────┘             │                │ [<a href="#b4">B4</a>] geo fetch-data
                                                │                │ (once per machine;
                                                ▼                │  open DGU services)
              ┌──────────────────────────────────────────┐       │
              │ Osnovni speleološki zapisnik/            │   [<a href="#b5">B5</a>] geo locate / kota
              │ SB_&lt;broj&gt;_OSZ.docx  (prefilled: identity,│   (verify the finders
              │ koordinate+izvori, lokacija, kota,       │    against any SB row)
              │ isječak karte)                           │
              └───────────────┬──────────────────────────┘
                              │ [<a href="#h2">H2</a>] recorder completes it in the field and files
                              │      it into the cave's SB_&lt;broj&gt;_… intake dir
                              ▼
              !Za digitalizirat/SB_&lt;broj&gt;_…/   ── from here [<a href="#b7">B7</a>] reads it back (Map 1)
</pre>

### Map 3 — identity, photos, readiness

The bridges that keep names/numbers straight and say when a cave is done.

<pre>
  intake dirs (!Za digitalizirat)  ◄──[<a href="#b2">B2</a>] intake map──── SB row numbers
                                        (SB_&lt;broj&gt;_ prefix proposals, --apply renames)

  staged photos (…za istražit)     ◄──[<a href="#b8">B8</a>] photos ──────► SB
                                        (match-queued names them SB_&lt;broj&gt;_…,
                                         check-flag crosses them against SB's
                                         "Fotografija ulaza" cell)

  everything gathered so far       ───[<a href="#b9">B9</a>] report ──────► gate 1 (SUE) / gate 2
                                        (per-cave verdict:                (CroSpeleo)
                                         blocker · warning · not-checked-yet)

  registar osoba + izjave dir      ◄──[<a href="#b12">B12</a>] people ─────► SB author cells
  (data/people/registry.json ↔          (list/check: aliases resolved, per-person
   !!Izjave za katastar RH)              izjava linkage, missing-statement audit)

  2.1a survey artifacts            ···[<a href="#b10">B10</a>] (M5, planned)···► dossier (Nacrt + dims)
  finished dossier                 ···[<a href="#b11">B11</a>] (M6, planned)···► SB write-back + archive
                                        delivery; the 2.1d mover rides along
</pre>

### Bridge catalog

What each label actually runs. One line here; flags and details in the
[command reference](features/cave-dossier/README.md#commands).

| Label | Runs | From → to | Run it when |
|---|---|---|---|
| <a name="b1"></a>**B1** | `cavedossier sat sync` | satellite sheet ↔ SB → 4 review lists | the Liburnija sheet changed, or periodically |
| <a name="b2"></a>**B2** | `cavedossier intake map [--apply]` | SB numbering → intake dir names | new field-material folders appeared |
| <a name="b3"></a>**B3** | `cavedossier karta <broj>` | SB row → georef.hr → `!!Isječci karte` | a cave needs its excerpt (B6 calls this for you); each run is a server-side save |
| <a name="b4"></a>**B4** | `cavedossier geo fetch-data` | open DGU services → `data/geo` | once per machine (and after deleting the cache) |
| <a name="b5"></a>**B5** | `cavedossier geo locate/kota <broj>` | `data/geo` + RGI ↔ one SB row | verifying what the finders would say — feeds nothing |
| <a name="b6"></a>**B6** | `cavedossier osz prefill <broj>` | SB + excerpt + geo → prefilled DOCX (+ `dopune-sb.csv`) | a queued cave is about to be explored, or an explored one needs its zapisnik started |
| <a name="b7"></a>**B7** | `cavedossier osz fetch <broj>` | filled zapisnik → `dopune-sb-iz-osz.csv` | a completed zapisnik landed in the cave's intake dir |
| <a name="b8"></a>**B8** | `cavedossier photos process` (per cave) · `photos check-flag` · `photos match-queued` (one-off staging sweep, finished) | intake photos → archive-ready copies; staged photos ↔ SB | a cave's field photos arrived in its intake leaf |
| <a name="b9"></a>**B9** | `cavedossier report --cave <x>` | gathered sources → gate verdicts | any time — it never changes anything |
| <a name="b10"></a>**B10** | *(M5, planned)* | 2.1a Nacrt + dimensions → dossier | — |
| <a name="b11"></a>**B11** | *(M6, planned)* | dossier → SB write-back + archive delivery | — |
| <a name="b12"></a>**B12** | `cavedossier people list/check` | people registry ↔ izjave dir ↔ SB author cells → audit + `statements-index.json` | a new izjava or author appeared, or periodically — it never changes anything |
| <a name="h1"></a>**H1** | a person, in Excel | any `dopune-*.csv` / review list → `Svi objekti` | after B1 / B6 / B7 produce one |
| <a name="h2"></a>**H2** | the recorder, in the field | prefilled DOCX → completed zapisnik → cave's intake dir | after B6, around the exploration |

### Chains — whole journeys, bridge by bridge

The map answers "how do I get from A to B" as a bridge sequence:

- **A LIDAR point becomes an SB cave:** Liburnija sheet → [**B1**](#b1) →
  [**H1**](#h1) → SB row (*Za istražit*).
- **Prepare the field kit for a queued cave:** [**B4**](#b4) (first time only) →
  [**B6**](#b6) (auto-runs [**B3**](#b3) if needed) → print/hand over →
  [**H2**](#h2).
- **After the exploration:** [**H2**](#h2) (zapisnik filed) → [**B7**](#b7) →
  [**H1**](#h1) (SB backfilled) → [**B8**](#b8) (photos) → [**B9**](#b9)
  (is gate 1 met?) → *(M6: [B11](#b11) delivers and writes back)*.
- **Just checking where a cave stands:** [**B9**](#b9) alone; to sanity-check
  the finders' data first, [**B5**](#b5).
- **A new author (or izjava) appears:** file `Izjava_<Ime>.<ext>` into
  `!!Izjave za katastar RH` → [**B12**](#b12) (`people check` links it, or names
  the registry entry to add) → [**B9**](#b9) re-checks any cave they authored.

## Key facts that shape the design

- **SB is an Excel workbook**, `!Speleo_baza_SUE_v3.0.xlsm` — live, macro-heavy, shared,
  on a Google Drive Desktop mount. No Google API anywhere: all cloud access is
  locally-synced paths (`LOCAL_DRIVE_ROOT`). Reads are openpyxl (save physically
  impossible); the only safe write path is xlwings/Excel COM (Excel itself saves).
  See `features/cave-dossier/docs/EXCEL_WORKBOOK_SAFETY.md`.
- **Gating discipline** (inherited from crospeleo-automation): two tiers — *warnings*
  (advisory) vs *blockers* (hard gate on the final action). Statements ("Izjava za
  katastar") are checked **per author**, drawing and photo authors separately;
  statements live in their own Drive dir. Since 2026-08-30 the check goes through
  the **registar osoba** (`features/cave-dossier/data/people/registry.json`): one
  canonical name per person with aliases derived automatically, so SB's
  `L.Kukuljan`, an OSZ's `Lovel Kukuljan` and `Izjava_LKukuljan.pdf` are one
  person, and a locality-scoped izjava no longer satisfies a cave elsewhere. A
  missing/wrong-scope author izjava blocks gate 1; any other named person
  (recorder, team) without an izjava — or absent from the registry — warns at
  gate 2.
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

The **canonical definition** of the M-numbers used across STATUS, SESSIONS and
the code comments. They are the build order of stage 2 (the stationary app),
roughly M0 → M6; M3/M4 were explicitly order-flexible. Current per-milestone
state lives in [STATUS.md](STATUS.md) — this table only says what each one IS.

| M | Name | What it delivers | Parts |
|---|---|---|---|
| **M0** | Docs scaffold | Feature skeleton: pyproject, config, docs, sessions/backlog discipline | — |
| **M1** | SB read-only | `SBReader` against the live workbook (sandbox → live), `sb columns/inspect/stats`, the mode banner | 2.2a |
| **M2** | Dossier skeleton + `report` | The `CaveDossier` object, two-gate rule table, lifecycle states, `report --cave`; archive **intake** (resolving a cave's files on Drive) is the tail that closes it | 2.1 |
| **M3** | Isječak karte | The georef.hr flow ported: `karta <broj>` → excerpt PNG + georef zapis delivered to `!!Isječci karte` | 2.1c |
| **M4** | OSZ builder | Both directions over the v10 template: **prefill** (SB + geo finders → `SB_<broj>_OSZ.docx`) and **fetch** (filled zapisnik → SB backfill review list); the CroSpeleo-field fetcher (checkboxes, narratives, Docs variant) is its tail | 2.1b |
| **M5** | 2.1a artifact handoff | Consume the survey pipeline's products (Nacrt PDF + dimensions) into the dossier — integration via files, never imports | 2.1a↔2.1 |
| **M6** | SB write-back + delivery | The only WRITE milestone: xlwings/COM write-back of gathered data into SB, delivery of finished dossiers into the archive dirs; the 2.1d **mover** rides along — downsizing and the `SB_<broj>_…` naming are done (2026-09-01), but the move into `!!Fotografije ulaza` under the katastarski broj can only happen once that number exists | 2.2a, 2.1d |
