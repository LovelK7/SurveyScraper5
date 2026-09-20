# 4S — Sastavnica

**The Nacrt's title block, prefilled — and, on the cSurvey route, the finished
Nacrt built around it.** This is the one point where the pipeline serves the
**Illustrator** drafting route, and since 2026-09-20 also the last step of the
**cSurvey** one.

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

cavedossier nacrt 1103                  # the same block + the printed plan and
                                        # profile -> SB_<broj>_nacrt.pdf
cavedossier nacrt 1103 --local --force  # same flags, same meanings
```

**Nine cells** come from SB alone, **fourteen** once the cave's zapisnik is
filled — so it is useful before the exploration and better after it.

## `cavedossier nacrt` — the cSurvey route's finished sheet

cSurvey prints **one design per sheet** and always centres it, so the Nacrt is
made by printing plan and profile separately at a *fixed* scale and composing
both onto one A4 that already carries this title block. `nacrt` is that last
step. It needs a cave that has been through
[3N's KORAK 3](../3N-nacrt/production/tools/README.md#nacrt-finishing-korak-3),
which leaves three files in the intake leaf:

| File | From | Carries |
|---|---|---|
| `<name>_plan.pdf` | `csurvey_driver.py print` | the plan, printed at a true scale, alone on an A4 page |
| `<name>_profile.pdf` | the same run | the profile, likewise |
| `<name>_dimenzije.json` | `csurvey_driver.py finish` | the speleometrics (`l`, `pl`, `nvr`, `pvr`…) **plus** the layout the finisher chose: `mjerilo`, both scales, and each drawing's rectangle in millimetres |

The command crops each printed page to its ink and drops that crop, **at its own
size**, centred on the rectangle the layout reserved — nothing is ever rescaled,
because the whole point of a fixed scale is that a 5 m scale bar measures 50 mm
at 1:100. When a drawing does not fit its rectangle, or would cross the title
block, the margin or the other drawing, the run **refuses with the millimetres**
rather than shrinking; re-run `nacrt_finish.py --layout N` and pick another
arrangement.

The title block itself is prefilled as always, with one source added: the
dimensions JSON outranks the zapisnik and SB for **Stvarna duljina**, **Tlocrtna
duljina** and **Dubina** (all measured off the very survey being composed), and
fills **Mjerilo** with the scale the designs were actually printed at. That
supersedes decision 3's `1:` stub **on this route only** — plain `cavedossier
sastavnica` never reads the file and is byte-for-byte unchanged.

**The two-line Mjerilo.** When plan and profile print at different scales the
cell reads `profil 1:200` over `tlocrt 1:100` — the only two-line cell in the
template, since `profil/tlocrt: 1:200/1:100` does not fit 43 pt on one line at
any readable size. See `render.MULTILINE`.

Delivered as `SB_<padded broj>_nacrt.pdf` beside the OSZ, with its **own**
metadata stamp: a delivered nacrt and a delivered sastavnica are different
documents and neither may overwrite the other.

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

- Code: [`src/cave_dossier/sastavnica/`](src/cave_dossier/sastavnica/) —
  `render.py`/`compose.py` are pure geometry (no SB, no Drive),
  `prefill.py`/`nacrt.py` orchestrate the two commands
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
and 811. `cavedossier nacrt` added 2026-09-20 (project
[0004-nacrt-finishing](../3N-nacrt/projects/0004-nacrt-finishing/brief.md), T3)
and validated on SB 1103 — a measured 50.00 mm for a 5 m bar at 1:100. Outside
the M-ladder — it needs only M1.
