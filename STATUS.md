# STATUS

Updated: 2026-10-03 (maintained by `/wrap-up` at the end of each session)


Stage labels per [ARCHITECTURE.md](ARCHITECTURE.md#the-labels) — `<digit><letter>`, digit = position in the pipeline, letter = the Croatian name. Entries written before 2026-09-19 use the old `2.1a`/`2.2b` numbers; the mapping is in that same section.

## Part status

Labels are `<digit><letter>` — digit = position in the pipeline, letter = the
Croatian name. The mapping from the old `2.1a`/`2.2b` numbers is in
[ARCHITECTURE.md](ARCHITECTURE.md#the-labels); entries below this table written
before 2026-09-19 still use the old numbers.

| Stage | Status |
|---|---|
| **0P** — dashboard (`cavedossier gui`) | **Round 2 (2026-10-02), dev-only so far.** Each cave's work is now a dependency graph (`gui/workflow.py`): done = green, next = gold, stale = amber when an input changed (the OSZ filled after the Nacrt makes 3c stale, a survey after the OSZ makes "OSZ ← duljine" due). One-click runs from the graph; gold `#EBAF01` palette + an SVG icon set; nav in working order; 4F photo gallery with recoverable delete; 5D draws both gates; 5O per cave. Backend the same day: `report`/`sb inspect`/`people check --broj`, `osz prefill` takes Duljina/Dubina from `_dimenzije.json`, cSurvey runs from the shared Drive copy `!!!Digitalizacija/Software/csurvey64` (headless needed `UnsafeLoadFrom`). Round 3 same day: photo-queue surfacing (54 photos / 34 caves found waiting), 4I map view, READMEs in the sidebar, uncropped photos, 5O tooltip. Round 4: `cavedossier intake create <broj>` (1T, the explicit folder step) and ★ Brze radnje (recipes: Novi objekt / Spoji nakon izmjere / Provjeri objekt as one job). Validated on SB 1220 / 1087 (live Drive). Not yet in a prod launcher (user: settle design first) |
| **1T** — teren / field mobile app | PARKED (manual workflow; revisit after stage 2 works) |
| **3N** — nacrt (csx-to-survey) | **OPERATIONAL, now with KORAK 3 (2026-09-20 evening)**: `csurvey_3_dovrsi_nacrt.bat` finishes a corrected `_lt` survey (entrance, Dislivello, scale bar, compass, print options), prints plan + profile headlessly from the installed cSurvey, and `cavedossier nacrt <broj>` composes them onto the sastavnica page → `SB_<broj>_nacrt.pdf`. Validated on SB 1103 and SB 1256; prod v1.5 + csx kit v1.3 published. Open: second-machine check. History: **Finishing step researched 2026-09-20** ([project 0004](stages/3N-nacrt/projects/0004-nacrt-finishing/brief.md)): the installed cSurvey drives headless from PowerShell with no build — load, recalc, **print-to-PDF without a dialog** — and every post-import manual step except sketch correction is an XML write. Five delegable tasks T1–T5 await the user's pick. **Entrance dimensions explored 2026-10-02** ([project 0005](stages/3N-nacrt/projects/0005-entrance-dimensions/brief.md), `research`): a ray cast across the drawn Borders at the decided entrance station reads the OSZ's Širina/Visina ulaza off the finished survey — SB 1220 0.64 × 1.49 m, SB 1103 (pit) 1.47 × 1.68 m; rules settled the same evening (splays first, walls fallback, pit small × large, one decimal) → SB 1220 **0,6 × 1,4**, SB 1103 **1,1 × 1,7**; next a vouched corpus, then into `nacrt_finish.py`. **Predefined cSurvey settings 2026-10-03**: KORAK 0 (`csurvey_0_postavi_csurvey.bat`) primes the registry app settings once per computer (pen smoothing off), KORAK 2 warns when a computer isn't primed; file settings get an open-ended `postimport.designproperties` ([csurvey-settings.md](stages/3N-nacrt/production/csurvey-settings.md)). **Per-cave mapping 2026-10-03**: the dashboard's *3N › Mapiranje simbola* draws and edits the TDX → cSurvey mapping (symbols with pictures, centerline colours with a live preview, sizes) and saves only the difference as `tdx-mapping-objekt.json` in the cave's SB_ folder, which KORAK 1/2 pick up per file; it shows TopoDroid's speleo and "speleo 2" (Extra speleo symbols) sets and filters what would arrive without a proper sign (29 points, 10 lines, 10 areas). Shared default now also has red station numbers and notes scale 1.0. Built and tested, **not yet published** (kit stays v1.5 until `/publish`). Corpus of 11 surveys run 2026-10-03 (9 plausible, 2 to check; raw TopoDroid exports work too) → awaiting the per-cave verdict, then into `nacrt_finish.py`. **Wall orientation 2026-10-03** ([project 0006](stages/3N-nacrt/projects/0006-wall-orientation/brief.md)): KORAK 2 now **merges the walls itself** (one cave border per design; strokes the survey cannot see, like a surface line, stay out) and reverses/orders the strokes of hand-merged borders, the cave's side voted by the survey - no more manual Merge and *Revert sequence*, only a check in the `_lt`; built, tested, cSurvey-verified, not yet published |
| **4O** — OSZ builder | **PREFILL SLICE OPERATIONAL (2026-08-30, evening)** — `cavedossier osz prefill <Redni broj>` fills the v10 template from SB + the new `geo/` finders (županija/grad-općina via DGU boundaries, najbliže mjesto/lokalitet via RGI, kota via open INSPIRE DMV grid), embeds the isječak karte, delivers `SB_<broj>_OSZ.docx` to `!!!Digitalizacija/Osnovni speleološki zapisnik`, and emits `dopune-sb.csv` (human-executed SB review list). SB wins on conflicts; LiDAR-named caves get Izvor koordinata/kote = LiDAR, others default GPS; Katastarski broj / Duljina / Dubina / Datum never prefilled (user rules). `--offline` works fully from local data. Validated live on 651, 764, 1320 + a 24-cave finder sweep. The reading direction shipped 2026-08-30 as **`cavedossier osz backfill <broj>`** (renamed from `osz fetch` 2026-09-02) — `w:sdt`-aware reader + fill-missing/note-conflicts proposals into `dopune-sb-iz-osz.csv`; M4's remaining tail is the **CroSpeleo-field reader** (checkbox groups, narratives, the Docs text variant). **Prod launcher shipped 2026-09-02** (see Productionization below) |
| **4I** — isječak karte | **OPERATIONAL (M3 done 2026-08-30)** — `cavedossier karta <Redni broj>` runs the ported georef.hr Playwright flow and delivers the excerpt + a row in `!georef_zapisi.csv` to the shared `!!Isječci karte` Drive folder. **Format changed same evening: landscape 5:4, ~1.5 km above/below the entrance** (was 1:1 / ~2.5 km); old-format or hand-deleted/mangled collections self-heal — refresh_reason detects wrong aspect, missing CSV rows, Excel-stripped padding |
| **4F** — fotografije ulaza | **PROCESSOR OPERATIONAL (2026-09-01)** — `cavedossier photos process <Redni broj>` takes a cave's photos out of its `SB_<broj>_…` intake leaf and writes downsized `SB_<broj>_<Ime>_<Autor>_<n>.jpg` **copies** beside them (1920 px / 1.5 MB, author from the OSZ cell *Autor fotografije ulaza*); originals stay untouched until the resolution is settled. Live: 6.92 MB → 1.23 MB. The staging sweep (`photos match-queued`) is finished and no longer run; `photos check-flag` + the staleness guard stay. Remaining: the **mover** into `!!Fotografije ulaza` renaming `SB_<broj>` → katastarski broj (rides with M6; designed 2026-09-02 in [m6-delivery-design.md](stages/6P-predaja/docs/m6-delivery-design.md) as one step of `deliver`). **Prod launcher shipped 2026-09-02** (see Productionization below) |
| **4S** — sastavnica (title block) | **OPERATIONAL (new 2026-09-19)** — `cavedossier sastavnica <Redni broj>` prefills the Nacrt's title block for the **Illustrator drafting route** and delivers `SB_<broj>_sastavnica.pdf` into the cave's intake leaf beside its OSZ. Fifteen cells: SB wins for identity/location, the leaf's FILLED OSZ for survey facts, the geo finders for the rest — nine cells without a zapisnik, fourteen with one. Katastarski broj stays `0000` and Mjerilo stays `1:` by decision (the archivist and the drafter fill those). Values are centred and shrunk to fit 10→6 pt, names abbreviated the drafter's way, kota rounded, depth signed. The blank template is generated once from the authored `!SUE_sastavnica.ai` export by content-stream surgery (`sastavnica-template/tools/build_blank.py`); PyMuPDF redaction cannot do it (it eats overlapping labels), and the same pass strips the embedded `.ai` that Illustrator's "Preserve editing capabilities" export leaves behind — without it Illustrator opens the TEMPLATE while every PDF viewer shows the real values (caught by the user on the first delivered file; 226 KB → 45 KB). Font: Myriad Pro found in the local Illustrator install, system fallback otherwise — never bundled. A delivered file this tool did not write (or that was edited) is refused, not overwritten. Validated live on SB 1220 (a cave mid-digitization, DXF in its leaf) and SB 811. **Prod launcher shipped the same day** (v1.4, see Productionization below). Design + decisions: [sastavnica-design.md](stages/4S-sastavnica/docs/sastavnica-design.md). Outside the M-ladder — needs only M1 |
| **5D** — dosje / dossier builder | **M2 in progress** — dossier model + **two-gate** gating + lifecycle + `report` done; **people registry + statement gates live (2026-08-30)**: `data/people/registry.json` (131 people, seeded from the izjave dir), registry/scope-aware per-author izjava blocker at gate 1, per-person missing-izjava warning at gate 2, `cavedossier people list/check`. Per-cave archive intake (nacrt/OSZ/foto) still next |
| **2B** — SB (master registry) | **M1 ✅ DONE** (read-only, live SB v3.0). Live workbook now **1438 rows**; write-back still M6 — [mechanics](stages/6P-predaja/docs/sb-write-back-design.md) + [what delivery writes](stages/6P-predaja/docs/m6-delivery-design.md) both designed, neither built |
| **2B** — satellite tables | **OPERATIONAL (new 2026-08-29)** — `cavedossier sat sync` compares a satellite against SB and emits four review lists; never writes to either side. Liburnija done end to end: **126 rows entered SB**, 7 synonyms added, run is idempotent. `Literatura` (45) and `Katastar RH` (4595) still untouched |

## Milestone ladder

Definitions live in [ARCHITECTURE.md §Milestones](ARCHITECTURE.md#milestones-stage-2);
this table is where each one STANDS. Detailed checklists follow below.

**Productionization (outside the M-ladder, first slice 2026-09-02, third
command 2026-09-19)** — `osz prefill` + `photos process` + `sastavnica` ship
as versioned double-click launchers on the Drive (`!!!Digitalizacija/SurveyScraper5/`: launchers + versioned bundle +
`podaci/geo` cloud copy + `_arhiva/`), generated/published by
`prod/build_prod.py --version X.Y --publish`. First run
self-installs to `%LOCALAPPDATA%\CaveDossier\v<X>` (guided Python 3.11+ setup,
venv+pip, geo copy, derived `.env`). Validated end-to-end on the dev machine as
operator (photos 1220 dry-run, prefill 1320 delivered). v1.1 same day after the
first real operator run: per-run logs + console font; v1.2 (user decision):
operators run the `[karta]` georef.hr flow themselves (Chromium in setup,
shared login injected at build time) — validated by fetching SB 1087's excerpt
on the prod install, which also caught+fixed the "unchanged" re-delivery bug
(`_karta_newly_embedded`). **v1.4 (2026-09-19)** adds the 2.1e `sastavnica`
launcher (bundle carries the blank PDF template; `[sastavnica]` extra = PyMuPDF;
the Myriad Pro font is found on the machine, never bundled) — validated by a
clean install from the published folder and a real delivery for SB 1220. First
launcher aimed at the Illustrator drafters rather than at recorders.
See ARCHITECTURE §Dev vs prod + README §Prod launchers.

| M | Name | Status |
|---|---|---|
| M0 | Docs scaffold | ✅ done (2026-08-16) |
| M1 | SB read-only | ✅ done (2026-08-25) — live workbook, banner, sandbox fallback |
| M2 | Dossier skeleton + `report` | ◐ in progress — model/gating/report + people registry & statement gates shipped; **per-cave archive intake is the open tail** |
| M3 | Isječak karte | ✅ done (2026-08-30) — 5:4 format + self-healing collection same day |
| M4 | OSZ builder | ◐ `osz prefill` + `osz backfill` shipped (2026-08-30; the latter renamed from `osz fetch` 2026-09-02); the CroSpeleo-field reader (checkbox groups) + real-zapisnik validation open |
| M5 | 2.1a artifact handoff | not started (blocked on the intake dir layout going live) |
| M6 | SB write-back + delivery (+ the 2.1d mover) | not started — everything upstream feeds review lists until then. **Delivery designed 2026-09-02**: [m6-delivery-design.md](stages/6P-predaja/docs/m6-delivery-design.md) (`deliver <broj>` — the last gate, katastarski-broj allocation, rename + file, SB write-back); write mechanics in [sb-write-back-design.md](stages/6P-predaja/docs/sb-write-back-design.md) |

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
      [stages/2B-baza/docs/sb-restructure-excel-prompt.md](stages/2B-baza/docs/sb-restructure-excel-prompt.md)
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
      One-off by design: the queue is named, and the command is not run any more
      (user, 2026-09-01).
- [x] **2.1d per-cave photo processor (2026-09-01)**: `cavedossier photos process
      <Redni broj>` reads the cave's `SB_<broj>_…` intake leaf, takes the photo author
      from the OSZ cell *Autor fotografije ulaza* (`Lovel Kukuljan` → `LKukuljan`, the
      archive's spelling), and writes downsized `SB_<broj>_<Ime>_<Autor>_<n>.jpg`
      **copies** next to the originals (config `photos:` targets, 1920 px / 1.5 MB;
      `--long-edge` / `--max-bytes` / `--author` / `--from` / `--overwrite`). Writes
      straight away — no `--apply`, since it only ever adds files; a run never
      re-processes its own output. Every run also checks the za-istražit queue for
      that cave and prints `photos pull-staged <broj> --apply`, which MOVES the
      queued photos into the intake leaf (creating it if needed, dropping the
      `SB_<broj>_` prefix) — the SB 811 case, where the leaf looked empty while
      four entrance photos sat in the queue. Validated live: 6.92 MB /
      3468×4624 → 1.23 MB / 1440×1920, matching the manual FastStone result.
- [x] **Satellite hub shipped (2026-08-29)** — `cave_dossier/satellites/`
      (`model` · `liburnija` · `resolver` · `sync`) plus `cavedossier sat sync`.
      Resolves every sheet row against SB on ranked keys (pločica → `LiDAR Kristal N`
      synonym → coordinates → name-as-duplicate-guard), never on a local row id, and
      emits four review lists: new SB rows as a paste-able CSV, synonym additions to
      existing rows, sheet corrections, and things to decide. **Read-only on both
      sides.** 41 tests. Design: [docs/sb-liburnija-hub.md](stages/2B-baza/docs/sb-liburnija-hub.md).
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
- [x] **SB backfill fetcher shipped (2026-08-30, late)** — `cavedossier osz backfill
      <broj> [--osz FILE]`: `osz/reader.py` (w:sdt-aware, placeholders read as
      empty) + `osz/backfill.py` (fill-missing / note-conflicts; new OSZ name
      replaces SB's and the old name moves to Sinonimi; Datum cropped to SB's
      godina/period convention; Crtali full names ↔ SB `L.Kukuljan` shorthand via
      the ported alias registry `core/person_aliases.py`; authors merge, never
      drop) → `dopune-sb-iz-osz.csv` review list. Validated: mockup 811 vs SB 764
      (7/7 fields confirmed across conventions) + a simulated completed zapisnik
      for queued 1320 (6 proposals incl. the name→synonym move). Tests 183 → 193.
- [ ] Validate `osz backfill` on the first REAL filled zapisnici from recorders;
      then the CroSpeleo-field reader (checkbox groups, narrative controls,
      Google-Docs text variant).
- [x] **Renamed `osz fetch` → `osz backfill` (2026-09-02)** — it never fetched anything,
      it proposes SB updates; now the exact mirror of `osz prefill`, matching the
      module that always was `osz/backfill.py`. Code + all docs + the test file;
      no alias, the old name errors and names the replacement.
- [ ] Batch mode (`osz prefill --missing`-style sweep) — backlog.

## Waiting on user

- **3N cSurvey settings:** close cSurvey and run `python stages/3N-nacrt/production/tools/csurvey_app_settings.py apply` once (pen smoothing is still on here; the live `apply` was blocked because cSurvey was open), then `/publish` the csx kit (v1.6: KORAK 0, the per-cave mapping, `tdx_mapping.py`, en-dash messages, red station numbers). Name further settings to predefine as they come up. Decide the mapping for the speleo 2 symbols that arrive without a proper sign (dashboard › 3N › Mapiranje › "Bez pravog znaka"); an agent can propose a first pass.
- **3N entrance dimensions (project 0005):** one optional look — Sopača (13.6 × 17.5 from station 5, which sits outside the drawn plan: doline rim or surface tie-in?). Rule 5 declines the three surveys without an entrance sign. Next is phase 3: fold into `nacrt_finish.py` (sign tie-break, registry type, rule 5) → `_dimenzije.json` → 4O prefill. Say when.

- ~~Society's blank OSZ template DOCX~~ → delivered 2026-08-23:
  [stages/4O-osz/src/cave_dossier/osz/templates/Zapisnik_OSZ_v10.docx](stages/4O-osz/src/cave_dossier/osz/templates/Zapisnik_OSZ_v10.docx)
- ~~Distribute OSZ v10 to recorders~~ → done 2026-08-25. Two cosmetic leftovers stay
  open (11 pt Literatura/Napomene, filled form runs to 5 pages), see
  [audit-v10.2.md](stages/4O-osz/template-workbench/docs/audit-v10.2.md) §"Sitnice";
  neither blocks use, both fold into the next template revision.
- First filled zapisnici coming back from recorders — collect 2–3 (ideally one from
  Word, one from Google Docs) as parser fixtures before M4 starts.
- Mobile-app context material (parked with part 1)
- **Five delivery questions** (new 2026-09-02, listed at the end of
  [m6-delivery-design.md](stages/6P-predaja/docs/m6-delivery-design.md)):
  does the photo `_<n>` index survive into the archive name; does a multi-sheet
  nacrt get a suffix; does the archived intake leaf take the katastarski broj or
  keep its field name; is `deliver` dev-only at first (it needs Excel + xlwings);
  does `Godina zadnjeg istraživanja` join the same SB write.
- **TDX kit redistribution** (new 2026-09-19, **done 2026-09-20**): the three drag-and-drop `.bat` files hardcoded one machine's absolute path *and* were copied out to operators — so every distributed copy had been inert since handover. `python prod/build_csx_kit.py --publish` now generates and publishes a self-contained kit as **`csurvey_<n>_*` v1.0 in `!!!Digitalizacija/SurveyScraper5/`** (three numbered launchers + the Croatian `csurvey_0_PROCITAJ_ME.txt` + `csurvey_alati/`, beside the `cavedossier_*` launchers), replacing the `Share/TDX` copies (folder since deleted by the user). A double-click now asks which caves to process by Redni broj instead of sweeping the intake tree. Remaining: tell the operators once that the tools moved into the same folder as the cavedossier commands.
- **Sastavnica Lokacija wording** (new 2026-09-19): the sastavnica inherits the
  OSZ's geo-admin-wins rule for Najbliže mjesto, so SB 811 prints
  *Kobiljak, Grižane-Belgrad* where SB says *Potkobiljak*. Kept for consistency
  between the two documents — say if a printed nacrt should prefer SB's wording
  instead (it would be a sastavnica-only exception).
- **Optimal entrance-photo resolution** (new 2026-09-01): `photos process` ships at
  1920 px / 1.5 MB and writes COPIES precisely so this stays revisable —
  `--long-edge N --overwrite` re-cuts a cave. Once the number is settled, the copies
  can replace the originals instead of sitting beside them.

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
   [stages/2B-baza/docs/sb-powerquery.md](stages/2B-baza/docs/sb-powerquery.md).
   (The earlier "ponor over-matches" note was **wrong** — all 5 ponor-only rows tag it
   deliberately: "ponor, možda kopati". No change was needed there.)
   *Minor:* the view is 2 rows behind the master (210 by the rule) because SB has grown to
   1313 rows since the last query refresh — refresh Nesređeni to catch up.

## Recent sessions

- 2026-10-03 — **3N: entrance dimensions, corpus and rules** (project 0005, `validation`): the prototype run over 11 example surveys from raw TopoDroid to finished; the user settled five rules on the way (splays first, walls fallback, pit small × large, one decimal, **no size without an entrance sign / surface leg**), the cave's type comes from the registry, a sign tie-break toward the highest station (Tavnjak). 8 measured, 3 declined without a sign, Sopača flagged. Two guards built on a krk_27/krk_37 mix-up were removed the same night. Raw exports work. Next: phase 3 → [journal/SESSIONS.md](journal/SESSIONS.md)
- 2026-10-03 — **3N: predefined cSurvey settings + per-cave mapping page**: KORAK 0 primes cSurvey's registry app settings once per computer (pen smoothing off) and KORAK 2 warns when a computer isn't primed; file settings gained an open-ended `postimport.designproperties`; the dashboard's *3N › Mapiranje simbola* shows and edits the TDX → cSurvey mapping per cave (`tdx-mapping-objekt.json`, picked up by KORAK 1/2), incl. the speleo 2 set; en dash in every Croatian string the dashboard shows. Not yet published → [journal/SESSIONS.md](journal/SESSIONS.md)
- 2026-10-02 (evening) — **3N: entrance dimensions feasibility** (project 0005, `research`): the entrance width (plan) and height (profile) can be read off the finished survey by casting a ray across the Borders walls at the station `decide_entrance` already picks — SB 1220 0.64 × 1.49 m against the surveyor's splays 0.57 × 1.4–1.75; SB 1103 pit 1.47 × 1.68 m. Found that cSurvey fills a Borders item as one polygon with straight joins between its `B` sequences, so an undrawn ceiling shows as a fill edge; and a latent `d=0` bug in `nacrt_finish.read_stations`. Prototype + plots in `findings/`; the user then settled the four rules (splays first, walls fallback, pit small × large, one decimal): SB 1220 → 0,6 × 1,4, SB 1103 → 1,1 × 1,7 → [journal/SESSIONS.md](journal/SESSIONS.md)
