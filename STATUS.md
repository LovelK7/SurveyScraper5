# STATUS

Updated: 2026-08-25 (maintained by `/wrap-up` at the end of each session)


Part numbering per [ARCHITECTURE.md](ARCHITECTURE.md).

## Part status

| Part | Status |
|---|---|
| 1 — field mobile app | PARKED (manual workflow; revisit after stage 2 works) |
| 2.1a — csx-to-survey | OPERATIONAL (own feature, semi-manual 4-step pipeline) |
| 2.1b — OSZ builder | NOT STARTED — **OSZ v10 template distributed to recorders 2026-08-25** (Word `.dotx` + Google-Docs `.docx`); M4 ungated. Reading filled zapisnici needs a `w:sdt`-aware parser for the Word form and a `[ ]`/`⟨ ⟩` text parser for the Docs form |
| 2.1c — isječak karte | NOT STARTED (port planned, M3) |
| 2.1d — fotografije ulaza | **new part, added 2026-08-26**. Matcher + staleness guard DONE (2026-08-28); downsizing not started. Staged photos are keyed by Redni broj in `…za istražit` (a queue, not a repo) and move to `!!Fotografije ulaza` as `<padded SUE>_…` when the cave is explored. Downsizing rides along with M6 |
| 2.1 — dossier builder | **M2 in progress** — dossier model + **two-gate** gating + lifecycle + `report` (SB-only) done; archive intake next |
| 2.2 — SB communication | **M1 ✅ DONE** (read-only, live SB v3.0); M2 next |

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
- [ ] Intake: resolve a cave's archive files from Drive (nacrt, izjave, fotografije ulaza)
      — needs the `drive_resolver` + `name_resolver` ports; until then `Source.ARCHIVE`
      rules report as *not checked yet*
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
  exception listed explicitly. Becomes a gate-1 rule at intake.
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

- 2026-08-25 — OSZ v10 shipped (Google-Docs variant, `.dotx` lock, distributed) + SB v3.0 adopted, M1 closed → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
- 2026-08-23 — project renamed SurveyScraper4 → SurveyScraper5 (complete: folder, Claude key, venv re-verified) → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
- 2026-08-23 — OSZ v10 template finalised: placeholders, checkbox vocabularies, workbench + conformance tooling → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
