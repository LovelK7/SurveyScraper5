# T4 — `choose_layout()`: per-design scale + page arrangement for the Nacrt

Paste everything below the line into a fresh Claude Code session opened in
`SurveyScraper5`. Report the result back in the research session (project 0004).

---

You are working in the SurveyScraper5 repo (read `CLAUDE.md` first; the cSurvey and
crospeleo-automation sibling repos are read-only and not needed for this task). This is task
**T4** of project 0004 — read `stages/3N-nacrt/projects/0004-nacrt-finishing/brief.md`
sections 1, 3.1 (row 6), 3.3 (T4) and 3.4 before writing code. Do not touch cSurvey, PowerShell
or PDFs: this task is a **pure Python function with tests**, nothing else.

## What to build

A module `stages/3N-nacrt/production/tools/nacrt_layout.py` (standalone script-style module
like its siblings in that folder — plain functions, no `cave_dossier` import, no external
dependencies beyond the standard library; `dataclasses` welcome) exposing:

```python
SCALES = (100, 200, 300, 500)                     # cSurvey _preview.* scalemode index: 1, 2, 4, 5
SCALEMODE = {100: 1, 200: 2, 300: 4, 500: 5}

@dataclass(frozen=True)
class BBox:            # metres, from the survey XML (any origin; only width/height matter)
    width: float
    height: float

@dataclass(frozen=True)
class Placement:       # millimetres on the A4 portrait page, origin top-left
    x: float; y: float; width: float; height: float

@dataclass(frozen=True)
class Layout:
    plan_scale: int
    profile_scale: int
    arrangement: str          # "vertical" | "side_by_side"
    profile: Placement
    plan: Placement
    mjerilo: str              # "1:100" or "profil/tlocrt: 1:200/1:100"
    note: str                 # one line a human reads in the console menu (why this one)

def choose_layout(plan: BBox, profile: BBox, *, page=A4_PORTRAIT_MM, title_block=TITLE_BLOCK_MM,
                  margin_mm=10.0, gap_mm=10.0, max_alternatives=3) -> tuple[Layout | None, list[Layout], str]:
    """Return (best, ranked alternatives, reason_when_none)."""
```

### Page geometry (fixed constants in the module, documented in a comment)

- Page: A4 portrait, 210 × 297 mm.
- The page is the **4S sastavnica** title-block page. Its cells sit in the upper-left; read the
  cell table in `stages/4S-sastavnica/docs/sastavnica-design.md` (coordinates in PDF points,
  1 pt = 25.4/72 mm, page 595.28 × 841.89 pt, y grows downward as listed) and derive the block's
  bounding rectangle from the outermost cells (leftmost x0, topmost y0, rightmost x1, bottommost
  y1 — include every row of the table). Store it as `TITLE_BLOCK_MM`. The drawings must not
  overlap it (respect `gap_mm` around it).
- Usable drawing area = page minus `margin_mm` on all sides, minus the title block. Treat the
  free area as: the full-width band **below** the title block, plus the band to the **right** of
  the title block at its height (usable for a side-by-side plan or a narrow profile).

### Rules (from brief §3.4 — these are the user's decisions, not suggestions)

1. **Scale per design.** For each design take the largest scale (smallest denominator) in
   `SCALES` at which its bbox, in mm (`m × 1000 / scale`), fits its allotted area. Profile and
   plan may differ; profile 1:200 + plan 1:100 is the common case.
2. **Profile is primary.** In `vertical` arrangement the profile sits on top (below the title
   block, full width) and the plan beneath. `side_by_side` puts profile left, plan right, and is
   preferred only when both are tall and narrow (each aspect height/width > 1.3) or when
   vertical does not fit at any acceptable pair of scales.
3. **Plan promoted to a larger scale** when the two bboxes differ drastically: if the profile's
   larger dimension is > 1.6 × the plan's larger dimension, prefer a plan scale one step larger
   (smaller denominator) than the profile's whenever it still fits.
4. Never rescale a drawing to fit; only choose among `SCALES`. Gaps ≥ `gap_mm`, margins ≥ `margin_mm`.
5. Prefer, in order: both drawings at the largest possible scales, then vertical over side by
   side, then the pair with less wasted area. Produce the best plus up to `max_alternatives`
   distinct alternatives (different scale pair or arrangement) so an operator can pick from a
   console menu.
6. `mjerilo` is `"1:<n>"` when the scales are equal, else `"profil/tlocrt: 1:<profile>/1:<plan>"`.
7. If nothing fits even at 1:500, return `(None, [], reason)` with a one-line reason mentioning
   the mm sizes at 1:500 (the caller falls back to cSurvey's fit-to-page and warns).
8. Placements centre each drawing horizontally in its band; the profile's top edge is the top of
   its band. Round mm to 0.1.

### Tests

`stages/3N-nacrt/tests/test_nacrt_layout.py` (pytest; the repo's `testpaths` already covers
`stages/`). Import via the same trick `test_sb_select.py` in that folder uses for tools modules.
Cover at least:

- **SB 1103**: plan 4 × 9 m, profile 5 × 10 m ⇒ both 1:100, `vertical`, mjerilo `"1:100"`, no
  overlap with the title block, all placements inside the margins.
- **Long profile**: profile 40 × 12 m, plan 6 × 8 m ⇒ profile 1:200 (400 mm wide at 1:100 cannot
  fit, 200 mm at 1:200 does), plan 1:100 (rule 3), mjerilo `"profil/tlocrt: 1:200/1:100"`.
- **1:300 is used**: a case where 1:200 misses by a little and 1:300 fits (e.g. profile 45 × 30 m).
- **Tall and narrow both**: profile 3 × 25 m, plan 2 × 12 m ⇒ `side_by_side` preferred.
- **Too big**: profile 200 × 120 m ⇒ `(None, [], reason)` with "1:500" in the reason.
- A generic invariant test over a grid of bboxes: no overlaps (profile/plan/title block), every
  placement inside the margins, alternatives never equal the best, `mjerilo` format.

Run `python -m pytest stages/3N-nacrt/tests -q` and make it green. Do not edit other tests.

### Docs (part of the work, not a follow-up)

- Add one row for `nacrt_layout.py` to the tool table in
  `stages/3N-nacrt/production/tools/README.md` (role: scale + page arrangement chooser for the
  finishing step; run when: called by the finisher, or `python nacrt_layout.py <plan_w> <plan_h>
  <profile_w> <profile_h>` to preview a proposal — give the module that tiny CLI which prints the
  best layout and the alternatives as a numbered menu).
- Append a dated entry to `stages/3N-nacrt/projects/0004-nacrt-finishing/log.md` following the
  block format already there (Did / Result / Evidence / Next).
- Run `python tools/pipeline_doctor.py`; it must stay at 0 fail.

Do **not** commit; leave the working tree for the research session to review. Finish by
printing: the derived `TITLE_BLOCK_MM`, the CLI output for the SB 1103 and long-profile cases,
and the pytest summary line.
