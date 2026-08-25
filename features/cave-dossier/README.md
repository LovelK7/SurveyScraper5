# cave-dossier — SB communication + cave dossier builder

Pipeline parts **2.1 / 2.1b / 2.1c / 2.2** ([ARCHITECTURE.md](../../ARCHITECTURE.md)):
talk to **SB** (Speleo baza, the society's cave-registry Excel workbook), build a
per-cave **dossier** with warning/blocker gating, create the **OSZ**, produce the
**isječak karte**. Python package `cave_dossier`, CLI `cavedossier`. Run from
VS Code — no GUI yet, function over form.

Much of the machinery is ported from the read-only `../crospeleo-automation`
repo (the downstream cadastre-submission tool) — every copy is logged in
[docs/PORTING.md](docs/PORTING.md). Excel safety rules:
[docs/EXCEL_WORKBOOK_SAFETY.md](docs/EXCEL_WORKBOOK_SAFETY.md).

> **If you read one section, read [What I need you to check and confirm](#what-i-need-you-to-check-and-confirm).**
> It lists every assumption the code currently makes about *your* data and *your*
> rules, with the command to check each one.

---

## The idea in one paragraph

A **dossier** is one cave's folder — except it lives in memory instead of on
Drive. Building it means walking up to each source in turn (the SB row, the
files on Drive, the processed survey, the filled zapisnik, the isječak karte),
copying what that source knows into one object, and then asking a fixed list of
rules: *is anything mandatory still missing?* The answer is what
`cavedossier report` prints. Later milestones use the same object to **write**
the OSZ and to update SB — nothing else in the tool has to know where a value
originally came from.

Because the tool is being built source by source, the dossier records **which
sources have actually been gathered**. That is the difference between "this
cave has no entrance photo" and "nobody has looked in the photo folder yet",
and the whole gating design hangs on it.

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
                                                                             │
                                                                             ▼
                                                          evaluate()   dossier/gating.py
                                                                             │
                                                      ReadinessReport ◄──────┘
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
   plus its **Excel row number** (that number is the handle M6 will write back
   through).
3. [dossier/sb_mapper.py](src/cave_dossier/dossier/sb_mapper.py) turns those
   raw cells into typed dossier fields: numbers parsed, `Sinonimi` split,
   `Autori nacrta` split into people, the `za istražit` marker parsed out of
   **Napomena**. It then marks `Source.SB` as gathered.
4. [dossier/gating.py](src/cave_dossier/dossier/gating.py) runs the rule table.
   Each rule declares which source feeds it; rules whose source is missing are
   set aside as *unchecked* instead of run.
5. [dossier/report.py](src/cave_dossier/dossier/report.py) prints identity →
   SB data → verdict. `--json` prints the dossier object instead (raw SB row
   omitted), which is what later stages and other tools will consume.

Nothing in this path can modify the workbook: reads go through openpyxl, and
the only write path in the package ([sb/safe_io.py](src/cave_dossier/sb/safe_io.py),
xlwings/Excel-COM with backups) is dormant until M6. See
[docs/sb-write-back-design.md](docs/sb-write-back-design.md).

## Three-tier verdict

| Tier | Meaning | Effect on `ready` |
|---|---|---|
| **BLOCKER** | A mandatory thing is genuinely missing or invalid | blocks |
| **warning** | Worth your attention, you decide | does not block |
| **not checked yet** | The rule's source has not been gathered — the tool has not looked | blocks *if* that rule could block |

`ready` is true only when there are no blockers **and** nothing blocking is left
unchecked. Today that means no cave can be "ready" yet — four of the five
sources are unimplemented, which is exactly what the report says.

## The rule table

Every rule below lives in [dossier/gating.py](src/cave_dossier/dossier/gating.py)
and encodes **Protokol v6** (Tablica 2 mandatory fields, §5.1 year-conditional
rules, §5 kaverna exemption), inherited from crospeleo-automation's
`readiness_validator.py`.

| Source | Rules | Tier |
|---|---|---|
| **SB** (working) | Ime objekta · Interni katastarski broj (SUE) · Najbliže mjesto · Lokalitet · Razdoblje istraživanja · Autori nacrta · Dubina | blocker |
| **SB** (working) | Koordinate ulaza · Broj pločice | blocker if exploration year ≥ 2015, otherwise warning (§5.1); kaverne are exempt from the plaque rule (§5) |
| **SB** (working) | Still in the `za istražit` queue · malformed exploration year | warning |
| **ARCHIVE** (next) | Zapisnik DOCX · Nacrt PDF · `Izjava za katastar` per author · Fotografija ulaza (year-conditional) | blocker |
| **ARCHIVE** (next) | SB "Fotografija ulaza" flag disagrees with what is on Drive | warning |
| **SURVEY** (M5) | Horizontalna duljina · Vertikalna razlika (falls back to Dubina) | blocker |
| **OSZ** (M4) | Podrijetlo imena · Položaj i pristup · Vrsta objekta · Hidrogeološka funkcija · Hidrološka karakteristika · Osnovni opis s tehničkim podacima · Perspektiva daljnjeg istraživanja · Zapisničar · Članovi ekipe · Istražile udruge · Širina ulaza · Visina/duljina ulaza · Izvor koordinata | blocker |
| **MAP** (M3) | Isječak karte · Georef zapis | blocker |

Run over the whole sandbox workbook today (1294 named rows, 185 of them
queued), the SB-fed rules alone report: **409** rows with no SUE number,
**292** with no Dubina, **238** modern rows with no pločica, **145** with no
Autori nacrta.

---

## What I need you to check and confirm

Three groups: **A** is "does the code read your data correctly" (checkable
against Excel in a minute), **B** is "are these the rules you want" (your call,
changes what blocks), **C** is "I cannot build the next piece until you decide".

### A — Data mapping (please spot-check against Excel)

**A1. The column map.** `config.yaml` → `sb.field_columns` maps 14 SB columns
onto dossier fields (Sinonimi, Lokalitet, Najbliže mjesto, Duljina, Dubina, Z,
Godina zadnjeg istraživanja, Napomena, Fotografija ulaza, Zagađenost, Ledenica,
Dopunski zapisnik?, Link Nacrt, Link Zapisnik). Nine more (name, SUE, pločica,
X/Y HTRS, …) come from the older `sb.*_column` settings.
*Check:* `cavedossier report --cave "<a cave you know well>"` and compare the
SB block line by line with its Excel row.

**A2. `Duljina` is NOT `Horizontalna duljina` — is that right?** I treat the SB
`Duljina` cell as the cave's total/polygon length and leave Tablica 2's
*Horizontalna duljina* to the survey (2.1a), which is why it currently shows as
unchecked. If your `Duljina` column already means horizontal length, tell me and
that rule moves to SB — 1200-odd caves would then satisfy it immediately.

**A3. `Z` = kota ulaza.** Used only as the entrance elevation on the
georeference, never as a dimension. Correct?

**A4. Which year decides §5.1?** I read `Godina ili period istraživanja` first
and fall back to `Godina zadnjeg istraživanja`, taking the **earliest** 4-digit
year found. For `2018-2019` that is 2018. Correct, or should the *last* year
decide?

**A5. Author splitting.** `Autori nacrta` is free text, so it gets split:

| SB cell | becomes |
|---|---|
| `Ivo Ivić; Ana Anić` | two people |
| `Lovel i Mate` | two people |
| `/` | nobody (placeholder, not an author) |
| `Malez, M. (1960)` | **one** person `Malez M. (1960)` |
| `A.Lipovac (SOV)` | one person, society suffix kept attached |

Two questions: should `(SOV)` be stripped and recorded as the author's
organization, and are there cell formats in SB that this would still get wrong?

**A6. Photo authors have no source.** SB has no "autor fotografije" column, so
the per-author izjava check for *photo* authors currently has nobody to check.
The photo filenames look like they carry it
(`006_Bani_ulazP4030014_TMarkanjević.JPG`). Should intake parse the author out
of the filename tail, or does this come from the OSZ?

### B — Policy decisions (your call)

**B1. What is "READY" the gate for?** Right now one gate answers both "may I
produce the OSZ?" and "may I deliver to the archive dirs?". If those should be
two different bars (e.g. you can write an OSZ without an isječak karte, but not
deliver one), say so and the rules split into two sets.

**B2. Missing SUE number blocks — should it?** 409 of 1294 rows have no
`Katastarski broj SUE`, including all 185 queued caves. If the SUE number is
assigned late in your workflow, this should be a warning until delivery.

**B3. Should queued (`za istražit`) caves be gated at all?** They currently run
the full rule set and collect blockers for data they cannot have yet. The
alternative: exclude them from readiness entirely and treat the queue as a
worklist ("these 185 need field work").

**B4. Missing `Autori nacrta` blocks** (145 rows). Blocker or warning?

**B5. Protokol v6 still current?** The 2015 threshold for
GPS/fotografija/pločica, and the kaverna exemption from the plaque rule, are
inherited from the protocol version crospeleo-automation encodes. Confirm no
newer protocol supersedes it.

**B6. Exit codes** for `report`: `0` ready, `1` not ready, `2` lookup/config
error — so it can be scripted. Fine?

### C — Open decisions that block the next step (archive intake)

**C1. How do I find a cave's files?** From the Drive dirs I can see the
convention is the zero-padded SUE number as the filename stem — `!!Nacrti/001.pdf`,
`!!Osnovni zapisnici/012.docx` — and the SB columns **`Link Nacrt` / `Link
Zapisnik` hold exactly that stem**. My plan: resolve by the Link column when
present, otherwise by zero-padded SUE, and treat suffixed variants
(`007_paus.pdf`, `092_A.docx`, `094_A.pdf`) as belonging to the same cave.
Confirm — and what do `_A` and `_paus` mean? (Is `_A` the *dopunski zapisnik*,
of which SB flags 17?)

**C2. Izjava filenames.** They look like `Izjava_ABahović.pdf`, sometimes with a
locality suffix (`Izjava_ACiceran_Šverda.pdf`). Proposed matching: first
initial + surname, diacritics folded, suffixes ignored. Anything else I should
expect? (There are also `!!!Fale_Brane.txt` / `!!!Traženje izjava.txt` notes in
that folder — are they authoritative lists I should read?)

**C3. Entrance photos.** 1521 files named `<SUE>_<ime>_…_<autor>.jpg`, plus a
subfolder `!!Fotografije ulaza za istražit`. Do subfolders count as part of the
archive, and is one photo per cave enough to satisfy §5.1?

**C4. Field-data intake dir layout on Drive** — still undecided, and it blocks
the 2.1a handoff (M5). What should the folder for a freshly surveyed cave look
like (`.csx`/`.tdx`, photos, voice-note text)?

### Quick check commands

```powershell
cavedossier sb columns                      # what the tool sees in the workbook
cavedossier report --cave "Konglomeratača"  # one cave, end to end
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

## Commands

```powershell
# M1 — read-only SB inspection
cavedossier sb columns                     # detected header row + all column names
cavedossier sb inspect --cave "Ponor X"    # dump a cave's row (name / SUE / plaque; substring OK)
cavedossier sb stats                       # sheets, row counts, fill counts of key columns

# M2 — per-cave dossier
cavedossier report --cave "Konglomeratača" # what is present / missing / blocking
cavedossier report --cave 570 --json       # same dossier as JSON (raw SB row omitted)
```

Console shows `?` instead of š/č/ž? `$env:PYTHONIOENCODING="utf-8"` (the CLI
also self-reconfigures its output streams, so this is rarely needed).

## Module map

| Path | What | Runs |
|---|---|---|
| `src/cave_dossier/cli.py` | `cavedossier` entry point (argparse), mode banner | every command |
| `src/cave_dossier/core/config.py` | config.yaml + .env → `Settings`; SANDBOX/LIVE resolution | every command |
| `src/cave_dossier/core/normalization.py` | diacritic-insensitive matching keys (ported) | column + name matching |
| `src/cave_dossier/core/people.py` | split a free-text author cell into people (ported+adapted) | SB mapping |
| `src/cave_dossier/sb/safe_io.py` | workbook preflight/backup/COM-write safety (ported) | reads: preflight only; writes: M6 |
| `src/cave_dossier/sb/loader.py` | `SBReader`: header autodetect, canonicalized columns, `find_caves` | `sb *`, `report` |
| `src/cave_dossier/dossier/model.py` | `CaveDossier` + `Source` provenance, files, issues, readiness | the shared object |
| `src/cave_dossier/dossier/sb_mapper.py` | SB row → dossier; parses the `za istražit` queue flag | `report` |
| `src/cave_dossier/dossier/gating.py` | Protokol v6 rules → blockers / warnings / unchecked | `report` |
| `src/cave_dossier/dossier/report.py` | the text rendering behind `cavedossier report` | `report` |
| `sessions/SESSIONS.md` | session journal (appended by `/wrap-up`) | — |
| `backlog/ideas.md` | dated idea capture | — |
| `example/` | **gitignored** — sandbox workbook + real cave data (PII, never committed) | — |
| `tests/` | pytest on tiny synthetic fixtures | `python -m pytest` |

Planned modules: `dossier/intake.py` (rest of M2 — resolve a cave's files on
Drive), `georef/` (M3 — isječak karte), `osz/` (M4 — OSZ builder).

## Testing

```powershell
python -m pytest
```

Fixtures are synthetic (fake caves, fake names) — `tests/fixtures/mini_sb.xlsx`
is regenerated by `python tests/fixtures/make_mini_sb.py` and deliberately
reproduces the live workbook's traps (metadata row above the header, header
spelling variants, a queue row with no SUE). Real-data checks run manually via
the CLI against the sandbox — see [STATUS.md](../../STATUS.md) for the current
checklist.
