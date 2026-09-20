# production/tools — Stage 0 survey inspector (+ TDX recovery tools)

## TopoDroid zip → csx recovery (`tdx_zip_to_csx.py`, `parse_tdr.py`, `csurvey_3_oporavi_iz_zipa.bat`)

Regenerates a raw-TopoDroid `.csx` (centerline **and** sketch) from a TopoDroid **project zip**
(`manifest` + `survey.sql` + `.tdr`), replaying TopoDroid's own csx exporter offline. Built in
[projects/0003-tdx-zip-recovery](../../projects/0003-tdx-zip-recovery/brief.md) after TopoDroid
6.4.99 shipped a 0-byte-csx crash and a tdr format bump that older app versions silently refuse
(sketches vanish on cross-version zip import — the data is fine, the readers aren't).

```
python production/tools/tdx_zip_to_csx.py <project.zip | folder> [more.zip ...] [--sb 811 908] [--raw-only]
```

- A folder argument is scanned recursively for project zips (non-project zips are skipped by a
  manifest+survey.sql sniff); `--sb` narrows that scan to the named caves' `SB_<broj>_…` leaves
  ([`sb_select.py`](sb_select.py), shared with the pre-processor). Outputs land next to each zip: `<survey>_recovered.csx` and — via an
  automatic `preprocess_tdx_csx.py` pass — `<survey>_recovered_pp.csx`, the one to import.
- **No-typing path:** `csurvey_3_oporavi_iz_zipa.bat` (published to
  `!!!Digitalizacija/SurveyScraper5/` by [`prod/build_csx_kit.py`](../../../../prod/build_csx_kit.py))
  — double-click, type the Redni broj of the caves to recover (or `SVE`), or drag zips onto it. Its
  sibling **`csurvey_1_pripremi_csx.bat`** does the same for the normal (non-recovery) flow:
  double-click and name the caves = preprocess their *raw* TopoDroid csx (sniffed by
  `creatid="TopoDroid"` without `creat_postprocessed`; `_pp.csx` outputs and post-import saves
  skipped), or drag csx files onto it. A third, **`csurvey_2_dovrsi_uvoz.bat`** (double-click = Redni broj, then pick the file to finish
  from a numbered menu of that cave's `.csz`/`.csx`, each annotated with whether cSurvey has saved
  it yet),
  runs the *post-import* fixer (`fix_imported_linetypes.py`) — drag the file you made with **Save
  As** after importing onto it to get `<name>_lt.<same ext>` (splines so decorations render, sizes,
  water brush); run it right after Save As and map in the `_lt` file. It accepts **both `.csz` and
  `.csx`** (whichever you saved — the rich zip is rewritten in place, all other entries preserved)
  and **blocks with instructions** if handed a not-yet-imported (raw/`_pp`) file, so you can't run
  the wrong step. The digit in each name is the running order, and all three print a runtime KORAK
  banner and carry a runtime "what to do next" footer, in Croatian; they are **generated** from [`prod/csx_templates/`](../../../../prod/csx_templates/) and
  find these tools in the `csurvey_alati/` folder published beside them, so they work on any
  machine (a developer path is only the last fallback rung). `preprocess_tdx_csx.py`
  and `fix_imported_linetypes.py` both also accept multiple files (the latter a folder-worth of
  dragged files) directly. **A plain-language Croatian operator guide — `csurvey_0_PROCITAJ_ME.txt` — is
  published beside the launchers** (the human entry point; the markdown protocol is its technical
  counterpart).
- `parse_tdr.py FILE.tdr [--items] [--json out]` is the underlying all-version `.tdr` binary reader
  (also a standalone diagnostic: proves whether a sketch file is intact).
- Only project zips work as input — TopoDroid's "export bundle" zips (csx/dxf/csv collections)
  contain no tdr/sql and are rejected. Multi-plot surveys: only the first plan + first profile plot
  are converted (matches TopoDroid's own csx export).

---

`inspect_survey.py` is the Stage 0 tool from [reference/mcp-blueprint.md](../../reference/mcp-blueprint.md):
a **read-only** command-line inspector for cSurvey `.csz` / `.csx` files. It needs no build, no
DevExpress, no therion — just Python 3 (stdlib only). Task brief:
[projects/0001-stage0-inspector/brief.md](../../projects/0001-stage0-inspector/brief.md).

Its headline number is the **count of drawing items per design** — the answer to *"does this
survey carry a usable phone sketch?"*, which decides whether the TopoDroid→map pipeline is
already implemented (Pipeline A) or needs wall synthesis from splays (Pipeline B).

## Usage

```
python production/tools/inspect_survey.py FILE [FILE ...] [--json]
```

- One report per file; with 2+ files, a summary table is appended (same columns as the
  verified baseline table in the task brief §4).
- `--json` emits a machine-readable report with **stable, sorted keys** — designed so two
  reports of the same survey (e.g. saved before/after a manual UI step) can be diffed:

```
python production/tools/inspect_survey.py --json before.csz > before.json
python production/tools/inspect_survey.py --json after.csz  > after.json
git diff --no-index before.json after.json
```

Guarantees: never writes or repacks a survey, never extracts zip entries to disk (all
in-memory), parses numbers invariant-culture (`.` decimal, locale-independent).

## ⚠ The two-sketch-shapes gotcha

A sketch can be stored in **two different XML shapes**, and confusing them produces the exact
false negative this tool exists to prevent:

| Shape | XML path | Written by |
|---|---|---|
| **Nested (native / post-import)** | `<plan>/<layers>/<layer>/<items>/<item>` | cSurvey's own serializer |
| **Flat (raw TopoDroid, pre-conversion)** | `<plan>/<item>` — direct children, no `<layers>` | TopoDroid's csx export ("TCsx") |

The flat shape is materialized into the nested one only by the TopoDroid fix-up chain
(`cImportTopoDroidHelper.ConvertDesign`) when cSurvey loads the file. A counter that only
looks inside `<layers>` reports **0 items for a raw TopoDroid export carrying a full phone
sketch** — which would wrongly send the project down the synthesize-walls-from-splays road.

The tool therefore counts **both shapes separately and labels them explicitly** in every
report (`nested (native <layers> shape)` vs `flat <item> (raw TopoDroid shape)`); the
summary "Items" column and JSON `sketch.total_items` are the sum of both, across plan and
profile. Legacy TopoDroid *empty*-sketch exports write a bare `<layers>` skeleton, so
"nested shape present but 0 items" is also a meaningful (and reported) state.

## What a report contains

- **Provenance verdict** — one of: *raw TopoDroid export* (`creatid="topodroid"`,
  case-insensitive, without `creat_postprocessed`), *post-import* (both present),
  *native cSurvey*, *other*. Plus `creatversion`/`creatdate`, file format version,
  custom datatable field definitions, and decoded `import_source` / `import_date` /
  `import_source_type` stamps from the pipe-positional `<datarow>` elements.
  Raw DistoX attributes (`g`/`m`/`dip`/`distox`) on segments are flagged as an extra
  raw-TopoDroid marker.
- **Centerline** — segments = shots + splays (`splay="1"`), trigpoints, count of shots with
  any nonzero LRUD, caves / branches / sessions, origin station (warns when unset — the
  centerline plot renders nothing without one).
- **Sketch** — per design (plan / profile): item counts in both shapes (nested broken out
  per layer, flat broken out per `type` and therion symbol `name`), per-design point
  totals split **bound vs unbound** (`S<guid>` tokens in `points@data`; unbound items never
  warp when the centerline changes), a count of items with zero bound points, and a
  **geometry digest** (bounding box + coordinate checksum) so that warping — which moves
  points without changing any count — shows up when diffing two reports.
- **Container** — zip entry count and asset classes (`_data/cliparts`, `_data/design`,
  `_data/surface`, `_data/design3d`), `_data.xml` size. `.csx` = bare XML. Extension chooses
  the format exactly as `cFile.vb` does; content that contradicts its extension is reported
  loudly (cSurvey itself would fail on such a file).
- **Cross-sections** — element count.
- **Calculate** — whether the file carries cached results (station count, speleometrics);
  absent means cSurvey recalculates on load, which requires therion.

## Verification status

Reproduces the verified nine-file baseline table (task brief §4, `cSurvey/cSurveyPC/data/`) exactly —
including `test extend 2.csz` = 1 item / 31 points all bound, and `buless_test1.csz` = 0 items
despite its 46 cliparts. On 2026-07-18 the tool ran on the first **real** TopoDroid export
(`example/ponor_rupa_babi_pod_kucu-1p.csx`, gitignored): verdict *raw TopoDroid export*,
34 flat items — the flat-shape counting and TopoDroid verdicts are validated against reality,
not just against synthetic fixtures. See
[projects/0002-tdx-symbol-mapping/runs/2026-07-19-ponor-import/](../../projects/0002-tdx-symbol-mapping/runs/2026-07-19-ponor-import/RUNLOG.md) for the
instrumented import run built on this tool, and
[production/methods/instrumented-run.md](../methods/instrumented-run.md) for the
protocol. When any file contradicts the docs, trust the file.

---

## Nacrt finishing (KORAK 3)

The tools of [projects/0004-nacrt-finishing](../../projects/0004-nacrt-finishing/brief.md) —
what the operator still does by hand inside cSurvey after the import is finished.

| Tool | Role | Run when |
|---|---|---|
| [`nacrt_finish.py`](nacrt_finish.py) | The XML finisher. Takes the corrected `_lt.csx`/`.csz` and writes `<name>_lt_fin.<same ext>` + `<name>_lt_fin.layout.json`: flags the entrance `<trigpoint>`, adds the Dislivello quota at the profile's lowest floor point, the horizontal scale bar right of the plan and the `N` arrow above it, then writes the A4 print layout into `_preview.plan`/`_preview.profile` and the render quality into `<sharedsettings>`. Never touches the input, and preserves every other byte of it | Right after the sketch is corrected and saved in cSurvey, before the headless print: `python nacrt_finish.py <file>_lt.csx` (or `<intake> --sb 1103`). `--dry-run` reports without writing; `--yes` / `--layout N` skip the layout menu |
| [`nacrt_layout.py`](nacrt_layout.py) | Scale + page-arrangement chooser: picks the largest of 1:100 / 1:200 / 1:250 / 1:300 / 1:400 / 1:500 at which each design fits (plan and profile independently — `scalemode` 1/2/3/4/99+`scale`/5 — but never more than one rung apart), stacks them in the band below the sastavnica title block (profil on top) or side by side, and returns the `Mjerilo` string plus up to three alternatives | Called by the finisher (it supplies the `_preview.*` scale) and by the compositor; or by hand, `python nacrt_layout.py <plan_w> <plan_h> <profile_w> <profile_h>` (metres), to preview the proposal and its alternatives as a numbered menu |
| [`csurvey_driver.py`](csurvey_driver.py) | The Python face of the headless driver: runs the `.ps1` below, enforces the timeout it cannot enforce on itself, maps its exit codes onto one `DriverError` and parses its JSON. `finish_and_print()` is the whole step in one call — recalculate, print both PDFs, read the dimensions, and write `<name>_dimenzije.json` next to them with the finisher's `mjerilo`/scales/placements merged in | After the finisher, on the `_lt_fin` file: `python csurvey_driver.py finish <file>_lt_fin.csx -o <dir>` (or `<intake> --sb 1103`). Also `info` / `recalc` / `print` / `dimensions` one at a time |
| [`csurvey_headless.ps1`](csurvey_headless.ps1) | Drives the **installed** `cSurveyPC.exe` as a library by reflection — no build, no DevExpress licence, no dialog. `info`, `recalc` (this is what fills `<sms>` with the entrance-relative `pvr`/`nvr`/`es`), `print` (the `_preview.*` options in the file decide scale and paper), `dimensions` (one JSON object on stdout) | Normally only through `csurvey_driver.py`; by hand for debugging, `powershell -STA -NoProfile -ExecutionPolicy Bypass -File csurvey_headless.ps1 -Survey <f> -Command info` |

**The driver's two per-machine facts** are `CSURVEY_DIR` (default `C:\csurvey64`) and
`CSURVEY_PRINTER` (default `Microsoft Print to PDF`), read from the environment and
then from the workspace `.env` — see [`.env.example`](../../../../.env.example).
The `.ps1` **must** run under Windows PowerShell 5.1 with `-STA` (the print path
constructs a WinForms form, never shown), which is why the wrapper spawns it rather
than importing anything. Exit codes are `0` ok · `2` usage · `3` cSurvey internals
changed (the missing member is named) · `4` load · `5` calculate · `6` print. A clean
run can still write to stderr: cSurvey shells out to therion's `cavern`, and a machine
without it on PATH says so while the calculation itself succeeds — judge a run by its
exit code. Everything is fail-soft: with no cSurvey installed the finisher's `.csx`
is still there for the operator to open and print in two clicks.

Stdlib only and free of repo imports, like every tool here, so they travel into the
operator kit — `nacrt_finish.py` ships with one asset beside it,
[`nacrt_finish_compass.xml`](nacrt_finish_compass.xml), the `compass3.svg` clipart
element it splices into a survey that does not already carry a north arrow. The page
geometry is derived from the cell table in
[4S sastavnica-design.md](../../../4S-sastavnica/docs/sastavnica-design.md); the
scale and arrangement rules are the user's, recorded in brief §3.4.

**Two things the finisher deliberately does not do.** The depth label the profile
shows next to the Dislivello (`-9 m` on SB 1103) is written by cSurvey at paint
time out of `quotavalue="0"` and the entrance station, not by us — the item goes
out with `text=""`. And the entrance decision is two independent witnesses
(highest station by `z`, plus the entrance sign the surveyor drew), reported
separately in the sidecar JSON and in `--dry-run`, so the rule can be re-weighed
once more than one real cave has been through it.
