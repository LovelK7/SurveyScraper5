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
| *(new)* `SUE`, `SB_redni_broj` | — | **SB** | **SB → sheet** |

The two proposed new sheet columns are what the user asked for in plain terms —
*"did cave 10 turn out to be explored, and what name did it get"* — and they
close the join problem permanently: once written, the link is explicit and never
has to be re-derived. The crosswalk stays the source of truth for the link;
the sheet column is a mirror, and a disagreement between them is a finding.

**Measured payload today**, on the 68 linked rows: 32 cells disagree —
15 × `Foto ulaza` false in the sheet but present in SB, 4 × the other two
deliverable flags, 12 name gaps (of which only 2 are real divergences —
*PP Bjeloučka*/*Bijeloučka*, *Ivanina zvijezdica*/*zvjezdica*; the other 10 are
SB holding the `LiDAR Kristal N` placeholder, which must **not** be written back
as a name), and 1 lifecycle disagreement (row 272 → SB 1256 *Paralelka*: sheet
says unexplored, SB says *"fali nacrt i zapisnik, ponoviti"*).

## 7. How to actually write to the sheet

Constraint: SB access is deliberately Google-API-free (local Drive mount), but a
native Google Sheet has no readable file on that mount, and **it is edited by
people in the field while we run**. Four options, ranked:

| | Approach | Verdict |
|---|---|---|
| **A** | **Generated mirror tab + formulas.** The tool writes a `SB_status` tab (or its own file) keyed by sheet `name`; the field sheet gains `SUE`, `Naziv (SB)`, `istraženo (SB)`, `Nacrt/Zapisnik/Foto` as `VLOOKUP`/`IMPORTRANGE` formulas over it. | **Recommended.** The tool never touches a human-edited cell, so concurrent editing is structurally impossible to break — the same split-responsibility trick that keeps SB safe. |
| B | Emit a **patch file** (TSV of changed cells + a printed before→after preview) the user pastes in. | Good fallback / first increment. Zero credentials, matches the existing `--apply` discipline. |
| C | Sheets API cell writes with a service account. | Real two-way, but adds credentials and breaks the no-Google-API rule. Only if A and B prove insufficient. |
| D | Drive MCP `update_file` on the sheet. | **No.** Media upload replaces the whole file — it would silently drop concurrent field edits. |

Start at B (it is a day's work and immediately useful), design the payload so A
is a drop-in swap for the same computed rows.

The read direction keeps the current shape: a cached CSV export under `example/`
(gitignored, UTF-8, society data), refreshed via the Drive MCP. One hardening
step is non-negotiable and already has a scar: **any run that reports "missing
from SB" must refresh both sides first**, or it repeats the stale-sandbox
incident that reported *Jamorinke* as absent when it had just been added.

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
| `cavedossier sat push liburnija` | the SB→sheet payload: preview the 32 disagreeing cells; `--apply` writes the patch file (option B) or the mirror tab (option A) |
| `cavedossier sat add liburnija <N>` | scaffold the SB row for one crossed candidate — the row's values, ready to paste, with `LiDAR Kristal N` in the right cell |

Sequencing (each step useful on its own):

1. **crosswalk + resolver + `sat sync`** over the existing plaque and Kristal
   keys. Materialises the 68 links; costs nothing new.
2. **`sat gaps`** — the report that surfaces the 117 missing rows. Read-only, and
   the highest-value single output here.
3. **`sat push` as a patch file.** Two-way begins; 32 cells of drift get fixed.
4. **Coordinate key**, with the §5 bands, behind a flag until it has been run
   once and eyeballed.
5. **`sat add`**, feeding SB write-back (M6 machinery, `safe_io`, backups,
   sandbox rehearsal — nothing new needed).
6. **Mirror tab** replaces the patch file if the round trip proves annoying.
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

## 10. Decisions needed before building

1. **Are the ~117 unexplored confirmed caves genuinely SB's?** They would grow
   *Za istražit* from 199 to ~316. Bulk-add, or add on demand as each is worked?
2. **`Istražili` as the out-of-scope rule** — is "not SUE" sufficient to keep a
   row out automatically (48 rows), or does each still need a look?
3. **Two new sheet columns** (`SUE`, `SB_redni_broj`) — acceptable to add to a
   sheet the society owns collectively?
4. **Patch file or mirror tab** for the first write-back increment (§7 A vs B).
5. **Does `Naziv_stari` ever outrank SB's name?** Today SB wins by default; the
   two real divergences are both spelling.
