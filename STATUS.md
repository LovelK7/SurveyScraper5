# STATUS

Updated: 2026-08-30 (maintained by `/wrap-up` at the end of each session)


Part numbering per [ARCHITECTURE.md](ARCHITECTURE.md).

## Part status

| Part | Status |
|---|---|
| 1 — field mobile app | PARKED (manual workflow; revisit after stage 2 works) |
| 2.1a — csx-to-survey | OPERATIONAL (own feature, semi-manual 4-step pipeline) |
| 2.1b — OSZ builder | **PREFILL SLICE OPERATIONAL (2026-08-30, evening)** — `cavedossier osz prefill <Redni broj>` fills the v10 template from SB + the new `geo/` finders (županija/grad-općina via DGU boundaries, najbliže mjesto/lokalitet via RGI, kota via open INSPIRE DMV grid), embeds the isječak karte, delivers `SB_<broj>_OSZ.docx` to `!!!Digitalizacija/Osnovni speleološki zapisnik`, and emits `dopune-sb.csv` (human-executed SB review list). SB wins on conflicts; LiDAR-named caves get Izvor koordinata/kote = LiDAR, others default GPS; Katastarski broj / Duljina / Dubina / Datum never prefilled (user rules). `--offline` works fully from local data. Validated live on 651, 764, 1320 + a 24-cave finder sweep. Still M4's other half: READING filled zapisnici back (`w:sdt` parser + Docs text parser) |
| 2.1c — isječak karte | **OPERATIONAL (M3 done 2026-08-30)** — `cavedossier karta <Redni broj>` runs the ported georef.hr Playwright flow and delivers the excerpt + a row in `!georef_zapisi.csv` to the shared `!!Isječci karte` Drive folder. **Format changed same evening: landscape 5:4, ~1.5 km above/below the entrance** (was 1:1 / ~2.5 km); old-format or hand-deleted/mangled collections self-heal — refresh_reason detects wrong aspect, missing CSV rows, Excel-stripped padding |
| 2.1d — fotografije ulaza | **new part, added 2026-08-26**. Matcher + staleness guard DONE (2026-08-28); downsizing not started. Staged photos are keyed by Redni broj in `…za istražit` (a queue, not a repo) and move to `!!Fotografije ulaza` as `<padded SUE>_…` when the cave is explored. Downsizing rides along with M6 |
| 2.1 — dossier builder | **M2 in progress** — dossier model + **two-gate** gating + lifecycle + `report` done; **people registry + statement gates live (2026-08-30)**: `data/people/registry.json` (131 people, seeded from the izjave dir), registry/scope-aware per-author izjava blocker at gate 1, per-person missing-izjava warning at gate 2, `cavedossier people list/check`. Per-cave archive intake (nacrt/OSZ/foto) still next |
| 2.2a — SB (master registry) | **M1 ✅ DONE** (read-only, live SB v3.0). Live workbook now **1438 rows**; write-back still M6 |
| 2.2b — satellite tables | **OPERATIONAL (new 2026-08-29)** — `cavedossier sat sync` compares a satellite against SB and emits four review lists; never writes to either side. Liburnija done end to end: **126 rows entered SB**, 7 synonyms added, run is idempotent. `Literatura` (45) and `Katastar RH` (4595) still untouched |

## Milestone ladder

