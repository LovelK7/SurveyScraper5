# Session journal

One block per working session, **newest on top**: terse, concrete, honest about
limits. Appended by `/wrap-up` at the end of every session.

Entries before 2026-09-19 were written when the repo was organised as
`features/cave-dossier` + `features/csx-to-survey-pipeline` and used the
`2.1a`/`2.2b` part numbers. They are kept **verbatim**; read their paths and
numbers through the mapping in
[ARCHITECTURE.md](../ARCHITECTURE.md#the-labels).
`stages/3N-nacrt/sessions/SESSIONS.md` holds that stage's own frozen history.

---

### 2026-09-19 — Codebase restructured around the pipeline (agent) ✅

- **Why:** `features/cave-dossier` and `features/csx-to-survey-pipeline` were
  not features — each was a span of the pipeline holding several separable
  substages, buried in one 56-module package and one 31 KB README. Nothing
  distinguished outward-facing from internal. And `2.1a`/`2.1b`/`2.1c` was a
  first guess that stuck: 2.1a (a 95-file survey pipeline) sat as a sibling of
  2.1c (a 7-module map screenshot), and the letters carried no meaning.
- **Shape:** twelve stage folders under `stages/`, labelled `<digit><letter>` —
  digit = position in the pipeline, letter = the Croatian name (`4O` = OSZ,
  `2B` = baza). Each owns its README, code (`src/cave_dossier/<sub>/`), tests,
  docs and templates. New root `prod/` holds the whole outward-facing surface
  (Drive launchers, the TDX kit, the Drive-layout contract). Workspace state
  (`config.yaml`, `.env`, `data/`, `runs/`, `sb-sync/`) moved to the repo root
  so dev and an extracted prod bundle are the same shape. `journal/` is the
  active log. **5D** for the dossier builder is the point: it was `2.1`, the
  umbrella everything nested under; it *consumes* stages 1–4, it does not
  contain them.
- **Packaging:** one import namespace, many source roots, via an explicit
  `[tool.setuptools.package-dir]` map. The obvious shorthand —
  `packages.find where=[roots]` — is **not** a union: setuptools collapses every
  root onto `cave_dossier` and the last one wins, so `pip install -e .` succeeds
  and `import cave_dossier.osz` then fails. Both branches verified empirically
  on setuptools 84.0.0 before committing to the layout. `build_prod.py` flattens
  the bundle and ships a generated single-root pyproject, so the operator's
  unattended `pip install -e .` never meets the multi-root map — proved by
  extracting a bundle and installing it in a scratch venv.
- **Anchor:** `core/paths.py` replaces `FEATURE_ROOT = parents[3]`, which was
  depth-sensitive and conflated three roots. `workspace_root()` finds
  `.cavedossier-workspace` by walking up (one rule for dev and for
  `%LOCALAPPDATA%\CaveDossier\v<X>`); `repo_root()` is dev-only and `None` in
  prod; package assets use `Path(__file__).parent` and travel with their code.
- **Safety:** the 13 `features/*/` ignore rules covered **745 files / 1.6 GB**
  of real cave data, and the auto-commit hook runs `git add -A`. Done on a
  branch, which makes the hook inert by its own existing guard; `.gitignore`
  rewritten and proven with `git check-ignore` **before** a byte moved; every
  move a `git mv`. A path-independent blob-set fingerprint
  (`8242cd10…`) held identical across all 17 move commits.
- **Found in passing:** every prod bundle v1.0–v1.4 shipped six stale
  `.egg-info` files the operator then pip-installed over (now excluded); the
  three TDX `.bat` files hardcode one developer's absolute path *and* are
  copied out to operators, so every distributed copy has been inert since
  handover (replaced by a generated self-contained kit); `/wrap-up`'s guard
  hardcoded one machine's path, making it useless elsewhere; the glossary still
  named `!Speleo_baza_SUE_v2.4.xlsm`.
- **Doctor:** rewritten around a new `pipeline.yaml` manifest. Eight of its
  checks had degraded to **silent no-ops** — it would have reported a clean bill
  of health while checking nothing, and both `/feature-dev` and `/wrap-up` gate
  on its exit code. Work counters now make "examined too little" a failure in
  its own right, and it has 14 tests of its own, each breaking one input and
  asserting exit 1. Writing those found a real bug: the CLI↔DOC check
  substring-matched, so "code in `osz/`" counted as documenting the `osz`
  command.
- **Verified:** 361 tests (347 + 14 new), doctor **0 fail · 3 warn** — the same
  three historical-log warns as before the restructure. Live: `sb stats` reads
  the LIVE workbook (1458 rows), `geo locate 1220` and `people list` resolve
  their workspace data, and the prod bundle installs and imports from a scratch
  venv.
- **Limits:** `docs/commands.md` and `docs/module-map.md` are parked verbatim at
  the root — splitting their per-command sections into the stage READMEs is an
  editorial job, not a move, and is left for a later session.
  `test_audit_and_photos.py` still straddles 2B and 4F. Historical documents
  (SESSIONS, design-decisions, roadmap-decisions, SETUP_PROMPT) keep the old
  part numbers deliberately; the mapping table in ARCHITECTURE is how to read
  them.

---

### 2026-09-19 — 2.1e sastavnica: the Illustrator branch, designed and shipped in one session (agent) ✅

- **Did:** (1) *The branch.* ARCHITECTURE gained **§Two routes to the Nacrt** —
  route A (2.1a, cSurvey, ours) and route B (Adobe Illustrator: TDX → DXF/PDF →
  hand-drafted `.ai` → Nacrt PDF), diverging after TopoDroid and converging on
  the same archived artifact, so everything downstream stays route-blind. New
  **part 2.1e** + **bridge B13**, wired into the overview diagram, the
  part→bridge table, Map 3, the chains list and the glossary. Route B is not
  hypothetical: `!!!Digitalizacija` on the Drive *is* that workshop
  (`!SUE_sastavnica.ai`, `!Alati za digitalizaciju.ai`, two Illustrator
  manuals, and `!!!UPUTE.txt` telling drafters to use them).
  (2) *The template.* The user dropped `!SUE_sastavnica.pdf` in the repo root;
  it now lives in `sastavnica-template/templates/`. Measured it rather than
  guessing: 1 page A4, no form fields, logo = 59 vector paths, one embedded
  MyriadPro **subset**, block 251.58 × 100.36 pt at the top-left, five 20.08 pt
  rows, 15 cells whose rects come from the block's own stroke operators.
  `tools/inspect_sastavnica.py` re-derives that table from any future export.
  (3) *The blank.* `tools/build_blank.py` strips the 15 example values by
  **content-stream surgery** — drop every `Tj`/`TJ` issued under the value
  colour, keep the positioning — because labels and values are separable by
  fill colour alone (`#5e6161` @5 pt vs `#030505` @8–10 pt) and the subset's
  custom encoding makes extracted text unusable (`Broj plo?ice`).
  (4) *The module.* `sastavnica/` (addresses · render · fonts · prefill ·
  models) + `cavedossier sastavnica <broj>` with `--offline/--local/--force`,
  31 tests. (5) *Prod.* Published as **v1.4** beside the other two launchers.
- **Result:** Shipped and validated live. 347 tests green, doctor clean.
  SB 1220 (a cave already mid-digitization, DXF in its leaf) and SB 811 both
  delivered; the v1.4 launcher was validated by a **clean install from the
  published Drive folder**, not from the staged copy. Nine of fifteen cells
  fill from SB alone, fourteen once the cave's zapisnik is filled.
- **Learned:**
  - **A PDF can carry a second, invisible copy of itself.** The template was
    exported with *Preserve Illustrator Editing Capabilities*, so the page held
    the whole `.ai` under `/PieceInfo` — 80 % of the file. Every PDF *viewer*
    renders the page content; **Illustrator prefers the payload**. The first
    delivered sastavnica was therefore correct in Acrobat and showed the
    TEMPLATE's example values in the one application it exists for. The user
    caught it; `build_blank.py` now drops `/PieceInfo`, the stale `/Thumb`
    (which also still pictured the old values) and the XMP packet — 226 KB →
    45 KB. Generalisable: when a generated document is meant to be *opened* in
    its authoring application, check what that application actually reads.
    Note it only surfaced because the user opened rather than placed it —
    File > Place uses the page content and would have looked fine.
  - **PyMuPDF redaction cannot strip these values.** It removes any glyph whose
    box intersects the rect, and the 10 pt value boxes overlap the 5 pt labels
    above them: `HTRS koordinate:` came back as `HTRS koordin`. Measured, then
    abandoned for the stream walk.
  - **Myriad Pro is on every machine that matters.** It ships inside the
    Illustrator install (`Support Files/Required/Fonts/MyriadPro-Regular.otf`),
    which is exactly the population this branch serves — so the font is
    *found*, never bundled (it is licensed with Illustrator). With it the
    computed widths reproduce the authored ones exactly (`339823 5037995`
    68.81/68.81 pt), which is what proved the whole geometry model.
  - **The authored example is the spec.** Its hand-chosen 10/9/8 pt sizes are
    shrink-to-fit done by hand; its abbreviated names are a rule. Printing
    `Dario Maršanić, Matija Vrkić, Tatjana Ilić` shrank Ekipa to 6.25 pt where
    `D. Maršanić, M. Vrkić, T. Ilić` sits at 9.5. Also: kota rounded to whole
    metres, Dubina signed downward, a `0` dimension treated as "not surveyed
    yet" rather than printed as `0 m`.
  - **"Refuse on collision" needed a stamp to be usable.** The literal rule
    would refuse every ordinary re-run, so the delivered PDF carries a metadata
    stamp and only an *unstamped* file is refused — and since an Illustrator
    re-save replaces the producer, the same one rule protects a sastavnica the
    drafter has already edited.
  - **A new pipeline branch does not imply a new feature folder.** `sastavnica/`
    reads SB, the intake leaf, the OSZ and the geo finders; a separate feature
    could not import any of that (artifacts, never imports), so it is a module
    beside `osz/` and `georef/`.
  - **Pre-existing bug, found by the new tool's output:** `core/people.py`
    treated the conjunction "i" as merely word-bounded, so it matched the
    *initial* of every author whose first name starts with I — `I. Dujmović`
    split into `. Dujmović`. That fed the izjava gates and `osz backfill`, not
    just this tool. A conjunction now has to stand between spaces; regression
    test in `tests/test_people.py`.
- **Next:** decide whether the sastavnica's Lokacija should keep the OSZ's
  geo-admin-wins Najbliže mjesto (SB 811 prints *Grižane-Belgrad* where SB says
  *Potkobiljak*) or take SB's wording as a nacrt-only exception; then let a real
  drafter run v1.4 and see what the fifteen cells still get wrong.

---

### 2026-09-02 (later) — `osz fetch` → `osz backfill`, and the M6 delivery step designed (agent) ✅

- **Did:** (1) *Rename*: `osz fetch` never fetched anything — it reads a filled
  zapisnik and proposes SB updates — so it became **`cavedossier osz backfill
  <broj>`**, the exact mirror of `osz prefill`, matching the module that always
  was `osz/backfill.py` and the CSV that always was `dopune-sb-iz-osz.csv`.
  Applied to `cli.py` (parser, dispatch, `cmd_osz_fetch` → `cmd_osz_backfill`,
  help text), the `osz/backfill.py` + `osz/reader.py` docstrings, README,
  `_INDEX`, design-decisions (incl. the section heading + its TOC anchor),
  ARCHITECTURE (2.1b row, B7 row, and the B7 box inside the ASCII bridge
  diagram), STATUS, and `tests/test_osz_fetch.py` → `test_osz_backfill.py`.
  No alias: the old name now errors and names the replacement. SESSIONS left
  verbatim (chronology), the rename recorded in the decision record instead.
  (2) *Designed M6 delivery* — the step the M6 plan never had — as
  [docs/m6-delivery-design.md](../stages/6P-predaja/docs/m6-delivery-design.md): `cavedossier
  deliver <Redni broj>`, dry-run by default, six steps (OSZ completeness gate →
  `/` filler → files present and nameable → allocate the katastarski broj →
  printed approval → apply: rename, file into the three archive dirs, leaf into
  `Arhiva`, SB write-back). Registered in `_INDEX`, ARCHITECTURE B11 and the
  STATUS M6 row; the five open questions went to STATUS "Waiting on user".
- **Result:** rename shipped and green — 300 passed / 5 skipped,
  `pipeline_doctor` 0 fail (3 pre-existing WARNs in the other feature). The
  delivery design is **paper only, nothing built**; it deliberately names its
  own blockers rather than pretending M6 is a single sitting. Fixed a stale
  STATUS claim the rename exposed: the 2.1b row still said "reading filled
  zapisnici back" was M4's unbuilt half, three days after it shipped.
- **Learned:** (all four from measuring the live workbook/Drive, not from docs)
  - **Writing only the katastarski broj would put a row in two Power Query
    views at once.** *Istraženi* is `[Katastarski broj SUE] <> null`, *Za
    istražit* is `Napomena` containing `za istražit` — independent filters.
    0 of 885 numbered rows currently hold a queue flag, i.e. the operator
    clears it by hand today and `deliver` would be the first tool to break that
    invariant. Clearing the flag is part of the same write, not a follow-up.
  - **`Katastarski broj SUE` is dense**: ints 1…885, 885 rows filled, zero gaps
    and zero duplicates. So `max + 1` is the next number *and* `max == count`
    is a free corruption check — a mismatch means someone else's allocation is
    half-finished, which is a refusal, not a guess. SB is shared, so `max` must
    be re-read inside the same COM session as the write.
  - **4 of the 11 obligatory OSZ fields are unreadable today.** Podrijetlo
    imena, Vrsta objekta, Hidrogeološka funkcija and Hidrološka karakteristika
    are *checkbox groups*: none is in `osz/addresses.py:V10`, and
    `reader.read_osz_content()` returns a flat tuple of ticked labels with no
    group membership, so "is Vrsta objekta answered?" is unanswerable. The
    group→labels manifest (the "CroSpeleo-field reader") is the hard blocker
    before any completeness gate can exist.
  - **The `/` filler has an ordering trap.** Filling unused optional fields
    with `/` must happen *after* the gate, or the filler satisfies the very
    check meant to catch an unfinished zapisnik; and `/` must join
    `reader.py`'s placeholder markers, or `osz backfill` starts proposing `/`
    into SB cells and a re-delivery reads a filled document where there is
    none.
  - Archive conventions confirmed by looking: `!!Nacrti/<broj>.pdf` (927 files,
    3-digit padded), `!!Osnovni zapisnici/<broj>.docx` (611), `!!Fotografije
    ulaza/<broj>_<Ime>_<Autor>.jpg` — stated verbatim in that folder's own
    `!!!UPUTE.txt` — and `!!!Digitalizacija/Arhiva` flat with 451 loose entries.
- **Next:** answer the five delivery questions, then build the checkbox-group
  manifest (M4 tail) — it unblocks both the CroSpeleo fetcher and the delivery
  gate. A useful intermediate is `deliver` **gate-only** (dry run, `--apply`
  refused) once that and `Source.OSZ` gathering land, so the gate is exercised
  before any write exists.

---

### 2026-09-02 — prod launchers on the Drive, v1.0 → v1.3 in one evening (agent) ✅

- **Did:** (1) *First productionization slice* (ARCHITECTURE §Dev vs prod):
  `tools/build_prod.py --version X.Y --publish` + `tools/prod_templates/`
  (launcher.bat / bootstrap.ps1 / PROCITAJ_ME.txt) generate versioned
  double-click launchers for `osz prefill` and `photos process` in the
  dedicated Drive folder `!!!Digitalizacija/SurveyScraper5/` (user-chosen
  layout: launchers + `v<X>/` bundle.zip+bootstrap + `podaci/geo/` cloud copy
  ~280 MB + `_arhiva/` + VERZIJE.txt publish log). First double-click
  self-installs to `%LOCALAPPDATA%\CaveDossier\v<X>` — guided Python 3.11+
  check, venv + pip extras, geo robocopy, `.env` generated with
  `LOCAL_DRIVE_ROOT` derived by probing upward for the SB workbook.
  (2) *Three same-evening iterations driven by the user's real first runs*:
  v1.1 per-run logs (`%LOCALAPPDATA%\CaveDossier\logs\`, tee of every stream
  incl. setup/pip) + Consolas-20 console font via `SetCurrentConsoleFontEx`;
  v1.2 operator-side karta (setup installs `[karta]` + Chromium, shared
  georef login injected at build time from dev `.env`) + PROCITAJ_ME in real
  Croatian (UTF-8 BOM); v1.3 waiting snake `~~o>` (async-polled
  `ReadLineAsync` runner) + `PYTHONUNBUFFERED=1`. (3) *Two prefill fixes*:
  playwright-probe note naming the dev step instead of a Python import error,
  and `_karta_newly_embedded` — "unchanged" no longer leaves an old document
  holding the placeholder when this run has an excerpt to embed. Tests
  197→305 (build_prod suite + embed regression).
- **Result:** v1.3 live on the Drive; every version validated end-to-end on
  this machine as the operator (photos 1220 dry-run; prefill 1320 and 1087 —
  1087's excerpt fetched from georef.hr *by the prod install itself* and
  embedded on re-run). User ran v1.0 for real on 1087; each complaint became
  the next version within the hour.
- **Learned:** (1) Redirecting a Python CLI's streams (for logging) flips it
  to block buffering — v1.1 silently broke live output, and the user's
  "nothing is going on" was that, not just a missing spinner;
  `PYTHONUNBUFFERED=1` is part of any tee-style runner. (2) A conhost window
  that opens with a raster font both shrinks text and mangles UTF-8 glyphs —
  one `SetCurrentConsoleFontEx` call fixes both. (3) `_content_unchanged`
  compared text cells only, so an excerpt arriving after first delivery left
  the doc "netaknut" with the 1.5 KB placeholder — found only because live
  validation re-ran a real cave. (4) PS 5.1 + `$ErrorActionPreference=Stop`
  turns redirected native stderr into terminating NativeCommandError — the
  logging runner must run at EA Continue. (5) The 1087 first run delivered
  into `SB_1087_Božur_Frustuck` — that folder carried the wrong prefix for a
  *different* cave (config `intake.new_entries` knew it); user corrected the
  folder, prefill then created the proper leaf.
- **Next:** test the launchers on a second (non-dev) computer — the logs dir
  is built for exactly that; backlog holds bundled-runtime / wheel-cache /
  update-notice / old-install-cleanup ideas when friction shows up.

### 2026-09-01 — 2.1d entrance-photo processor + queue pull (agent) ✅

- **Did:** (1) *`photos/process.py` + `cavedossier photos process <Redni broj>`* —
  the standing 2.1d step: a cave's raw photos out of its `SB_<broj>_…` intake leaf
  into downsized `SB_<broj>_<Ime objekta>_<Autor>_<n>.jpg` **copies** beside the
  originals (config `photos:` targets, 1920 px / 1.5 MB; `--long-edge`,
  `--max-bytes`, `--author`, `--from`, `--osz`, `--overwrite`, `--dry-run`). Author
  read from the OSZ cell *Autor fotografije ulaza* and converted to the archive's
  filename spelling (`Lovel Kukuljan` → `LKukuljan` — no dot, unlike SB's
  `L.Kukuljan`); several people join with `-`, a missing author drops the component.
  (2) *`photos pull-staged <broj>`* — MOVES a cave's photos out of the
  `…za istražit` queue into its intake leaf, creating the leaf when the cave has
  none (`prefill.intake_folder_name`, made public and now shared); every `photos
  process` exit ends with a queue check that prints this command. (3) *`STATS.png`
  ignore list* — `photos.ignore_filenames` in config.yaml (fnmatch patterns),
  matches listed as skipped, removed before the numbering. (4) *Shared
  `intake.find_cave_leaf`*, replacing prefill's private copy. (5) *Fixed
  `locate_filled_osz`*: `backfill._pick_docx` and `prefill._find_old_osz` had
  drifted apart — unified into `backfill.pick_osz_docx`. (6) *`[photos]` extra*.
  290 tests (was 224), doctor 0 fail.
- **Result:** Live end to end. SB 1238: 6.92 MB / 3468×4624 → 1.23 MB / 1440×1920,
  the same result as the manual FastStone "resize to screen size". SB 1250: OSZ
  author `Renata Jerković` → `RJerković`, STATS.png skipped. SB 811 full loop:
  4 queued photos pulled in, queue emptied for that cave, processed to
  `SB_811_Possibile Grotta_1..4.jpg`. `photos match-queued` is retired (its sweep
  is finished) but kept; the mover into `!!Fotografije ulaza` under the katastarski
  broj is still the open last step of 2.1d.
- **Learned:**
  - **The fetcher went blind on exactly the leaves prefill had touched.** A
    migrated leaf holds both `SB_<broj>_OSZ.docx` and prefill's own
    `<ime>_stari_<datum>.docx` backup. `prefill._find_old_osz` excluded that
    marker and preferred the canonical name; `backfill._pick_docx` did neither, so
    every such leaf read as "no unambiguous OSZ" — affecting `osz fetch`, not just
    the new command. Two functions answering the same question is the bug; one
    (`pick_osz_docx`) is the fix.
  - **A locator's notes ARE the answer.** Taking only `.path` and discarding
    `location.notes` turned "two candidates, pick one" into a flat, wrong "no OSZ".
    Anything consuming that API has to print them.
  - **Re-encoding an already-small JPEG GROWS it.** SB 1250's phone photos
    (900×1600, already compressed) went 0.25 MB → 0.35 MB at quality 92, plus a
    generation of loss. A JPEG within both the pixel target and the size budget is
    now copied byte-for-byte.
  - **A leaf cannot tell you what is missing from it.** SB 811 processed
    "successfully" with nothing to do while four entrance photos sat in the queue —
    the worst answer, because it looks like success. Hence the queue check on
    *every* exit, the empty ones most of all.
  - **The `SB_<broj>_` prefix collides with itself.** It is what marks a queued
    photo, and also what `source_photos` reads as "already my output" — so pulled
    photos must lose it, or the next `process` cannot see them.
  - **Dry-run-by-default is not free.** It protects files a command CHANGES;
    `photos process` only adds (originals byte-for-byte, existing copies skipped),
    so `--apply` was friction with no safety behind it (user). `pull-staged`, which
    moves files, keeps the guard.
- **Next:** the 2.1d **mover** — file the processed copies into `!!Fotografije
  ulaza` and swap `SB_<Redni broj>` for the katastarski broj (rides with M6, since
  that number only exists then). Before that, settle the output resolution: the
  copies exist precisely so 1920 px stays revisable.

---

### 2026-08-30 (late evening) — People registry + statement gates (agent) ✅

- **Did:** (1) *`people/` package* (crospeleo ports, PORTING.md rows) —
  `registry.py` (design port of `crospeleo_registry` + the alias *generator*:
  aliases DERIVED at load from full "First Last" names with collision
  detection, curated `aliases` win, `(SOV)`-bracket strip-retry, exact-key
  resolution only), `name_resolver.py` (near-verbatim; NEW dual tokenization so
  the hyphen in `SKapidžić-Antolič` is a name joiner), `statements.py`
  (statement_checker restructured: stems go through `archive/izjave.py` so the
  SCOPE survives; per-person `PersonStatementStatus`). (2) *Committed registry*
  `data/people/registry.json` — 132 people seeded from the 133 real izjave
  (gitignore exception à la crospeleo `curated/`); curated aliases added live:
  `S.Antolič`→`SKapidžić-Antolič`, `R.Reš`→`RResch`; `V.Malnar` first
  `deceased: true` (exempt — no blocker/warning/listing). (3) *Gates* — izjave
  got their own gather step (`Source.STATEMENTS`; the dir is shared, so no
  waiting on archive intake): gate 1 blocks per author, registry- and
  scope-aware (scoped-elsewhere is its own blocker message); NEW gate-2
  per-person warnings (missing izjava for recorder/team; `UNKNOWN_PERSON` for
  names the registry can't resolve). (4) *Author-vs-finder criterion (user)* —
  in `Autori nacrta ili izvor` only `N.Surname` marks a survey author
  (`is_author_shorthand`); finders are fully exempt. (5) *CLI* —
  `people list` / `people check` (audit + `runs/people/statements-index.json`
  snapshot; caves + exploration years shown, sorted newest-first); `report`
  runs the statements enrich with an `Osobe · izjave` block. Tests 183 → 198.
- **Result:** Live `people check`: 133 izjave all linked, 0 orphans, 0 registry
  people missing statements; unresolved SB authors 125 → 28 (criterion) → 24
  (aliases + deceased), year-sorted so the chase-able top is F.Karabaić 2026 /
  N.Grozić 2025 and the hard tail is the 2000-era SG caves. Konglomeratača
  (SUE 570) report exercises the whole path (A.Lipovac → registry → universal
  izjava → gate 1 pass).
- **Learned:** (a) The izjava convention makes the hyphen load-bearing, so the
  ported variant algorithm needed keys over BOTH tokenizations — crospeleo's
  own resolver would miss `S.Kapidžić-Antolič` vs `SKapidžić-Antolič`.
  (b) The single spelling criterion (`N.Surname` = author, else finder) beats
  any scraping heuristic: it cut the unresolved list 125 → 28 with zero manual
  triage. (c) Statements can gate BEFORE archive intake because the izjave dir
  is flat and shared — modeling that as its own `Source` kept "not checked
  yet" honest for the rest of `Source.ARCHIVE`. (d) Deceased authors are a
  registry fact (`deceased: true`), not a warning to re-triage every run.
- **Next:** work the 24-name worklist (add registry entries / upgrade token
  names to full "First Last"); then the M2 tail — per-cave archive intake
  (`drive_resolver` port).

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
  (1) *Design* — [docs/sb-liburnija-hub.md](../stages/2B-baza/docs/sb-liburnija-hub.md): the
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
  ([osz-template/docs/placeholders.md](../stages/4O-osz/template-workbench/docs/placeholders.md)),
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
  mapping rules in [audit-v10.2.md](../stages/4O-osz/template-workbench/docs/audit-v10.2.md) §"Pravila
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
