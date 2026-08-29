# SB ↔ Liburnija — data structure and a communication hub

How the LIDAR-candidate Google Sheet and SB should talk to each other, and the
data structure that makes the same mechanism work for the other satellites.
Companion to [sb-satellite-tables.md](sb-satellite-tables.md), which establishes
the join rules; this doc adds the **candidate lifecycle**, the **crosswalk**, and
a **two-way** design. Every number below is measured — see
[§9](#9-measured-baseline-2026-08-29).

> The sheet is `1-YNyvG5p9pkiqss0au5IEKZfwkXzUUAylCcFDRPCFY8` —
> *Liburnija_pot_speleo_2024*, the same file people call the **LiDAR Kristal
> table**. One file, two names.

---

## 1. The constellation

SB is the master registry, but it is one of five tables that hold cave data, and
**none of the other four carries an SB row number**.

```text
                    ┌───────────────────────────────────────────┐
                    │  SB · Svi objekti  (SO_v2_1)   1312 rows  │   MASTER
                    │  Redni broj · Katastarski broj SUE        │
                    └───┬───────────┬───────────┬───────────┬───┘
        Broj pločice ───┘   HTRS ───┘  Kat.br RH ┘   HTRS ───┘
        + "LiDAR Kristal N"      (unused)                (unused)
            synonym
            ▲                    ▲             ▲             ▲
  ┌─────────┴────────┐  ┌────────┴───────┐ ┌───┴─────────┐ ┌─┴──────────────┐
  │ Liburnija        │  │ Literatura     │ │ Katastar RH │ │ future LIDAR   │
  │ Google Sheet     │  │ SB sheet, 45   │ │ SB sheet    │ │ campaigns      │
  │ 410 rows         │  │ own "Broj"     │ │ 4595 rows   │ │ (same shape)   │
  │ own "name"       │  │                │ │ own kat.br. │ │                │
  └──────────────────┘  └────────────────┘ └─────────────┘ └────────────────┘
        ▲ live, edited in the field          Kategorije (88) = vocabulary only
        │ people type into it during a trip
```

Liburnija is the only one that is **live and externally owned** — people enter
data there while in the field. That is what makes it a *communication* problem
rather than a one-off import: both sides keep changing, and neither may clobber
the other.

## 2. The Liburnija row, as a structure

18 columns, and they fall into three clean groups by **who is entitled to change
them**. That grouping is the whole design.

| Column | Group | Meaning |
|---|---|---|
| `name` | identity | LIDAR point number (396 rows) **or** a free-text name for field finds (14 rows, `vjerojatnost = "nije na Lidaru"`) |
| `x` `y` `z` | field-owned | HTRS coordinates + elevation. Present on all 410 rows |
| `vjerojatnost` | field-owned | LIDAR confidence: niska 277 / visoka 99 / srednja 20 / nije na Lidaru 14 |
| `provjereno (1/0)` | field-owned | **has anyone walked to the point** |
| `provjerio`, `datum provjere` | field-owned | who checked it, when |
| `speleo_obj (1/0)` | field-owned | **is it a cave at all** — the verdict of that visit |
| `istrazeno (1/0)` | shared → SB | explored yes/no |
| `Istražili` | shared → SB | which society (SUS · SUE · Karsterra) — the out-of-scope signal |
| `Naziv_novi`, `Naziv_stari` | shared → SB | the name it got |
| `Br.pl` | shared → SB | **Broj pločice — the join key** |
| `Komentar` | field-owned | free text |
| `Zapisnik`, `Nacrt`, `Foto ulaza` | SB-owned | TRUE/FALSE — the exact three deliverables gate 1 checks |

**A trap in the last three.** SB's `Link Nacrt` / `Link Zapisnik` record only
whether a **digital** copy is on file; every *Istraženi* object has both, analog
or digital (user, 2026-08-29). So an empty link cell is no evidence the document
is missing, and the sheet claiming one is not a disagreement. The katastarski
broj SUE is the real signal: hold one, and both documents exist by definition.
`Fotografija ulaza` is different — an explicit DA/NE claim, so it disagrees in
both directions and the sheet's own TRUE is worth acting on.

The last three columns are the interesting discovery: **the field sheet already
tries to track gate-1 deliverables**, by hand, and drifts. SB (plus the dossier)
knows the truth for all of them. That is the ready-made payload for the SB→sheet
direction.

## 3. The state SB does not model

A LIDAR table holds *probable* caves. Before "unexplored" there is a stage SB has
no room for: **not yet known to be a cave at all**. The sheet expresses it with
two flags, and their combination is a four-state machine:

```text
                       provjereno=0
                   ┌── neprovjeren ──┐            16 rows
                   │  nobody has     │            NEVER enters SB
                   │  walked there   │
                   └────────┬────────┘
                    someone walks there
                            │
              ┌─────────────┴─────────────┐
     speleo_obj=0                    speleo_obj=1
   ┌──────────────────┐        ┌────────────────────────┐
   │  nije objekt     │        │ potvrđen speleo objekt │   244 rows
   │  150 rows        │        │  ── THE CROSSING ──    │   entitled to an SB row
   │  NEVER enters SB │        └───────────┬────────────┘
   │  (but stays in   │            ┌───────┴────────┐
   │   the sheet as   │      istrazeno=0      istrazeno=1
   │   a negative     │            │                │
   │   result)        │            ▼                ▼
   └──────────────────┘     SB "Za istražit"   SB Nesređeni/Istraženi
                            128 rows           116 rows
```

**The crossing rule (user, 2026-08-29):** a row earns an SB row when
`provjereno=1 AND speleo_obj=1` — nothing earlier. No *Za provjeriti* sheet is
added to SB for now; the unverified stage stays in the satellite where it
belongs. (If SB ever wants that stage, it is one more Napomena flag and one more
Power Query view — the design below does not change.)

**Confirmed caves are added to SB in bulk, not on demand** (user, 2026-08-29),
carrying the naming convention of §5. What that batch looks like, exactly: §10.

Two consequences that the code must enforce, not merely document:

1. **`nije objekt` and `neprovjeren` rows are ineligible for matching.** They are
   not caves, so any key that links them to an SB cave is by definition a false
   positive. Measured: at a 30 m coordinate tolerance, 10 of 17 proposed new
   links were exactly this error — a rejected point 21–27 m from a real cave.
2. **A `nije objekt` row is a result, not an absence.** It must survive in the
   sheet and in the crosswalk with status `not_a_cave`, or the next run proposes
   it again. Same reasoning as the existing out-of-scope list.

## 4. The link is a crosswalk, not a merge

The hub owns **one** persistent structure, and it is not a copy of anyone's data:

```python
@dataclass(frozen=True)
class ObjectLink:
    source: str            # "liburnija" | "literatura" | "katastar_rh" | …
    local_id: str          # sheet `name` — PROVENANCE ONLY, never a join key
    serial_number: int|None    # SB Redni broj — the SB side of the link
    status: str            # linked | candidate | not_a_cave | out_of_scope |
                           # unresolved | conflict
    key: str|None          # plaque | kristal_synonym | coordinate | name | manual
    evidence: str          # "Br.pl 051-723" · "4.7 m, unique within 15 m"
    distance_m: float|None
    decided_on: date
    decided_by: str        # "auto" | "user"
    note: str|None
```

Why a crosswalk rather than importing the sheet into SB:

- **SB stays master and stays untouched.** No new columns (hard rule, see
  [sb-write-back-design.md](sb-write-back-design.md)), no imported rows nobody
  asked for.
- **Decisions persist.** `out_of_scope` (row 89, *Jama na Patuhovcu* — another
  society's cave) and `not_a_cave` (150 rows) are recorded once and never
  re-raised. This is habit 4 of [sb-satellite-tables.md](sb-satellite-tables.md),
  given a place to live.
- **It is auditable.** ~410 rows of YAML committed under
  `features/cave-dossier/crosswalk/liburnija.yaml` gives every link a git history:
  who decided, when, on what evidence. When a link later proves wrong, the diff
  says how it was made.
- **It generalises.** `Literatura` and `Katastar RH` get their own file and the
  same resolver; nothing about the structure is Liburnija-specific.

The crosswalk is the hub. Everything else is an adapter reading into it or a
report reading out of it.

> **Not built yet, deliberately.** Decision 2 turned *out of scope* into a rule
> (`Istražili` names another society) and the sheet's own flags settle
> `not_a_cave` / `unchecked`, so after increment 1 there was nothing left for a
> crosswalk file to remember: every status is derived on each run. The handful
> of cases a rule cannot reach are the `manual` and `out_of_scope` arguments of
> `resolve_rows`, fed from `config.yaml` like every other override in this tool.
> Promote to the file above the moment human decisions outgrow that — the types
> are already shaped for it.

## 5. Resolving a row: ranked keys, with measured strength

Applied in order; the first hit wins, later keys **corroborate rather than
override** (a disagreement is a `conflict`, not a silent choice).

| # | Key | Coverage (of 410) | Verdict |
|---|---|---|---|
| 0 | crosswalk hit | grows to 100 % | free, and the only key that survives a renamed row |
| 1 | **Broj pločice** | **68** | strongest; the key that cracked Liburnija |
| 2 | **`LiDAR Kristal N` synonym in SB** | 56 | **0 conflicts with plaque, 56 ⊂ 68** — perfect corroboration, no new coverage *today* |
| 3 | coordinate proximity | +3 credible | tight bands only, see below |
| 4 | name / synonym | +0 links, **1 stop** | never links — spellings drift and names get reused. But an exact match *blocks the add*: sheet 285 *Jama u Puharima* is SB 733 under the same name 5 m away, and pasting it would have duplicated a cave |
| — | local row id | — | **never** (5 of 5 resolved wrong in the 2026-08-29 measurement) |

### Key 2 is the one to institutionalise

Today it adds nothing — every `LiDAR Kristal N` row also has a plaque. Its value
is **forward**: it converts the sheet's local id from a forbidden key into a
legitimate one, because the number is written *into SB* as a synonym rather than
guessed from a folder name. Make it a rule at the crossing:

> Every SB row created from Liburnija row **N** carries `LiDAR Kristal N` — as
> `Ime objekta` if the cave has no real name yet (7 rows do this today), else in
> `Sinonimi` (48 rows do this today).

That single convention gives all 126 currently-missing rows a deterministic
identity from the moment they are created, and it costs one cell.

### Key 3 needs tight bands — the terrain is dense

The 68 plaque-linked pairs give an exact picture of what a *true* pair looks
like, and the sheet's own point spacing says how much room there is to be wrong:

```text
 true pairs (n=68):     median 0.9 m │ p90 2.6 m │ max 12.3 m
 sheet self-spacing:    min 1.4 m    │ p5  6.9 m │ p10 12.3 m
                        54 sheet points sit within 15 m of another sheet point
 SB rows in the window: 134, median spacing 142 m, min 4.2 m
```

The true-pair distribution and the neighbour distribution overlap. So:

| Distance | Second-nearest | Action |
|---|---|---|
| ≤ 5 m | > 15 m away | **auto-link** |
| ≤ 5 m | another within 15 m | propose, flag ambiguity |
| 5 – 15 m | — | **propose for review, never auto** |
| > 15 m | — | no link (past the observed true-pair maximum) |

Plus the eligibility filter from §3 — only `speleo_obj=1` rows are candidates at
all. Measured together on the 342 rows the hard keys miss: a naive 30 m scan
proposes **17** links; the eligibility filter kills 11 of them outright (10
rejected points sitting 21–27 m from a real cave, plus one nobody has checked
yet) and the 15 m ceiling kills 3 more, leaving **3 credible** — two auto-links at 0.0 m and 5.1 m, and one ambiguous
(*Špiljuljak*, 4.7 m, with *Jama kraj Špiljuljaka* 7.1 m away). A key that yields
three links and no nonsense is worth having; one that yields seventeen and mostly
nonsense is the local-id trap again.

Everything here is a **statement about this terrain**, not a universal constant.
`Literatura` and `Katastar RH` need their own calibration run before their
tolerances are trusted — the method is: link a subset on a hard key, measure the
resulting distance distribution, set the auto band inside it.

## 6. Two-way, without a fight: ownership per stage

Two-way sync is safe only when **no field has two owners at the same time**.
The crossing (§3) is the moment ownership transfers:

| Field | Before crossing | After crossing | Direction |
|---|---|---|---|
| `x` `y` `z`, `vjerojatnost` | sheet | sheet | sheet → SB once, at crossing |
| `provjereno`, `provjerio`, `datum provjere`, `speleo_obj` | sheet | sheet | never leaves the sheet |
| `Komentar` | sheet | sheet | read-only for us (feeds a new row's Napomena at crossing) |
| `Br.pl` | sheet | **SB** | sheet → SB at crossing, then SB → sheet |
| `Naziv_novi` | sheet | **SB** | **SB → sheet** |
| `istrazeno`, `Istražili` | sheet | **SB** (lifecycle) | **SB → sheet** |
| `Zapisnik`, `Nacrt`, `Foto ulaza` | — | **SB + dossier** | **SB → sheet** |
| ~~*(new)* `SUE`, `SB_redni_broj`~~ | — | — | **refused** (user, 2026-08-29) — the sheet keeps its 18 columns; see §7 |

No new columns (user, 2026-08-29). The sheet answers *"did cave 10 turn out to be
explored, and what name did it get"* through the columns it already has —
`istrazeno`, `Naziv_novi`, `Br.pl`, `Zapisnik`/`Nacrt`/`Foto ulaza` — and the
**link itself is never written into the sheet**. It lives only in the crosswalk
file in this repo, which makes that file the thing that must not be lost (§4).

**Names: SB is ground truth** (user, 2026-08-29). `Naziv_novi` is filled in after
the fact, so where it disagrees with SB it is the sheet that is wrong — both
divergences found (*PP Bjeloučka*, *Ivanina zvijezdica*) are sheet-side typos to
correct.

**Measured payload today** (`sat sync --coords`, LIVE, 2026-08-29): on the 70
linked rows, **24 cells** disagree — 15 × `Foto ulaza` false in the sheet but
present in SB, 2 × `Nacrt`/`Zapisnik` on caves that hold a SUE number, 5 name
gaps, and 1 lifecycle disagreement (row 272 → SB 1256: sheet says unexplored,
SB says *"fali nacrt i zapisnik, ponoviti"*). Plus **7 synonym additions** to
existing SB rows, and **1** thing to decide.

The name gaps are the interesting few. Only two are real divergences —
*PP Bjeloučka*/*Bijeloučka* and *Ivanina zvijezdica*/*zvjezdica*, both sheet-side
typos; the other three are rows where SB has a name and the sheet never recorded
one. The dozen rows where SB holds the `LiDAR Kristal N` placeholder produce
**no** difference at all, which is the point: writing that back would claim the
cave has been named when it has not.

## 7. Getting the answers back — plainly

### First: two destinations, two different mechanisms

They are constantly confused, so keep them apart:

| Destination | What it physically is | How anything gets written to it |
|---|---|---|
| **SB** | an `.xlsm` workbook sitting on the Google Drive Desktop mount — a real file, opened in real Excel | Excel COM / xlwings, backup first. Already designed: [sb-write-back-design.md](sb-write-back-design.md) |
| **Liburnija** | a *native* Google Sheet. There is no file on disk, Excel cannot open it, and people are typing into it in the field while the tool runs | **this section** |

### What the tool produces: four lists, and nothing else

No automatic writing anywhere. Each `sat sync` run ends in four reviewable
lists — exactly the *"here are the differences, these rows would be added"* step
you described:

| List | Direction | Contents today |
|---|---|---|
| **1 · Za SB** | sheet → SB | confirmed caves with no SB row, each rendered as a full SB row in **the workbook's own 24 columns, in its own order**, already named. **126 rows** |
| **2 · Dopune SB** | sheet → SB | the `LiDAR Kristal N` synonym to add to *existing* SB rows — an addition, never a replacement. **7 rows** |
| **3 · Za tablicu** | SB → sheet | cells the sheet has wrong, one line each: `red 43 · Foto ulaza · FALSE → TRUE (SB 1257 ima Fotografija ulaza)`. **24 cells** |
| **4 · Za odluku** | — | conflicts and ambiguities. Nothing is ever decided automatically. **1** |

Lists 2–4 need no tooling at all to act on: they are instructions a person
carries out by hand, one cell at a time. 24 cells is a coffee's worth of
clicking, and after the first pass each run produces a handful. That is the
answer to "manageable for people without the tools" — the *output* is the
product, not the automation.

**List 2 is the one that compounds.** Every synonym added there converts a link
that today rests on coordinates or a name into one that rests on a hard key, so
the next run resolves it for free and no longer has to guess.

### The jargon, unpacked

**TSV** — "tab-separated values". A plain text table where a Tab character
separates one column from the next. It matters for exactly one reason: when you
copy TSV text and paste it into Excel or Google Sheets, it lands **spread across
cells**. Paste comma-separated text instead and the whole line piles into a
single cell. So TSV is not a technology, it is just the format that makes
copy-paste work.

**Patch file** — list 1, written to a file instead of only printed, so that
adding 126 caves is *select → copy → paste below the last row of `Svi objekti`*
rather than typing 126 rows by hand. Its destination is **SB**, in Excel, on your
machine. A paste is an ordinary Excel action: it does not disturb macros,
validations or the Power Query views, which recompute on their own — unlike
letting Python save the workbook, which is what the safety doc forbids.

Two things make the difference between a block that pastes and one that does
not, both learned the hard way on the first generated file:

* **Every column, in the workbook's order.** The block carries all 24 columns of
  `Svi objekti` as the header row spells them, with empties where the sheet has
  nothing to offer. A tidy nine-column subset cannot be pasted into a table at
  all.
* **A BOM.** Windows Excel reads a UTF-8 file as the local codepage unless it
  finds one, which turns every č/š/ž into mojibake. The files are written
  `utf-8-sig`.

**Mirror tab** — a *tab* is one page inside a spreadsheet (the tabs along the
bottom edge). The idea was that the tool would own one tab in the Liburnija
spreadsheet, called something like `SB status`, fill it with SB's answers, and
the field table would display them through formulas — so the tool would never
touch a cell a human typed. **Your answer to question 3 rules it out**: showing
anything from that tab in the field table requires new columns in the field
table. Dropped; nothing is written into the spreadsheet by machine.

### What keeping the sheet as-is costs

Somebody looking only at the spreadsheet cannot tell which SB row a LIDAR point
became — that link exists only in the crosswalk file here. Acceptable for now,
and worth revisiting if field users start asking "is this one already in SB?".

Two cheap ways out, if that day comes:
- `Komentar` is an existing free-text column. `SB 1248` written into it
  materialises the link with no schema change — at the cost of a human field's
  tidiness.
- The `Naziv_novi` write-back already carries the answer implicitly: once the
  sheet says *LiDAR Kristal 43*, the cave is in SB by definition.

### Later, when the manual step gets annoying

Only two things would change, and neither is needed to start: writing list 1 into
SB automatically (the `safe_io` machinery already exists — it needs the rehearsal
protocol, not new code), and writing list 2 into the Google Sheet through the
Sheets API with a service account. The second one adds credentials and breaks the
"no Google API" rule, so it wants a real reason. The Drive MCP is **not** that
route: its `update_file` replaces a whole file and would silently discard
whatever someone typed in the field that morning.

## 8. Shape of the implementation

Built 2026-08-29 (steps 1–2 of the sequence below):

```text
cave_dossier/satellites/
  model.py       CandidateState · LinkStatus · Difference · NewRow · Decision · SyncResult
  liburnija.py   the full sheet reader: 18 columns, the four-state lifecycle
  resolver.py    SBRecord index · ranked keys · eligibility filter · coordinate bands
  sync.py        the three review lists + the paste-able TSV block
cave_dossier/intake/liburnija.py   the narrow number→plaque→SB slice, now over the
                                   same reader (one CSV parser, two callers)

sb-sync/<satellite>/<YYYY-MM-DD>/  where a run lands. Gitignored (real society
                                   data, and a run goes stale the moment either
                                   side moves); only its README is tracked
```

| Command | Does |
|---|---|
| `cavedossier sat sync [liburnija]` | **built** — resolves every sheet row against SB and prints the four lists. Read-only on both sides |
| `… --coords` | adds the coordinate key, auto-linking only under 5 m and unambiguous; everything else lands in list 3 |
| `… --out` | writes the lists into `sb-sync/<satellite>/<today>/` — `1-za-sb.tsv` (paste into `Svi objekti`), `2-dopune-sb.txt`, `3-za-tablicu.txt`, `4-za-odluku.txt`. `--out DIR` puts them elsewhere |
| `… --limit N` | rows printed per list |

Sequencing (each step useful on its own):

1. ✅ **resolver + `sat sync`** over the plaque and Kristal keys.
2. ✅ **the gap report** — list 1 surfaces the 126 rows SB is missing.
3. **Paste the block** into `Svi objekti`. The one-off that clears the backlog;
   no write code involved.
4. **List 2 by hand** in the browser. Two-way begins.
5. **Coordinate key** promoted from `--coords` to default, once a run has been
   eyeballed.
6. **Automated SB write** for subsequent (small) batches, on the M6 machinery —
   `safe_io`, backups, sandbox rehearsal. Nothing new to build, only to rehearse.
7. **Second satellite** (`Literatura`, 45 rows — the cheap one) to prove the
   protocol generalises before touching `Katastar RH`'s 4595.

Where this sits in the pipeline: the hub is part **2.2** (SB communication), and
it feeds 2.1 the same way SB does. `intake/` is a consumer of the same reader,
so folder `108_Renata` and the sync agree on what row 108 is by construction.

### Four things the live runs caught that the analysis had not

- **SB carried a blank pre-numbered row** (`Redni broj` 1313, no name).
  Numbering new caves from the highest *named* row would have handed out 1313
  twice. The user removed that row the same day — live is now a dense 1…1312 —
  but `next_serial_number` still spans every row, named or not: the guard costs
  nothing and the next blank row will not announce itself.
- **Scope must be checked after the keys, not before.** *Akupunktura* (sheet 381,
  `Istražili = "Karsterra, SUE"`) is already SB 823. Rejecting other societies'
  rows up front dropped that link and stopped syncing a row that exists. Scope
  decides whether a row may be **added**, never whether it may be **linked**.
- **A name too weak to link on is still strong enough to stop an add.** The first
  generated paste block contained sheet 285 *Jama u Puharima* — SB 733 under that
  exact name, 5 m away. The keys all missed it (no plaque, no number in SB) and
  it would have been pasted as a duplicate. An exact name match now yields a
  question, not a row.
- **`neistraženo` is a second way SB says "not explored".** Reading only the
  v3.0 queue flag made the tool propose *istraženo = 1* for SB 914 while quoting
  a note that begins "neistraženo" — a contradiction on the very line someone is
  meant to act on. The Nesređeni keyword now counts too.
- **A link column is not a document column.** `Link Zapisnik` says only whether a
  *digital* zapisnik is on file, and the tool was reading its absence as "SB has
  no zapisnik" — raising decisions about caves that certainly have one. Every
  Istraženi object has both documents; the SUE number is what says so.
- **An exact name inside the review radius is corroboration, not coincidence.**
  Sheet 285 was 5.1 m from SB 733 *Jama u Puharima* and carried that exact name.
  One tenth of a metre outside the auto band, it sat in the decision list twice
  over. Two signals that agree now link, and the run proposes the synonym that
  makes the link permanent.
- **A near miss needs somewhere to be settled.** *Špiljuljak* is 4.7 m from
  SB 1172 and is genuinely its own cave. Without a `confirmed_new` list in
  `config.yaml`, that proximity would be re-raised on every run forever.

## 9. Measured baseline (2026-08-29)

SB `!Speleo_baza_SUE_v3.0.xlsm` × cached CSV export (650 lines = 410 real rows
+ 240 blank). Re-measured against **LIVE** on 2026-08-29 after the blank row was
removed: 1312 rows, all named, `Redni broj` a dense 1…1312 with no gaps. Sandbox
and live agreed on every named row. Re-measure after either side changes.

| Quantity | Value |
|---|---|
| Sheet rows with data | 410 — 396 LIDAR points + 14 field finds (`nije na Lidaru`) |
| provjereno = 1 | 380 of 396 LIDAR points |
| Confirmed caves (`provjereno=1 ∧ speleo_obj=1`) | **244** |
| … explored / to explore | 116 / 128 |
| Rejected (`speleo_obj=0`) | 150 · unchecked 16 |
| Linked to SB today (plaque ∪ Kristal) | **68** |
| SB rows carrying `LiDAR Kristal N` | 56 — 7 as `Ime objekta`, 48+ as `Sinonimi`, 0 duplicate N |
| Plaque vs Kristal conflicts | **0** |
| **Confirmed caves with no SB row** | **176** — 48 `Istražili=SUS` + 1 Karsterra (out of scope), 2 SUE, 125 with no society recorded |
| `sat sync` candidates (out-of-scope + duplicates already removed) | **126** with `--coords` (the recommended run) |
| … of those, with no SB row within 50 m at all | **117** |
| … carrying no name at all | 124 → they enter SB as `LiDAR Kristal N` |
| Cells disagreeing on linked rows | 32 (see §6) |
| CRS | identical — no reprojection; 68 pairs median 0.9 m, max 12.3 m |

The headline is the gap. The earlier folder-driven pass found exactly one row to
add (*Jamorinke*) because it only looked at folders that already held data; a
sheet-driven pass looks at every confirmed cave, and the queue is two orders of
magnitude bigger. `sat sync`'s own figure — **126** — is the one to work from
(§10); the rows above it are the raw gap before scope, the coordinate bands and
the duplicate-name guard are applied.

## 10. Decided (user, 2026-08-29)

| # | Question | Answer | What it means in code |
|---|---|---|---|
| 1 | Do the confirmed unexplored caves belong in SB? | **Yes, add them**, named per the convention | one-off `sat sync --out` batch of 126; *Za istražit* grows 199 → 325 |
| 2 | Is `Istražili ≠ SUE` enough to keep a row out? | **Yes** — other societies' caves do not enter SB | automatic `out_of_scope`, no prompt; 48 SUS + 1 Karsterra |
| 3 | May the sheet gain `SUE` / `SB_redni_broj` columns? | **No, keep the sheet as it is** | mirror tab dropped; the link lives only in the crosswalk (§7) |
| 4 | Patch file or mirror tab? | patch file — but the real product is the **review list** | §7 rewritten around four lists |
| 5 | Can `Naziv_novi` outrank SB's name? | **No — SB is ground truth**; `Naziv_novi` is filled in afterwards | name disagreements are always sheet-side corrections |

### What decision 1 actually produces

`sat sync` against LIVE, 2026-08-29 — the authoritative count, since it applies
decision 2 (other societies removed) and the calibrated bands:

- **126 rows** with `--coords` (the recommended run), taking `Redni broj`
  **1313 – 1438**. *Špiljuljak* is among them — 4.7 m from SB 1172 and still its
  own cave, settled once in `config.yaml` rather than re-raised every run.
  *Jama u Puharima* is not: it links to SB 733 on name + distance, and list 2
  proposes the synonym that keeps it linked.
- **119 have no name at all** → they enter as `Ime objekta = "LiDAR Kristal N"`.
  Two carry a real name (*Jama iznad Andreti* 288, *Guštićeva jama* 338) → real
  name, with `LiDAR Kristal N` in `Sinonimi`.
- **Five have a text id, not a number** (the `nije na Lidaru` field finds —
  *Ljicašpi*, *Špilja kraj 15*, *Puhalica kraj 41*, *BSOL 1*, *pokraj jame 73*). The `LiDAR Kristal N` convention cannot reach them — they
  enter under their own sheet name. Worth a glance before the batch goes in;
  `sat sync` flags each one.
- **Eight have an SB row within 50 m** but beyond the 15 m band. Not links by
  the calibration, but the batch is the moment to eyeball them.
- Only one carries a plaque already; the rest get theirs when someone visits.
- Every row gets `Napomena` seeded with the queue flag `za istražit, <komentar>`
  so SB's own Power Query files it under *Za istražit* — which grows **199 → 325**.
- The earlier figures in this doc (*117*, then *127*) predate two guards the
  live runs added — the duplicate-name stop and the coordinate bands. **126** is
  the number to work from; the eight above are the difference worth looking at.

### Still open

- ~~Whether the explored-by-others rows should exist in SB as *sudjelovanje*~~ —
  **no** (user, 2026-08-29): SUS explored them years ago, separately. There was
  no participation, so they stay out of SB entirely. The one row where the sheet
  *does* name a joint trip (*Akupunktura*, `Karsterra, SUE`) is already in SB and
  keeps its link.
- Per-table coordinate tolerances for `Literatura` and `Katastar RH` (§5), to be
  calibrated when those are picked up.
