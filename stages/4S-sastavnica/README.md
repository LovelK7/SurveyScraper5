# 4S — Sastavnica

**The Nacrt's title block, prefilled.** This is the one point where the pipeline
serves the **Illustrator** drafting route.

## What it does

Produces `SB_<padded broj>_sastavnica.pdf` into the cave's intake leaf, beside
its OSZ: the logo plus fifteen cells — numbers, name, koordinate, kota, lokacija,
duljine/dubina, mjerilo, crtali/mjerili/istražili/ekipa, datum — filled from SB,
the cave's filled OSZ, and the geo finders. The drafter places it into the
Illustrator document instead of typing fifteen values by hand.

## Commands

```powershell
cavedossier sastavnica 1220             # SB + filled OSZ + geo -> the PDF
cavedossier sastavnica 1220 --offline   # local RGI gpkg + cached DEM tiles only
cavedossier sastavnica 1220 --local     # keep the runs/ copy; do not deliver
cavedossier sastavnica 1220 --force     # overwrite a delivered file we did not produce
```

**Nine cells** come from SB alone, **fourteen** once the cave's zapisnik is
filled — so it is useful before the exploration and better after it.

## Why route B gets served at all

The Nacrt has two drafting routes. They diverge right after TopoDroid and
converge on the same deliverable:

- **Route A** ([3N-nacrt](../3N-nacrt/README.md), ours) — `.tdx` → `.csx` →
  cSurvey → Nacrt PDF, with cSurvey's own title block.
- **Route B** (Illustrator) — `.tdx` → DXF/PDF export → a hand-drafted `.ai` →
  Nacrt PDF, with **this** title block.

Route B is not a fork of the pipeline and not our intent — it is the society's
established practice, with its own manuals and tool files in `!!!Digitalizacija`.
People who draft that way will keep drafting that way. Everything else in the
pipeline is route-blind: same SB row, same intake leaf, same OSZ, same photos,
same gates. Route B needs no second dossier builder and gets none.

## How it works

Pure PDF geometry. `addresses.py` holds the measured cell rectangles in PDF
points (origin top-left); `render.py` centres each value, shrinks it to fit, and
never wraps. The font is **not** bundled — Myriad Pro is licensed with
Illustrator and found on the machines that run this branch, with system
fallbacks after it. A `STAMP` in the PDF metadata marks files this tool
produced, so an edited one is refused rather than silently overwritten.

## Where things are

- Code: [`src/cave_dossier/sastavnica/`](src/cave_dossier/sastavnica/)
- **Runtime asset, inside the package**: `templates/sastavnica_blank_v1.pdf`
- **[`template-workbench/`](template-workbench/README.md)** — the authored
  `!SUE_sastavnica.pdf` Illustrator export plus `build_blank.py`, which generates
  the blank from it by content-stream surgery (and strips the embedded `.ai`
  payload that otherwise made Illustrator open the *template*). Build-time only,
  never bundled.
- Design + decisions: [`docs/sastavnica-design.md`](docs/sastavnica-design.md)
- Tests: [`tests/`](tests/)

## Status

Operational (2026-09-19, the same day as its design); validated live on SB 1220
and 811. Outside the M-ladder — it needs only M1.
