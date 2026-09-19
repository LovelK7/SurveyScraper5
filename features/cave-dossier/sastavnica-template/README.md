# sastavnica-template — the Nacrt title block

The **sastavnica** is the title block placed on a finished Nacrt: the society
logo plus fifteen labelled cells (katastarski broj, ime, pločica, HTRS,
nadmorska visina, lokacija, duljine, dubina, mjerilo, crtali, mjerili, istražili,
ekipa, datum). It belongs to the **Illustrator route** to the Nacrt — part
[2.1e](../../../ARCHITECTURE.md#part-21e) — where a drafter types all fifteen
values by hand today.

This folder is the template workbench, the counterpart of
[osz-template/](../osz-template/README.md).

## Provenance

`templates/!SUE_sastavnica.pdf` is a verbatim copy of the society's authored
template on the Drive, `!!!Digitalizacija/!SUE_sastavnica.pdf` (exported from
`!SUE_sastavnica.ai`, Adobe Illustrator 24.0). The Drive copy is the source of
truth; refresh this one when the drafter revises the `.ai`, and re-run the blank
builder afterwards. The `!` prefix is kept so the provenance is obvious — it is
a Drive sorting convention, not part of any name the code constructs.

The file ships filled with **example values** (cave "Neka jama jako jako
dugačkog imena", pločica 051-580, …), which is what makes it a usable spec: the
example is how the drafter's own typesetting choices — centring, per-cell
shrink-to-fit, the 8/9/10 pt sizes — were measured.

## What is planned here

Both are designed but **not yet built** — the full design, with every measured
number, is [docs/sastavnica-design.md](../docs/sastavnica-design.md):

| Path | What |
|---|---|
| `templates/sastavnica_blank_v1.pdf` | the authored template with the fifteen example values stripped — the artifact the prefill fills |
| `tools/build_blank.py` | generates that blank by content-stream surgery (drop every text operator drawn in the value colour `#030505`, keep labels, rules and the 59 logo paths) |
| `tools/inspect_sastavnica.py` | dump any version's cells, colours, fonts and value bboxes — how the address map is re-derived |

Do **not** use PyMuPDF redaction to strip the values; it eats label glyphs
whose boxes overlap. The design note records the measurement.
