# Session journal — cave-dossier

One block per working session, **newest on top**. Same discipline as
csx-to-survey-pipeline: terse, concrete, honest about limits. Appended by
`/wrap-up` at the end of every session.

---

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
