# cave-dossier — SB communication + cave dossier builder

Pipeline parts **2.1 / 2.1b / 2.1c / 2.1d / 2.2** ([ARCHITECTURE.md](../../ARCHITECTURE.md)):
talk to **SB** (Speleo baza, the society's cave-registry Excel workbook), build a
per-cave **dossier** with warning/blocker gating, create the **OSZ**, produce the
**isječak karte**, process the **fotografije ulaza**. Python package
`cave_dossier`, CLI `cavedossier`. Run from VS Code — no GUI yet, function over
form.

Much of the machinery is ported from the read-only `../crospeleo-automation`
repo (the downstream cadastre-submission tool) — every copy is logged in
[docs/PORTING.md](docs/PORTING.md). Excel safety rules:
[docs/EXCEL_WORKBOOK_SAFETY.md](docs/EXCEL_WORKBOOK_SAFETY.md).

> Your answers of 2026-08-26 are built into the code and into this document.
> What is still undecided is collected in [Still open](#still-open).

---

## The idea in one paragraph

A **dossier** is one cave's folder — except it lives in memory instead of on
Drive. Building it means walking up to each source in turn (the SB row, the
files on Drive, the processed survey, the filled zapisnik, the isječak karte,
the processed photos), copying what that source knows into one object, and then
asking a fixed list of rules: *is anything mandatory still missing?* The answer
is what `cavedossier report` prints. Later milestones use the same object to
**write** the OSZ and to update SB — nothing else in the tool has to know where
a value originally came from.

Because the tool is being built source by source, the dossier records **which
sources have actually been gathered**. That is the difference between "this cave
has no entrance photo" and "nobody has looked in the photo folder yet", and the
whole gating design hangs on it.

## The workflow this encodes

A cave moves through SB in a handful of states, and there are **two gates**, not one.

```text
   Za istražit ──explored──► Nesređeni ──Nacrt + OSZ + foto + pločica + izjave──► Istraženi
   not explored yet          "fali nacrt         ▲                                 has a SUE
   no SUE number              i zapisnik"        │                                 number
                                            ┌────┴──────────────────┐
                                            │ GATE 1 — katastarski  │  ← this tool's gate
                                            │ broj (SUE)            │
                                            └───────────┬───────────┘
                                                        │ "almost a certain go"
                                                        ▼
                                            ┌───────────────────────┐
                                            │ GATE 2 — CroSpeleo    │  ← crospeleo-automation
                                            │ (Protokol v6)         │     submits; we pre-check
                                            └───────────────────────┘
```

**Gate 1 — katastarski broj (SUE).** The society's own acceptance step: a
readable Nacrt PDF, an OSZ with its mandatory fields filled, entrance photo(s),
a pločica, and an *Izjava za katastar* for every author (sketch **and** photo).
Passing it earns the cave its SUE number. That is why the SUE number is **not a
requirement of gate 1** — it is the *output*. Old caves are the standing
exception: a 1960 exploration has no pločica and never will, and it can still be
given a katastarski broj.

**Gate 2 — CroSpeleo.** The stricter national bar, a strict superset of gate 1:
adds isječak karte, georef zapis, izvor koordinata, vertikalna razlika,
istražile udruge, and the SUE number itself. The submission stays
crospeleo-automation's job downstream; this tool only pre-checks, so nothing
reaches that tool with a known-missing field.

**The queue is everything that is not Istraženi** — za istražit, nesređeni,
sudjelovanje, and the rows carrying neither a SUE number nor a flag.

### How the states are decided

Not by guesswork: the definitions are lifted from SB's **own Power Query**
(`Formulas/Section1.m` inside the workbook), so the tool and the Excel views
cannot drift apart.

| State | SB view | Filter | Rows (v3.0) |
|---|---|---|---|
| **Istraženi** | `IO_v2_1` | `Katastarski broj SUE` is not empty — that is the entire filter | 885 |
| **Za istražit** | `ZI_v2_1` | Napomena contains `za istražit` | 185 |
| **Nesređeni** | `NO_v2_1` | Napomena contains `neistraženo`, `fali nacrt`, `fali zapisnik`, `<5 m`, `puhalica`, `ponor`, `ponoviti`, `nastaviti` or `umjetan objekt` | 177 |
| **Sudjelovanje** | *(none yet)* | Napomena contains `sudjelovanje` — another society's cave that SUE took part in | 78 total, 28 otherwise unclassified |
| **Nesvrstano** | *(none)* | no SUE number and no flag of any kind | 19 |

Precedence when they overlap (29 caves hold a SUE number *and* say "ponoviti"):
SUE number → queue flag → outstanding work → provenance. Nesređeni deliberately
outranks sudjelovanje — a cave we only took part in that still says "fali nacrt"
belongs on the worklist. The dossier keeps the Nesređeni keywords that hit even
when another state wins.

Two things worth knowing: 8 rows land in Nesređeni only because their Napomena
happens to contain the word "ponor" (a word-boundary match in the Power Query
would fix that, Excel-side), and *sudjelovanje* has no view of its own yet —
recognising it here is what shrank the unclassified list from 47 rows to 19.

## Data flow

```text
                       config.yaml  +  .env          core/config.py → Settings
                                  │                  (which workbook? SANDBOX or LIVE?)
                                  ▼
  !Speleo_baza_SUE_v3.0.xlsm ─► SBReader ─► CaveRow ─► build_from_sb ─► CaveDossier
      (Excel, read-only)       sb/loader.py  one row   dossier/         the in-memory
                                                       sb_mapper.py     "cave folder"
                                                                             ▲
   Drive archive dirs   ·······························  intake      (M2, next)
   survey from 2.1a     ·······························  handoff     (M5)
   filled zapisnik      ·······························  OSZ fetcher (M4)
   isječak karte        ·······························  georef      (M3)
   processed photos     ·······························  2.1d        (with M6)
                                                                             │
                                                                             ▼
                                                          evaluate()   dossier/gating.py
                                                                             │
                                                  ReadinessReport ◄──────────┘
                                                  (one verdict per gate)
                                                                             │
                                              render() → console  dossier/report.py
```

Dotted lines are the sources that are **not implemented yet**. Their rules do
not fail — they report as *not checked yet*.

## What `cavedossier report --cave 570` actually does

1. [core/config.py](src/cave_dossier/core/config.py) reads `config.yaml` +
   `.env` into a `Settings` object and decides SANDBOX vs LIVE. The banner you
   see first is printed from this.
2. [sb/loader.py](src/cave_dossier/sb/loader.py) opens the workbook read-only
   (openpyxl), finds the header row by scoring rows against the configured
   column names, and returns the matching row as a `CaveRow` — the raw cells
   plus its **Excel row number** (the handle M6 will write back through).
3. [dossier/sb_mapper.py](src/cave_dossier/dossier/sb_mapper.py) turns those raw
   cells into typed dossier fields: numbers parsed, `Sinonimi` split, `Autori
   nacrta` split into people (society bracket peeled off as a flag), the
   `za istražit` marker parsed out of Napomena, and the **lifecycle state**
   derived. It then marks `Source.SB` as gathered.
4. [dossier/gating.py](src/cave_dossier/dossier/gating.py) runs the rule table.
   Each rule declares which source feeds it **and which gate it belongs to**;
   rules whose source is missing are set aside as *unchecked* instead of run.
5. [dossier/report.py](src/cave_dossier/dossier/report.py) prints identity →
   SB status → data → **both gate verdicts**. `--json` prints the dossier object
   instead (raw SB row omitted), which is what later stages will consume.

Nothing in this path can modify the workbook: reads go through openpyxl, and the
only write path in the package ([sb/safe_io.py](src/cave_dossier/sb/safe_io.py),
xlwings/Excel-COM with backups) is dormant until M6. See
[docs/sb-write-back-design.md](docs/sb-write-back-design.md).

## Three-tier verdict

| Tier | Meaning | Effect on a gate |
|---|---|---|
| **BLOCKER** | A mandatory thing is genuinely missing or invalid | blocks |
| **warning** | Worth your attention, you decide | does not block |
| **not checked yet** | The rule's source has not been gathered — the tool has not looked | blocks *if* that rule could block |

A gate passes only when it has no blockers **and** nothing blocking is left
unchecked. Today no cave can pass either gate: five of the six sources are
unimplemented, which is exactly what the report says.

## The rule table

Every rule lives in [dossier/gating.py](src/cave_dossier/dossier/gating.py).
**Gate 2 includes every gate-1 rule**; the last column lists only what it adds.

| Source | Gate 1 — katastarski broj | Gate 2 adds |
|---|---|---|
| **SB** (working) | Ime objekta · Lokalitet · Najbliže mjesto · Razdoblje istraživanja · Autori nacrta · Dubina | Interni katastarski broj (SUE) |
| **SB** (working) | Koordinate ulaza · Broj pločice — blockers if the exploration year is ≥ 2015, warnings otherwise (§5.1); kaverne exempt from the pločica rule (§5) | |
| **ARCHIVE** (next) | Nacrt PDF · Zapisnik (OSZ DOCX) · Fotografija ulaza (§5.1) · Izjava za katastar **per author** | |
| **SURVEY** (M5) | Horizontalna duljina | Vertikalna razlika (falls back to Dubina) |
| **OSZ** (M4) | Podrijetlo imena · Položaj i pristup · Vrsta objekta · Hidrogeološka funkcija · Hidrološka karakteristika · Osnovni opis s tehničkim podacima · Perspektiva daljnjeg istraživanja · Zapisničar · Članovi ekipe · Širina ulaza · Visina/duljina ulaza | Izvor koordinata · Istražile udruge |
| **MAP** (M3) | — | Isječak karte · Georef zapis |
| **PHOTOS** (2.1d) | *warnings only*: photos over the size budget, or not renamed to `<SUE>_…` | |

Warnings that never block either gate: the SB `Fotografija ulaza` flag
disagreeing with the archive, an author flagged as drawing for another society,
a malformed `Razdoblje istraživanja`, and the queue-state note.

### What §5.1 is (you asked)

**Protokol v6** is the Ministry's rulebook for the national cave cadastre
(`docs/protocol_katastar_speleoloskih_objekata_RH_v6.md` in
crospeleo-automation). Two of its sections drive rules here:

- **§6.1, Tablica 2** — the mandatory-field matrix. Fields marked `*` are
  mandatory, `**` advisory. Most gate-2 rules come from that table.
- **§5.1** — the *year-conditional* rule: GPS coordinates, an entrance
  photograph and the entrance pločica are mandatory **only if the exploration
  started in 2015 or later**. Older caves are exempt. That is exactly the
  exception you described — a pre-2015 cave without a pločica can still get a
  katastarski broj — so the tool drops those three checks to warnings when the
  exploration year is earlier or unreadable. §5 adds one more exemption:
  caverns (`kaverna`) never need a pločica.

The year is read from `Godina ili period istraživanja`, falling back to `Godina
zadnjeg istraživanja`, and the **earliest** 4-digit year in the cell decides (so
`2018-2019` → 2018).

### Where the whole workbook stands today

The gate-1 rules run over all 1294 named rows. SB is the only gathered source,
so this measures SB data quality alone:

| Gate-1 blocker | Rows |
|---|---|
| Dubina missing | 292 |
| Broj pločice missing (post-2015 caves) | 238 |
| Autori nacrta missing | 145 |
| Razdoblje istraživanja missing | 10 |
| Najbliže mjesto missing | 7 |
| Lokalitet missing | 1 |

Gate 2 adds 409 rows with no SUE number — which is simply "everything not yet
Istraženi". 108 rows carry an author with an outside-society bracket.

---

## What I understood from your answers

Recorded so the next session — human or agent — does not have to re-ask.

| # | Your answer | What the code does with it |
|---|---|---|
| A2 | `Duljina` = **stvarna duljina** (total length), not horizontal | SB `Duljina` stays total length; *Horizontalna duljina* is expected from the survey (2.1a) and stays unchecked until M5 |
| A3 | `Z` / kota ulaza lives only in SB + OSZ, never reaches CroSpeleo | Stored as `georeference.z_m`, displayed, never gated |
| A5 | Authors are comma-separated in practice; `(SOV)` is a **flag** meaning the sketch came from outside SUE; the column needs cleaning | The bracket is peeled off the name into `drawing_author_societies` and surfaced as a warning; a bare year in brackets (`Malez, M. (1960)`) is *not* treated as a society |
| A6 | Photo author is most reliably in the OSZ; filenames usually carry it too, and the two should agree | Photo authors will be read from the OSZ (M4) and cross-checked against filenames at intake; the per-author izjava check already has its slot |
| B1 / B2 | Two gates; the SUE number is the *reward* for passing gate 1 | `GateLevel.SUE` vs `GateLevel.CROSPELEO`; the SUE-number rule moved to gate 2 only |
| B3 | The queue is everything not in Istraženi | `LifecycleState` + `dossier.is_queued`; queue state is reported as context, never as a failure |
| B4 | Missing `Autori nacrta` blocks gate 1 | Blocker at gate 1 |
| B5 | Protokol v6 stands | §5.1 / §5 kept as ported |
| B6 | Exit codes `1` ready, `0` not ready, `99` error | Implemented; `--gate {sue,crospeleo}` picks which gate the code reports on (both always printed) |
| C1 | The SUE number is the filename key across nacrt / OSZ / photos; `_A` was *dopunski zapisnik*, now superseded by updating the OSZ in place | Intake will resolve by `Link Nacrt` / `Link Zapisnik` first, then padded SUE; `_A` files count as the same cave and get flagged as legacy |
| C2 | `Izjava_<Initial><Prezime>[_<Lokalitet>].pdf`; a locality-scoped izjava does **not** cover caves outside that locality; the `!!!` text files are the missing-izjava lists | Locality scope becomes a gate-1 rule at intake; the person registry comes from the crospeleo port |
| C3 | One photo suffices; the *za istražit* photo folder is a **staging queue**, not a repo — photos move into `!!Fotografije ulaza` and take the SUE prefix when the cave earns its number | Modelled as part 2.1d; the mover becomes a delivery action at M6 |
| C4 / 1 | Before a SUE number exists the cave's ID is its **Redni broj** | `dossier.serial_number` + `working_id`; the staged-photo matcher proposes `<Redni broj>_…` |
| 2 | Photo budget: cut 7 MB down to 1–2 MB, "resize to screen size" (FastStone) | Gate warns above **2 MB**; the processing targets (1920 px long edge, 1.5 MB) are in `config.yaml` under `photos:` |
| 4 | The column is now **`Autori nacrta ili izvor`** — for queued caves it holds the finder/source, not a survey author | Config renamed, with `sb.column_aliases` so the old spelling still reads; the gating label follows; `sb audit-authors` flags citation-shaped values |
| 5 | List the unclassified rows | `cavedossier sb unclassified` |
| 6 | Staged photos keep free names but gain a Redni broj prefix; needs a name-matching exercise | `cavedossier photos match-queued` — 44 of 53 matched |
| — | **2.1d entrance-photo processing** is a missing pipeline part | Added to [ARCHITECTURE.md](../../ARCHITECTURE.md) as part 2.1d, plus `Source.PHOTOS`, a gate-1 warning for oversized / unrenamed photos, and the `photos/` module |

## Identity: which number names a cave

Settled 2026-08-26. A cave has **two** identifiers over its life, and the
handover between them is the last step of gate 1:

| | Before gate 1 | After gate 1 |
|---|---|---|
| Identifier | **Redni broj** (SB column) | **Katastarski broj SUE** |
| In the dossier | `serial_number` | `sue_number` |
| Used for | intake folders, staged photo prefixes, any processing | archive filenames (`954.pdf`, `954.docx`, `954_…jpg`) |

`dossier.working_id` resolves the pair: the SUE number when it exists, the Redni
broj otherwise. Note the third number that is **not** an identifier: the Excel
row (`sb_row_number`) is only the write-back handle for M6 — it shifts whenever
a row is inserted above.

> The Redni broj is stable only going forward: the v3.0 restructure renumbered
> the column wholesale, which is why files still named after the *old*
> Za-istražit broj (`478_…`) need re-prefixing. `cavedossier photos match-queued`
> does that mapping.

## Workbook-wide audits

Some problems are only visible as a column-wide sweep, and are only fixable in
Excel. These commands are read-only worklists for exactly that.

```powershell
cavedossier sb audit-authors      # cells the name splitter cannot read confidently
cavedossier sb unclassified       # rows in none of SB's three views
cavedossier photos match-queued   # 2.1d: propose a Redni broj prefix per staged photo
```

`sb audit-authors` currently reports **483 rows** across six flags:
`single_name` 172 (a bare first name like "Renata"), `society` 108,
`placeholder` 96 (a "/" meaning nobody), `conjunction` 93 (split on "i" — verify
the halves are two people), `empty` 49, `citation` 2 (a literature source such
as `Malez, M. (1960)`, not a survey author).

`photos match-queued` matches the 53 free-form files in the staging folder
against SB and proposes `<Redni broj>_<rest>`, replacing a stale old-number
prefix where there is one. **51 of 53 matched.** Evidence, weighed rather than
ranked — two independent signals agreeing is the strongest result:

| Evidence | Example | Note |
|---|---|---|
| plaque number | `051-550_…`, `… 051 418 …` | strongest single signal |
| cave name or **synonym** | `Poljička Kosa_…`, `Goli breg 4` → *Sik Šits* | longest match wins; an exact whole-stem match is accepted at any length, which is what resolves `ak 47.jpg` → *AK-47* |
| old Za-istražit broj | `478_…`, `479 (1)` | the number the file already carries — stale since the v3.0 renumbering, so it is *replaced*, not kept |
| manual mapping | `Jama GB 1` → 812 | `photos.manual_matches` in config.yaml, for abbreviations no rule can reach |

Two signals that disagree are reported as a **conflict** and propose nothing.
`--apply` performs the renames (dry run is the default); it never touches
conflicts, unmatched files or already-correct names, and never overwrites an
existing target.

## Izjava za katastar — who signed, and what it covers

Settled 2026-08-26. Filenames in `!!Izjave za katastar RH` read as
`Izjava_<Osoba>[_<Opseg>].<ext>`:

| Example | Meaning | Covers |
|---|---|---|
| `Izjava_ABahović.pdf` | no suffix → **universal** | every cave |
| `Izjava_ACiceran_Šverda.pdf` | **locality** scope | caves whose `Lokalitet` is Šverda — the same author elsewhere needs a new izjava |
| `Izjava_MMarić_Kaverna-Učka.pdf` | **single-cave** scope (also `Kotluša`) | that one cave; both are exceptions, not the rule |
| `Izjava_SKapidžić-Antolič.pdf` | a **double surname**, hyphen-joined | not a scope at all |

The hyphen is what makes this parseable: it keeps a married double surname
together, so an underscore always means scope. The one legacy underscore form is
listed explicitly in `archive/izjave.py` until the file is renamed. Files
starting with `!` are templates and the society's own missing-izjave lists
(`!!!Fale_Brane.txt`), never izjave.

Scope resolution compares the suffix against the cave's `Lokalitet`, then its
name and synonyms — diacritic-insensitively. It becomes a gate-1 rule when
intake lands.

## Still open

**1. Two unmatched staged photos.** `606_rubinija_ulaz.jpg` and
`kostrčani_ulaz.jpg` — neither *rubinija* nor *kostrčani* appears anywhere in SB
under any spelling, so they need you. (`605_Ponor Prijeboj_*` turned out to be
*Ponor kraj Prijeboja*, Redni broj 1185 — its Napomena even says "fotke br 605";
it is in `photos.manual_matches` now.)

**2. A Power Query view for *sudjelovanje*** is yours to add in Excel if you
want it — 78 rows carry the keyword. The tool already treats it as a state, so
nothing here depends on it.

**3. Field-data intake dir layout** (C4) — unblocked by the Redni broj decision.
I will propose a layout keyed on it when you want it; that is the next thing
that gates the 2.1a handoff.

### Quick check commands

```powershell
cavedossier sb columns                      # what the tool sees in the workbook
cavedossier report --cave "Konglomeratača"  # one cave, end to end, both gates
cavedossier report --cave 570 --json        # the same dossier as data
```

---

## Setup (once)

```powershell
cd features/cave-dossier
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env     # then fill in (see below)
```

`.env` (gitignored, per-machine):

- `SB_WORKBOOK_PATH` — path to a **sandbox copy** of the SB workbook
  (recommended during development; relative paths resolve against this feature's
  root, e.g. `example/sb-sandbox/!Speleo_baza_SUE_v3.0.xlsm`).
- `LOCAL_DRIVE_ROOT` — the Drive Desktop mount of the society archive; used for
  LIVE mode (workbook resolves as `<LOCAL_DRIVE_ROOT>/<sb.workbook_filename>`)
  and, from M2 on, the archive dirs (nacrti, izjave, photos).

Every command prints `SB mode: SANDBOX (...)` or `SB mode: LIVE (...)` first —
always check the banner.

### Two venvs exist — know which one you are in

| Venv | What it holds | Use it for |
|---|---|---|
| `SurveyScraper5/.venv` (repo root) | this package **plus every optional extra** (playwright, python-docx, xlwings, pymupdf, pywin32) + pytest | day-to-day work across features |
| `features/cave-dossier/.venv` | this package + `[dev]` only | isolated feature work / the setup above |

Both provide the `cavedossier` command, so either is fine — just don't expect
`playwright` or `xlwings` in the feature-local one.

> **If a command dies with `uv trampoline failed to canonicalize script path`**
> (or pip/pytest suddenly "vanish"), the venv was created under an older
> absolute path — moving or renaming the repo folder breaks every `.exe` shim
> and every editable install inside it. Fix: recreate the venv
> (`uv venv .venv --python "C:/Program Files/Python311/python.exe"`, reinstall
> from a `pip freeze` taken beforehand) and re-run
> `uv pip install -e features/cave-dossier`. This happened once already, after
> the SurveyScraper4 → SurveyScraper5 rename.

## Commands

```powershell
# M1 — read-only SB inspection
cavedossier sb columns                     # detected header row + all column names
cavedossier sb inspect --cave "Ponor X"    # dump a cave's row (name / SUE / plaque; substring OK)
cavedossier sb stats                       # sheets, row counts, fill counts of key columns

# M2 — per-cave dossier
cavedossier report --cave "Konglomeratača"      # both gates, text
cavedossier report --cave 570 --json            # the dossier as data
cavedossier report --cave 570 --gate crospeleo  # exit code follows gate 2 instead

# Workbook-wide audits (read-only worklists for an Excel cleanup pass)
cavedossier sb audit-authors --limit 40    # author cells the splitter cannot read
cavedossier sb unclassified                # rows in none of SB's three views

# Part 2.1d — staged entrance photos
cavedossier photos match-queued            # DRY RUN: propose <Redni broj>_… per staged photo
cavedossier photos match-queued --apply    # perform the proposed renames in place
```

Exit codes (your convention): **1** = ready, **0** = not ready, **99** = error.
`--gate` only chooses which gate the exit code reports on — both are always
printed.

Console shows `?` instead of š/č/ž? `$env:PYTHONIOENCODING="utf-8"` (the CLI
also self-reconfigures its output streams, so this is rarely needed).

## Module map

| Path | What | Runs |
|---|---|---|
| `src/cave_dossier/cli.py` | `cavedossier` entry point (argparse), mode banner, exit codes | every command |
| `src/cave_dossier/core/config.py` | config.yaml + .env → `Settings`; SANDBOX/LIVE resolution | every command |
| `src/cave_dossier/core/normalization.py` | diacritic-insensitive matching keys (ported) | column + name matching |
| `src/cave_dossier/core/people.py` | split an author cell into people; peel off the society bracket | SB mapping |
| `src/cave_dossier/sb/safe_io.py` | workbook preflight/backup/COM-write safety (ported) | reads: preflight only; writes: M6 |
| `src/cave_dossier/sb/loader.py` | `SBReader`: header autodetect, column aliases, `find_caves` | `sb *`, `report` |
| `src/cave_dossier/sb/audit.py` | workbook-wide data-quality sweeps (authors, unclassified rows) | `sb audit-authors`, `sb unclassified` |
| `src/cave_dossier/photos/matcher.py` | 2.1d: match staged photos to SB rows, propose/apply `<Redni broj>_…` | `photos match-queued` |
| `src/cave_dossier/archive/izjave.py` | izjava filenames: person, scope, and what a scope covers | intake (next) |
| `src/cave_dossier/dossier/model.py` | `CaveDossier`, `Source`, `GateLevel`, `LifecycleState`, files, issues, readiness | the shared object |
| `src/cave_dossier/dossier/sb_mapper.py` | SB row → dossier; queue flag + lifecycle derivation | `report` |
| `src/cave_dossier/dossier/gating.py` | the rule table → blockers / warnings / unchecked, per gate | `report` |
| `src/cave_dossier/dossier/report.py` | the text rendering behind `cavedossier report` | `report` |
| `sessions/SESSIONS.md` | session journal (appended by `/wrap-up`) | — |
| `backlog/ideas.md` | dated idea capture | — |
| `example/` | **gitignored** — sandbox workbook + real cave data (PII, never committed) | — |
| `tests/` | pytest on tiny synthetic fixtures | `python -m pytest` |

Planned modules: `dossier/intake.py` (rest of M2 — resolve a cave's files on
Drive), `georef/` (M3 — isječak karte), `osz/` (M4 — OSZ builder), and the
downsize/rename half of `photos/` (2.1d — the matcher is done, the processor is
not).

## Testing

```powershell
python -m pytest
```

Fixtures are synthetic (fake caves, fake names) — `tests/fixtures/mini_sb.xlsx`
is regenerated by `python tests/fixtures/make_mini_sb.py` and deliberately
reproduces the live workbook's traps (metadata row above the header, header
spelling variants, a queue row with no SUE, a surname-first author cell). Real
data checks run manually via the CLI against the sandbox — see
[STATUS.md](../../STATUS.md) for the current checklist.
