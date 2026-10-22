# 6P — Predaja

**The last gate.** Someone else does everything upstream: the Nacrt, the
zapisnik, the photos. Then the society's archivist opens this one page, looks at
everything once more, and confirms. One click then:

1. writes the cave's new **katastarski broj SUE** into the Nacrt PDF (over the
   title block's `0000`) and into the OSZ (its *Katastarski broj* cell);
2. writes it into **SB**, together with the cells that move the row from *Za
   istražit* into *Istraženi* (Excel COM, backup first);
3. **files** the Nacrt, the OSZ and the processed entrance photos under that
   number into `!!Nacrti`, `!!Osnovni zapisnici` and `!!Fotografije ulaza`;
4. **moves** the cave's whole intake leaf into `!!!Digitalizacija/Arhiva/<broj>_<Ime>/`.

The [4F](../4F-fotografije/README.md) **mover** is step 3: `photos process`
already downsized and named the photos `SB_<broj>_…`, and filing them under the
katastarski broj could only happen here, where that number is created.

## Contents

- [Run it](#run-it)
- [The archivist's page](#the-archivists-page)
- [What the gate checks](#what-the-gate-checks)
- [What is written, and in which order](#what-is-written-and-in-which-order)
- [SB cells](#sb-cells)
- [When something goes wrong](#when-something-goes-wrong)
- [Where things are](#where-things-are)
- [Status](#status)

## Run it

```powershell
cavedossier deliver 968                                   # dry run: the review list, nothing changes
cavedossier deliver 968 --json                            # the same plan as data
cavedossier deliver 968 --apply --katastarski-broj 902    # deliver under the number you reviewed
cavedossier deliver 968 --katastarski-broj 950            # plan with a number assigned by hand
```

Exit codes follow the house convention: **1** = ready / delivered, **0** = not
ready (a blocker), **99** = error.

`--apply` **requires** `--katastarski-broj`: the archivist confirms a number
they have seen, never "whatever comes next". If the next free number has
changed since the review (someone else delivered in between), the run refuses.
The number it plans is `max + 1`, or the hand-given one when it is free.

Needs the `[sb-write]` extra (xlwings, Windows + Excel) for `--apply`, and
`[sastavnica]` (PyMuPDF) for the PDF.

## The archivist's page

Dashboard (`cavedossier gui`) → **6P Predaja**, with the cave picked at the top.
It is drawn from `deliver --json` (`GET /api/predaja/<broj>`):

- **verdict**: *SPREMNO ZA PREDAJU* / *NIJE SPREMNO*, the proposed number in large
  type, and every blocker (BLOKIRA) and warning (UPOZORENJE);
- **Za pregled**, everything to look at once more, each openable in its own
  app:
  - the Nacrt, rendered inline (click to enlarge), with *Otvori PDF*;
  - the OSZ, with its obligatory-field count (*Otvori u Wordu*);
  - every processed entrance photo, as thumbnails;
  - the isječak karte;
  - the people and their izjave;
  - the SB row (*Otvori SB*);
  - the leaf's file list (*Otvori mapu*);
- **Što će potvrda napraviti**: every file and where it goes, and every SB cell
  before → after;
- the **confirmation**: a tick box (*Pregledao/la sam…*), then *Potvrđujem –
  predaj pod brojem N*. It is always confirmed once more in a dialog, even when
  "don't ask again" is on for other runs, and it runs as a job in the console.

A delivered cave shows *PREDANO – katastarski broj N* and links to its archive files.

## What the gate checks

`predaja/plan.py`, read-only. **Blockers:**

- SB is read **LIVE** (a fallback copy may lag the live workbook);
- the SB row exists and has no katastarski broj yet;
- the **SUE gate** ([`predaja/gate.py`](src/cave_dossier/predaja/gate.py)): SB's
  Ime objekta, Lokalitet, Najbliže mjesto, Razdoblje istraživanja, Autori nacrta
  ili izvor; a Dubina in SB **or** the zapisnik (delivery fills SB from it); and
  Protokol §5.1 coordinates + pločica (blocker from 2015, warning before; a
  kaverna needs no pločica). **No izjava** — that is CroSpeleo's (5D), the next
  gate, shown on the page only as information (user, 2026-10-22);
- exactly one intake leaf, and nothing in it is open in Word or Excel;
- the OSZ is present, readable as v10, and has no obligatory **SUE** field empty
  ([`osz provjera`](../4O-osz/README.md)); its Katastarski broj cell is empty or
  already holds this number;
- the Nacrt `SB_<broj>_nacrt.pdf` is present and its *Katastarski broj* cell can
  be found (one `0000`, or the one nearest the label);
- at least one processed entrance photo (the archive never gets a field original);
- the numbering is dense (`max == count`, no duplicates, no gaps), or the
  hand-given number is free;
- no archive target exists yet. A taken `902.pdf` means the number is wrong,
  which is a stop, never an overwrite.

**Warnings** (shown, not blocking):

- a Nacrt older than the OSZ;
- 3N-only OSZ gaps;
- photo originals that only go to Arhiva;
- photos still in the queue;
- a Napomena that is neither the queue flag nor `ok`;
- SB and the OSZ disagreeing on Duljina/Dubina (SB wins).

## What is written, and in which order

`predaja/apply.py`. The principle: **a reserved-but-unfiled number is cheap to
repair, a duplicated number is not.**

1. **Stage**: the stamped OSZ and Nacrt are written into
   `runs/predaja/<broj>/` first. A document problem fails here, before anything
   shared changes.
2. **SB**: one Excel session writes the row. Inside that session a guard
   re-reads the row: it must still have no number, the number must still be
   free and still `max + 1`, and the cells must still hold what the archivist
   saw. If any of that fails, the workbook is closed without saving.
3. **File**: *copies* go to the three archive dirs. A target that appeared since
   the review is a stop.
4. **Leaf**: the leaf's OSZ and Nacrt are replaced by the stamped copies, so
   the archived leaf says what the archive says. The exception is an
   **Illustrator** Nacrt: its editable original stays in the leaf, and only the
   `!!Nacrti` copy carries the number. Then the whole leaf moves to `Arhiva`.
5. **Manifest**: `runs/predaja/<broj>/manifest.json` is updated after every
   step: each src → dst, the SB cells before → after, and the backup name.

**How the number gets into the PDF.** It is written over the placeholder, not by
rebuilding the PDF, because the archivist approved *this* PDF:

- the middle of the `0000` span is redacted, so the cell's label and rules
  survive;
- the number is set at the same centre, baseline and size, in the sastavnica's
  face;
- an Illustrator PDF also loses its embedded `/PieceInfo` artwork, which would
  otherwise reopen in Illustrator still showing `0000`.

The number is written as 3 digits (`007`), as the archive does.

## SB cells

| Column | Written | Why |
|---|---|---|
| Katastarski broj SUE | the number | the delivery itself; moves the row into *Istraženi* |
| Napomena | `za istražit, [n,] <note>` → `ok[, <note>]`; empty → `ok` | otherwise the row is in *Za istražit* AND *Istraženi*; `ok` is what 768 of 901 numbered rows say |
| Fotografija ulaza | `DA` | a photo was filed |
| Duljina, Dubina | from the zapisnik, **only when empty** | SB wins; a disagreement is a warning |
| Link Nacrt, Link Zapisnik, Godina zadnjeg istraživanja | **never** | formulas over the number (live SB, 2026-10-22); they follow by themselves |

A formula cell is never overwritten even if asked (`sb/safe_io.write_row_via_excel_com`).

## When something goes wrong

The run stops at the failing step and prints what is safe to do, naming the manifest.

- **A failure before the SB write changes nothing.**
- **A failure after it** leaves the number reserved in SB. Re-running `deliver`
  then **resumes** under that number: it sees the number in SB and the leaf still
  in intake, skips the files the manifest says are already filed, and blocks on
  any other existing target.
- **A delivered cave** (number in SB, leaf gone) only reports where its files are.
- **There is no `--rollback` yet** (backlog). The manifest is the undo list, and
  SB has its daily backup beside the workbook.

## Where things are

- Code: [`src/cave_dossier/predaja/`](src/cave_dossier/predaja/) — `gate.py` (the
  SUE rules over the SB row), `plan.py` (the whole last gate + plan), `stamp.py` (number into PDF + OSZ), `apply.py` (the click);
  the SB row write is `write_row_via_excel_com` in
  [2B's `sb/safe_io.py`](../2B-baza/src/cave_dossier/sb/safe_io.py)
- CLI: `cmd_deliver` in [0P's CLI](../0P-platform/src/cave_dossier/cli/__init__.py);
  page: `renderPredaja` in [`gui/static/app.js`](../0P-platform/src/cave_dossier/gui/static/app.js)
- Tests: [`tests/test_predaja.py`](tests/test_predaja.py)
- Design: [`docs/m6-delivery-design.md`](docs/m6-delivery-design.md);
  write mechanics: [`docs/sb-write-back-design.md`](docs/sb-write-back-design.md);
  safety: [`EXCEL_WORKBOOK_SAFETY.md`](../0P-platform/docs/EXCEL_WORKBOOK_SAFETY.md)
- The Drive dirs it writes: [`prod/drive-layout.md`](../../prod/drive-layout.md)

## Status

**Built 2026-10-22, dev-only, not yet run against the live SB.**

Validated so far:

- 22 unit tests;
- a dry-run sweep over the live intake: SB 968 → 902 proposed. It was blocked
  by one missing izjava until that moved to CroSpeleo (2026-10-22), and is now
  **ready**;
- the stamp on SB 968's real Nacrt and OSZ, checked visually and in Word;
- the SB rehearsal on a copy of the sandbox with real Excel: cells written,
  formulas, validations and every VBA module intact, and a second run refused;
- a full `--apply` end to end on a scratch Drive tree with real Excel.

The first live delivery is the archivist's, on a cave that passes the gate.
