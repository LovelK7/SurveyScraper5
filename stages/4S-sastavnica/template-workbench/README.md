# sastavnica-template — the Nacrt title block

The **sastavnica** is the title block placed on a finished Nacrt: the society
logo plus sixteen labelled cells (katastarski broj, ime, pločica, HTRS,
nadmorska visina, lokacija, duljine, dubina, mjerilo, crtali, mjerili, ekipa,
istražili, nacrt uredio, datum). It belongs to the **Illustrator route** to the
Nacrt — part [2.1e](../../../ARCHITECTURE.md#part-21e) — and, composed with the
printed designs, to the cSurvey route's finished sheet.

This folder is the template workbench, the counterpart of
[osz-template/](../../4O-osz/template-workbench/README.md).

## Provenance

`templates/!SUE_sastavnica_v2.pdf` is a verbatim copy of the society's authored
template on the Drive, `!!!Digitalizacija/!SUE_sastavnica_v2.pdf` (Adobe
Illustrator 24.0, 2026-10-03). The Drive copy is the source of truth; refresh
this one when the drafter revises it, and re-run the blank builder afterwards.
A new version gets a new file name and `build_blank.VERSION` /
`addresses.TEMPLATE_VERSION` move with it; the v1 export is in git history. The `!` prefix is kept so the provenance is obvious — it is
a Drive sorting convention, not part of any name the code constructs.

The file ships filled with **example values** (cave "Neka jama jako jako
dugačkog imena", pločica 051-580, …), which is what makes it a usable spec: the
example is how the drafter's own typesetting choices — centring, per-cell
shrink-to-fit, the 8/9/10 pt sizes — were measured.

## What lives here

Built 2026-09-19; the full design, with every measured number, is
[docs/sastavnica-design.md](../docs/sastavnica-design.md):

| Path | What |
|---|---|
| `../src/cave_dossier/sastavnica/templates/sastavnica_blank_v2.pdf` | the authored template with the sixteen example values stripped — the artifact the prefill fills (a package asset, so it lives with the code) |
| `tools/build_blank.py` | generates that blank by content-stream surgery (drop every text operator drawn in the value colour — the darkest text fill, black in v2 — keep labels, rules and the 61 logo/rule paths) — and strips the embedded `.ai` payload (see below) |
| `tools/inspect_sastavnica.py` | dump any version's cells, colours, fonts and value bboxes — how the address map is re-derived |

Two traps, both measured and both recorded in the design note:

- Do **not** use PyMuPDF redaction to strip the values — it eats label glyphs
  whose boxes overlap ("HTRS koordinate:" comes back as "HTRS koordin").
- The authored export carries the whole `.ai` under the page's `/PieceInfo`
  ("Preserve Illustrator Editing Capabilities"), and **Illustrator opens that
  in preference to the page content**. A PDF edited without stripping it looks
  correct in every viewer and shows the template's example values in
  Illustrator. `build_blank.py` removes it — along with the stale `/Thumb`
  preview and the XMP packet — which also takes the file from 226 KB to 45 KB.
