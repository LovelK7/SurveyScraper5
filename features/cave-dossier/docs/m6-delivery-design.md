# M6 delivery — `cavedossier deliver <Redni broj>` (design note)

The step that was missing from the M6 plan: **the last gate**. Everything
upstream produces material inside the cave's intake leaf; delivery is the one
action that ends the cave's life as a queue item — it checks the dossier is
genuinely complete, allocates the **katastarski broj SUE**, renames every file
to the archive convention, files it into its dedicated dir, archives what is
left, and writes the number back into SB.

This is bridge [**B11**](../../../ARCHITECTURE.md#b11) and it carries the 2.1d
**mover** with it. The *mechanics* of writing to SB (COM, preflight, backup,
rehearsal protocol) are not repeated here — they live in
[sb-write-back-design.md](sb-write-back-design.md). This note is about **what
delivery does and in which order**.

Status: **design only, not built.** Written 2026-09-02 from the user's spec.

## Contents

- [The command](#the-command)
- [Step 1 — the completeness gate](#step-1--the-completeness-gate)
- [Step 2 — the `/` filler pass](#step-2--the--filler-pass)
- [Step 3 — files present and nameable](#step-3--files-present-and-nameable)
- [Step 4 — allocate the katastarski broj](#step-4--allocate-the-katastarski-broj)
- [Step 5 — the approval gate](#step-5--the-approval-gate)
- [Step 6 — apply](#step-6--apply)
- [Failure, rollback, idempotency](#failure-rollback-idempotency)
- [Archive conventions — measured, not assumed](#archive-conventions--measured-not-assumed)
- [Prerequisites this exposes](#prerequisites-this-exposes)
- [Open questions for the user](#open-questions-for-the-user)

## The command

```powershell
cavedossier deliver 1234                    # DRY RUN: gate + the full plan, nothing moves
cavedossier deliver 1234 --apply            # execute the plan (after the printed approval)
cavedossier deliver 1234 --katastarski-broj 890   # override the proposed number
```

Top level, not under `osz` — delivery spans the OSZ, the nacrt, the photos and
SB at once. Dry-run-by-default with `--apply`, matching `intake map` and
`photos pull-staged`. Exit codes stay the house convention: **1** = delivered /
ready to deliver, **0** = not ready (gate failed), **99** = error.

The input is the **Redni broj**, as everywhere else: the cave's identity right
up until this command gives it a katastarski broj. That swap of identity is the
whole point of the step.

## Step 1 — the completeness gate

Re-run the gate-1 rule table (`dossier/gating.py`) with the OSZ **actually
gathered**, and refuse to deliver on any blocker. Today `report` marks only
`Source.SB` as gathered (`dossier/sb_mapper.py:209`), so every OSZ-sourced rule
reports as *unchecked* rather than pass/fail — "nobody looked" is exactly the
answer delivery must not accept. Delivery must therefore be the first consumer
that gathers `Source.OSZ`, `Source.ARCHIVE` and `Source.PHOTOS` for real.

The gate-1 blockers sourced from the OSZ (`dossier/gating.py:244-266`):

| Field | Where in the v10 document |
|---|---|
| Podrijetlo imena | **checkbox group** (*smišljeno novo* / *prema toponimu* / *iz literature* / …) |
| Vrsta objekta | **checkbox group** (*jama* / *špilja* / *kaverna* / …) |
| Hidrogeološka funkcija | **checkbox group** (*suh* / *nakapnica* / *povremeni tok* / …) |
| Hidrološka karakteristika | **checkbox group** |
| Položaj i pristup objektu | `polozaj_pristup` (sdt_cell) |
| Osnovni opis s tehničkim podacima | `opis` |
| Perspektiva daljnjeg istraživanja | `perspektiva` |
| Zapisničar | `zapisnicar` |
| Članovi ekipe | `clanovi_ekipe` (+ `_2`, `_3`) |
| Širina ulaza | `sirina_ulaza` |
| Visina/duljina ulaza | `visina_duljina_ulaza` |

**The first four are checkbox groups and none of them is in
`osz/addresses.py:V10`.** `reader.read_osz_content()` returns a flat tuple of
*ticked labels* with no notion of which group a label belongs to, so "is
Vrsta objekta answered?" is not a question the current reader can answer. A
**group → labels manifest** is the missing piece — see
[Prerequisites](#prerequisites-this-exposes).

Dimensions (Duljina / Dubina / Horizontalna duljina / Visinska razlika) are
gated from `Source.SURVEY`, not from the OSZ — they arrive with M5.

## Step 2 — the `/` filler pass

An archived zapisnik should not carry grey placeholder hints in the sections
that genuinely have nothing to say. After — and **only** after — the gate
passes, every *non-obligatory* field still showing its placeholder gets a
literal `/`: *geologija, mikroklima, biospeleologija, arheologija, opasnosti,
zagađenost, povijest, literatura, napomene, sporedni ulazi, sinonimi*.

Three rules make this safe:

- **After the gate, never before.** `/` is indistinguishable from a real answer
  once written; running it first would let the filler satisfy the very check
  that is supposed to catch an unfinished zapisnik.
- **`/` reads back as EMPTY.** `osz/reader.py` already treats a
  placeholder-showing control as empty (`w:showingPlcHdr`, `_PLACEHOLDER_MARKERS`);
  a lone `/` joins that list. Otherwise `osz backfill` would happily propose
  `/` into an SB cell, and a re-delivery would read a filled document where
  there is none.
- **Written in place, with prefill's backup convention.** The filler edits the
  leaf's own OSZ and keeps the superseded file as `<ime>_stari_<datum>.docx`,
  exactly as `osz/prefill.py` already does on a migration — so the copy that
  goes to `!!Osnovni zapisnici` and the copy that goes to `Arhiva` say the
  same thing.

## Step 3 — files present and nameable

Nothing is renamed yet; this step only proves each deliverable exists and
resolves to exactly one file, so the preview can show real target names.

| Deliverable | Found where | Delivered as |
|---|---|---|
| **Zapisnik** | `backfill.pick_osz_docx` on the intake leaf | `!!Osnovni zapisnici/<broj>.docx` |
| **Nacrt** | the leaf's finished survey PDF (2.1a / M5 artifact) | `!!Nacrti/<broj>.pdf` |
| **Fotografije ulaza** | the `SB_<broj>_<Ime>_<Autor>_<n>.jpg` copies `photos process` already writes | `!!Fotografije ulaza/<broj>_<Ime>_<Autor>_<n>.jpg` |
| **everything else in the leaf** | — | `!!!Digitalizacija/Arhiva/<broj>_<Ime>/` |

Photo delivery is a pure prefix swap: `photos process` has already downsized
and named them, so `SB_1234_` → `886_`. If the processed copies are absent the
gate says *run `photos process` first* rather than delivering originals — the
archive must never receive a 7 MB field photo.

**A target that already exists is a blocker, never an overwrite.** An existing
`<broj>.pdf` means the number is taken, which means the allocation is wrong;
that is a stop, not a merge. (The legacy `_A` *dopunski zapisnik* suffix is
superseded — decision C1 in [design-decisions.md](design-decisions.md) — so
delivery never generates one.)

## Step 4 — allocate the katastarski broj

Proposal is `max(Katastarski broj SUE) + 1`, read live from SB.

Measured against the live workbook on 2026-09-02: the column holds **ints,
1…885, 885 rows filled, no gaps and no duplicates**. The sequence is dense, so
`max == count` is a real invariant and a cheap corruption check:

- if `max != count`, someone else's allocation is half-finished (or a number
  was deleted) — **refuse and report**, rather than handing out a number that
  may collide;
- re-read `max` inside the same COM session immediately before writing, and
  verify the target cell is still empty. SB is a shared workbook; the gap
  between "the preview said 886" and "the write happens" is where a second
  archivist takes 886.

`--katastarski-broj N` overrides the proposal for the case where the archivist
assigns a number by hand; it is still validated (free, in range, not taken).

## Step 5 — the approval gate

The dry run prints the complete plan and stops. This is the last human
checkpoint before the cave becomes permanent archive:

```
Cave: SB 1234 — Jama pod dalekovodom
Gate 1: PASS (0 blockers, 2 warnings)
Katastarski broj SUE: 886   (SB max 885, sequence dense, 886 free)

Files:
  OSZ    SB_1234_OSZ.docx            -> !!Osnovni zapisnici\886.docx
  Nacrt  SB_1234_nacrt.pdf           -> !!Nacrti\886.pdf
  Foto   SB_1234_..._LKukuljan_1.jpg -> !!Fotografije ulaza\886_Jama pod dalekovodom_LKukuljan_1.jpg
         (+ 3 more)
  Leaf   SB_1234_Jama pod dalekovodom\ -> !!!Digitalizacija\Arhiva\886_Jama pod dalekovodom\
  OSZ filler: 6 empty optional fields get "/"

SB write-back (Svi objekti, row 1236):
  Katastarski broj SUE   (empty) -> 886
  Fotografija ulaza      NE      -> DA
  Napomena               "za istražit; ..." -> "..."      # queue flag cleared
  Duljina                (empty) -> 47       # from the OSZ backfill
  Link Nacrt / Link Zapisnik -> <SUE-keyed links>

Nothing has been changed. Re-run with --apply to deliver.
```

**Clearing the queue flag out of `Napomena` is not optional.** SB's views are
Power Query filters (`docs/sb-powerquery.md`): *Istraženi* is
`[Katastarski broj SUE] <> null`, *Za istražit* is `Napomena` containing
`za istražit`. Writing only the number would put the row in **both** views.
Measured 2026-09-02: **0 of 885 numbered rows currently hold a queue flag** —
the operator clears it by hand today, and delivery would otherwise be the first
tool to break that invariant.

## Step 6 — apply

Order matters, and the ordering principle is: **a claimed-but-unfiled number is
cheap to repair; a duplicated number is not.**

1. **Write the number to SB first** (COM, preflight + backup per
   [sb-write-back-design.md](sb-write-back-design.md)) — this *reserves* it.
   Same session: `Fotografija ulaza`, the `Napomena` queue flag, and any
   `osz backfill` proposals the operator accepted.
2. **`/`-filler pass** on the leaf's OSZ.
3. **Copy** the OSZ, the nacrt and the processed photos into their three
   archive dirs under the new names. Copy, not move — the leaf stays whole.
4. **Write `Link Nacrt` / `Link Zapisnik`** now that the files exist.
5. **Move the leaf** to `Arhiva/<broj>_<Ime>/`.
6. Write `runs/deliver/<broj>/manifest.json`: every src → dst, every SB cell
   before → after, the backup filename.

Proposed `Arhiva` layout is `<broj>_<Ime objekta>/` — one folder per delivered
cave, sorting alongside the other three dirs. The 451 loose entries already in
`Arhiva` are pre-existing and stay as they are.

## Failure, rollback, idempotency

Four dirs on a Drive mount plus a macro-heavy workbook cannot be made atomic,
so the design is *recoverable* instead:

- the manifest from step 6 is the undo list — `deliver --rollback <broj>` walks
  it backwards;
- a failed step aborts the rest and prints the exact manual repair, naming the
  manifest;
- **re-running a delivered cave is a no-op**, not a second delivery: a cave
  that already holds a katastarski broj is detected in step 4 and the command
  reports what is already filed (and what, if anything, is missing) instead;
- the number stays reserved on a partial failure. A reserved number with no
  files is visible to `report` and costs one katastarski broj; a number handed
  out twice costs an archive cleanup.

## Archive conventions — measured, not assumed

Read off the live Drive on 2026-09-02 rather than taken from the docs:

| Dir | Convention | Evidence |
|---|---|---|
| `!!Nacrti` | `<broj>.pdf`, zero-padded to 3 | 927 files, `001.pdf` … `885.pdf`; variants `007_paus.pdf`, `007_stari.pdf` |
| `!!Osnovni zapisnici` | `<broj>.docx` | 611 files; a few `.pdf`, legacy `092_A.docx` |
| `!!Fotografije ulaza` | `<broj>_<Ime>_<Autor>.jpg` | 1521 files; `!!!UPUTE.txt` states it verbatim: *Katastarski broj_Ime speleološkog objekta_Inicijali ili ime i prezime fotografa* |
| `!!!Digitalizacija/Arhiva` | flat, free-form today | 451 mixed entries |
| SB `Katastarski broj SUE` | int, dense 1…885 | 885 filled, 0 gaps, 0 duplicates |
| SB `Fotografija ulaza` | `DA` / `NE` | 723 / 162 among numbered caves |

## Prerequisites this exposes

Delivery cannot be built alone; in order:

1. **The checkbox-group manifest** (the M4 tail, currently called the
   CroSpeleo-field reader). Without "which labels belong to Vrsta objekta" the
   completeness gate cannot check 4 of its 11 OSZ blockers. This is the one
   hard blocker.
2. **`Source.OSZ` / `ARCHIVE` / `PHOTOS` gathering** on the dossier — the M2
   intake tail. The rules exist; nothing fills them.
3. **M5** for the nacrt and the dimensions — until then delivery would have to
   accept a hand-pointed `--nacrt FILE`.
4. **`[sb-write]` (xlwings) proven** through the rehearsal protocol in
   [sb-write-back-design.md](sb-write-back-design.md) — sandbox first, twice.

A useful intermediate: ship `deliver` **gate-only** (steps 1–5, dry run,
`--apply` refused) as soon as (1) and (2) land. It is immediately useful as the
"is this cave finished?" answer and it exercises the whole gate before any
write exists.

## Open questions for the user

1. **Photo filename** — the archive convention has no index (`<broj>_<Ime>_<Autor>.jpg`)
   but real files carry one (`006_Jama kod sela Bani_LKukuljan_10.jpg`), and
   `photos process` already emits `_<n>`. Keep the index (proposed), or drop it
   for single-photo caves?
2. **Nacrt naming** — is `<broj>.pdf` the only delivered form, or does a cave
   with several sheets get `<broj>_2.pdf` / a suffix like `_paus`?
3. **`Arhiva/<broj>_<Ime>/`** — is renaming the leaf to the katastarski broj
   right, or should the archived folder keep its field name so people recognise
   it?
4. **Prod or dev-only?** Delivery needs Excel + xlwings and is the archivist's
   step, not every recorder's. Proposed: dev-only at first, promoted to its own
   launcher once the rehearsal protocol has run live.
5. **Does anything else belong in the same SB write?** `Godina zadnjeg
   istraživanja` is an obvious candidate alongside the dimensions.
