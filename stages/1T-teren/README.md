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
# Map each leaf folder to its SB row and propose an SB_<Redni broj> prefix
cavedossier intake map
cavedossier intake map --apply     # actually perform the renames
```

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
