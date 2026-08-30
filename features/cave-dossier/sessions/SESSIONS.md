# Session journal — cave-dossier

One block per working session, **newest on top**. Same discipline as
csx-to-survey-pipeline: terse, concrete, honest about limits. Appended by
`/wrap-up` at the end of every session.

---

### 2026-08-30 (evening) — 2.1b prefill slice: geo finders + OSZ writer + `osz prefill` (agent) ✅

- **Did:** (1) *`geo/` package* — locality finder ported from crospeleo
  `locality/` (RGI WFS client + NEW offline fallback over a locally provisioned
  `rgi_named_places.gpkg`, DGU admin point-in-polygon simplified to one PIP over
  `naselja.gpkg`, toponym matcher verbatim, enricher restructured into an SB-wins
  synthesizer) + NEW elevation finder over the open INSPIRE EL-COV DMV grid
  (pyproj 3765→3045, lazy ~34 MB tiles, nodata rescue ±2 cells + neighbour tile)
  + `geo fetch-data` (RGI paged WFS → 125,731 places; admin boundaries
  stream-parsed from the 600 MB INSPIRE AU GML with lxml `huge_tree`, 21/556/6759
  units). (2) *`osz/` package* — writer with make_mockup's primitives + NEW
  `embed_png`; `fill_plain` REWRITTEN to use each cell's own paragraph-mark rPr
  (user caught Arial-12-everywhere; template stores Arial 20 bold etc. on the
  mark); versioned v10 address map; prefill orchestrator with `prefill.json`
  sidecar + `dopune-sb.csv` review list, fail-soft Drive delivery. (3) *CLI* —
  `geo fetch-data/locate/kota`, `osz prefill`, `--offline` everywhere; extras
  `[geo]` new, `[osz]`→lxml. (4) *2.1c format change* — excerpt now landscape
  5:4 / ~1.5 km half-height (was 1:1 / ~2.5 km); `refresh_reason` self-heals
  hand-managed collections (wrong aspect, deleted/mangled CSV rows, Excel-stripped
  padding). (5) *Field rules (user)* — SB wins + 10 m kota tolerance; LiDAR-named
  caves ⇒ Izvor koordinata + Izvor kote = "LiDAR", others ⇒ GPS default;
  Katastarski broj / Duljina / Dubina / Datum istraživanja never prefilled.
  Tests 135 → 183, all green.
- **Result:** Live: 651/764/1320 prefilled, delivered to
  `!!!Digitalizacija/Osnovni speleološki zapisnik`, Word-verified (81 controls,
  correct fonts, embedded 5:4 excerpt); 24-cave stratified sweep — admin fields
  24/24 plausible, Δkota ≤5 m for 20/24 (two Δ30 are honest steep-terrain
  cases, correctly warned). Fully offline run produces a complete document.
- **Learned:** (a) The v10 template stores every empty value cell's intended
  style on the paragraph mark (`pPr/rPr`) — copying a sibling's run style (the
  make_mockup way) flattens everything. (b) GDAL's GML driver drops INSPIRE AU's
  level (xlink:title attribute) AND names (nested `gn:text`) — hand parsing was
  the only way; the archive is one 600 MB line needing lxml `huge_tree`.
  (c) EL-COV tiles are EPSG:3045 with real nodata holes; tile extents overlap,
  and the neighbour tile often has the missing value. (d) SB's Najbliže mjesto
  is routinely a *zaselak* — validating only against official DGU naselja
  false-alarmed 10/24; RGI's zaselak-typed points close the gap. (e) The Drive
  delivery dirs are hand-managed: Excel strips `0651`→`651` in the CSV, people
  delete PNGs — every staleness check must live in the tool. (f) georef.hr's
  elevation is nowhere in its record; the open DMV grid was the right source
  (DMR1 is registered-WMS visualization only).
- **Next:** (1) collect the first filled zapisnici → the M4 fetcher half
  (`w:sdt` + Docs text parsers); (2) batch prefill over the Za istražit queue;
  (3) sat-sync list 3 corrections + the `Najbliže mjesto` default question are
  still open from earlier sessions.

