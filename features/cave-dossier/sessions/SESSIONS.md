# Session journal — cave-dossier

One block per working session, **newest on top**. Same discipline as
csx-to-survey-pipeline: terse, concrete, honest about limits. Appended by
`/wrap-up` at the end of every session.

---

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
