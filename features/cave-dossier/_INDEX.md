# cave-dossier — feature index
<!-- Manually maintained map for agents and developers. Update when adding,
     removing or renaming modules/docs. Last updated: 2026-08-30. -->
<!-- LLM quick-find: this file is the map of the feature. Match the layer in
     the cheat-sheet, then the one-liner in the tables, then open the path.
     The operator-facing view is README.md; settled design rationale is
     docs/design-decisions.md. -->

> **Layer cheat-sheet** — *Where does X live?*
>
> - **A command / flag** → `src/cave_dossier/cli.py` (single argparse file: parser in `build_parser()`, dispatch ladder in `main()`, bodies as `cmd_*`)
> - **Settings / config resolution** (LIVE vs SANDBOX workbook, .env, geo knobs) → `core/config.py` + `config.yaml`
> - **Reading SB** → `sb/loader.py` (`SBReader`); write safety → `sb/safe_io.py`
> - **The shared dossier object + gating rules** → `dossier/model.py` + `dossier/gating.py`
> - **Isječak karte (georef.hr browser flow)** → `georef/` — staleness/self-healing in `georef/worker.refresh_reason`
> - **Locality / elevation from coordinates** → `geo/`
> - **OSZ template writing + prefill** → `osz/` — cell addresses per template version in `osz/addresses.py`
> - **Satellite tables (Liburnija sheet ↔ SB)** → `satellites/`
> - **Name/plaque/number matching shared by photos + intake** → `core/matching.py`
> - **People: the author registry, aliases, izjava linkage** → `people/` + `data/people/registry.json`
> - **Why a rule/heuristic exists** → [docs/design-decisions.md](docs/design-decisions.md)
> - **Where a ported file came from** → [docs/PORTING.md](docs/PORTING.md)

## Module map (`src/cave_dossier/`)

| Path | What | Runs |
|---|---|---|
| `cli.py` | `cavedossier` entry point (argparse), mode banner, exit codes (1 ready / 0 not / 99 error) | every command |
| `core/config.py` | config.yaml + .env → `Settings`; LIVE-first workbook resolution with fallback; `geo.*` knobs | every command |
| `core/normalization.py` | diacritic-insensitive matching keys (ported) | column + name matching |
| `core/people.py` | split an author cell into people; peel off the society bracket | SB mapping, `osz fetch` |
| `core/person_aliases.py` | "First Last" abbreviation variants (ported), `to_sb_shorthand` (`L.Kukuljan`), cross-convention `same_person` | `osz fetch` |
| `core/matching.py` | the shared name/plaque/number matcher behind photo and folder mapping; `SB_PREFIX` | `photos *`, `intake *` |
| `sb/safe_io.py` | workbook preflight/backup/COM-write safety (ported) | reads: preflight only; writes: M6 |
| `sb/loader.py` | `SBReader`: header autodetect, column aliases, `find_caves` | `sb *`, `report`, all serial lookups |
| `sb/audit.py` | workbook-wide data-quality sweeps (authors, unclassified rows) | `sb audit-authors`, `sb unclassified` |
| `dossier/model.py` | `CaveDossier`, `Source`, `GateLevel`, `LifecycleState`, files, issues, readiness | the shared object |
| `dossier/sb_mapper.py` | SB row → dossier; queue flag + lifecycle derivation | `report` |
| `dossier/gating.py` | the rule table → blockers / warnings / unchecked, per gate | `report` |
| `dossier/report.py` | the text rendering behind `cavedossier report` | `report` |
| `georef/` | 2.1c: georef.hr Playwright flow (ported) — `worker` (orchestration, delivery, `refresh_reason` self-healing, Excel-tolerant CSV), `flows` (5:4 marker-centered crop, PNG budget), `client`, `models`, `selectors`, `artifacts` | `karta`, `osz prefill` |
| `geo/` | 2.1b finders: `locality` (SB-wins synthesizer), `admin_lookup` (DGU PIP), `rgi_client` (WFS + offline gpkg), `toponym_matcher`, `elevation` (INSPIRE DMV grid, 3765→3045), `provision` (`fetch-data`), `models` | `geo *`, `osz prefill` |
| `osz/` | 2.1b: `writer` (lxml on word/document.xml — cell-own styles, `embed_png`), `addresses` (v10 table coordinates), `prefill` (orchestrator + sidecar + dopune-sb.csv), `reader` (filled-document cells; placeholders read as empty), `backfill` (OSZ vs SB → review proposals), `models` | `osz prefill`, `osz fetch` |
| `satellites/` | 2.2b: `model` · `liburnija` · `resolver` (ranked keys, never local row ids) · `sync` (four review lists) | `sat sync` |
| `intake/scanner.py` | field-data leaf folders → SB rows, `SB_<Redni broj>_<Ime>_…` proposals | `intake map` |
| `intake/liburnija.py` | read-only bridge over the cached Liburnija sheet CSV | `intake map` |
| `photos/matcher.py` | 2.1d: match staged photos to SB rows, propose/apply `SB_<Redni broj>_…`, staleness guard | `photos *` |
| `archive/izjave.py` | izjava filenames: person, scope, and what a scope covers | `people *`, `report` |
| `people/registry.py` | the people registry: canonical names + curated aliases (`data/people/registry.json`), derived alias keys with collision detection, exact-key resolution (ported design) | `people *`, `report` |
| `people/name_resolver.py` | comparison keys for a name as written anywhere (full / shorthand / 3+ tokens / hyphenated double surname; đ-fold) (ported) | statement matching |
| `people/statements.py` | scan `!!Izjave za katastar RH`, link people ↔ izjave (scope-aware), fill `person_statements` + statement files on the dossier, JSON index snapshot (ported) | `people *`, `report` |

