# 5D — Dosje

**Everything known about one cave, and whether it is ready.** This stage
consumes what stages 1–4 produced and returns a verdict.

## What it does

Gathers a cave's data from every source — SB, the intake leaf, the archive dirs,
the people registry — into one `CaveDossier` object, then evaluates it against
two gates and reports what is present, what is missing, and what blocks.

## Commands

```powershell
cavedossier report --cave 1220                      # the text report, both gates
cavedossier report --cave 1220 --json               # the dossier as JSON
cavedossier report --cave 1220 --gate crospeleo     # which gate the EXIT CODE reports on
cavedossier report --broj 1438                      # by SB Redni broj instead of --cave
```

`--cave` takes an object name, a SUE number or a plaque number, and must resolve
to exactly one row. `--broj N` takes the SB **Redni broj** instead — the pre-SUE
identity, and the only handle that survives an intake folder named differently
from SB's object name (`Platak-Hrđava špilja` vs `Hrđava špilja`). Exactly one of
the two is required. The command never changes anything.

### In-process (the dashboard)

The assembly `report` runs is one reusable function, so the dashboard and
`people check --broj` evaluate a cave exactly the same way:

- `cave_dossier.dossier.assemble(settings, cave) -> CaveDossier` — SB mapping +
  izjave linkage through the people registry + gating. Fail-soft: unreachable
  Drive leaves the statement gates "not checked yet".
- `cave_dossier.dossier.to_view(dossier) -> dict` — the same content `render()`
  prints, as JSON-serialisable data (identity, sources, SB pairs, survey, files,
  people with `ok`/`scope`/`missing`/`unknown`, and both gates; gate 2 lists only
  what it adds). Its keys are the dashboard front end's contract.
- `cave_dossier.dossier.view_for_serial(settings, serial, reader=None)` —
  Redni broj → `to_view`, or `None` when no SB row carries that number.

Exit codes: `1` ready · `0` not ready · `99` error.

## Two gates, not one

- **Gate 1 — SUE.** The society's own step: Nacrt + OSZ + fotografije ulaza +
  pločica + izjave earn the cave its **katastarski broj SUE**, which is what
  moves its SB row into *Istraženi*.
- **Gate 2 — CroSpeleo.** The stricter national bar (Protokol v6). A superset of
  gate 1 — holding a SUE number makes it "almost a certain go".

Findings come in three kinds, and the distinction is load-bearing: a **blocker**
stops the final action, a **warning** is advisory, and **not-checked-yet** means
the source has not been wired up rather than that the cave is fine.

A cave's SB lifecycle is *Za istražit* → *Nesređeni* → *Istraženi*; everything
short of *Istraženi* is a queue item.

## Why it is stage 5, not the umbrella

This was "2.1", the number the whole feature was named after — which made it
look like the container for everything else. It is not. It **consumes** stages
1–4 and produces a verdict, which is what putting it at 5 says.

## Where things are

- Code: [`src/cave_dossier/dossier/`](src/cave_dossier/dossier/) — `model.py` is the
  object, `gating.py` the rule table, `sb_mapper.py` the SB→dossier mapping,
  `report.py` the rendering (text + `to_view`), `assemble.py` the shared
  SB → izjave → gating recipe
- Tests: [`tests/`](tests/)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md) — the rule
  table and the two-gate reasoning are the largest sections there

## Status

M2 in progress. The model, the gating and `report` are shipped, along with the
people registry and statement gates. **Open:** per-cave archive intake — until
it lands, `Source.ARCHIVE` honestly reports "not checked yet" rather than
claiming a file is absent.
