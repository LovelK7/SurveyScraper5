# Implementation log: Symbol themes

Brief: [brief.md](brief.md)

---

### 2026-10-04 — viability research (agent) ✅

- **Did:** two read-only digs — the 3N mapping pipeline/kit and cSurvey's clipart, pen and brush code; checked sign-item XML in the SB 1103 fixture.
- **Result:** viable with no cSurvey build: signs reference a hash-keyed glyph pool, and `type="98"` library pens/brushes exist in the format; the importer is hard-coded, so themes apply post-import (KORAK 2). Constraint: SVG colours are ignored — fill = item brush colour (white stays white), outlines = item pen.
- **Evidence:** brief §2.
- **Next:** user answers §3.5; user makes the T0 oracle file.

### 2026-10-04 — user answers, scope set to signs (both) ✅

- **Did:** recorded the answers (brief §3.5); checked whether the `tdxpp:` marker survives import.
- **Result:** signs first, one colour per symbol, B/W also blackens the centerline. Key = cSurvey sign name, because `tdxpp:` is absent in all 10 post-import files under `example/`. The Illustrator set is one artboard, so the recipe is one named group per symbol + an export with layer-name IDs, and T1 splits it.
- **Evidence:** brief §2.4, §3.1, §3.5.
- **Next:** T0 (user) ∥ T1.

### 2026-10-05/06 — user's drawing catalogue reviewed, three passes (both) ✅

- **Did:** reviewed `drawing_catalogue.svg` (27 groups on `Znakovi`/`Linije`/`Površine`) against the cSurvey SVG subset; settled double-line meanders (centred, base pen off), dashes (pen setting), decoration placement (`cClipartOnPath.vb`), and the per-scale tuning (scale rules).
- **Result:** the file is ready as the T1 fixture. The user decided: `vegetable-debris` kept as is, `rope` = a plain red pen. Points recover their TopoDroid name 1:1 by coordinates (symbol-zoo run), so T8 was added.
- **Evidence:** [findings/drawing-catalogue-review.md](findings/drawing-catalogue-review.md), brief §2.4, §3.1 addendum, §3.7.
- **Next:** T0 (user oracle) ∥ T1 (splitter on this fixture) ∥ T8 (name-recovery spike).

### 2026-10-06 — T8 spike: TopoDroid names recovered after import (agent) ✅

- **Did:** read the import code (`cImportTopoDroidHelper.vb` ConvertItem/pConvertItem, `cPoints.vb` Parse) and compared items by hand. Built `production/tools/tdx_name_recover.py` (`recover PRE POST.csx|.csz [--json]`, stdlib). It matches per sequence: an exact coordinate set first, then a tolerant point/polyline coverage match with an ambiguity margin. Misses, ambiguities and cSurvey-drawn items are reported, never guessed. Tests: `tests/test_tdx_name_recover.py` (synthetic inline pair + real pairs skipped when absent). Ran it on every pre/post pair in the repo, plus the KORAK 2 output made from them in scratch, plus simulated edits.
- **Result:** the import copies coordinates unchanged, reverses the order unless `reversed="1"`, and only re-encodes the flags (`BS<guid>`). KORAK 2 merges walls into one multi-sequence item. **100 % points / lines / areas recovered, all exact, 0 ambiguities, on every pair.** Pairs: zoo ×3, rupe ×6 (real TopoDroid export) and bunker_studena ×2 (real cave). The only items not recovered were 3 drawn in cSurvey, all reported as `native`. Simulated edits degrade to reported misses with 0 wrong names. No real-cave pair with hand edits after KORAK 2 exists in the repo.
- **Evidence:** [findings/t8-name-recovery.md](findings/t8-name-recovery.md); `python -m pytest stages/3N-nacrt -q` 270 passed; pipeline doctor 0 fail.
- **Next:** orchestrator/user decides whether to switch the theme key to TopoDroid-first (brief §3.1 addendum) and add TopoDroid-name rows to §3.7. Optionally, the user supplies a real `_prep` + hand-edited `_postp` pair to measure the edit case.

### 2026-10-06 — T1: `theme_svg.py split|normalize|check` (agent) ✅