### 2026-08-30 — isječak karte (2.1c / M3) shipped + `SB_` prefix convention (agent) ✅

- **Did:** (1) *Port* — `cave_dossier/georef/` from crospeleo-automation
  (`models` · `selectors` · `client` · `flows` near-verbatim with every timing
  calibration kept; `artifacts` relaid to gitignored `runs/georef/<padded>/`;
  `worker` new) + `config/selectors.yaml`; all logged in docs/PORTING.md.
  (2) *CLI* — `cavedossier karta <Redni broj>` (`--debug` headed, `--force`
  refresh): SB row → HTRS96 → georef.hr point → record copy → marker-centered
  TK25 crop → delivery to the shared `!!Isječci karte` Drive folder as
  `SB_<4-digit padded broj>.png` plus an upserted row in `!georef_zapisi.csv`
  (comma/CRLF/BOM, same dialect as `sat sync`). (3) *Live validation* — caves
  764 (Piccolo Bertarelli) and 651 (Jama na Globoko) end to end, all three CLI
  paths (fetch / skip-if-collected / unknown broj). (4) *Quality* — capture
  window raised to 2560×1600 (the crop is 1:1 screen pixels, so window size IS
  resolution) with a 1 MB budget: truecolor → 256-color palette → 15 % downscale
  as last resort; a reserved palette slot keeps the red pin from being quantized
  away. (5) *`SB_` convention* (user, 2026-08-30) — shared matcher now proposes
  `SB_<broj>_…`, treats bare `<broj>_` as a one-time upgrade and `SB_<broj>_` as
  the fixed point; migrated in place: 2 excerpts, 34 intake folders
  (`intake map --apply`), 62 staged photos (`photos match-queued --apply`), all
  idempotent on re-run. Tests 124 → 135.
- **Result:** 2.1c operational. Excerpts are 1017×1017 at ~880 KB with a clearly
  red pin (verified visually); `!georef_zapisi.csv` carries both validation
  records. One bug found by the live run (missing `deliver` export) — fixed, the
  captured run was delivered from persisted artifacts without re-hitting the
  site. Limits: SANDBOX workbook lags live SB (banner warns); headed `--debug`
  clamps the window to the display, so full-res captures are headless-only.
- **Learned:**
  - **Every georef.hr save allocates a new server-side point ID** (321725→321732
    across the test runs) — the flow validates coordinates, not identity. Re-runs
    litter the registry a little; same behavior crospeleo has always had.
  - **PNG-24 was the resolution bottleneck, not the site**: the TK25 scan
    compresses poorly in truecolor (527 px ≈ 668 KB) but quantizes almost for
    free — palette PNG is what buys 1017 px under 1 MB. The catch: median-cut
    spends no palette entry on a few hundred pin pixels, so the marker came out
    green-grey until a slot was reserved for it.
  - **`Image.quantize` + a reserved index** is a clean pattern for "compress the
    map, never lose the overlay" — worth reusing for any future map artifact.
  - The Drive folder URL the user shares resolves via `get_file_metadata` to a
    name that already exists under `LOCAL_DRIVE_ROOT` — no Google API needed at
    runtime, consistent with the no-API rule.
- **Next:** wire `Isječak karte` / `Georef zapis` presence into the CroSpeleo
  gate rules (they still report *not checked yet*); a `karta --missing` batch
  sweep; decide `Jama Petrci` (new intake leaf, closest *Jama kod Petrci* 1043 —
  user says leave as is for now).

### 2026-08-29 — satellite hub (part 2.2b): Liburnija ↔ SB, end to end (agent) ✅

