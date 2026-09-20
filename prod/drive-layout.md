# The Drive layout — the prod interface

**Prod is the registry Google Drive**, not this repo. The shared
`Speleo baza SUE` folder is where the society's real work lives; the tools write
into it and non-technical people manage it by hand.

This document is the contract. The dir names themselves are declared in
[`config.yaml`](../config.yaml) under `archive:` — that file is authoritative,
this one explains it.

## How the tools find it

One per-machine setting, `LOCAL_DRIVE_ROOT` in `.env`:

```
LOCAL_DRIVE_ROOT=G:/.shortcut-targets-by-id/<id>/Speleo baza SUE
```

**There is no Google API anywhere.** All cloud access is locally-synced paths
via Google Drive Desktop. That is a deliberate decision, not a gap — see
[`EXCEL_WORKBOOK_SAFETY.md`](../stages/0P-platform/docs/EXCEL_WORKBOOK_SAFETY.md).
On an operator machine `bootstrap.ps1` derives this value from where the
launcher itself sits, so nobody has to type it.

## The dirs

| Drive dir | `config.yaml` key | Who writes it | Stage |
|---|---|---|---|
| `!Speleo_baza_SUE_v3.0.xlsm` | `sb.workbook_filename` | a person, in Excel (write-back at M6) | [2B](../stages/2B-baza/README.md) |
| `!!!Digitalizacija/!Za digitalizirat` | `intake_dir` | the field, then the tools | [1T](../stages/1T-teren/README.md) |
| `!!Isječci karte` | `map_excerpts_dir` | `cavedossier karta` | [4I](../stages/4I-isjecak/README.md) |
| `!!Fotografije ulaza` | `entry_photos_dir` | the M6 mover (manual today) | [4F](../stages/4F-fotografije/README.md) |
| `!!Fotografije ulaza/!!Fotografije ulaza za istražit` | `queued_photos_dir` | the field | [4F](../stages/4F-fotografije/README.md) |
| `!!Izjave za katastar RH` | `statements_dir` | a person, filing signed izjave | [5O](../stages/5O-osobe/README.md) |
| `!!Osnovni zapisnici` | `osz_dir` | the M6 delivery | [6P](../stages/6P-predaja/README.md) |
| `!!Nacrti` | `drawings_dir` | the M6 delivery | [6P](../stages/6P-predaja/README.md) |
| `!!!Digitalizacija/SurveyScraper5` | `build_prod.TARGET_REL` | `build_prod.py --publish` | [prod](README.md) |
| `!!!Digitalizacija/SurveyScraper5` (the `csurvey_*` kit + `csurvey_alati/`) | `build_csx_kit.TARGET_REL` | `build_csx_kit.py --publish` | [3N](../stages/3N-nacrt/README.md) |

The `!` prefixes are the society's own convention for sorting these to the top
of a Drive listing. They are part of the names — do not "clean them up".

## The per-cave intake leaf

The unit of work is a **leaf folder** per cave under `!Za digitalizirat`, named
`SB_<Redni broj>_<Ime>[_<Sinonimi>][_<Autori>]`. It holds that cave's survey
files, photos, prefilled OSZ and sastavnica **together**. `osz prefill` reuses
an existing `SB_<broj>_…` leaf found anywhere in the tree and only creates a new
one at the intake root if there is none.

This superseded an earlier flat "Osnovni speleološki zapisnik" folder
(user decision, 2026-08-30).

## Filename conventions

| Artifact | Name |
|---|---|
| Map excerpt | `SB_<padded broj>.png` in `!!Isječci karte`, plus a row in `!georef_zapisi.csv` |
| Prefilled OSZ | `SB_<broj>_OSZ.docx` in the cave's intake leaf |
| Sastavnica | `SB_<padded broj>_sastavnica.pdf` in the cave's intake leaf |
| Processed entrance photo | `SB_<broj>_<Ime>_<Autor>_<n>.jpg` in the leaf |
| Archived entrance photo | `<padded SUE>_<ime>_…_<autor>.jpg` in `!!Fotografije ulaza` (M6) |
| Izjava | `Izjava_<Ime>.<ext>`, optionally scope-suffixed |

## The two rules that govern everything written here

**1. The dirs are hand-managed by non-technical people.** Assume files get
deleted, renamed, moved, and opened in Word or Excel (which strips zero-padding,
reformats dates and adds blank rows). So:

- every staleness and consistency check lives in the tool and re-derives state
  on the next run, rather than trusting the last run;
- a failed delivery **degrades to the local `runs/` copy** instead of erroring;
- **no workflow may require a manual cleanup ritual.**

**2. Nothing writes to a live shared source automatically.** SB is macro-heavy
and the satellite sheets are typed into in the field. Tools emit review lists
(`dopune-sb.csv`, the four `sat sync` lists) and a person carries them out.
The single exception will be M6 delivery, via Excel COM, deliberately.

## Downstream

`../crospeleo-automation` is the **downstream consumer** of these dirs — it
submits finished dossiers to the national CroSpeleo cadastre. SurveyScraper5 is
the upstream producer. That handshake is *these directory names and these
filename conventions*, nothing else: no shared code, no shared database. Design
every delivery format for that continuity — SUE-prefixed filenames, OSZ labels
its parser recognizes.