- **Did:** built `production/tools/theme_svg.py` (stdlib only). It resolves styles, including `<defs><style>` classes; bakes transforms; turns arcs into cubics and circles, ellipses, rects, lines and polys into `M L C Q Z` paths; drops shapes with no fill and no stroke; flattens fills to `#FFFFFF`/`#000000`/none; keeps strokes and reports their widths; reports image, use, text, clip, mask and opacity. Signs get `csurvey:sign` (cSurvey name → `tdx-mapping.json` `to` → TopoDroid natural) and `csurvey:scale` (size ÷ the median sign). `check` mirrors `cDrawPaths.vb`: arcs, ellipses, space-separated or multi-function transforms, transforms lost on grand-parent groups, and the fill-inheritance gap. Tests in `tests/test_theme_svg.py` (18).
- **Result:** the catalogue splits into 12 signs, 9 lines and 6 areas, every piece written. Converted: 1592 arcs; dropped: 7 invisible rects. The outputs contain 0 arcs, ellipses or transforms. `vegetable-debris`: 45 gradients and 18 colours flattened, 117 strokes (0.1–0.3). Area `blocks`: 54 strokes. No `csurvey:sign` for `danger`, `plus`, `minus`, `plus-minus` and `bones` (T8). Found: `tree-trunk` and `vegetable-debris` both resolve to sign 33. In `continuation`, the "?" sits about 900 units from its circle in the export (scale 25×, flagged as a stray). All 79 stock `Cliparts\Signs` glyphs pass `check` with 0 errors.
- **Evidence:** [findings/t1-split/](findings/t1-split/) (outputs + `report.json`); `python -m pytest stages/3N-nacrt -q` 288 passed; pipeline doctor 0 fail. A headless-Edge side-by-side (bones, vegetable-debris, floor-meander, slope, pebbles, blocks) shows the geometry identical to the source.
- **Next:** user moves the "?" back into `continuation` and decides tree-trunk vs vegetable-debris for sign 33; T2 (theme format) can consume `t1-split/*/index.json`.

### 2026-10-06 — T2: theme format + loader `themes.py` (agent) ✅

- **Did:** built `production/tools/themes.py` (stdlib only): `load_theme` (`extends` deep merge, child wins, cycles rejected, `null` drops an inherited entry; `monochrome` forced on every sign/line/decoration/area colour and every centerline colour), `resolve` (TopoDroid name → cSurvey target → None), `list_themes`, `validate`, plus `list` / `check` / `show`. Keys are checked against `tdx-mapping-catalog.json` (TopoDroid names incl. subtypes, or targets; point targets compared without dashes). Colours become signed ARGB ints, as in `postimport.centerline`. SVG paths resolve against the folder of the theme that wrote them and must exist. Centerline names come from `fix_imported_linetypes.CENTERLINE_TYPES`; `scale_rules` take scales 100/200/250/300/400/500 and an allow-list of 13 `Design*/Base*ScaleFactor` properties. Hooked into `check_defaults.py`: every theme, plus a top-level `"theme"` in `tdx-mapping.json` if one is ever set (none today; the file is unchanged). Starter themes: `production/themes/boja/` (the 16:45 re-export of `findings/t1-split/` copied in; colours = each group's dominant non-white fill in `drawing_catalogue.svg`, near-black → `#000000`; `rope` a plain `#EF5553` pen of width 0.1; `floor-meander` with style none, alignment center, spacing 0) and `crno-bijelo` (`extends boja`, `monochrome #000000`). Docs: `production/themes/README.md`, a row in `production/README.md`. Tests: `tests/test_themes.py` (26).
- **Result:** both themes check clean: 12 signs, 10 lines, 6 areas each. `crno-bijelo` also forces 6 centerline colours. Found: cSurvey reads a stored `decorationspacepercentage` of 0 as 100 (`cPen.vb:434-435`) and saves it with one decimal, so T3 must write ≥ 0.1 for the meander's butted rails (in the themes README under Known limits).
- **Evidence:** `python -m pytest stages/3N-nacrt -q` 314 passed; `check_defaults.py` OK (2 themes); pipeline doctor 0 fail (3 old link warnings). No `pyproject.toml`/`pipeline.yaml` change: only tool scripts and data under `production/`.
- **Next:** T3 `apply_theme` consumes `themes.load_theme` + `themes.resolve` with the names from `tdx_name_recover.py`. The user confirms the colours in `boja/theme.json`.
