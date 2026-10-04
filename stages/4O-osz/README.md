# 4O — OSZ builder

**The osnovni speleološki zapisnik**, in both directions: prefill a blank one
from what we already know, and read a filled one back to propose SB updates.

The OSZ is one of the pipeline's two final products (the other is the Nacrt).

## What it does

**Prefill** — SB row + the geo finders + the isječak karte → a maximally filled
`SB_<broj>_OSZ.docx` delivered into the cave's intake leaf, ready for a recorder
to take to the cave. It fills identity, coordinates with their sources, locality,
kota, the "Položaj i pristup" text, and embeds the map excerpt.

**Measured dimensions (from the Nacrt).** When the cave's intake leaf holds a
`<name>_dimenzije.json` — what [3N-nacrt](../3N-nacrt/README.md)'s cSurvey route
leaves there — prefill also fills the four "Karakteristike objekta" numbers from
the **newest** such file:

| OSZ cell | from the JSON |
|---|---|
| Duljina | `l` |
| Horizontalna duljina | `pl` |
| Dubina | `nvr_m`, else `nvr` (depth below the entrance) |
| Visinska razlika | `vr`, else depth + `pvr_m`/`pvr` |

Bare whole metres, unsigned (`9`, not `-9 m` — the headers say `(m)`, and 4S
adds the minus when it prints the nacrt); a zero means "not surveyed" and stays
empty. SB's Duljina/Dubina are **never** used to fill these. No file, an
unreadable one, or `"calculated": false` is a note (the last still fills).

**Re-run after the survey.** The zapisnik and the nacrt need each other, so
whichever comes first, run `osz prefill` again once the Nacrt is done: the
filled zapisnik in the leaf is migrated forward (narratives, team, ticks…), the
measured numbers go in, and the old file is kept as `…_stari_<datum>.docx`. A
measured value **wins** over a different number the old zapisnik recorded (the
note names both); one that rounds to the same metres keeps the recorder's text.
Nothing changed → the document is left untouched. If the zapisnik is **open in
Word** (`~$…` file in the leaf), prefill warns at the start and leaves the leaf
alone — close Word and run it again.

**Backfill** — the reverse. Reads a **filled** zapisnik and proposes the SB
backfill (pločica, ime→sinonimi, duljina/dubina, godina, autori via the alias
registry) as a review CSV. It never writes to SB.

## Commands

```powershell
cavedossier osz prefill 1220     # SB + finders + excerpt -> SB_1220_OSZ.docx
cavedossier osz izmjera 1220     # 3N KORAK 4: the nacrt's numbers into the EXISTING OSZ
cavedossier osz backfill 1220    # filled zapisnik -> dopune-sb-iz-osz.csv
```

**Izmjera** — 3N's KORAK 4 (user, 2026-10-04). Once KORAK 3b has produced
`<ime>_dimenzije.json`, `osz izmjera <broj>` writes the measured cells — Duljina,
Horizontalna duljina, Dubina, Visinska razlika, Broj / Širina / Visina-duljina
ulaza — into the zapisnik already in the leaf. Nothing else is touched: no SB,
no finders, no excerpt, no new document. Same precedence as the prefill (the
measurement wins over a different recorded number, the same measurement keeps
the recorder's text), the entrance reading follows the zapisnik's own *Vrsta
objekta* ticks, nothing to change leaves the file alone, a document open in
Word is refused, the old file survives as `…_stari_<datum>.docx`. A legacy
zapisnik is not edited in place: run `osz prefill` first, which migrates it.
The dashboard's 3N page carries it as KORAK 4; the Drive kit as
`csurvey_4_upisi_osz.bat`.

Prefill runs [4I-isjecak](../4I-isjecak/README.md) itself when the excerpt is
missing or stale, so one command is enough to produce a field-ready zapisnik.

## How it works

The v10 template is a Word document with `w:sdt` **content controls**, which are
invisible to python-docx — so the writer works on the `document.xml` inside the
.docx with lxml directly, at the cell addresses recorded in `addresses.py`. The **legacy** parser
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