Definitions live in [ARCHITECTURE.md §Milestones](ARCHITECTURE.md#milestones-stage-2);
this table is where each one STANDS. Detailed checklists follow below.

| M | Name | Status |
|---|---|---|
| M0 | Docs scaffold | ✅ done (2026-08-16) |
| M1 | SB read-only | ✅ done (2026-08-25) — live workbook, banner, sandbox fallback |
| M2 | Dossier skeleton + `report` | ◐ in progress — model/gating/report + people registry & statement gates shipped; **per-cave archive intake is the open tail** |
| M3 | Isječak karte | ✅ done (2026-08-30) — 5:4 format + self-healing collection same day |
| M4 | OSZ builder | ◐ prefill + SB-backfill fetch shipped (2026-08-30); CroSpeleo-field fetcher + real-zapisnik validation open |
| M5 | 2.1a artifact handoff | not started (blocked on the intake dir layout going live) |
| M6 | SB write-back + delivery (+ 2.1d processing) | not started — everything upstream feeds review lists until then |

## M1 — SB read-only communication ✅ complete (2026-08-25)

- [x] Feature scaffold `features/cave-dossier/` (pyproject, config, docs, sessions)
- [x] Port normalization + sb_safe_io + trimmed SB reader (see docs/PORTING.md)
- [x] CLI: `cavedossier sb columns` / `sb inspect --cave` / `sb stats` with SANDBOX/LIVE banner
- [x] Unit tests on synthetic fixture (header autodetect, find_cave)
- [x] Sandbox copy of the live workbook in `example/sb-sandbox/` (refreshed 2026-08-25 → v3.0)
- [x] One read-only run against the LIVE workbook; stats identical to sandbox
- [x] User eyeballed known caves via `sb inspect` against Excel — dossier data checks out (2026-08-25)
- [x] "Caves to be explored" source confirmed: **"Za istražit"** table. Decision
      2026-08-22: SB gets restructured — Za istražit rows merge into Svi objekti
      (by year), flagged by a `za istražit, <old broj>, <note>` prefix in
      **Napomena**; Za istražit becomes a Power Query view (like
      Istraženi/Nesređeni). Prompt for Claude in Excel:
      [features/cave-dossier/docs/sb-restructure-excel-prompt.md](features/cave-dossier/docs/sb-restructure-excel-prompt.md)
- [x] User executed the SB restructure in Excel → **`!Speleo_baza_SUE_v3.0.xlsm`**
      (2026-08-25). Single master `Svi objekti` (table `SO_v2_1`, header row 2,
      1301 rows, 24 cols — GK columns dropped); Istraženi / Nesređeni / **Za
      istražit** are all Power Query views now (`IO_v2_1`, `NO_v2_1`, `ZI_v2_1`);
      old sheet kept as `Za istražit ARHIVA v2.4`. 185 rows carry the
      `za istražit, …` flag in Napomena. Config + sandbox + `safe_io` repointed;
      7 tests green.

## Current milestone — M2: dossier skeleton + `report` command

Scope per [ARCHITECTURE.md](ARCHITECTURE.md) §Milestones. **Draft — confirm at kickoff.**

- [x] Dossier model (`dossier/`): fields the OSZ + SB + archive supply, warning/blocker gating
      — `model.py` (`CaveDossier` + `Source` provenance), `sb_mapper.py` (SB row -> dossier,
      queue-flag parsing), `gating.py` (Protokol v6 Tablica 2 / §5.1 rules, each declaring the
      source that feeds it), `report.py`. 33 tests green; gating smoke-run over all 1294
      named sandbox rows without a crash.
- [x] **Workflow model corrected to the society's real two gates** (user answers 2026-08-26):
      gate 1 = katastarski broj SUE (Nacrt + OSZ + foto + pločica + izjave), gate 2 = CroSpeleo
      (Protokol v6 superset). The SUE number moved OUT of gate 1 — it is what gate 1 *produces*.
      `LifecycleState` (Istraženi / Za istražit / Nesređeni / sudjelovanje / nesvrstano) is derived from the
      **workbook's own Power Query** (`Formulas/Section1.m`, extracted 2026-08-26), so the tool
      and the Excel views cannot drift. Exit codes are now 1 ready / 0 not ready / 99 error,
      with `--gate {sue,crospeleo}`. Author cells: the `(SOV)` bracket is parsed as an
      outside-society flag, not part of the name.
      Live counts: 885 Istraženi · 185 Za istražit · 177 Nesređeni · 77 sudjelovanje · **19 in no view at all**.
- [x] **People registry + statement gates (2026-08-30, user request)** — `people/`
      package (`registry` · `name_resolver` · `statements`; crospeleo ports, see
      PORTING.md) + committed `data/people/registry.json` (131 people, seeded from
      `!!Izjave za katastar RH`; aliases derived at load with collision detection,
      curated `aliases` win). Izjave get their own gather step (`Source.STATEMENTS`
      — the dir is shared, so no waiting on per-cave intake): gate 1 now blocks
      per author through the registry AND the izjava scope rule (a Šverda-scoped
      izjava no longer covers an Učka cave); gate 2 **warns per person** —
      recorder/team member without any izjava, or a person the registry cannot
      resolve. New CLI `cavedossier people list` / `people check` (registry-wide
      audit + `runs/people/statements-index.json`). **Author-vs-finder criterion**
      (user, same day): in `Autori nacrta ili izvor` only the `N.Surname` shape
      marks a survey author — everything else is a finder/source with no izjava
      obligation (`is_author_shorthand`, applied in gating and the sweep). First
      live `people check`: 133 izjave all linked, 0 orphans; **28 real authors
      outside the registry** (down from 125 before the criterion — the standing
      worklist, S.Antolič 21× at the top). 197 tests green.
- [ ] Intake: resolve a cave's archive files from Drive (nacrt, fotografije ulaza, OSZ)
      — needs the `drive_resolver` port; until then `Source.ARCHIVE`
      rules report as *not checked yet* (izjave no longer wait on this — see above)
- [~] `cavedossier report --cave <n>`: what is present / missing / blocking, per Protocol v6
      Tablica 2 — **shipped SB-only** (`--json` too); fills out as intake / 2.1a / OSZ land
- [~] Queue reader over the v3.0 Napomena flag (`za istražit, [<old broj>,] <note>` — the
      old Broj is optional, see `Ponor Gotovž`) — **parser done** (`parse_queue_flag`,
      185/185 rows flagged, surfaced as a context warning in `report`); the listing
      command (`sb za-istrazit`) is still open
- [x] Workbook-wide audits added on the user's request (2026-08-26):
      `cavedossier sb audit-authors` (483 rows flagged across 6 categories) and
      `cavedossier sb unclassified` (the 47 rows in no SB view). Both read-only.
- [x] **2.1d staged-photo matcher**: `cavedossier photos match-queued` maps the free-form
      files in `!!Fotografije ulaza za istražit` back to SB rows by plaque / cave name / old
      Za-istražit broj and proposes `<Redni broj>_…`, replacing stale old-number prefixes.
      **52 of 52 matched**; dry run by default, `--apply` performs the renames.
- [x] **Satellite hub shipped (2026-08-29)** — `cave_dossier/satellites/`
      (`model` · `liburnija` · `resolver` · `sync`) plus `cavedossier sat sync`.
      Resolves every sheet row against SB on ranked keys (pločica → `LiDAR Kristal N`
      synonym → coordinates → name-as-duplicate-guard), never on a local row id, and
      emits four review lists: new SB rows as a paste-able CSV, synonym additions to
      existing rows, sheet corrections, and things to decide. **Read-only on both
      sides.** 41 tests. Design: [docs/sb-liburnija-hub.md](features/cave-dossier/docs/sb-liburnija-hub.md).
- [x] **Liburnija round trip completed** — 126 confirmed caves pasted into `Svi objekti`
      (Redni broj 1313–1438, `Lokalitet = Ćićarija`, year from `datum provjere`,
      `Napomena` seeded with the `za istražit` queue flag) and 7 `LiDAR Kristal N`
      synonyms added to existing rows. Verified cell by cell against the generated
      CSV: every cell matches bar three deliberate capitalisations. Re-run is clean —
      0 to add, 0 conflicts. *Za istražit* 199 → 325.
- [~] Field-data intake dir layout on Drive (blocks the 2.1a handoff) — **layout settled
      2026-08-28**: the leaf folders under `!!!Digitalizacija/!Za digitalizirat` get a
      `<Redni broj>_<Ime objekta>_<original>` prefix. `cavedossier intake map` proposes the
      mapping (dry run; `--apply` renames). The Veprinac folders are named after rows in
      the **Liburnija_pot_speleo_2024** Google Sheet (396 LIDAR candidates); that row's
      plaque number is what links them to SB, resolving 14 of 15. Read-only bridge in
      `intake/liburnija.py` over a gitignored CSV cache — wiring the sheet in as a real
      source is a later architecture decision (user, 2026-08-29).
      Mapping **agreed 2026-08-29**: user added *Jamorinke* (row 1311, pločica 051-814),
      deleted two duplicate folders, confirmed five empty leaves are placeholders and
      that sheet row 89 (*Jama na Patuhovcu*, another society's cave) stays out of SB.
      **End state: 53 leaves = 34 mapped + 19 new entries, nothing unresolved.**
      User supplied the last mappings (kripanj_ivana -> 1215 Paraglajderska, Solareva
      draga -> 1312, both Tingen-BP leaves -> 1122 BP) and confirmed every remaining
      leaf is a cave to be entered into SB. Renames approved in principle, awaiting
      `intake map --apply`.
      Sandbox copy refreshed from live the same day (1301 -> 1313 rows): a stale sandbox
      had reported the freshly added Jamorinke row as missing.

**M4 (OSZ builder) is no longer gated** — the template shipped 2026-08-25; picking it up
before M2 finishes is allowed (ARCHITECTURE calls the M3/M4 order flexible).

## M4 progress — 2.1b prefill slice ✅ shipped (2026-08-30)

- [x] `cave_dossier/geo/` — locality finder (ported from crospeleo `locality/`:
      RGI WFS client + offline gpkg fallback, DGU admin point-in-polygon, toponym
      matcher, SB-wins synthesizer) + NEW elevation finder (open INSPIRE EL-COV
      DMV grid, EPSG:3765→3045, lazy 34 MB tiles, nodata window + neighbour-tile
      rescue) + `geo fetch-data` provisioning (RGI paged download 125,731 places;
      admin boundaries stream-parsed out of the 600 MB INSPIRE AU GML — GDAL
      cannot read its xlink attributes). Data in gitignored `data/geo/`.
- [x] `cave_dossier/osz/` — writer (lxml primitives from make_mockup + NEW
      `embed_png`; fills in each cell's OWN paragraph-mark style), versioned v10
      address map, prefill orchestrator + `prefill.json` sidecar + `dopune-sb.csv`.
- [x] CLI: `geo fetch-data / locate / kota`, `osz prefill`, `--offline` on all
      finders + prefill; new extras `[geo]`, `[osz]`→lxml.
- [x] Field rules (user): SB wins + mismatch warnings (kota tolerance 10 m);
      LiDAR flag → Izvor koordinata + Izvor kote = "LiDAR"; GPS default otherwise;
      Katastarski broj / Duljina / Dubina / Datum istraživanja never prefilled.
- [x] Live validation: 651 / 764 / 1320 delivered + Word-verified (81 controls,
      correct fonts, embedded 5:4 excerpt); 24-cave stratified finder sweep
      (Δkota ≤ 5 m for 20/24, admin fields 24/24 correct).
- [x] **SB backfill fetcher shipped (2026-08-30, late)** — `cavedossier osz fetch
      <broj> [--osz FILE]`: `osz/reader.py` (w:sdt-aware, placeholders read as
      empty) + `osz/backfill.py` (fill-missing / note-conflicts; new OSZ name
      replaces SB's and the old name moves to Sinonimi; Datum cropped to SB's
      godina/period convention; Crtali full names ↔ SB `L.Kukuljan` shorthand via
      the ported alias registry `core/person_aliases.py`; authors merge, never
      drop) → `dopune-sb-iz-osz.csv` review list. Validated: mockup 811 vs SB 764
      (7/7 fields confirmed across conventions) + a simulated completed zapisnik
      for queued 1320 (6 proposals incl. the name→synonym move). Tests 183 → 193.
- [ ] Validate `osz fetch` on the first REAL filled zapisnici from recorders;
      then the CroSpeleo-field fetcher (checkbox groups, narrative controls,
      Google-Docs text variant).
- [ ] Batch mode (`osz prefill --missing`-style sweep) — backlog.

## Waiting on user

- ~~Society's blank OSZ template DOCX~~ → delivered 2026-08-23:
  [features/cave-dossier/osz-template/templates/Zapisnik_OSZ_v10.docx](features/cave-dossier/osz-template/templates/Zapisnik_OSZ_v10.docx)
- ~~Distribute OSZ v10 to recorders~~ → done 2026-08-25. Two cosmetic leftovers stay
  open (11 pt Literatura/Napomene, filled form runs to 5 pages), see
  [audit-v10.2.md](features/cave-dossier/osz-template/docs/audit-v10.2.md) §"Sitnice";
  neither blocks use, both fold into the next template revision.
- First filled zapisnici coming back from recorders — collect 2–3 (ideally one from
  Word, one from Google Docs) as parser fixtures before M4 starts.
- Mobile-app context material (parked with part 1)

### Settled 2026-08-30

- **Redni-broj prefixes are marked `SB_`** (`SB_1234_…`): a bare number reads
  like a katastarski broj, and both numberings coexist in the archive. Applied
  everywhere at once — map excerpts (`SB_0764.png`), the 34 intake folders, the
  62 staged photos. The matcher treats a bare `<broj>_` prefix as an upgrade
  proposal and `SB_<broj>_` as the fixed point; SUE prefixes stay bare.
- **Georef record collation**: one `!georef_zapisi.csv` at the top of
  `!!Isječci karte` (upserted by Redni broj), not per-cave text files.
- Each georef.hr save allocates a **new server-side point ID** — `--force`
  re-runs litter the registry a little; acceptable, same as crospeleo re-runs.

### Settled 2026-08-26 (details in the feature README)

- **Pre-SUE ID = `Redni broj`** (SB column). `sue_number` takes over at gate 1;
  the Excel row number is only the M6 write-back handle, never an identifier.
- **Photo budget**: gate warns above 2 MB; processing target 1920 px long edge / ~1.5 MB
  ("FastStone resize to screen size"), in `config.yaml` under `photos:`.
- **Column renamed live**: `Autori nacrta` → **`Autori nacrta ili izvor`** (for queued caves
  the cell holds the finder/source, not a survey author). `sb.column_aliases` keeps older
  copies of the workbook readable — without it the tool would have found no authors at all.
- **Staged photos** keep free names + a `Redni broj` prefix; `photos match-queued` matches
  them by plaque / name / synonym / old queue broj / a manual map.

- **Izjava filenames**: `Izjava_<Osoba>[_<Opseg>]`; no suffix = universal, a suffix is a
  scope (locality or a single cave), and a **double surname is hyphen-joined** so the
  underscore always means scope. Encoded in `archive/izjave.py` with the one legacy
  exception listed explicitly. ~~Becomes a gate-1 rule at intake~~ — **live since
  2026-08-30** via the people registry + `Source.STATEMENTS` (no waiting on intake).
- **`sudjelovanje` is its own lifecycle state** (77 rows) — another society's cave that
  SUE took part in. Recognising it shrank the unclassified list from 47 rows to 19.
- **`photos match-queued --apply`** performs the renames; dry run is the default.

- **Staged photos now match 52 of 52** (2026-08-28): `rubinija` was a transposition of
  *Rubijina jama* (Redni broj 1214), `kostrčani` was removed by the user as unidentifiable.
- **Staleness guard added**: promoting a queued cave's photos to the SUE number is manual
  and gets forgotten, so `photos match-queued` flags any staged photo whose cave already
  holds a SUE number as PROMOTE-or-DELETE and excludes it from the Redni-broj rename.
  Currently 0 such photos — the guard is preventive.
- **User added the Sudjelovanje Power Query** to SB (`S_v2_1`, sheet *Sudjelovanje*);
  its filter is the same keyword this tool matches, verified against the live workbook.

### Still open

1. **Field-data intake dir layout on Drive** — unblocked by the Redni-broj decision;
   proposal to be drafted. This is what gates the 2.1a handoff.
2. **Liburnija sheet corrections not yet applied** (30 cells) — `sat sync` list 3,
   to be typed into the Google Sheet by hand: 15 × `Foto ulaza`, 9 names SB is
   authoritative for, 1 `Br.pl`, 1 `istrazeno`, 2 deliverable flags.
3. **Two entrance-photo questions** (`sat sync` list 4): sheet rows 130 (SB 1370)
   and 369 (SB 407) claim a `Foto ulaza` that SB does not say DA to — check which
   side is right and fix SB if the photo exists.
4. **`Najbliže mjesto` left empty** on the 126 new rows. 53 of the existing LiDAR
   Kristal rows say *Veprinac*; the sheet does not carry it, so it was not guessed.
   Say if it should be defaulted the way `Lokalitet` is.
2. ~~**Excel-side**: exclude `za istražit` rows from the Nesređeni Power Query.~~
   **DONE — user applied it, verified against live 2026-08-29.** `NO_v2_1` now opens with
   `not Text.Contains([Napomena] ?? "", "za istražit") and ( … )`; the view holds **208 rows,
   0 of them za istražit** — exactly the predicted 221 → 208. M code kept for reference in
   [features/cave-dossier/docs/sb-powerquery.md](features/cave-dossier/docs/sb-powerquery.md).
   (The earlier "ponor over-matches" note was **wrong** — all 5 ponor-only rows tag it
   deliberately: "ponor, možda kopati". No change was needed there.)
   *Minor:* the view is 2 rows behind the master (210 by the rule) because SB has grown to
   1313 rows since the last query refresh — refresh Nesređeni to catch up.

## Recent sessions

- 2026-08-30 (late evening) — people registry + statement gates: `people/` (crospeleo ports), committed `data/people/registry.json` (132 people), registry/scope-aware gate-1 izjava blocker + gate-2 per-person warning, `N.Surname` author-vs-finder criterion, deceased exemption, `people list/check` — unresolved SB authors 125 → 24 → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
- 2026-08-30 (evening) — 2.1b prefill slice shipped: `geo/` finders (RGI + DGU boundaries + DMV elevation, offline-capable) + `osz/` writer/prefill, karta format → 5:4, LiDAR/GPS source flags, validated live on 3 caves + 24-cave sweep → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
- 2026-08-30 — 2.1c shipped (georef port, live-validated) + `SB_` prefix convention rolled out across excerpts, intake folders and staged photos → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
