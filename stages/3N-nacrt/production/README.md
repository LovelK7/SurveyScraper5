# production/ — what we run routinely

The "shipped" surface of the fork: the tools, procedures, and config we run on **real surveys**,
plus the run-verified knowledge they depend on. Everything here has been through a project's
validation and was accepted on real data — if something is still being figured out, it lives in a
[projects/](../projects/README.md) folder, not here.

## The standing procedure

**[tdx-processing-protocol.md](tdx-processing-protocol.md)** — the step-by-step SOP for turning a
phone-drawn TopoDroid survey into a finished Nacrt. Operational since 2026-07-26; KORAK 3, which
carries it past the import all the way to `SB_<broj>_nacrt.pdf`, joined the standing protocol
2026-09-20 ([project 0004](../projects/0004-nacrt-finishing/brief.md)). Start here for routine
survey processing.

## Toolkit (`tools/`)

| Tool | Role | Run when |
|---|---|---|
| [`csurvey_0_PROCITAJ_ME.txt`](../../../prod/csx_templates/csurvey_0_PROCITAJ_ME.txt.template) (published into `!!!Digitalizacija/SurveyScraper5/`) | the Croatian operator guide for the whole routine (drag-drop, the SB-number prompt, the `_pp`/`_lt`/`_lt_fin` endings, black-window messages); KORAK 1 → 2 → 3, with the zip rescue at the bottom as KORAK 9 | the human starting point — read before running anything |
| [`inspect_survey.py`](tools/inspect_survey.py) | read-only stats/diff report for any `.csz`/`.csx` (Stage 0) — see [tools/README.md](tools/README.md) | inspecting or diffing any survey, before/after any step |
| [`preprocess_tdx_csx.py`](tools/preprocess_tdx_csx.py) | rewrites a raw TDX export so symbols survive import (renames, label conversions, stroke reversal, orientation) | on the raw phone export, before opening in cSurvey |
| [`fix_imported_linetypes.py`](tools/fix_imported_linetypes.py) (drag-drop: `csurvey_2_dovrsi_uvoz.bat`) | post-import fixer for what import can't express (**spline linetypes so slope/gradient/etc. line decorations render**, non-standard water brush, sign/label sizes) | right after **Save As**, before mapping — then map in the `_lt.csx` |
| [`nacrt_finish.py`](tools/nacrt_finish.py) + [`nacrt_layout.py`](tools/nacrt_layout.py) + `nacrt_finish_compass.xml` (drag-drop: `csurvey_3_dovrsi_nacrt.bat`) | KORAK 3, XML half: flags the entrance, measures the entrance opening for the OSZ (`entrance_dims.py`: Broj / Širina / Visina ulaza → the sidecar's `entrance_size`, only when a sign or a surface leg names the station), writes the Dislivello quota, the horizontal scale bar and the north arrow, and the A4 print options at a scale chosen per design → `_lt_fin` + a `.layout.json` sidecar. The layout menu draws each option as an ASCII sketch of the sheet (sastavnica, profile, plan) | after the sketch is corrected in the `_lt` file and saved |
| [`csurvey_headless.ps1`](tools/csurvey_headless.ps1) + [`csurvey_driver.py`](tools/csurvey_driver.py) | KORAK 3, cSurvey half: drives the installed cSurvey by reflection — `info` / `recalc` / `print` / `dimensions` / `finish`, no dialog → `_plan.pdf`, `_profile.pdf`, `_dimenzije.json` | right after the finisher; the only step that needs cSurvey installed |
| [`make_signs_catalog.py`](tools/make_signs_catalog.py) → `tdx-mapping-workbench.html` + `cs-targets.html` + `tdx-mapping-catalog.json` | visual mapping editor: every TDX tool → numbered cSurvey targets; exports the mapping json. The catalog json carries the same pictures (TopoDroid's own colours for lines and areas) for the dashboard's **3N › Mapiranje simbola** page | when tuning the mapping; after a cSurvey/TopoDroid upgrade |
| [`tdx_mapping.py`](tools/tdx_mapping.py) | the mapping a survey is processed with: shared `tdx-mapping.json` + the cave's own `tdx-mapping-objekt.json` (only the differences; written by the dashboard). KORAK 1 and 2 import it; `python tdx_mapping.py show FILE` prints the result — see [csurvey-settings.md](csurvey-settings.md#per-cave-mapping-the-dashboards-mapiranje-page) | read by KORAK 1/2 for every file |
| [`tdx-mapping.json`](tools/tdx-mapping.json) | **the user-owned mapping** the pre/post-processors read; its `postimport` section also holds the cSurvey **file settings** KORAK 2 writes into every `_lt` (red centerline, sizes, any typed `designproperties`) — see [csurvey-settings.md](csurvey-settings.md) | edit to change how symbols map, or a predefined file setting |
| [`csurvey_app_settings.py`](tools/csurvey_app_settings.py) + [`csurvey-app-settings.json`](tools/csurvey-app-settings.json) (double-click: `csurvey_0_postavi_csurvey.bat`) | KORAK 0: primes cSurvey's **app settings** (registry, per user per computer — e.g. pen smoothing off); refuses while cSurvey is open; `check` is KORAK 2's warning, `show` compares profile vs this computer — see [csurvey-settings.md](csurvey-settings.md) | once per computer, before the first survey; again when KORAK 2 warns |
| [`sb_select.py`](tools/sb_select.py) | turns the Redni broj an operator types into that cave's `SB_<broj>_…` intake leaf and picks the file at that step by itself — the `_lt` for KORAK 3, the file cSurvey saved for KORAK 2; cSurvey's `_backup` copies are never offered — asking only when a cave has none or several (`--sb` on all three tools) | whenever a launcher asks which caves, or which file |
| [`signs-pack/`](tools/signs-pack) | 8 SVG glyphs for mapped-but-artwork-less signs; installed into cSurvey's Signs gallery | after a cSurvey upgrade (re-copy) |

## Predefined cSurvey settings

**[csurvey-settings.md](csurvey-settings.md)** — the two kinds of cSurvey settings (file vs app),
where each is kept, why app settings are primed once with cSurvey closed, what is predefined now,
and how to add a setting.

## Methods (`methods/`)

Reusable procedures that aren't a single script:

- [`methods/instrumented-run.md`](methods/instrumented-run.md) — the save-after-each-step protocol for
  producing diffable ground truth from a manual cSurvey session. The template for any new run under a
  project's `runs/`.

## Reference knowledge produced here

- [`tdx-symbol-matrix.md`](tdx-symbol-matrix.md) — the run-verified TDX symbol → cSurvey outcome matrix
  the SOP and pre-processor depend on. (Produced by project 0002; kept beside the tools that consume it.)

---

*Provenance:* this toolkit was built and validated by [project 0002](../projects/0002-tdx-symbol-mapping/brief.md).
Upstream fix candidates it identified (parked behind the DevExpress build) are noted at the bottom of the
protocol and in the matrix.
