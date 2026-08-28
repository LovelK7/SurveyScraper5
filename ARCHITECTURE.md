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
         copies files by hand)           │              │ dims           │ coords, year   │
                                         │              ▼                │                │
                                         │        2.2 SB (Speleo baza) ─┘                │
                                         │        read basic data · write back new data  │
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
| **2.1c** | Isječak karte: map excerpt from georef.hr (HTRS96 coords → marker-centered PNG + record text) | `features/cave-dossier/` (module `georef/`, to be ported from crospeleo-automation) | not started |
| **2.1d** | Entrance-photo processing: field photos come off the camera at full resolution, so they are downsized (~1920 px / ~1.5 MB) and renamed to the archive convention (`<padded SUE>_<ime>_…_<autor>.jpg`) before being filed into `!!Fotografije ulaza`. Queued caves' photos live in the `!!Fotografije ulaza za istražit` staging folder keyed by **Redni broj**, and move across when the cave earns its SUE number. That move is manual today and routinely forgotten, so the tool also **flags staged photos whose cave already has a SUE number** — the leak that leaves old photos in the queue forever | `features/cave-dossier/` (module `photos/`) | matcher + staleness guard done 2026-08-28; downsizing not started |
| **2.2** | SB (Speleo baza) communication: the registry of all caves (discovered + to-be-explored). Source of coordinates/year/etc. for the OSZ; updated with new data (dimensions) once a survey is finished | `features/cave-dossier/` (module `sb/`) | **M1 in progress** |

## Key facts that shape the design

- **SB is an Excel workbook**, `!Speleo_baza_SUE_v2.4.xlsm` — live, macro-heavy, shared,
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
- **Real data from day one**: development and testing run against real dirs (photos,
  csx, descriptions) under gitignored `example/` zones; committed test fixtures are
  tiny and synthetic.
- **Reuse by porting**: code is COPIED from read-only `../crospeleo-automation` and
  adapted; every copy is logged in `features/cave-dossier/docs/PORTING.md`.

## Milestones (stage 2)

M0 docs scaffold ✅ → **M1 SB read-only (sandbox → live)** ✅ → M2 dossier skeleton +
`report` command → M3 isječak karte port / M4 OSZ builder (order flexible; M4 gated on
template) → M5 2.1a artifact handoff → M6 SB write-back + delivery to archive dirs
(2.1d entrance-photo processing rides along with M6: resizing + renaming is a
delivery action, and the SUE number it renames to only exists at that point).
Current state: [STATUS.md](STATUS.md).
