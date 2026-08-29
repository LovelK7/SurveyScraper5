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
                    │  SB · Svi objekti  (SO_v2_1)   1313 rows  │   MASTER
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

## 5. Resolving a row: ranked keys, with measured strength

Applied in order; the first hit wins, later keys **corroborate rather than
override** (a disagreement is a `conflict`, not a silent choice).

| # | Key | Coverage (of 410) | Verdict |
|---|---|---|---|
| 0 | crosswalk hit | grows to 100 % | free, and the only key that survives a renamed row |
| 1 | **Broj pločice** | **68** | strongest; the key that cracked Liburnija |
| 2 | **`LiDAR Kristal N` synonym in SB** | 56 | **0 conflicts with plaque, 56 ⊂ 68** — perfect corroboration, no new coverage *today* |
| 3 | coordinate proximity | +3 credible | tight bands only, see below |
| 4 | name / synonym | +0 new | the 3 name hits are the same 3 the coordinates find; 124 of the unlinked rows have no name at all |
| — | local row id | — | **never** (5 of 5 resolved wrong in the 2026-08-29 measurement) |

### Key 2 is the one to institutionalise

Today it adds nothing — every `LiDAR Kristal N` row also has a plaque. Its value
is **forward**: it converts the sheet's local id from a forbidden key into a
legitimate one, because the number is written *into SB* as a synonym rather than
guessed from a folder name. Make it a rule at the crossing:

> Every SB row created from Liburnija row **N** carries `LiDAR Kristal N` — as
> `Ime objekta` if the cave has no real name yet (7 rows do this today), else in
> `Sinonimi` (48 rows do this today).

That single convention gives all 117 currently-missing rows a deterministic
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

**Measured payload today**, on the 68 linked rows: 32 cells disagree —
15 × `Foto ulaza` false in the sheet but present in SB, 4 × the other two
deliverable flags, 12 name gaps (of which only 2 are real divergences —
*PP Bjeloučka*/*Bijeloučka*, *Ivanina zvijezdica*/*zvjezdica*; the other 10 are
SB holding the `LiDAR Kristal N` placeholder, which must **not** be written back
as a name), and 1 lifecycle disagreement (row 272 → SB 1256 *Paralelka*: sheet
says unexplored, SB says *"fali nacrt i zapisnik, ponoviti"*).

## 7. Getting the answers back — plainly

### First: two destinations, two different mechanisms

They are constantly confused, so keep them apart:

| Destination | What it physically is | How anything gets written to it |
|---|---|---|
| **SB** | an `.xlsm` workbook sitting on the Google Drive Desktop mount — a real file, opened in real Excel | Excel COM / xlwings, backup first. Already designed: [sb-write-back-design.md](sb-write-back-design.md) |
| **Liburnija** | a *native* Google Sheet. There is no file on disk, Excel cannot open it, and people are typing into it in the field while the tool runs | **this section** |

### What the tool produces: three lists, and nothing else

No automatic writing anywhere. Each `sat sync` run ends in three reviewable
lists — exactly the *"here are the differences, these rows would be added"* step
you described:

| List | Direction | Contents today |
|---|---|---|
| **1 · Za SB** | sheet → SB | confirmed caves with no SB row, each rendered as a complete SB row in SB's column order, already named. **117 rows** |
| **2 · Za tablicu** | SB → sheet | cells the sheet has wrong, one line each: `red 43 · Foto ulaza · FALSE → TRUE (SB 1247 ima fotografiju ulaza)`. **32 cells** |
| **3 · Za odluku** | — | conflicts and ambiguities. Nothing is ever decided automatically |

Lists 2 and 3 need no tooling at all to act on: they are instructions a person
carries out in the browser, one cell at a time. 32 cells is a coffee's worth of
clicking, and after the first pass each run produces a handful. That is the
answer to "manageable for people without the tools" — the *output* is the
product, not the automation.

### The jargon, unpacked

**TSV** — "tab-separated values". A plain text table where a Tab character
separates one column from the next. It matters for exactly one reason: when you
copy TSV text and paste it into Excel or Google Sheets, it lands **spread across
cells**. Paste comma-separated text instead and the whole line piles into a
single cell. So TSV is not a technology, it is just the format that makes
copy-paste work.

**Patch file** — list 1, written to a file instead of only printed, so that
adding 117 caves is *select → copy → paste below the last row of `Svi objekti`*
rather than typing 117 rows by hand. Its destination is **SB**, in Excel, on your
machine. A paste is an ordinary Excel action: it does not disturb macros,
validations or the Power Query views, which recompute on their own — unlike
letting Python save the workbook, which is what the safety doc forbids.

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

```text
cave_dossier/
  satellites/                 ← new; the hub
    __init__.py
    model.py                  ObjectLink, LinkStatus, SatelliteRow protocol
    crosswalk.py              load / save / merge the committed YAML, diff runs
    resolver.py               ranked keys §5 + eligibility filter + bands
    liburnija.py              ← moves here from intake/, gains the state machine
    (literatura.py, katastar_rh.py — same protocol, later)
  intake/liburnija.py         ← becomes a thin re-export; intake keeps using it
crosswalk/
  liburnija.yaml              committed; ~410 entries, one per sheet row
```