- **Did:** turned the read-only Liburnija bridge into a real two-way hub.
  (1) *Design* — [docs/sb-liburnija-hub.md](../docs/sb-liburnija-hub.md): the
  four-state candidate lifecycle (`provjereno` × `speleo_obj`), the crossing rule,
  per-stage field ownership, ranked join keys with measured thresholds, and the
  write-back transport options. (2) *Code* — new `cave_dossier/satellites/`
  (`model` · `liburnija` · `resolver` · `sync`, ~900 lines) and
  `cavedossier sat sync [--coords] [--out [DIR]] [--limit N]`; `intake/liburnija.py`
  reduced to a thin slice over the same reader so intake and sync cannot disagree.
  (3) *Run* — generated the lists, user pasted 126 rows into `Svi objekti`
  (1313–1438) and added 7 synonyms; re-ran to verify. (4) *Docs* — ARCHITECTURE.md
  now shows 2.2 REGISTRY with 2.2a SB / 2.2b satellites in the schema and the part
  map; `sb-satellite-tables.md` gained the Kristal key and the candidate stage;
  new `sb-sync/` output tree (gitignored, README tracked).
- **Result:** operational and **idempotent** — the re-run after the paste reports
  0 rows to add, 0 synonyms, 0 conflicts, 196 linked. Every pasted cell matches the
  generated CSV bar three deliberate capitalisations; no duplicate Redni broj, no
  gaps, no column shift. 41 satellite tests (122 total) green. Still open: 30 sheet
  corrections and 2 photo questions, both for the user to carry out by hand.
- **Learned:**
  - **The satellite's own row number is a trap, but the number written *into SB* is
    not.** `LiDAR Kristal N` as `Ime objekta` or `Sinonimi` gave 56 links with **zero**
    disagreements against the plaque key. Making it a rule at row creation converts a
    forbidden key into a hard one — which is why `sat sync` now also proposes adding
    the synonym to rows that link only by coordinates or name.
  - **Coordinate proximity is much weaker than it looks here.** True pairs run to
    12.3 m (median 0.9), but 54 sheet points sit within 15 m of another point. A naive
    30 m scan proposed 17 links of which 11 were nonsense. What made it usable: only
    confirmed caves are eligible to match, a 5 m auto band, and `EXACT_MATCH_M = 1.0`
    — a row on the same point *is* that row, whatever else is near.
  - **Idempotency is the real test of a sync, and it failed twice.** `confirmed_new`
    (a human override saying "this is a new cave") suppressed matching permanently, so
    after the paste the tool proposed the same row again; and a 0.0 m match with an
    11 m runner-up was called ambiguous by a flat radius. Both fixed by the exact-match
    rule; both now regression-tested as propose → paste → re-run finds nothing.
  - **`Link Zapisnik` is not "has a zapisnik"** (user) — it records only whether a
    *digital* copy is on file, and every *Istraženi* object has one analog or digital.
    Reading its absence as absence raised false findings; the SUE number is the signal.
  - **Excel-facing files need three things or they are useless:** every column in the
    workbook's own order (a tidy subset cannot be pasted into a table), a BOM (else
    Windows Excel reads UTF-8 as the local codepage and every č/š/ž breaks), and
    newlines written through untranslated (`write_text` turned CRLF into CR-CRLF and
    126 rows parsed back as 253 — invisible in an editor).
  - **The gap was two orders of magnitude bigger than the folder-driven pass found.**
    That pass saw one missing row (*Jamorinke*) because it only looked at folders that
    already held data; a sheet-driven pass found 126.
  - `sList` on this machine is `,` despite an hr-HR locale, so comma CSV splits into
    columns correctly. On a `;` machine the same file lands in one column.
- **Next:** apply the 30 sheet corrections and answer the 2 photo questions, then
  point the same protocol at `Literatura` (45 rows — the cheap one) to prove it
  generalises before touching `Katastar RH`.

### 2026-08-25 — OSZ v10 shipped to recorders + SB v3.0 adopted, M1 closed (agent) ✅

