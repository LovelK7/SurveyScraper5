# /feature-dev [what is being built]

Guide for developing a feature or capability in SurveyScraper5 — from design
through build, test, and the **documentation close-out that is part of the
work, not an afterthought**. Every rule below exists because the user had to
ask for it once; following this skill means never asking twice. Finish with
the pipeline doctor, then hand off to `/wrap-up`.

## Phase 1 — Orient and design

1. Read [ARCHITECTURE.md](../../../ARCHITECTURE.md) first: find the **part**
   this work belongs to and the **bridges** it touches (§Bridges — part →
   bridge → command is the repo's navigation model). Read
   [STATUS.md](../../../STATUS.md) for the milestone ladder, and the touched
   feature's `_INDEX.md` for its module map.
2. When the user answers a design question, that answer is a **decision** —
   it will be recorded in `docs/design-decisions.md` at close-out (with date
   and the why), never left only in chat and never dumped into the README.
3. Porting from `../crospeleo-automation` is copy-and-adapt, one
   `docs/PORTING.md` row per file, at the moment of the copy. The reference
   repos are never edited and never get git commands.

## Phase 2 — Build rules (standing, non-negotiable)

- **SB is never written by a tool** before M6. Anything that "changes" SB
  emits a review CSV (`dopune-*.csv`, utf-8-sig / comma / CRLF) that a person
  carries into Excel. Precedence everywhere: **SB wins** — computed values
  fill EMPTY cells; disagreements are printed warnings, never overrides.
- **The Drive dirs are hand-managed by non-technical people.** Assume files
  get deleted, renamed, opened in Word/Excel (which strips zero-padding,
  reformats dates, adds blank rows), or replaced with wrong formats. Every
  staleness/consistency check lives in the tool (self-healing on the next
  run); a failed delivery degrades to the local `runs/` copy with a clear
  message. No workflow may require a manual cleanup ritual.
- **Fail-soft by contract**: missing optional deps, network trouble, missing
  data files → a note and a degraded-but-useful result, never a crash. Any
  network-touching capability gets an `--offline` path over locally cached
  data.
- **Dev/prod portability** (ARCHITECTURE §Dev vs prod): one `cavedossier`
  subcommand per tool with the Redni broj as the only input; per-machine
  facts only in `.env`; user-tunable knobs in `config.yaml` (heuristic
  constants stay module-level with their rationale in a comment); every
  local dataset regenerable by one command.
- Identity conventions: pre-SUE id is `SB_<Redni broj>` (files pad to 4,
  intake dirs don't — accept both when matching); SUE prefixes stay bare.
  Diacritic-insensitive matching via `core/normalization.py`; person names
  via `core/people.py` + `core/person_aliases.py`.

## Phase 3 — Test protocol

1. **Unit tests on synthetic fixtures** (`tests/`, `mini_sb.xlsx` pattern —
   fake data reproducing the live workbook's traps). New behavior lands with
   tests; the whole suite stays green (`python -m pytest`).
2. **Terminal-first live validation**: before wiring a new data source into a
   document or delivery, prove its OUTPUT with debug commands over many real
   caves (the `geo locate`/`geo kota` pattern; a stratified sweep found three
   real bugs in one run). Data first, integration second.
3. **Verify in the real consumer**: a produced DOCX is opened via Word COM
   (controls intact? styles from the template's own cells — Word stores an
   empty cell's intended style on the paragraph mark, never copy a sibling's);
   a delivered file is checked at its Drive destination; an SB-facing change
   is exercised against the sandbox workbook AND once against a known live
   cave (651/764/1320 are the validated references).
4. Anything server-side-writing (georef.hr saves) is spent deliberately —
   one cave per validation, never a sweep without the user's say-so.

## Phase 4 — Documentation close-out (the part that keeps getting forgotten)

Docs are updated **in the same session as the code**, in the right bucket
(audience split, root CLAUDE.md): agents read `_INDEX.md`, the operator reads
`README.md`, rationale lives in `docs/design-decisions.md`. Walk this
checklist explicitly — every box, every time:

- [ ] **Feature README — Commands section**: every new subcommand/flag
      appears in its part-grouped block, with the behavioral rules as
      comments. Living content (Commands) stays ABOVE run-once content
      (Setup). TOC updated; headings linkable.
- [ ] **`_INDEX.md`**: new modules in the module map + layer cheat-sheet;
      new docs in the docs map; new data locations in the locations table.
- [ ] **`docs/design-decisions.md`**: every decision settled this session,
      dated, with its why — including what was validated and against what.
      TOC entry added.
- [ ] **ARCHITECTURE.md**: the part-map row's STATUS column reflects reality
      (stale "waiting on X" rows are exactly what rots); a new script that
      connects two nodes is a **bridge** — add/extend the bridge maps, the
      catalog row (anchored `<a name>`), the per-part table, and the chains.
      Diagrams stay maximally linkable (`<pre>` + `<a href>` — regenerate
      with width verification, see the scratch pattern in the 2026-08-30
      session).
- [ ] **STATUS.md**: milestone-ladder row + the detailed checklist for the
      touched milestone.
- [ ] **`docs/PORTING.md`**: a row per ported file (already done in Phase 1,
      verify none were missed).
- [ ] **`backlog/ideas.md`**: dated one-liners for every "we should also"
      that surfaced and was not built.

## Phase 5 — Pipeline doctor, then wrap up

```powershell
python tools/pipeline_doctor.py
```

- **FAIL** lines (broken links, CLI commands missing from the README,
  `_INDEX` paths that don't exist) are fixed before finishing — no
  exceptions.
- **WARN** lines are triaged: fix what's cheap, backlog the rest with a
  dated line.
- **STALE?** lines are re-confirmed one by one — each is a status claim that
  may have just been invalidated by this very session's work.

Then end the session with `/wrap-up` (STATUS session one-liner, SESSIONS
block, curated commit). The doctor being clean is part of "done".
