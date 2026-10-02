# 4F — Fotografije ulaza

**Entrance photos**, from wherever they landed to archive-ready copies.

## What it does

A cave's photos arrive in one of two places: its own `SB_<broj>_…` intake leaf,
or the `!!Fotografije ulaza za istražit` staging queue. This stage moves them
into the leaf, downsizes them (~1920 px / ~1.5 MB) and names them
`SB_<broj>_<Ime>_<Autor>_<n>.jpg` — the author taken from the OSZ cell
*Autor fotografije ulaza*.

## Commands

```powershell
cavedossier photos pull-staged 1220   # queue -> the cave's intake leaf (creates it)
cavedossier photos process 1220       # downsize + rename, as COPIES
cavedossier photos check-flag         # staged photos whose cave already has a SUE number
cavedossier photos match-queued       # one-off 2026-08 staging sweep; finished, not run
```

`process` makes **copies** and leaves the originals alone. Each run also checks
the queue and prints the `pull-staged` command when this cave still has photos
waiting there — the leak that otherwise leaves old photos queued forever.

Nobody browses the queue folder itself (user, 2026-10-02), so it is also
surfaced wherever a cave gets its working folder: `osz prefill` (which creates
the leaf) and `intake map --apply` (which names it) print a 📷 line with the
`pull-staged … --apply` command for every cave that has photos waiting. The
dashboard lists them on Pregled and in 4F. Nothing is moved automatically —
the pull stays a deliberate, confirmed step. On 2026-10-02 the queue held 54
photos for 34 caves, three of which (1035, 1087, 1214) already had a leaf.

## What is still missing

The **mover**: filing finished photos into `!!Fotografije ulaza` under the
archive convention `<padded SUE>_<ime>_…_<autor>.jpg`. That can only happen once
the cave has earned its katastarski broj, so it rides with
[6P-predaja](../6P-predaja/README.md) at M6. Today that move is manual and
routinely forgotten, which is exactly why `check-flag` exists.

HEIC sources are **reported, not converted** — `pillow-heif` is deliberately not
a dependency.

## Where things are

- Code: [`src/cave_dossier/photos/`](src/cave_dossier/photos/)
- Tests: [`tests/`](tests/) — note that `test_audit_and_photos.py` currently sits in
  [2B-baza](../2B-baza/tests/) because it straddles `sb.audit` and this stage
- The Drive dirs it reads and writes: [`prod/drive-layout.md`](../../prod/drive-layout.md)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)

## Status

Matcher + staleness guard done 2026-08-28; downsize + rename done 2026-09-01.
The mover is the remaining step.