Planned modules: `dossier/intake.py` (rest of M2 — resolve a cave's files on
Drive), the CroSpeleo half of the OSZ fetcher (checkbox groups + narrative
controls + the Google-Docs text variant — `osz/reader.py` covers the
identity/metadata cells the SB backfill needs), the downsize/rename half of
`photos/` (2.1d).

## Docs map

| File | What | Kind |
|---|---|---|
| [README.md](README.md) | operator view: what this is, setup, commands, testing | living reference |
| [docs/design-decisions.md](docs/design-decisions.md) | settled decisions + their why: two gates, rule table, identity, Q&A record, intake/izjava/photo matching, people registry + statement gates, prefill rules | decision record |
| [docs/PORTING.md](docs/PORTING.md) | ledger of every file copied from crospeleo-automation | living ledger |
| [docs/EXCEL_WORKBOOK_SAFETY.md](docs/EXCEL_WORKBOOK_SAFETY.md) | why reads are openpyxl and writes are Excel-COM only | decision record |
| [docs/sb-liburnija-hub.md](docs/sb-liburnija-hub.md) | satellite-hub design (2.2b) | design |
| [docs/sb-satellite-tables.md](docs/sb-satellite-tables.md) | why satellites join on shared keys, never local row ids (with measurements) | decision record |
| [docs/sb-powerquery.md](docs/sb-powerquery.md) | SB's Power Query view filters (M code) + how to re-extract them | reference |
| [docs/sb-write-back-design.md](docs/sb-write-back-design.md) | M6 write-back design (dormant) | design |
| [docs/sb-restructure-excel-prompt.md](docs/sb-restructure-excel-prompt.md) | the prompt that drove the v3.0 workbook restructure | history |
| [osz-template/README.md](osz-template/README.md) | the OSZ v10 template workbench (tools, audits, conformance) | living reference |
| [data/README.md](data/README.md) | provenance + licences of the downloaded geodata | reference |
| [sessions/SESSIONS.md](sessions/SESSIONS.md) | session journal, newest on top | chronology |
| [backlog/ideas.md](backlog/ideas.md) | dated idea capture (promote when an idea's time comes) | living ledger |

Repo-level: [ARCHITECTURE.md](../../ARCHITECTURE.md) (part numbering — the
reference vocabulary; dev-vs-prod rules), [STATUS.md](../../STATUS.md) (where
the dev cycle stands), [CLAUDE.md](../../CLAUDE.md) (agent orientation),
[shared/glossary.md](../../shared/glossary.md) (Croatian domain terms).

## Data & runtime locations

| Where | What | Tracked? |
|---|---|---|
| `config.yaml` | committed config (SB columns, archive dirs, geo knobs, manual matches) | yes |
| `.env` | per-machine: `LOCAL_DRIVE_ROOT`, `SB_*`, `GEOREF_*` | no (`.env.example` is) |
| `config/selectors.yaml` | georef.hr DOM selectors (line-based, not real YAML) | yes |
| `osz-template/templates/Zapisnik_OSZ_v10.docx` | the template `osz prefill` fills | yes |
| `data/geo/` | boundary GeoPackages, RGI gazetteer, DEM tiles (`geo fetch-data`) | no (README is) |
| `data/people/registry.json` | the people registry: canonical authors + curated aliases (hand-curated record) | **yes** |
| `runs/people/statements-index.json` | derived person ↔ izjava linkage snapshot (`people check`) | no |
| `example/` | sandbox workbook + real cave data (PII) | no |
| `runs/georef/<broj>/`, `runs/osz/<broj>/` | per-cave run artifacts, overwritten on re-run | no |
| `sb-sync/<satellite>/<date>/` | `sat sync --out` review lists | no (README is) |
| `tests/` + `tests/fixtures/mini_sb.xlsx` | pytest on tiny synthetic fixtures (`make_mini_sb.py` regenerates) | yes |
