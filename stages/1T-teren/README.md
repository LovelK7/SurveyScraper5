# 1T — Teren

**Field capture, and the intake-dir contract it produces.** The mobile app is
**PARKED**; the folder contract it was designed around is live and in daily use.

## What it does

Field material for a cave — photos, the filled zapisnik, TopoDroid exports —
arrives in a **leaf folder** under `!!!Digitalizacija/!Za digitalizirat` on the
Drive. `intake/scanner.py` is what reads those folders: it maps each leaf to
its SB row and hands other stages `find_cave_leaf(broj)`, which is how 4O-osz,
4F-fotografije and 4S-sastavnica all know where to deliver.

## Commands

```powershell
# Make a cave's working folder: SB_<broj>_<Ime>[_<Sinonimi>][_<Autori>]
cavedossier intake create 1220     # an existing SB_1220_… leaf is reused, never duplicated

# Map each leaf folder to its SB row and propose an SB_<Redni broj> prefix
cavedossier intake map
cavedossier intake map --apply     # actually perform the renames
```

`intake create` is the explicit way to start a cave (2026-10-02). Before it,
a leaf only appeared as a side effect of `osz prefill` or `photos
pull-staged`. All three name the folder with the same function
(`osz.prefill.intake_folder_name`), so whichever runs first, the cave ends up
with one leaf. It writes only the empty folder, and it prints a 📷 line when
the cave has photos waiting in `!!Fotografije ulaza za istražit`, as `intake
map --apply` does for every folder it renames.

**A Redni broj several SB rows share is refused** (2026-10-02). It happened:
three rows carried 1458, because a new row copied the number above it, and
`intake map` was about to give a second folder the prefix `SB_1458_`. Both
commands now print the clashing rows (⛔), `intake create` refuses such a
number, and `intake map --apply` leaves those folders alone until SB is fixed.
The dashboard shows the same list on Pregled and marks the numbers in the
cave picker.

## How it works

Folder names are free-form and written by people, so the match is evidence-based
rather than exact: `core/matching.py` scores a leaf's name against SB rows
(name, synonyms, plaque number), and `config.yaml` carries the manual overrides
for the ones no heuristic should be asked to guess (`intake.manual_matches`,
`intake.new_entries`, `intake.split_folders`, `intake.ignore_folders`).

## Why the parked app still has a stage

Part 1 was the Android field app: voice→text descriptions, photos to the cloud,
TopoDroid `.csx` over Bluetooth. The manual workflow turned out to suffice, so
it is parked — but ARCHITECTURE records that **its one live design interface is
the intake-dir contract**. That contract is code, it is here, and everything
downstream depends on it.

## Where things are

- Code: [`src/cave_dossier/intake/`](src/cave_dossier/intake/)
- Tests: [`tests/`](tests/)
- The Drive dirs it reads: [`prod/drive-layout.md`](../../prod/drive-layout.md)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)

## Status

Scanner operational; the mobile app is parked with no scheduled work.