- **Did:** (1) *Google Docs compatibility* — traced the reported corruption to
  Word content controls: Docs drops every `w:sdt`, leaving the raw `Wingdings 2`
  glyph where a checkbox was and turning placeholders into real grey text, plus a
  floating table (`w:tblpPr`) that shifted page breaks. Wrote
  `tools/flatten_for_gdocs.py` (66 checkboxes → `[ ]`, 15 controls → `⟨ … ⟩` hints,
  table un-anchored, embedded fonts dropped, footer line pointing at the Word
  original) and `tools/check_gdocs_roundtrip.py` (diffs checkbox/hint counts, table
  geometry, all 48 labels, run fragmentation). Result: 4.5 MB → 30 KB, 4 pages.
  (2) *Hints de-styled* after user feedback — no grey, no italic, because without a
  control nothing resets formatting and the answer inherits whatever the hint wears;
  the flattener became idempotent so the hand-edited variant is fixed in place.
  (3) *Template locking* — `tools/lock_template.py` produces
  `templates/Zapisnik_OSZ_v10.dotx` (48 KB): Word-template part type, all 81 controls
  `sdtLocked`, read-only-recommended, fonts stripped. (4) *SB v3.0* — found
  `!Speleo_baza_SUE_v3.0.xlsm` on Drive, verified the restructure, repointed
  `config.yaml` / `.env` / `safe_io`, refreshed the sandbox. (5) STATUS: M1 closed,
  M2 drafted. (6) Distribution package assembled; user distributed it.
- **Result:** template shipped in both variants. SB v3.0 parses unchanged — header
  autodetect still lands on row 2, 1301 data rows (was 1117), 24 columns (GK pair
  dropped), every column `config.yaml` names still present, 7 tests green. Shipped
  one wrong lock first: `documentProtection edit="forms"` looked right but makes 27 of
  31 fillable cells read-only (only 4 are content controls) — user caught it while
  filling, removed. Never verified: Drive's handling of `.dotx` (expected to skip
  Office-editing mode), and the Google-Docs round-trip itself — the upload path
  through the MCP corrupts a 45 KB base64 payload, so the checker script exists but
  has not been run against a real Google export.
- **Learned:** (1) Google Docs edits `.docx` **in place** from Drive, so the only
  real lock on a shared template is a Viewer permission — `documentProtection`,
  `writeProtection` and Mark-as-Final are all silently ignored on import; a `/copy`
  link on a native Google Doc is the clean pattern for Docs users. (2) A plain-text
  content control may not contain a second `w:p` — Word rejects the file as corrupt
  even with `multiLine="1"`; use `<w:br/>`. Duplicated `w14:paraId` breaks it the same
  way. (3) `wdFormatXMLTemplate` is **14**, not 13 (13 = macro-enabled document) —
  saving with 13 under a `.dotx` name produces a file Word refuses to open. (4) Word's
  own *Save As → Word Template* reproduces the distributed `.dotx` exactly (52 KB,
  81 controls, all field types fillable), so the whole deploy loop can be script-free
  once *Embed fonts in the file* is unticked in the master — 4453 KB → 52 KB. (5) SB
  v3.0 flags 185 queue rows as `za istražit, …` but the old Broj is **optional** in
  that string (`Ponor Gotovž`: `za istražit, detalji u literaturi`), so the queue
  reader must not require it.
- **Next:** M2 — dossier model + `report` command, and a queue reader over the v3.0
  Napomena flag. Collect 2–3 filled zapisnici (one Word, one Docs) as parser fixtures
  before M4; run `check_gdocs_roundtrip.py` against a real Google export when the
  first Docs-filled zapisnik arrives.

### 2026-08-23 — project renamed SurveyScraper4 → SurveyScraper5 (agent) ✅

- **Did:** repo-wide rename (SurveyScraper was already at v4; the superapp is v5).
  36 occurrences in 14 tracked files (`CLAUDE/README/ARCHITECTURE/STATUS`, glossary,
  wrap-up skill, SETUP_PROMPT, cave-dossier docstrings/pyproject, csx `.bat` TOOLS
  paths); `git mv` of the workspace file; `.env` sandbox path made **relative to the
  feature root** (config.py resolves it — rename-proof from now on); TDX-folder bat
  copies re-synced; Claude memory files updated. 7 tests + `sb stats` re-verified.