CLI, matching the existing verb style (dry-run by default, `--apply` to act):

| Command | Does |
|---|---|
| `cavedossier sat sync liburnija` | resolve every sheet row, update the crosswalk, print the diff: new links, new conflicts, newly confirmed candidates |
| `cavedossier sat gaps liburnija` | the two-way gap report — confirmed caves with no SB row (with the proposed `Ime objekta`/synonym), and SB rows the sheet could enrich |
| `cavedossier sat push liburnija` | list 2 — the 32 cells the sheet has wrong, as `red N · stupac · staro → novo (razlog)`, for a human to correct in the browser |
| `cavedossier sat add liburnija [<N>]` | list 1 — the SB rows to create, in SB column order with `LiDAR Kristal N` in the right cell. `--tsv` writes the paste-able block for all 117; a bare `<N>` scaffolds one |

Sequencing (each step useful on its own):

1. **crosswalk + resolver + `sat sync`** over the existing plaque and Kristal
   keys. Materialises the 68 links; costs nothing new.
2. **`sat gaps`** — the report that surfaces the 117 missing rows. Read-only, and
   the highest-value single output here.
3. **`sat add --tsv`** — the 117 rows as a paste-able block for `Svi objekti`.
   The one-off that clears the backlog; pasted by hand into Excel, no write code.
4. **`sat push`** — list 2. Two-way begins; 32 cells of drift get corrected in
   the browser by hand.
5. **Coordinate key**, with the §5 bands, behind a flag until it has been run
   once and eyeballed.
6. **Automated SB write** for subsequent (small) batches, on the M6 machinery —
   `safe_io`, backups, sandbox rehearsal. Nothing new to build, only to rehearse.
7. **Second satellite** (`Literatura`, 45 rows — the cheap one) to prove the
   protocol generalises before touching `Katastar RH`'s 4595.

Where this sits in the pipeline: the hub is part **2.2** (SB communication), and
it feeds 2.1 the same way SB does. `intake/` becomes a *consumer* of the
crosswalk instead of carrying its own bridge — folder `108_Renata` resolves via
a recorded link rather than by re-deriving the chain every run.

## 9. Measured baseline (2026-08-29)

Sandbox SB `!Speleo_baza_SUE_v3.0.xlsm` (1313 rows) × cached CSV export
(650 lines = 410 real rows + 240 blank). Re-measure after either side changes.

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
| … unexplored (127 of the 176) and >50 m from any SB row | **117 genuinely absent** |
| … carrying no name at all | 124 → they enter SB as `LiDAR Kristal N` |
| Cells disagreeing on linked rows | 32 (see §6) |
| CRS | identical — no reprojection; 68 pairs median 0.9 m, max 12.3 m |

The headline is the 117. The earlier folder-driven pass found exactly one row to
add (*Jamorinke*) because it only looked at folders that already held data; a
sheet-driven pass looks at every confirmed cave, and the queue is two orders of
magnitude bigger.

## 10. Decided (user, 2026-08-29)

| # | Question | Answer | What it means in code |
|---|---|---|---|
| 1 | Do the ~117 confirmed unexplored caves belong in SB? | **Yes, add them**, named per the convention | one-off `sat add --tsv` batch; *Za istražit* grows 199 → ~316 |
| 2 | Is `Istražili ≠ SUE` enough to keep a row out? | **Yes** — other societies' caves do not enter SB | automatic `out_of_scope`, no prompt; 48 SUS + 1 Karsterra |
| 3 | May the sheet gain `SUE` / `SB_redni_broj` columns? | **No, keep the sheet as it is** | mirror tab dropped; the link lives only in the crosswalk (§7) |
| 4 | Patch file or mirror tab? | patch file — but the real product is the **review list** | §7 rewritten around three lists |
| 5 | Can `Naziv_novi` outrank SB's name? | **No — SB is ground truth**; `Naziv_novi` is filled in afterwards | name disagreements are always sheet-side corrections |

### What decision 1 actually produces

Measured against the same baseline, after decision 2 removes the other societies:

- **117 rows**, taking `Redni broj` **1314 – 1430** (the column is a dense 1…1313
  today, no gaps to fill).
- **115 of them have no name at all** → they enter as `Ime objekta =
  "LiDAR Kristal N"`. Two carry a real name (*Jama iznad Andreti* 288,
  *Guštićeva jama* 338) → real name, with `LiDAR Kristal N` in `Sinonimi`.
- **Five have a text id, not a number** (the `nije na Lidaru` field finds, e.g.
  *Špilja kraj 15*). The `LiDAR Kristal N` convention cannot apply to them — they
  enter under their own sheet name, and the crosswalk is the only link. Worth a
  glance before the batch goes in.
- Only one carries a plaque already; the rest get theirs when someone visits.
- Every row needs `Napomena` seeded with the queue flag `za istražit, <komentar>`
  so SB's own Power Query puts it in the right view, plus coordinates from the
  sheet.

### Still open

- Whether the 49 explored-by-others rows should exist in SB as *sudjelovanje*
  where SUE took part — decision 2 keeps them out entirely, which is right for
  caves SUE had nothing to do with.
- Per-table coordinate tolerances for `Literatura` and `Katastar RH` (§5), to be
  calibrated when those are picked up.
