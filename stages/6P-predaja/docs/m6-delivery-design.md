# M6 delivery — `cavedossier deliver <Redni broj>` (design note)

**The last gate.** Everything upstream produces material inside the cave's
intake leaf. Delivery is the one action that ends the cave's life as a queue
item:

- it checks the dossier is genuinely complete;
- it lets the society's **archivist** look at all of it once more;
- on one click it allocates the **katastarski broj SUE** and writes it into
  the Nacrt, the OSZ and SB;
- it files every deliverable under that number and archives the leaf.

This is bridge [**B11**](../../../ARCHITECTURE.md#b11), and it carries the 4F
**mover** with it. The *mechanics* of writing to SB (COM, preflight, backup,
rehearsal protocol) live in
[sb-write-back-design.md](sb-write-back-design.md). This note is about **what
delivery does and in which order**. How to run it is in the
[stage README](../README.md).

**Status.**

| Date | What happened |
|---|---|
| 2026-09-02 | Designed from the user's spec |
| 2026-10-22 | **Built**, with the archivist's review page on the dashboard (user, same day). Every number measured below was re-measured on the live SB. Not yet run against the live SB |

## Contents

- [The user's spec (2026-10-22)](#the-users-spec-2026-10-22)
- [The command](#the-command)
- [The archivist's review page](#the-archivists-review-page)
- [Step 1 — the completeness gate](#step-1--the-completeness-gate)
- [Step 2 — the `/` filler pass (not built)](#step-2--the--filler-pass-not-built)
- [Step 3 — files present and nameable](#step-3--files-present-and-nameable)
- [Step 4 — allocate the katastarski broj](#step-4--allocate-the-katastarski-broj)
- [Step 5 — the approval](#step-5--the-approval)
- [Step 6 — apply](#step-6--apply)
- [The number in the documents](#the-number-in-the-documents)
- [Failure, resume, idempotency](#failure-resume-idempotency)
- [Archive conventions — measured, not assumed](#archive-conventions--measured-not-assumed)
- [Prerequisites — where they stand](#prerequisites--where-they-stand)
- [The 2026-09-02 open questions — how they were settled](#the-2026-09-02-open-questions--how-they-were-settled)
- [Validation (2026-10-22)](#validation-2026-10-22)

## The user's spec (2026-10-22)

> The last step should also contain all material to check one last time, such
> as links to the survey, OSZ, and photos — as if someone else does everything
> else, and this last step is viewed by the society's archivist, who should
> confirm the end result. If satisfied, a single click should fill the PDF
> survey and OSZ with the Katastarski broj, and reflect these changes to SB.
> Also, a moving of files should commence in G Drive.

That spec splits the step into two roles:

- **everyone else** produces the material;
- **the archivist** reviews it and confirms.

The design below kept its order (gate → number → SB → files). It gained a
**review surface**, and the number now goes **into the documents** as well as
into SB. The 2026-09-19 backlog item *"carry the katastarski broj across all
products in one step"* is this.

## The command

```powershell
cavedossier deliver 1234                              # DRY RUN: gate + review list + full plan
cavedossier deliver 1234 --json                       # the same plan as data (the dashboard draws it)
cavedossier deliver 1234 --apply --katastarski-broj 902   # execute, under the number reviewed
cavedossier deliver 1234 --katastarski-broj 950       # plan under a hand-assigned free number
```

Top level, not under `osz`: delivery spans the OSZ, the nacrt, the photos and
SB at once. Dry-run by default, matching `intake map` and `photos pull-staged`.
Exit codes follow the house convention: **1** = delivered / ready, **0** = not
ready (gate failed), **99** = error.

**`--apply` requires `--katastarski-broj`** (decision, 2026-10-22). The click
carries the number the archivist saw. If SB has moved on since the review, the
run refuses rather than handing out a number nobody looked at. Confirming the
proposal is not an "override": `--katastarski-broj` equal to `max + 1` is still
the proposal, with the same in-session `max + 1` check.

The input is the **Redni broj**, as everywhere else. It is the cave's identity
right up until this command gives it a katastarski broj, and that swap of
identity is the whole point of the step.

## The archivist's review page

The dashboard's **6P Predaja** tab (`renderPredaja`, data from
`GET /api/predaja/<broj>` = `build_plan(...).to_json()`). Top to bottom:

1. **Verdict.** *SPREMNO ZA PREDAJU* / *NIJE SPREMNO* / *SPREMNO – NASTAVAK
   PREKINUTE PREDAJE*, the number in large type with the sequence facts, then
   every BLOKIRA and UPOZORENJE line.
2. **Za pregled** — the material, every item openable in its own application:

   | Item | Shown as |
   |---|---|
   | Nacrt | first page rendered inline (`media.thumbnail` renders PDFs since this change), click to enlarge, *Otvori PDF* |
   | OSZ | obligatory-field count and gaps, *Otvori u Wordu* |
   | Entrance photos | processed photos as thumbnails |
   | Isječak karte | thumbnail |
   | People + izjave | the 5D people card |
   | SB row | its cells, *Otvori SB* |
   | The leaf | its file list, *Otvori mapu* |

3. **Što će potvrda napraviti** — every file src → dst (`+ broj` where the
   number is written in), every SB cell before → after.
4. **Confirmation.** A tick box (*Pregledao/la sam nacrt, zapisnik i
   fotografije…*) unlocks *Potvrđujem – predaj pod brojem N*, but only when
   there is no blocker. A dialog always asks once more, even when the page's
   "don't ask again" is on: this is the one step that hands out a number. The
   run is the `deliver-apply` catalog action, so it goes through the same job
   console, log and token as every other button.

**Why one gate, not a separate "review" state.** The archivist's confirmation
is the click itself; nothing records "reviewed but not delivered". Such a state
would have to live somewhere shared, it would be one more thing that rots, and
the plan is cheap to recompute.

## Step 1 — the completeness gate

The checks of `predaja/plan.py`, in the order the plan runs them. **Blockers:**

| Check | Source |
|---|---|
| SB read **LIVE** | `settings.sb_mode`; FALLBACK is a copy that can lag |
| SB row found, no katastarski broj yet | the row (a number with the leaf still in intake = *resume*, below) |
| The SUE gate: SB fields, Dubina (SB or OSZ), §5.1 coordinates + pločica | `predaja/gate.py` over the 5D dossier mapping — **no izjava** (2026-10-22) |
| Exactly one intake leaf, nothing open in Word/Excel | `SB_<broj>_…` leaves, `~$` files |
| OSZ present, v10-readable, no obligatory **SUE** field empty | `osz provjera` (`provjera.check_content`) |
| OSZ Katastarski broj cell empty or already this number | the v10 cell |
| Nacrt `SB_<broj>_nacrt.pdf` present, its cell findable | `stamp.check_pdf` |
| ≥ 1 processed entrance photo | `SB_<broj>_…jpg` in the leaf |
| Numbering dense, or the given number free | the SB column |
| No archive target exists | the three dirs + `Arhiva/<broj>_<Ime>` |

**Warnings:**

- the Nacrt is older than the OSZ (KORAK 4 writes discounted, as on the 3c step);
- the OSZ has gaps only the sastavnica reads;
- photo originals will go only to Arhiva;
- photos still sit in the queue;
- the Napomena is neither the queue flag nor `ok`;
- SB and the OSZ disagree on Duljina/Dubina.

**The checkbox groups are no longer a prerequisite.** The 2026-09-02 note
called the group → labels manifest "the one hard blocker", because gating's
OSZ rules could not tell which ticked label answers *Vrsta objekta*.
`osz provjera` (2026-10-04) already carries those groups (`_VRSTA`,
`_PODRIJETLO`, `_HIDROLOSKA`, `_HIDROGEOLOSKA`), with SUE marked on each field
gate 1 needs. Delivery asks provjera instead of waiting on `Source.OSZ`
gathering in 5D.

**Dubina in SB or in the zapisnik** is enough, because this very delivery
fills an empty SB Dubina from the zapisnik. Found on the first live sweep: SB
968 was blocked on *Missing 'Dubina'* while its OSZ said 13 m.

**No izjava (user, 2026-10-22).** The first build took 5D's "gate 1", which also
demanded an *Izjava za katastar* per author, and SB 968 was blocked on exactly
that. The izjava is a **CroSpeleo** requirement only. 5D now judges CroSpeleo
alone. The SUE rules (the old gate 1 minus izjave) live here, in
`predaja/gate.py`, and the CroSpeleo verdict appears on the page only as a note
about the next gate. After the change, SB 968 is ready.

## Step 2 — the `/` filler pass (not built)

Designed 2026-09-02: after the gate, every non-obligatory field still showing
its placeholder gets a literal `/`. **Not in the 2026-10-22 slice.** The user's
spec did not ask for it, and it carries a reader change (`/` must read back as
EMPTY), so it lands on its own. The rules stand as designed:

- after the gate, never before;
- `/` reads back as empty;
- written in place.

See the backlog.

## Step 3 — files present and nameable

| Deliverable | Found where | Delivered as |
|---|---|---|
| **Zapisnik** | `pick_osz_docx` on the leaf | `!!Osnovni zapisnici/<broj>.docx`, **number in its cell** |
| **Nacrt** | newest `SB_<broj>_nacrt.pdf` in the leaf | `!!Nacrti/<broj>.pdf`, **number in its title block** |
| **Fotografije ulaza** | the leaf's `SB_<broj>_<Ime>_<Autor>_<n>.jpg` (4F output) | `!!Fotografije ulaza/<broj>_<Ime>_<Autor>_<n>.jpg` |
| **the whole leaf** | — | `!!!Digitalizacija/Arhiva/<broj>_<Ime objekta>/` |

`<broj>` is 3 digits (`007`), the archive's own spelling. Photo delivery is a
pure prefix swap. Processed copies absent means a blocker that says *run
`photos process`*: the archive must never receive a 7 MB field photo.

**A target that already exists is a blocker, never an overwrite.** An existing
`<broj>.pdf` means the number is taken, so the allocation is wrong; that is a
stop, not a merge. (The legacy `_A` *dopunski zapisnik* suffix is superseded —
decision C1 in [design-decisions.md](../../../docs/design-decisions.md) — so
delivery never generates one.)

`Arhiva` became a config key, `archive.arhiva_dir` (default
`!!!Digitalizacija/Arhiva`).

## Step 4 — allocate the katastarski broj

The proposal is `max(Katastarski broj SUE) + 1`, read from SB.

The column was measured dense twice:

| Date | Range | Filled | Gaps | Duplicates |
|---|---|---|---|---|
| 2026-09-02 | 1…885 | 885 | 0 | 0 |
| 2026-10-22 | 1…901 | 901 | 0 | 0 |

Sixteen caves were numbered by hand in between, and the column stayed dense.
So `max == count` is a real invariant and a cheap corruption check:

- if the column has gaps, duplicates or unreadable values, someone else's
  allocation is half-finished (or a number was deleted): **refuse and report**,
  unless the archivist gives a number by hand;
- **re-read inside the same COM session** immediately before writing
  (`apply.sb_guard`). The row must still have no number, the number must still
  be free, a proposed number must still be `max + 1`, and every other cell must
  still hold what the archivist saw. Any change refuses the write and closes the
  workbook unsaved. SB is a shared workbook; the gap between the review and the
  click is where a second archivist takes 902.

`--katastarski-broj N` assigns by hand. It is validated as free and ≥ 1; a
number other than `max + 1` is a warning.

## Step 5 — the approval

The [review page](#the-archivists-review-page) is the approval; the CLI dry run
is its text form:

```
Objekt: SB 968 — Češki turist  (Excel red 970)
Katastarski broj SUE: 902   (proposed; SB max 901, 901 brojeva, niz bez rupa)

Datoteke:
  osz    SB_0968_OSZ.docx  -> …\!!Osnovni zapisnici\902.docx  [+ broj]
  nacrt  SB_0968_nacrt.pdf -> …\!!Nacrti\902.pdf  [+ broj]
  foto   SB_968_Češki turist_NMalbašić_1.jpg -> …\!!Fotografije ulaza\902_Češki turist_NMalbašić_1.jpg
  leaf   SB_0968_Češki turist -> …\!!!Digitalizacija\Arhiva\902_Češki turist
SB (Svi objekti, red Rednog broja 968):
  Katastarski broj SUE   (prazno) -> 902
  Napomena               (prazno) -> 'ok'
  Fotografija ulaza      (prazno) -> 'DA'
  Duljina                (prazno) -> 22    # iz OSZ-a (prazno u SB-u)
  Dubina                 (prazno) -> 13
```

**Clearing the queue flag out of `Napomena` is not optional.** SB's views are
Power Query filters (`docs/sb-powerquery.md`):

- *Istraženi* is `[Katastarski broj SUE] <> null`;
- *Za istražit* is `Napomena` containing `za istražit`.

Writing only the number would put the row in **both** views. Numbered rows say
**`ok`** in Napomena — measured 2026-10-22: 768 of 901 rows are `ok`, plus `ok,
sudjelovanje` (35), `ok, ZOSO` (9)… So delivery writes:

| Napomena before | After |
|---|---|
| `za istražit, [<old broj>,] <note>` | `ok, <note>` (the note survives, like the `ok, …` rows) |
| empty | `ok` |
| `ok…` | unchanged |
| anything else (`skica`…) | unchanged, with a warning to settle it by hand |

## Step 6 — apply

The ordering principle: **a reserved-but-unfiled number is cheap to repair; a
duplicated number is not.** As built (`predaja/apply.py`):

1. **Stage** the stamped OSZ and Nacrt into `runs/predaja/<broj>/`. Every
   document failure happens here, before anything shared changes. *(New: the
   2026-09-02 order wrote SB first; staging first moves every cheap failure in
   front of the reservation.)*
2. **Write SB** in one Excel session (`safe_io.write_row_via_excel_com`): daily
   backup, the row found by Redni broj *inside* the session, the guard, every
   cell, Excel saves. This *reserves* the number.
3. **Copy** the stamped OSZ, the stamped Nacrt and the processed photos into
   the three archive dirs. Copy, not move: the leaf stays whole.
4. **Stamp the leaf too.** The leaf's OSZ and Nacrt are replaced by the stamped
   copies, so the archived leaf and the archive say the same thing. An
   Illustrator Nacrt keeps its editable original in the leaf; see below.
5. **Move the leaf** to `Arhiva/<broj>_<Ime objekta>/`.
6. `runs/predaja/<broj>/manifest.json` is rewritten after **every** step:
   - every src → dst;
   - every SB cell before → after;
   - the backup filename;
   - `done_dst` (what resume skips).

**`Link Nacrt` / `Link Zapisnik` are not written — dropped from the
2026-09-02 design.** On the live SB they are table formulas
(`=IF(ISBLANK(B…),"",HYPERLINK(".\!!Nacrti\"&B…&".pdf",…))`), and so is
`Godina zadnjeg istraživanja` (`=RIGHT(O…,4)`). They follow the number by
themselves. The write refuses any formula cell outright, so a later
caller cannot overwrite one by accident.

## The number in the documents

**Nacrt.** The PDF the archivist approved is *edited*, not recomposed. A
recompose could pick up an OSZ edited after the review.

- `stamp.check_pdf` finds the `0000` span; with several, it takes the one
  nearest the *Katastarski broj* label.
- The redaction covers only the middle half of that span's height, because a
  redaction removes every glyph it touches and the label sits just above.
- The number is set at the old span's centre, baseline, size and colour, in the
  sastavnica's face (`sastavnica.fonts.resolve`).
- The hyphen/space ToUnicode fix (`render.plain_hyphens_and_spaces`) is applied
  again.
- A post-check confirms exactly one placeholder fewer and the number present.

This works for both routes, because it never assumes where the title block
sits.

**Illustrator Nacrt.** A PDF saved by Illustrator carries `/PieceInfo` — the
editable artwork Illustrator opens in preference to the page. It would still
show `0000`: the trap 4S's `build_blank.py` found on 2026-09-19. So:

- the stamped copy drops `/PieceInfo`, `/Thumb` and the XMP packet;
- the **leaf keeps the unstamped, editable original**, so a drafter can still
  reopen the drawing;
- `!!Nacrti` gets the stamped page.

**OSZ.** The number goes through the same writer KORAK 4 uses (`OszDocument`,
`V10["katastarski_broj"]`, a plain cell) and is read back afterwards. A cell
that already holds a *different* number is refused, both by the plan and by the
stamp. Word opens the result with the template's own style for that cell (Arial
18 bold) and all 81 content controls.

## Failure, resume, idempotency

Four dirs on a Drive mount plus a macro-heavy workbook cannot be made atomic,
so the design is *recoverable*:

- **A failure before SB** (a document cannot be stamped, Word holds the OSZ, SB
  is open or the guard refuses) changes nothing on SB or Drive. The manifest
  records the failed step.
- **A failure after SB** leaves the number reserved. The message says so, and
  `deliver` is simply run again. `build_plan` sees the number in SB with the
  leaf still in intake and plans a **resume** under it:
  - targets listed in the manifest's `done_dst` are skipped;
  - any other existing target is still a blocker (a hand-filed `<broj>.pdf` is
    not ours to overwrite);
  - the SB step is skipped when the cells already match.
- **Re-running a delivered cave** (number in SB, leaf gone from intake) is a
  report, not a second delivery: where its archive files are, and which are
  missing.
- `deliver --rollback` is **not built** (backlog, 2026-09-02). The manifest is
  the undo list, and SB's daily backup sits beside the workbook.

## Archive conventions — measured, not assumed

Read off the live Drive, 2026-09-02, and re-checked 2026-10-22:

| Dir | Convention | Evidence |
|---|---|---|
| `!!Nacrti` | `<broj>.pdf`, zero-padded to 3 | 927 files (2026-09-02); variants `007_paus.pdf`, `007_stari.pdf`. 884–889 are Illustrator 26 files whose title block reads `884`…`889` |
| `!!Osnovni zapisnici` | `<broj>.docx`, the number in its first cell | 886–889 read `'886'`…`'889'`; 885 is a pre-v10 layout |
| `!!Fotografije ulaza` | `<broj>_<Ime>_<Autor>.jpg` | 1521 files; `!!!UPUTE.txt`: *Katastarski broj_Ime speleološkog objekta_Inicijali ili ime i prezime fotografa* |
| `!!!Digitalizacija/Arhiva` | flat, free-form; delivery adds `<broj>_<Ime>/` | 451 mixed entries (2026-09-02) |
| SB `Katastarski broj SUE` | int, dense | 1…885 (2026-09-02), 1…901 (2026-10-22) |
| SB `Napomena` on numbered rows | `ok[, <note>]` | 768 `ok`, 35 `ok, sudjelovanje`, … of 901 |
| SB `Fotografija ulaza` | `DA` / `NE` | 723 / 162 (2026-09-02) |
| SB `Link Nacrt`, `Link Zapisnik`, `Godina zadnjeg istraživanja` | **formulas** | read with `data_only=False`, 2026-10-22 |

## Prerequisites — where they stand

| 2026-09-02 prerequisite | 2026-10-22 |
|---|---|
| 1. Checkbox-group manifest | **met** by `osz provjera` (see Step 1) |
| 2. `Source.OSZ` / `ARCHIVE` / `PHOTOS` gathering in 5D | **bypassed**: delivery reads the leaf itself; 5D still reports those rules as unchecked |
| 3. M5 (nacrt + dimensions) | **met** by 3N KORAK 3c / 4 (`SB_<broj>_nacrt.pdf`, `_dimenzije.json`) |
| 4. `[sb-write]` proven through the rehearsal protocol | **done on a copy**: see [Validation](#validation-2026-10-22) |

## The 2026-09-02 open questions — how they were settled

Taken as the proposals of the 2026-09-02 note when the feature was built
(2026-10-22). They are recorded in the decision record and can be revisited:

1. **Photo filename index**: **kept** (`<broj>_<Ime>_<Autor>_<n>.jpg`). `photos
   process` always emits it, the real archive carries it, and a second photo
   would otherwise collide.
2. **Nacrt naming**: `<broj>.pdf` only. Several `_nacrt.pdf` files in one leaf
   → the newest is delivered, and the page lists the others as a warning.
   Suffixes like `_paus` stay a hand job.
3. **`Arhiva/<broj>_<Ime>/`**: **yes, renamed to the number**. The files inside
   keep their `SB_<broj>_…` names, so the field identity is still readable.
4. **Prod or dev-only**: **dev-only first** — the dashboard is not in a prod
   launcher yet, and the first live delivery should be watched.
5. **Anything else in the same SB write**: `Godina zadnjeg istraživanja`
   turned out to be a formula. The write is the number, Napomena, Fotografija
   ulaza, and Duljina / Dubina when empty.

## Validation (2026-10-22)

- **Unit**: `stages/6P-predaja/tests/test_predaja.py`, 22 tests:
  - allocation and the Napomena rule;
  - the PDF stamp, including the Illustrator strip and two placeholders;
  - the OSZ stamp on the real v10 template;
  - the in-session guard (four ways SB can move on);
  - `apply` end to end on a tmp Drive with a fake writer, including a guard
    refusal leaving the Drive untouched and a target appearing after the
    review.
- **Live dry run**: a sweep of every intake leaf holding both a Nacrt and an
  OSZ. One cave: **SB 968 Češki turist**, number 902 proposed. It is blocked
  only by a missing izjava for F.Karabaić. That was not a SUE requirement, so
  the izjava moved to CroSpeleo (5D) the same day, and 968 is now **ready**.
  Its *Missing 'Dubina'* block led to the "SB or OSZ" rule in Step 1.
- **Stamp on real documents**: SB 968's Nacrt and OSZ, stamped 902 into the
  scratchpad. The title block was checked visually: label intact, number
  centred, no leftover `0000` in the text layer. The OSZ was opened in Word.
- **SB rehearsal**: [sb-write-back-design.md](sb-write-back-design.md) protocol,
  on a **copy** of the sandbox, with real Excel COM.
  - Row 970 got 902 / ok / DA / 22 / 13.
  - The `Link` and `Godina` formulas, the sheet's 3 data validations and all 18
    VBA modules and forms survived. Only Excel's compiled-code cache
    (`__SRP_*`) and the *Nesređeni* sheet's empty styled cells shrank; its
    values were identical.
  - A second run was **refused** by the guard.
  - The first attempt hung once after the save, with no Excel process left; the
    instrumented re-run did not reproduce it.
- **End to end**: `--apply` on a scratch Drive tree (SB 968's real leaf + the
  izjave + a sandbox copy), with real Excel. Everything was filed as planned,
  the leaf moved to `Arhiva\902_Češki turist`, and a re-plan reports
  *delivered*.
- **Not done**: no live SB write and no live Drive move. The first one is the
  archivist's, on a cave that passes the gate.
