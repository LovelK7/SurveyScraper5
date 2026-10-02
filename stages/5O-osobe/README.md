# 5O — Osobe

**The registar osoba**: one canonical identity per person, and the link to their
*Izjava za katastar*. This is what gate 1 checks authorship against.

## What it does

Makes SB's `L.Kukuljan`, an OSZ's `Lovel Kukuljan` and a file named
`Izjava_LKukuljan.pdf` resolve to **one person** — then reports who is missing
an izjava, which izjave belong to nobody in the registry, and which SB author
names fall outside it entirely.

## Commands

```powershell
cavedossier people list    # every person with derived/curated aliases + linked izjave
cavedossier people check   # the audit; writes runs/people/statements-index.json
cavedossier people check --broj 1438   # ONE cave: its people and their izjave
```

Both are read-only. They change nothing, ever.

`people check --broj N` is the per-cave face of the statement gates. It
assembles the cave's dossier exactly like `cavedossier report` and prints only
the izjave part: one line per person (`✓` an izjava covers this cave · `~` izjave
exist but for another locality/cave · `✗` none on file · `?` not in the
registry), then the statement findings of gate 1 (per-author blockers) and gate 2
(per-person warnings, only what it adds). The findings are picked out by
`Source.STATEMENTS` — only the two statement rules carry it, so SB-field and
file rules never leak in. Exit codes: `1` every person gate 1 needs is covered ·
`0` not, or the izjave dir could not be read (Drive) · `99` error / no row with
that Redni broj. It writes no snapshot.

## How it works

`registry.json` holds one canonical name per person; the alias spellings are
**derived automatically** (initial forms, diacritic-folded keys) with collision
detection, and only genuinely irregular ones are curated by hand. `statements.py`
scans the `!!Izjave za katastar RH` Drive dir and links each file to a person
**scope-aware** — a locality-scoped izjava does not satisfy a cave somewhere else.

`archive/izjave.py` is the filename grammar: who signed, and what the signature
covers.

## Why it gates

A missing or wrong-scope **author** izjava is a hard **blocker** on gate 1 —
the cave cannot earn its katastarski broj without it. Any other named person
(recorder, team member) without an izjava, or absent from the registry
altogether, is a **warning** at gate 2. Drawing authors and photo authors are
checked separately.

Before the registry existed (2026-08-30) this check compared raw strings, which
meant the same person read as several and an izjava filed under one spelling
silently failed to satisfy another.

## Where things are

- Code: [`src/cave_dossier/people/`](src/cave_dossier/people/),
  [`src/cave_dossier/archive/`](src/cave_dossier/archive/)
- The record: `data/people/registry.json` at the workspace root — **curated by
  hand, so it is tracked**, unlike everything else under `data/`
- Tests: [`tests/`](tests/)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)

## Status

Operational. 132 people, 137 keys (135 derived, 2 manual) against 142 izjave.
