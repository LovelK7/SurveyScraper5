# Design decisions — the record of what was settled, and why

This file is the **decision record** for the cave-dossier feature: material
that was worked out once (mostly in the 2026-08-25/26 sessions with the user)
and is now built into the code. Read it to understand *why* the tool behaves
as it does — not to operate it. Operating instructions live in the
[README](../README.md); the module map for agents/developers is
[_INDEX.md](../_INDEX.md).

Nothing here is a live worklist. When a decision changes, update the section
and note the date; the session journal ([sessions/SESSIONS.md](../sessions/SESSIONS.md))
keeps the chronology.

## Contents

- [The idea in one paragraph](#the-idea-in-one-paragraph)
- [The workflow this encodes (two gates)](#the-workflow-this-encodes-two-gates)
  - [How the lifecycle states are decided](#how-the-lifecycle-states-are-decided)
- [Data flow](#data-flow)
- [What `cavedossier report` actually does](#what-cavedossier-report-actually-does)
- [Three-tier verdict](#three-tier-verdict)
- [The rule table](#the-rule-table)
  - [What §5.1 is](#what-51-is)
  - [Where the whole workbook stood (2026-08-26)](#where-the-whole-workbook-stood-2026-08-26)
- [Q&A record (2026-08-26)](#qa-record-2026-08-26)
- [Identity: which number names a cave](#identity-which-number-names-a-cave)
- [Workbook-wide audits — design](#workbook-wide-audits--design)
  - [Cross-check against SB's Fotografija ulaza](#cross-check-against-sbs-fotografija-ulaza)
  - [The staleness guard](#the-staleness-guard)
- [Izjava za katastar — filename scheme](#izjava-za-katastar--filename-scheme)
- [People registry and the statement gates (2026-08-30)](#people-registry-and-the-statement-gates-2026-08-30)
- [Field-data intake — matching design](#field-data-intake--matching-design)
  - [The third source: the Liburnija LIDAR sheet](#the-third-source-the-liburnija-lidar-sheet)
- [2.1b prefill rules (2026-08-30)](#21b-prefill-rules-2026-08-30)
- [OSZ fetch → SB backfill rules (2026-08-30)](#osz-fetch--sb-backfill-rules-2026-08-30)

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

## The workflow this encodes (two gates)

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

### How the lifecycle states are decided

Not by guesswork: the definitions are lifted from SB's **own Power Query**
(`Formulas/Section1.m` inside the workbook), so the tool and the Excel views
cannot drift apart.

| State | SB view | Filter | In the view | Assigned by the tool |
|---|---|---|---|---|
| **Istraženi** | `IO_v2_1` | `Katastarski broj SUE` is not empty — that is the entire filter | 885 | 885 |
| **Za istražit** | `ZI_v2_1` | Napomena contains `za istražit` | 199 | 199 |
| **Nesređeni** | `NO_v2_1` | Napomena contains `neistraženo`, `fali nacrt`, `fali zapisnik`, `<5 m`, `puhalica`, `ponor`, `ponoviti`, `nastaviti` or `umjetan objekt` | 221 | 179 |
| **Sudjelovanje** | `S_v2_1` | Napomena contains `sudjelovanje` — another society's cave that SUE took part in | 77 | 28 |
| **Nesvrstano** | *(none)* | no SUE number and no flag of any kind | — | 19 |

Live workbook, 2026-08-28; 1310 named rows. The two count columns differ
because **SB's views overlap and the tool's states do not**: a row shows up in
every view whose filter it matches, while the dossier assigns exactly one state
by precedence — SUE number → queue flag → outstanding work → provenance. So the
42 Nesređeni rows the tool "loses" are 29 that already hold a SUE number and 13
that are really still *za istražit*; the 49 sudjelovanje rows are ones where
outstanding work or a SUE number outranks the provenance note.

Nesređeni deliberately outranks sudjelovanje — a cave we only took part in that
still says "fali nacrt" belongs on the worklist. The dossier keeps the Nesređeni
keywords that hit even when another state wins.

The **Sudjelovanje** view was added to the workbook by the user on 2026-08-28
(`S_v2_1`, `Text.Contains([Napomena], "sudjelovanje")`) — the same keyword this
tool matches on, verified against the live file, so the two agree row for row.
Recognising the state is what shrank the unclassified list from 47 rows to 19.

The filters themselves, an M snippet to re-extract them from the workbook, and
the applied *exclude za-istražit from Nesređeni* edit are in
[sb-powerquery.md](sb-powerquery.md).

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
   isječak karte        ·······························  georef      (M3 ✅)
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

## What `cavedossier report` actually does

Using `report --cave 570` as the example:

1. [core/config.py](../src/cave_dossier/core/config.py) reads `config.yaml` +
   `.env` into a `Settings` object and resolves the workbook — LIVE by default,
   FALLBACK onto the local copy on conflict, SANDBOX when forced. The banner you
   see first is printed from this.
2. [sb/loader.py](../src/cave_dossier/sb/loader.py) opens the workbook read-only
   (openpyxl), finds the header row by scoring rows against the configured
   column names, and returns the matching row as a `CaveRow` — the raw cells
   plus its **Excel row number** (the handle M6 will write back through).
3. [dossier/sb_mapper.py](../src/cave_dossier/dossier/sb_mapper.py) turns those raw
   cells into typed dossier fields: numbers parsed, `Sinonimi` split, `Autori
   nacrta` split into people (society bracket peeled off as a flag), the
   `za istražit` marker parsed out of Napomena, and the **lifecycle state**
   derived. It then marks `Source.SB` as gathered.
4. [dossier/gating.py](../src/cave_dossier/dossier/gating.py) runs the rule table.
   Each rule declares which source feeds it **and which gate it belongs to**;
   rules whose source is missing are set aside as *unchecked* instead of run.
5. [dossier/report.py](../src/cave_dossier/dossier/report.py) prints identity →
   SB status → data → **both gate verdicts**. `--json` prints the dossier object
   instead (raw SB row omitted), which is what later stages will consume.

Nothing in this path can modify the workbook: reads go through openpyxl, and the
only write path in the package ([sb/safe_io.py](../src/cave_dossier/sb/safe_io.py),
xlwings/Excel-COM with backups) is dormant until M6. See
[sb-write-back-design.md](sb-write-back-design.md).

## Three-tier verdict

| Tier | Meaning | Effect on a gate |
|---|---|---|
| **BLOCKER** | A mandatory thing is genuinely missing or invalid | blocks |
| **warning** | Worth your attention, you decide | does not block |
| **not checked yet** | The rule's source has not been gathered — the tool has not looked | blocks *if* that rule could block |

A gate passes only when it has no blockers **and** nothing blocking is left
unchecked.

## The rule table

Every rule lives in [dossier/gating.py](../src/cave_dossier/dossier/gating.py).
**Gate 2 includes every gate-1 rule**; the last column lists only what it adds.

| Source | Gate 1 — katastarski broj | Gate 2 adds |
|---|---|---|
| **SB** (working) | Ime objekta · Lokalitet · Najbliže mjesto · Razdoblje istraživanja · Autori nacrta · Dubina | Interni katastarski broj (SUE) |
| **SB** (working) | Koordinate ulaza · Broj pločice — blockers if the exploration year is ≥ 2015, warnings otherwise (§5.1); kaverne exempt from the pločica rule (§5) | |
| **ARCHIVE** (next) | Nacrt PDF · Zapisnik (OSZ DOCX) · Fotografija ulaza (§5.1) | |
| **STATEMENTS** (✅ 2026-08-30) | Izjava za katastar **per author** (drawing + photo, registry- and scope-aware) | *warnings*: a named person (recorder, team member) with no izjava on file · a person missing from the registry |
| **SURVEY** (M5) | Horizontalna duljina | Vertikalna razlika (falls back to Dubina) |
| **OSZ** (M4) | Podrijetlo imena · Položaj i pristup · Vrsta objekta · Hidrogeološka funkcija · Hidrološka karakteristika · Osnovni opis s tehničkim podacima · Perspektiva daljnjeg istraživanja · Zapisničar · Članovi ekipe · Širina ulaza · Visina/duljina ulaza | Izvor koordinata · Istražile udruge |
| **MAP** (M3 ✅) | — | Isječak karte · Georef zapis |
| **PHOTOS** (2.1d) | *warnings only*: photos over the size budget, or not renamed to `<SUE>_…` | |

Warnings that never block either gate: the SB `Fotografija ulaza` flag
disagreeing with the archive, an author flagged as drawing for another society,
a malformed `Razdoblje istraživanja`, and the queue-state note.

### What §5.1 is

**Protokol v6** is the Ministry's rulebook for the national cave cadastre
(`docs/protocol_katastar_speleoloskih_objekata_RH_v6.md` in
crospeleo-automation). Two of its sections drive rules here:

- **§6.1, Tablica 2** — the mandatory-field matrix. Fields marked `*` are
  mandatory, `**` advisory. Most gate-2 rules come from that table.
- **§5.1** — the *year-conditional* rule: GPS coordinates, an entrance
  photograph and the entrance pločica are mandatory **only if the exploration
  started in 2015 or later**. Older caves are exempt. That is exactly the
  exception the user described — a pre-2015 cave without a pločica can still get
  a katastarski broj — so the tool drops those three checks to warnings when the
  exploration year is earlier or unreadable. §5 adds one more exemption:
  caverns (`kaverna`) never need a pločica.

The year is read from `Godina ili period istraživanja`, falling back to `Godina
zadnjeg istraživanja`, and the **earliest** 4-digit year in the cell decides (so
`2018-2019` → 2018).

### Where the whole workbook stood (2026-08-26)

The gate-1 rules run over all 1294 named rows. SB was the only gathered source,
so this measured SB data quality alone:

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

## Q&A record (2026-08-26)

The user's answers from the M2 kickoff, recorded so no session — human or agent
— has to re-ask. Each is built into the code as described.

| # | Answer | What the code does with it |
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
| C4 / 1 | Before a SUE number exists the cave's ID is its **Redni broj** | `dossier.serial_number` + `working_id`; the staged-photo matcher proposes `SB_<Redni broj>_…` |
| 2 | Photo budget: cut 7 MB down to 1–2 MB, "resize to screen size" (FastStone) | Gate warns above **2 MB**; the processing targets (1920 px long edge, 1.5 MB) are in `config.yaml` under `photos:` |
| 4 | The column is now **`Autori nacrta ili izvor`** — for queued caves it holds the finder/source, not a survey author | Config renamed, with `sb.column_aliases` so the old spelling still reads; the gating label follows; `sb audit-authors` flags citation-shaped values |
| 5 | List the unclassified rows | `cavedossier sb unclassified` |
| 6 | Staged photos keep free names but gain an SB_<Redni broj> prefix; needs a name-matching exercise | `cavedossier photos match-queued` |
| — | **2.1d entrance-photo processing** is a missing pipeline part | Added to [ARCHITECTURE.md](../../../ARCHITECTURE.md) as part 2.1d, plus `Source.PHOTOS`, a gate-1 warning for oversized / unrenamed photos, and the `photos/` module |

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
> does that mapping. Redni-broj prefixes carry an `SB_` marker (`SB_1234_…`,
> user 2026-08-30) so the number never reads as a katastarski broj; SUE
> prefixes stay bare.

## Workbook-wide audits — design

Some problems are only visible as a column-wide sweep, and are only fixable in
Excel — so `sb audit-authors`, `sb unclassified` and `photos match-queued` are
read-only worklists (commands in the [README](../README.md#commands)).

`sb audit-authors` (first run, 2026-08-26) reported **483 rows** across six
flags: `single_name` 172 (a bare first name like "Renata"), `society` 108,
`placeholder` 96 (a "/" meaning nobody), `conjunction` 93 (split on "i" —
verify the halves are two people), `empty` 49, `citation` 2 (a literature
source such as `Malez, M. (1960)`, not a survey author).

`photos match-queued` matches the free-form files in the staging folder against
SB and proposes `SB_<Redni broj>_<rest>`, replacing a stale old-number prefix
where there is one (**52 of 52 matched**, 2026-08-28). Evidence, weighed rather
than ranked — two independent signals agreeing is the strongest result:

| Evidence | Example | Note |
|---|---|---|
| plaque number | `051-550_…`, `… 051 418 …` | strongest single signal |
| cave name or **synonym** | `Poljička Kosa_…`, `Goli breg 4` → *Sik Šits* | longest match wins; an exact whole-stem match is accepted at any length, which is what resolves `ak 47.jpg` → *AK-47* |
| old Za-istražit broj | `478_…`, `479 (1)` | the number the file already carries — stale since the v3.0 renumbering, so it is *replaced*, not kept |
| manual mapping | `Jama GB 1` → 812 | `photos.manual_matches` in config.yaml, for abbreviations no rule can reach |

The proposed name is **`SB_<Redni broj>_<Ime objekta>_<sve ostalo>`** — the
number alone is unreadable in a folder listing, and most of these filenames
already carry an author or a description worth keeping after it. The cave name
is only inserted when the filename does not already contain it, illegal
filename characters in a name are replaced, and the longest resulting path is
224 chars (Windows allows 260).

Two signals that disagree are reported as a **conflict** and propose nothing.
`--apply` performs the renames (dry run is the default); it never touches
conflicts, unmatched files or already-correct names, and never overwrites an
existing target.

### Cross-check against SB's Fotografija ulaza

The photo folder is ground truth; the SB cell is a human-maintained claim about
it. `photos check-flag` reports every cave that has a staged photo but is not
flagged `DA` — the list to fix in Excel. It also prints any non-photo file in
the folder (a stray `.mp4`, say) rather than skipping it silently: quietly
ignoring unknown extensions is exactly how four `.jfif` entrance photos went
uncounted until 2026-08-28.

### The staleness guard

Promoting a queued cave's photos into `!!Fotografije ulaza` under its new SUE
number is a manual step, and it gets forgotten — especially when newer photos
arrive and nobody goes back for the old ones. The result is photos of long-since
explored caves sitting in the staging queue forever.

So every run checks it: a staged photo whose cave **already has a SUE number**
is flagged *PROMOTE or DELETE*, shown with the name it would carry in the main
archive (`<padded SUE>_…`), and deliberately excluded from the Redni-broj
rename — stamping the pre-SUE id on it would only bury the problem. `--apply`
never touches those files; promoting or deleting is the operator's call.

As of 2026-08-28 the folder is clean: **0 of 52** staged photos belong to an
explored cave. The check is a standing guard, not a cleanup.

## Izjava za katastar — filename scheme

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
name and synonyms — diacritic-insensitively. Since 2026-08-30 this IS a gate-1
rule: the statements dir is shared (not per-cave), so it gets its own gathering
step (`Source.STATEMENTS`) and does not wait for archive intake — see the next
section.

## People registry and the statement gates (2026-08-30)

**The registry.** `data/people/registry.json` — one committed, hand-curated
JSON, loaded by [people/registry.py](../src/cave_dossier/people/registry.py).
One entry per person; `name` in full `First Last` form derives its
abbreviation aliases automatically at load time (`L.Kukuljan`, `LKukuljan`,
`Lovel K.` …), so the file mostly holds bare names. The design is the
crospeleo-automation port (docs/PORTING.md): derived aliases with **collision
detection** (a key two people claim resolves nobody — never guess), curated
`aliases` entries that win over derived keys (crospeleo's `S.M.` case; ours:
`S.Antolič` likely belongs on `SKapidžić-Antolič`), no global surname-only
keys, exact-key resolution only (no fuzzy). Entries seeded from the izjava
files are still in token form (`ABahović`); they match the izjava and SB's
`A.Bahović` shorthand but not an OSZ's full spelling — **upgrade them to full
names as they are learned**. Committing real names follows existing repo
practice (config.yaml manual matches, test fixtures) — crospeleo's *scraped*
mirror is gitignored PII, but its *curated* registry files are committed, and
this file is all curation.

**Linking people to statements.** The izjava's person token, SB's shorthand
and the OSZ's full name all normalize into the registry's key space, so
`Izjava_LKukuljan.pdf` ↔ `L.Kukuljan` ↔ `Lovel Kukuljan` are one person. The
per-run linkage snapshot (person → izjave, orphans) lands as JSON in
`runs/people/statements-index.json` (`cavedossier people check`); the registry
stays the only curated record.

**Author vs finder — the single criterion (user, 2026-08-30).** SB's `Autori
nacrta ili izvor` cell mixes two groups: **survey authors**, who need an
izjava, and **cave finders/sources**, who do not. The distinguishing rule is
the spelling alone: authors are consistently written **`N.Surname`**
(initial·dot·surname — `L.Kukuljan`, `S.Kapidžić-Antolič`), finders every
other way (bare first names, full names, phrases). Encoded as
`core/people.is_author_shorthand`; only names it accepts enter the statement
gates and the `people check` SB sweep — finders get no entry, no blocker, no
warning, and are deliberately not scraped into the registry. Measured effect
on the first live run: the unresolved-SB-authors list dropped from 125 noisy
names to **28 real authors**. (The rule applies to that SB cell only —
recorder/team names come from the OSZ, where everyone listed took part.)

**The two statement gates.**

| Gate | Severity | Rule |
|---|---|---|
| 1 (SUE) | BLOCKER | Every **author** (drawing + photo, separately — the SUE 575 lesson) needs an izjava **whose scope covers this cave**. "Has an izjava, but it is scoped to another locality" is its own blocker message. |
| 2 (CroSpeleo) | warning | Every **person** the dossier names (recorder, team members too) with no izjava on file at all; and every person the registry cannot resolve (aliases unassessable). Advisory by design — only authors are hard-gated — and a person already blocked at gate 1 is not repeated. |

The gate-2 per-person warning is the user's request of 2026-08-30 ("warn if
the person is missing a statement"); it sits at gate 2 because that is where
the full CroSpeleo submission types these people in. `cavedossier people
check` is the same check registry-wide, off any one cave: people without an
izjava, izjave without a person, and every SB author cell swept through the
registry.

## Field-data intake — matching design

`!!!Digitalizacija/!Za digitalizirat` holds the raw material per cave. Its
**leaf** folders (any depth — the tree runs 1–3 levels) each get a **Redni
broj** prefix: `SB_<Redni broj>_<Ime objekta>_<original name>`. Nothing is ever
stripped, because the original name carries the collector and the local id.

**Numbers in these folder names are a suggestion, never evidence.** They are old
*Za istražit* numbers (user, 2026-08-29), and SB keeps those in Napomena as
`za istražit, NNN, …` — so `old_queue_candidates` looks them up there and prints
what it finds. But the numbering collides across campaigns: of 20 folder numbers
checked against the live workbook, 5 resolved and every one pointed at a Šverda
cave while the folder sat in a Veprinac LIDAR group. So a number never drives a
rename on its own; a folder carrying nothing else stays unresolved.

Matching therefore leans on names, in four passes (see `core/matching.py`):
exact stem → SB name inside the folder name → folder name inside the SB name
(unique hits only) → same words in any order (`Grotta possibile` → *Possibile
Grotta*). Two config hooks close the rest: `intake.manual_matches` (fragment →
Redni broj, for spelling variants like *Bilova* → *Billova ponikva*) and
`intake.new_entries`, which marks a folder as a cave SB does not have yet —
needed because a new cave often resembles an existing name (`Božur_Frustuck` is
**not** *Božur* 1087).

### The third source: the Liburnija LIDAR sheet

The Veprinac folders are named after row numbers in a Google Sheet,
*Liburnija_pot_speleo_2024* — 396 LIDAR candidates with coordinates, whether
someone checked the point, and for the ones that turned out to be caves, a name
and a **plaque number**. That plaque is the bridge: `108_Renata` → sheet row 108
→ pločica 051-723 → SB *LiDAR Kristal 108* (Redni broj 1248). It resolved 14 of
the 15 numbered Veprinac folders.

Two guards keep it from over-reaching. A number only counts when it stands on
its own — at a separator or after a lone LIDAR marker letter (`lisina L366`) —
and two digits minimum, because `Mune_Nat4_Natalija` otherwise offers the "4"
inside "Nat4" and matches sheet row 4 (*Integral*, somewhere else entirely; a
false positive caught on the first live run). And the row must carry a plaque
that exists in SB, so numbers from other schemes simply fail to resolve.

The sheet is cached as CSV under `example/` (gitignored) and read read-only:
`intake/liburnija.py`. Wiring it in as a real source — people do enter data
there — is a later architecture decision.

**An unresolved folder means a new cave.** Confirmed by the user: the caves in
these folders were mostly never entered into SB. So the tool reports them as
"no SB row — create one, then re-run", not as a matching failure. **End state
(2026-08-29): 53 leaves = 34 mapped + 19 new entries, nothing unresolved.**

Three findings the mapping surfaced, all settled: two folders held the same
cave twice (`43_Jasna` / `Jasnina jam lidar 43`, `366_Nina` / `lisina L366` —
duplicates deleted, the Venio copies kept); five leaves are empty placeholders;
and sheet row 89 (*Jama na Patuhovcu*) stays out of SB deliberately — another
society explored it.

## 2.1b prefill rules (2026-08-30)

Settled with the user during the prefill build; enforced in `osz/prefill.py`:

- **SB wins.** A computed value (locality finder, DMV elevation) only fills an
  EMPTY cell; a disagreement (kota beyond the 10 m tolerance, an unrecognised
  Najbliže mjesto) is a printed warning, never an override.
- **Never prefilled:** Katastarski broj (the archivist's manual final step),
  Duljina / Dubina (come from the survey process, not SB), Datum istraživanja
  (SB only holds a year; the real date comes from field data).
- **LiDAR flag:** a cave whose name or synonym carries "lidar" (Lidarka, the
  `LiDAR Kristal N` Liburnija convention) had its coordinates and Z produced by
  the LiDAR analysis → `Izvor koordinata` and `Izvor kote ulaza` are prefilled
  as **"LiDAR"**, known in advance — even when the DMV grid disagrees (the
  warning then stays advisory). Any other cave with coordinates gets
  `Izvor koordinata = "GPS"`, the most common source.
- **SB write-back stays human:** `dopune-sb.csv` lists the empty SB cells a
  finder could fill (`Z`, `Najbliže mjesto`, `Lokalitet`); a person pastes them
  into Excel. Nothing writes to SB automatically.
- **The delivery dirs are hand-managed** — people delete PNGs, edit the CSV in
  Excel (which strips zero-padding), drop wrong files. Every staleness check
  lives in the tool (`georef/worker.refresh_reason`): wrong excerpt aspect
  (format migrations), missing CSV rows, unreadable PNGs all auto-refresh on
  the next run; nothing requires a manual cleanup ritual.

## OSZ fetch → SB backfill rules (2026-08-30)

The fetcher direction (`cavedossier osz fetch`), settled with the user the
same day the prefill shipped; enforced in `osz/reader.py` + `osz/backfill.py`:

- **Scope**: only the SB-relevant cells — Broj pločice, Ime objekta/Sinonimi,
  Duljina, Dubina, Datum → Godina/period, Crtali → Autori nacrta. The
  CroSpeleo material (checkbox groups, narrative controls, the Google-Docs
  text variant) is a later stage.
- **Fill-missing, note-conflicts**: an empty SB cell gets a proposal; a
  non-empty cell that disagrees with the OSZ is printed as a difference and
  SB is kept — the operator decides.
- **Name change**: when the OSZ carries a different Ime objekta, the field
  name is the new authoritative one — it replaces SB's, and the old SB name
  (typically a working `LiDAR Kristal N`) moves into Sinonimi, merged with
  any OSZ synonyms; the new name never appears in Sinonimi.
- **Godina convention**: the OSZ's free-form Datum is cropped to SB's style —
  the single year (`"10.05.2025." → 2025`) or `min-max` when several years
  appear (`"12.10.2025. i 3.5.2026." → 2025-2026`).
- **Author conventions**: the OSZ writes full names, SB writes
  initial·dot·surname (`Lovel Kukuljan` ↔ `L.Kukuljan`).
  `core/person_aliases.py` (ported from crospeleo's alias generator) matches
  across the two spellings so an author already in SB is never duplicated;
  new authors are **merged, never dropped** — for queued caves the SB cell
  holds the finder/source, and a later survey legitimately adds people.
- **A control still showing its placeholder reads as EMPTY** (`w:showingPlcHdr`,
  or a literal `⟨…⟩` in the Docs variant) — the grey hint text is not a value.
- **Where the zapisnik lives** (user, 2026-08-30): a cave's filled OSZ is
  filed with its field material — the `SB_<Redni broj>_…` dir in the intake
  tree (`!Za digitalizirat`). `osz fetch` searches there by default
  (preferring a DOCX whose name says osz/zapisnik, refusing to guess among
  several), `--osz-dir` overrides the search root, `--osz` names an exact
  file; the prefilled copy in `osz_prefill_dir` is only a flagged fallback.
- **No writes**: the output is `dopune-sb-iz-osz.csv` under `runs/osz/<broj>/`,
  carried into Excel by hand. Exit 1 = something to carry over.
- **Validated** against `osz-template/mockups/v10.2_primjer_811.docx` vs SB 764
  (all 7 fields confirmed identical across conventions) and a simulated
  completed zapisnik for queued SB 1320 (6 proposals incl. the name→synonym
  move; year conflict correctly surfaced, not overridden).
