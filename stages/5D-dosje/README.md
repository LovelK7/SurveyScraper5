# 5D — Dosje

**Everything known about one cave, and whether it is ready for CroSpeleo.** This
stage consumes what the earlier stages produced and returns a verdict against
the national cadastre bar.

## What it does

Gathers a cave's data from every source (SB, the intake leaf, the archive dirs,
the people registry) into one `CaveDossier` object. It then evaluates that
object against **one gate, CroSpeleo** (Protokol v6), and reports what is
present, what is missing, and what blocks.

The society's own step, the **katastarski broj SUE**, is not judged here. That
is [6P](../6P-predaja/README.md)'s last gate, where the archivist reviews and
delivers. So 5D is the step *after* delivery: CroSpeleo needs the SUE number.

## Commands

```powershell
cavedossier report --cave 1220            # the text report, the CroSpeleo gate
cavedossier report --cave 1220 --json     # the dossier as JSON
cavedossier report --broj 1438            # by SB Redni broj instead of --cave
```

`--cave` takes an object name, a SUE number or a plaque number, and must
resolve to exactly one row. `--broj N` takes the SB **Redni broj** instead. That
is the pre-SUE identity, and the only handle that survives an intake folder
named differently from SB's object name (`Platak-Hrđava špilja` vs `Hrđava
špilja`). Exactly one of the two is required. The command never changes
anything.

Exit codes: `1` ready for CroSpeleo · `0` not ready · `99` error.

### In-process (the dashboard)

The assembly `report` runs is one reusable function. The dashboard, `people
check --broj` and 6P's review page all use it, so they evaluate a cave exactly
the same way:

- `cave_dossier.dossier.assemble(settings, cave) -> CaveDossier` — SB mapping,
  then izjave linkage through the people registry, then gating. It is
  fail-soft: an unreachable Drive leaves the statement rules "not checked yet".
- `cave_dossier.dossier.to_view(dossier) -> dict` — the same content `render()`
  prints, as JSON-serialisable data:
  - identity, sources, SB pairs, survey and files;
  - people with `ok`/`scope`/`missing`/`unknown`;
  - `gate`, the CroSpeleo verdict.

  Its keys are the dashboard front end's contract.
- `cave_dossier.dossier.view_for_serial(settings, serial, reader=None)` —
  Redni broj → `to_view`, or `None` when no SB row carries that number.

## The gate

**CroSpeleo** (Protokol v6, Tablica 2 + §5): everything the cave needs to be
submitted to the national cadastre. That covers:

- the SB fields and the OSZ fields;
- the Nacrt and the entrance photo;
- the pločica and coordinates (mandatory from 2015, §5.1);
- the isječak karte and georef zapis;
- izvor koordinata, istražile udruge, vertikalna razlika;
- the **katastarski broj SUE** itself;
- an ***Izjava za katastar* for every author** of the nacrt and photos. A
  missing or wrongly scoped one blocks; any other named person without one
  only warns.

Submission itself stays crospeleo-automation's job downstream; this pre-checks it.

**The izjava is a CroSpeleo requirement only** (user, 2026-10-22). Until then
5D carried two gates: a "gate 1 — SUE" that also demanded izjave, and gate 2 —
CroSpeleo. The SUE step moved to 6P without the izjava, and 5D kept CroSpeleo.

Findings come in three kinds, and the distinction is load-bearing:

- a **blocker** stops the submission;
- a **warning** is advisory;
- **not-checked-yet** means the source has not been wired up, not that the cave
  is fine.

A cave's SB lifecycle is *Za istražit* → *Nesređeni* → *Istraženi* (delivered by
6P); everything short of *Istraženi* is a queue item.

## Why it is stage 5, not the umbrella

This was "2.1", the number the whole feature was named after. That made it look
like the container for everything else. It is not: it **consumes** the earlier
stages and produces a verdict, which is what putting it at 5 says.

## Where things are

- Code: [`src/cave_dossier/dossier/`](src/cave_dossier/dossier/):
  - `model.py` — the object;
  - `gating.py` — the rule table;
  - `sb_mapper.py` — the SB → dossier mapping;
  - `report.py` — the rendering (text + `to_view`);
  - `assemble.py` — the shared SB → izjave → gating recipe.
- Tests: [`tests/`](tests/)
- The SUE gate: [6P `predaja/gate.py`](../6P-predaja/src/cave_dossier/predaja/gate.py)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md) — the rule
  table, and the 2026-10-22 split of the SUE gate into 6P

## Status

M2 in progress. The model, the gating and `report` are shipped, along with the
people registry and the statement rules.

**Open:** per-cave archive intake. Until it lands, `Source.ARCHIVE` honestly
reports "not checked yet" rather than claiming a file is absent. 6P reads the
leaf itself, so delivery does not wait on this.
