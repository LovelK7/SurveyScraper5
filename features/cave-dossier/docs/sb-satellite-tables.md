# Satellite tables around SB — what they are and how to join them

Context for whoever picks this up next. SB (`Svi objekti`) is the master cave
registry, but it is not the only table the society keeps. Several others hold
cave data and **none of them carries an SB row number**. Everything below was
established by working one of them end to end (Liburnija, 2026-08-29) — the
findings generalise, the mechanism is in `core/matching.py` and `intake/`.

## The tables

| Table | Where | Size | Own id | What it holds |
|---|---|---|---|---|
| **Svi objekti** | SB workbook, `SO_v2_1` | 1313 | `Redni broj`, `Katastarski broj SUE` | the master registry |
| **Liburnija_pot_speleo_2024** | separate Google Sheet, owner `grozicdino@` | 410 | `name` = row number | LIDAR candidates: coords, checked y/n, is-it-a-cave, plaque, comment. Also called the **LiDAR Kristal** table |
| **Literatura** | SB workbook, own sheet | 45 | `Broj` | caves known only from literature; has plaque, name, GK + HTRS coords, lokalitet |
| **Katastar RH** | SB workbook, own sheet | 4595 | `Katastarski broj` (RH) | mirror of the national cadastre: status, name, year, synonyms, HTRS + GK coords |
| **Kategorije** | SB workbook | 88 | — | vocabularies (Lokalitet, Vrsta objekta), not objects |

`Promjene` (changelog) and `Statistika` (pivot) hold no cave data.

## The one rule that matters: never join on a local id

Every satellite numbers its own rows, and those numbers **leak into the field**:
folder names, photo filenames, notes. They look like identifiers and are not.
Three numbering schemes were seen colliding on the same integers:

* Liburnija row number (`43_Jasna` = LIDAR point 43)
* old *Za istražit* number, still kept in SB's Napomena as `za istražit, NNN, …`
* `Redni broj` itself, once a folder has been renamed

Measured: of 20 field numbers checked against the old-Za-istražit index, 5
resolved and **all 5 pointed at the wrong cave** — Šverda rows for folders that
were plainly Veprinac. Joining on a local id produces confident nonsense.

## Join on a shared key, ranked by strength

| Key | Available in | Strength |
|---|---|---|
| **Broj pločice** | SB, Liburnija (`Br.pl`), Literatura | strongest — this is what cracked Liburnija |
| **`LiDAR Kristal N` synonym** | SB (`Sinonimi`/`Ime objekta`), Liburnija (`name` = N) | strong and *deterministic* — the sheet's own number, but written INTO SB rather than guessed. 56 rows, **0 conflicts with the plaque key** |
| **Katastarski broj RH** | SB, Katastar RH | strong, but only for caves already in the national cadastre |
| **HTRS coordinates** | SB, Liburnija, Literatura, Katastar RH | **strong and universal — not yet used, see below** |
| Object name / synonym | all | weak alone; fine with a second signal |
| Local row id | all | never |

The Liburnija chain that worked, worth copying:

```
folder "108_Renata" → sheet row 108 → Br.pl 051-723 → SB "LiDAR Kristal 108" (Redni broj 1248)
```

Two guards make it safe to run over every folder rather than only the ones known
to use that scheme: the number must stand alone in the name (two digits, at a
separator or after a LIDAR marker letter — `Mune_Nat4` otherwise offers "4" and
matches the wrong row), and the sheet row must carry a plaque that exists in SB.
Numbers from other schemes then simply fail to resolve, which is the correct
outcome.

## The unused key: coordinates

Every table above carries HTRS X/Y, and SB carries them for 1200+ rows. A
proximity join (a few tens of metres) would link tables that share no id and no
spelling at all — including `Literatura` and `Katastar RH`, neither of which has
been touched yet. This is the most promising next step for making these links
systematic rather than per-table. Watch for: entrance vs. centroid coordinates,
GK vs HTRS columns in the older tables, and caves genuinely metres apart.

## How to treat a satellite table

1. **Cache it read-only.** Liburnija lives as a CSV export under `example/`
   (gitignored) and is re-exported via the Drive MCP when numbers stop
   resolving. The workbook stays the master; nothing writes back.
2. **Record the local id as provenance, never as a key** — `IntakeMatch.sheet_number`.
3. **Report gaps in both directions.** Rows in the satellite that SB lacks are
   candidates to add (this found exactly one, *Jamorinke*, now Redni broj 1311);
   SB rows the satellite could enrich are the reverse case, untouched so far.
4. **Keep an out-of-scope list.** Not every missing row should be added —
   Liburnija row 89 (*Jama na Patuhovcu*) is another society's cave and stays
   out deliberately. Without this the same row is re-raised on every run.
5. **Refresh before trusting a "missing" verdict.** A stale sandbox copy
   reported a freshly added row as absent (2026-08-25 copy, 1301 rows, vs 1313
   live). Anything that compares SB against another source wants LIVE or a fresh
   copy.

## The stage SB does not have

A LIDAR table holds **probable** caves — rows nobody has checked are caves at
all. Liburnija flags this with `provjereno` + `speleo_obj`, and the two together
make a four-state machine of which SB models only the last two. A row crosses
into SB when `provjereno=1 AND speleo_obj=1`, never earlier (user, 2026-08-29);
`nije objekt` and `neprovjeren` rows are ineligible for matching, because a link
from a non-cave to a cave is a false positive by definition.

## Open

* Promote Liburnija from a read-only bridge to a real **two-way** source — people
  enter data there, and the sheet needs SB's answers back (was it explored, what
  name did it get). Designed in **[sb-liburnija-hub.md](sb-liburnija-hub.md)**;
  the architecture decision itself is still the user's to make.
* `Literatura` (45) and `Katastar RH` (4595) are entirely unlinked so far.
* A coordinate-proximity join subsumes less than it promised: measured on
  Liburnija, true pairs run to 12.3 m while 54 sheet points sit within 15 m of
  another sheet point, so the usable auto-link band is ~5 m — it adds ~7 links,
  not a wholesale replacement for the per-table keys. Calibrate per table
  (see the hub doc §5).
