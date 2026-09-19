# 4O — OSZ builder

**The osnovni speleološki zapisnik**, in both directions: prefill a blank one
from what we already know, and read a filled one back to propose SB updates.

The OSZ is one of the pipeline's two final products (the other is the Nacrt).

## What it does

**Prefill** — SB row + the geo finders + the isječak karte → a maximally filled
`SB_<broj>_OSZ.docx` delivered into the cave's intake leaf, ready for a recorder
to take to the cave. It fills identity, coordinates with their sources, locality,
kota, the "Položaj i pristup" text, and embeds the map excerpt.

**Backfill** — the reverse. Reads a **filled** zapisnik and proposes the SB
backfill (pločica, ime→sinonimi, duljina/dubina, godina, autori via the alias
registry) as a review CSV. It never writes to SB.

## Commands

```powershell
cavedossier osz prefill 1220     # SB + finders + excerpt -> SB_1220_OSZ.docx
cavedossier osz backfill 1220    # filled zapisnik -> dopune-sb-iz-osz.csv
```

Prefill runs [4I-isjecak](../4I-isjecak/README.md) itself when the excerpt is
missing or stale, so one command is enough to produce a field-ready zapisnik.

## How it works

The v10 template is a Word document with `w:sdt` **content controls**, which are
invisible to python-docx — so the writer works on `word/document.xml` with lxml
directly, at the cell addresses recorded in `addresses.py`. The **legacy** parser
(`legacy.py`) is the exception: pre-v10 zapisnici have no controls and their
selections live in run-level bold, which python-docx exposes cleanly.

Nothing it discovers is written to SB. Values the finders could fill but SB
lacks come out as `dopune-sb.csv` — a person pastes them into `Svi objekti`.

## Where things are

- Code: [`src/cave_dossier/osz/`](src/cave_dossier/osz/) — `prefill.py` orchestrates,
  `writer.py` / `reader.py` handle the v10 document, `legacy.py` the old ones,
  `addresses.py` is the cell map
- **Runtime assets, inside the package**: `templates/Zapisnik_OSZ_v10.docx` (the
  document prefill actually fills) and `pristupi.yaml` (the prefilled access texts)
- **[`template-workbench/`](template-workbench/README.md)** — everything *about*
  the template rather than read by the tool: the `.dotx` / `_gdocs.docx` pair handed
  out to recorders, the audits, the mockups, and the six QA scripts
  (`inspect_osz.py` is the source of truth for `addresses.py`)
- Tests: [`tests/`](tests/)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)

## Status

Prefill and backfill both operational (2026-08-30). Open: validation against the
first **real** filled zapisnici, and the CroSpeleo-field reader (checkbox groups,
narratives, the Google Docs variant).