- **Result:** all tracked content says SurveyScraper5. Disk folder rename left to
  the user (steps in STATUS): close VS Code, rename the repo folder + the
  `.claude/projects` key folder, reopen; venv recreation next session.
- **Learned:** the TDX-folder bat copies on G: were still pointing at the
  **pre-migration** `cSurvey\dev\production\tools` — the 2026-08-16 migration
  updated the repo's canonical bats but nobody re-synced the deployed copies.
  Deployed-copy sync deserves a standing check whenever `production/tools/` changes.
- **Next:** ~~user performs the folder rename~~ → done same day: folder + Claude
  project-key folder renamed by user, venv recreated, 7/7 tests + `sb stats` +
  `sb inspect` green under `Programming\SurveyScraper5`. Rename closed.

### 2026-08-23 — OSZ v10 template finalised + osz-template workbench (agent) ✅

- **Did:** answered "what did I want changed in the next OSZ" from
  `crospeleo-automation/TODO` (§"OSZ template overhaul", §"replace sa with s"), then
  wrote Croatian placeholder texts for the 11 narrative fields
  ([osz-template/docs/placeholders.md](../osz-template/docs/placeholders.md)),
  grounded in `osz_parser.py` field specs, `RULES.md`, the CroSpeleo UI inventories
  and the three archived OSZ samples (502/795/811). Created
  `features/cave-dossier/osz-template/` (templates + archive, docs, tools, mockups)
  with three tools: `inspect_osz.py` (layout/index/controls dump), `check_conformance.py`
  (checkbox vocab diff vs CroSpeleo + `OSZParser._canonical_key` alias check + control
  hygiene), `make_mockup.py` (fills the template with SUE 811 data). Audited three
  template iterations across the session (v10.0 → v10.1 → final v10) and generated a
  filled mockup for each.
- **Result:** template finalised. Six checkbox groups now match CroSpeleo exactly —
  Podrijetlo imena (6), Stanje ulaza (10), Hidrološka (8), Hidrogeološka (10),
  **Perspektiva daljnjeg istraživanja (12/12)**, Vrsta objekta (8, forms confirmed
  against the live dropdown). Prirodne opasnosti 8 of 13 (anthropogenic labels split
  into their own group), Antropogene deliberately trimmed to `onečišćenje otpadom` +
  `minsko-eksplozivna sredstva`, snow/ice reduced to two presence checkboxes. Three
  defects found and fixed by the user: no `multiLine` on any narrative control (Enter
  was blocked), a signature-row cell squashed 1851→250 twips (date wrapped vertically,
  pushed the form to 5 pages), and `Povijesni podaci` printing at 11 pt. Final mockup
  is 4 pages, all 15 controls filled, 9 boxes ticked.
- **Learned:** (1) **python-docx cannot see content-control text at all** — verified on
  1.2.0: `paragraph.text`, `cell.text` and `document.paragraphs` all skip `w:sdt`, and a
  cell-level control hides its whole `w:tc` from `row.cells`. Every field the new
  template puts in a control reads as empty for today's parser; it must read
  `w:sdtContent//w:t` and treat `w:showingPlcHdr` as empty, else untouched placeholders
  get ingested as real text (measured: the Mikroklimatski placeholder alone would fire
  `led - stalno`, `snijeg - stalno`, 6,7 °C, 95 %, strujanje `povremeno`). (2) A
  plain-text control may not contain a second `w:p` — Word calls the file corrupted even
  with `multiLine="1"`; use `<w:br/>`. Duplicated `w14:paraId` breaks it the same way.
  (3) Ticking a checkbox needs `w14:checked val="1"` **and** the run's `w:sym` swapped to
  the checkedState char, else it looks empty. (4) CroSpeleo's Vrsta objekta vocabulary is
  asymmetric: `jama sa špiljskim ulazom` but `špilja s jamskim ulazom`. (5) `RULES.md` §2
  lists a stale Izvor-koordinata option set; `_COORD_SOURCE_OPTIONS` in the parser is
  authoritative.
