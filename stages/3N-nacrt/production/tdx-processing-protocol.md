# TDX → cSurvey processing protocol (closing report of the symbol-mapping brief)

**Status: OPERATIONAL** — brief [tdx-symbol-mapping-brief.md](../projects/0002-tdx-symbol-mapping/brief.md) closed 2026-07-26 with user sign-off after full acceptance on real surveys (`ponor_rupa_babi_pod_kucu`, `rupe_preko_vertikale`; runs in [projects/0002-tdx-symbol-mapping/runs/](../projects/0002-tdx-symbol-mapping/runs)).

## What was built

| Piece | File | Role |
|---|---|---|
| Inspector | `production/tools/inspect_survey.py` | read-only stats/diff report for any `.csz`/`.csx` (Stage 0) |
| Pre-processor | `production/tools/preprocess_tdx_csx.py` | rewrites a raw TDX export so symbols survive the import (renames, label conversions, stroke reversal, orientation) |
| Mapping config | `production/tools/tdx-mapping.json` | **the user-owned mapping**: per-symbol `to`/`label`/`leave` + `reverse`/`orientation`, generic subtype/`-area` stripping, and `postimport` switches |
| Mapping workbench | `production/tools/make_signs_catalog.py` → `tdx-mapping-workbench.html` + `cs-targets.html` | visual editor: every TDX tool (icons rendered from TopoDroid's own symbol files, all 9 sets + system tools) → numbered cSurvey targets; exports the json |
| Post-import fixer | `production/tools/fix_imported_linetypes.py` | fixes what import cannot express: spline linetypes (decoration rendering), non-standard water brush, per-sign/label sizes |
| Operator kit | `prod/build_csx_kit.py` → `csurvey_*.bat` + `csurvey_alati\` on the Drive | the drag-and-drop surface: three launchers, the plain-language checklist, and the Python tools they drive, generated and published together (v1.0, 2026-09-20) |
| Signs pack | `production/tools/signs-pack/*.svg` | 8 glyphs for mapped-but-artwork-less signs; installed into `C:\csurvey64\Objects\Cliparts\Signs\` |
| Knowledge | [tdx-symbol-matrix.md](tdx-symbol-matrix.md) | run-verified symbol matrix (mapping + glyph coverage + remediation decisions) |

## Key findings (details in the matrix and RUNLOGs)

- Conversion is name-driven and *fixed*: 13 line targets, 6 area targets, points via `SignEnum` (name minus dashes); unknown names degrade silently and irrecoverably (original name discarded).
- Rendering has its own gates: signs need a gallery SVG (X-box otherwise); line decorations need splines — cSurvey stamps decorations per polyline segment without accumulating distance ([cClipartOnPath.vb:88-99](../../../../cSurvey/cSurveyPC/cClipartOnPath.vb#L88)), so dense TopoDroid polylines render plain (upstream fix candidate; worked around post-import).
- `water-flow`-named points get a built-in +90° orientation tweak at import; sizes with TDX scale 0 are not applied — both handled via config.
- Winding/orientation of wall strokes is irrelevant to fill rendering; the historical "draw CCW" guideline is legacy advice.

## Where the kit lives

**`<LOCAL_DRIVE_ROOT>\!!!Digitalizacija\`** — the society's digitalization
folder, beside the caves it processes:

```
!!!Digitalizacija\
    csurvey_preprocess_tdx.bat                     STEP 2
    csurvey_recover_tdx.bat                        STEP 1b (only when a csx is broken)
    csurvey_fix_tdx.bat                            STEP 4
    csurvey_READ ME FIRST - process a survey.txt   the operator checklist
    csurvey_alati\                                 the Python tools the .bat files drive
    !Za digitalizirat\SB_<broj>_<Ime>\             the surveys themselves
```

Published with `python prod\build_csx_kit.py --publish` (staging only without
the flag; `--publish-to DIR` for anywhere else). This is kit **v1.0**, 2026-09-20
— it replaces the copies that used to sit in `G:\My Drive\Share\TDX`, each of
which hardcoded one developer's `TOOLS=` path and was therefore inert on every
other machine. That folder now holds only a note pointing here.

Two consequences of the layout:

- **A double-click scans `!Za digitalizirat`**, not the whole digitalization
  tree — that is where the per-cave folders are. Dragging files onto a launcher
  works from anywhere, as before.
- **`csurvey_alati\` is a published copy.** Edit the tools and
  `tdx-mapping.json` in [`production/tools/`](tools/) and re-publish; never edit
  the Drive copy.

## The standing protocol (routine survey)

> **Non-technical operator?** The step-by-step, jargon-free version lives beside the launchers as **`csurvey_READ ME FIRST - process a survey.txt`**. It explains drag-and-drop, the `_pp`/`_lt` name endings, and what each black-window message means. The rule in one line: **import the `_pp` file → draw in the `_lt` file.**

1. **Phone:** draw in TopoDroid preferring green-verdict tools (see workbench); export **one** csx (it contains both plan and profile) into that cave's folder under `!!!Digitalizacija\!Za digitalizirat\SB_<broj>_<Ime>\` (anywhere else works too — then drag the file onto the launcher instead of double-clicking it). **Also export the project ZIP archive every time** (Survey window → menu → Archive) — since TopoDroid 6.4.99 the zip is the durable artifact: it always carries the full sketch and survives app-version churn (see step 1b).

   **1b. If the csx is missing/0-byte or the sketch vanished (TopoDroid ≥6.4.98 bugs):** regenerate the csx from the project zip — double-click `csurvey_recover_tdx.bat` (processes every project zip under `!Za digitalizirat`), or drag specific zips onto it; equivalently `python stages\3N-nacrt\production\tools\tdx_zip_to_csx.py <zip|folder>`. It writes `<survey>_recovered.csx` **and already runs step 2** (`<survey>_recovered_pp.csx` → continue at step 3). Background + validation: [projects/0003-tdx-zip-recovery](../projects/0003-tdx-zip-recovery/brief.md). Export-bundle zips (csx/dxf/csv collections) are not project archives and are skipped.
2. **Pre-process:** double-click **`csurvey_preprocess_tdx.bat`** (preprocesses every raw
   TopoDroid csx under `!Za digitalizirat`; `_pp` outputs and post-import saves are skipped
   automatically), or drag specific `.csx` files onto it. Terminal equivalent (takes files or a folder):
   `python stages\3N-nacrt\production\tools\preprocess_tdx_csx.py "<...>\!Za digitalizirat\SB_<broj>_<Ime>\<survey>.csx"`
   → `<survey>_pp.csx` + a report; read the ⚠ warnings (they list what will degrade).
3. **Import:** open `<survey>_pp.csx` in cSurvey (fix-up chain + therion calculation run automatically), then **Save As** your working file (either save type — `.csz` or `.csx` — is fine).
4. **Post-fix (do it right after Save As, *before* you start mapping — else lines stay straight):**
   drag your saved working file onto **`csurvey_fix_tdx.bat`** (accepts `.csz` **or** `.csx`, one or more files), or
   `python stages\3N-nacrt\production\tools\fix_imported_linetypes.py <saved>.csz`
   → `<saved>_lt.<same ext>`; **open that one and do all mapping in it** — it is the finished import (decorated lines, sizes, water brush). This is what flips imported slope/gradient/etc. lines from *Line style: Straight line* (decorations hidden) to *Splines* so their graphics render; cSurvey stamps decorations per straight segment and only spline lines take the curve branch. Skipping this step is why decorated lines show up plain. The fixer **blocks** (with instructions) if you hand it a not-yet-imported file, and is safe to re-run.
5. **Optional:** `inspect_survey.py --json` snapshots before/after any step for diffable ground truth (protocol: [pipeline-a-instrumented-run.md](methods/instrumented-run.md)).

**Tuning the mapping:** edit `stages\3N-nacrt\production\tools\tdx-mapping.json` directly, or visually — `python stages\3N-nacrt\production\tools\make_signs_catalog.py`, open `tdx-mapping-workbench.html` (+ `cs-targets.html` side by side), type target numbers (`105 r`, `12 o90`, `label:!`, `leave`), export, replace the json. Sizes/water/splines live in the json's `postimport` section. Re-run steps 2–4 after changes, and `python prod\build_csx_kit.py --publish` to push the new mapping into `csurvey_alati\`.

## Known limits

- Deliberate `user` tools are unmappable by design (X-box/plain line/plain soil) — prefer named tools on the phone.
- Designer-only cSurvey tools (presumed line variants, faults, concretion, "Acqua (non standard)"… — listed at the bottom of `cs-targets.html`) are unreachable at import; the post-import fixer covers water, others need manual re-typing or a future generalized re-typer.
- After a cSurvey upgrade, re-copy the signs pack (install dir may be overwritten) and re-scan (`make_signs_catalog.py`).
- Upstream fix candidates (parked behind the DevExpress build): accumulate decoration distance across segments; spline linetype in `ConvertItem`; preserve the therion name on unmapped items; new enum members (real water-drip, danger, ±).