- **Next:** teach the fetcher content controls (`w:sdt` + `w14:checkbox`), then the
  mapping rules in [audit-v10.2.md](../osz-template/docs/audit-v10.2.md) §"Pravila
  preslikavanja" — notably `onečišćenje otpadom` → also Opasnosti `otpad u objektu`,
  MES → two CroSpeleo controls, and the snow/ice presence rule that can retire
  `infer_snow_ice_negative`.

### 2026-08-22 — SB restructure designed: single master table + Za istražit as PQ view (agent) ✅

- **Did:** settled the SB queue question with the user. Confirmed via sandbox
  inspection that Istraženi/Nesređeni are already Power-Query views (`IO_v2_1`,
  `NO_v2_1`; DataMashup present), Svi objekti is table `SO_v2_1` (A2:Z1119), Za
  istražit is `Table_4` (A2:M191, has X/Y HTRS so dropping GK loses nothing, GK
  cells are literals not formulas). Wrote the Claude-in-Excel migration prompt
  (`docs/sb-restructure-excel-prompt.md`): merge Za istražit rows into Svi objekti
  **by year**, flag = `za istražit, <old Broj>, <note>` prefix in **Napomena**
  (user's call — overrode the dedicated-Status-column suggestion), renumber Redni
  broj wholesale, old sheet kept as ARHIVA rollback, new Za istražit = PQ view
  filtered on the Napomena prefix.
- **Result:** decision recorded; execution is the user's (in Excel). Column-name
  drift flagged: user's "Godina ili datum istraživanja"/"Autor nacrta" mapped to
  the real "Godina ili period istraživanja"/"Autori nacrta".
- **Learned:** the single-master + PQ-view pattern was already the workbook's own
  idiom — Za istražit was the only hand-maintained lifecycle table; the flag-in-
  Napomena format doubles as traceability (old Broj embedded). Filename bump would
  break two tool configs (ours + crospeleo's .env) — warned in the prompt doc.
- **Next:** user runs the prompt in Excel → refresh sandbox copy → M2 dossier
  skeleton with a `sb za-istrazit` queue reader on the Napomena prefix.

### 2026-08-16 — M0 docs scaffold + M1 SB read-only communication (agent) ✅

- **Did:** superapp docs layer (root `ARCHITECTURE.md` with the canonical 1/2.1a-c/2.2
  numbering, `STATUS.md`, `shared/glossary.md`, `/wrap-up` skill that commits);
  scaffolded this feature (pyproject src-layout, `cavedossier` CLI, slim
  config.yaml+.env instead of crospeleo's profile system); ported
  `normalization.py` (verbatim), `sb_safe_io.py` (near-verbatim, write path dormant),
  `sb_loader.py` → trimmed `SBReader` (kept header autodetect / canonicalization /
  `__excel_row_number`, stripped queue machinery, added `find_caves` with substring
  fallback). 7 unit tests on a synthetic mini workbook. Sandbox copy of the live SB
  taken to `example/sb-sandbox/`; all three commands (`sb columns/inspect/stats`)
  verified on it; one read-only LIVE run — stats identical to sandbox.
- **Result:** SB communication established, read-only, 1117 rows / 26 columns.
  Inspect of Konglomeratača (SUE 570, Excel row 722) returns the full row correctly.
  Honest limit: user hasn't eyeballed rows against Excel yet, and one introduced
  off-by-one (`__excel_row_number`) was caught only because the port was reviewed
  against the original — trust the ported originals.
- **Learned:** the workbook has a **"Za istražit"** sheet — likely the
  caves-to-be-explored queue from the app vision, no custom filter needed; the
  dimension columns for M6 write-back are **`Duljina`/`Dubina`** (plain meters);
  crospeleo's `EXCEL_WORKBOOK_SAFETY.md` is itself a port from a portfolio-tracker
  project (references `chp_portfolio_master_v1.2.xlsx`) — the principles are generic.
- **Next:** user eyeballs 2–3 known caves via `sb inspect`; confirm "Za istražit"
  semantics; then M2 (dossier skeleton: model + intake + statement gating + `report`).
