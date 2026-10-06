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

### 2026-10-06 — T3 phase 1: `theme_apply.py` (signs + centerline) (agent) ✅

- **Did:**
  - Built `production/tools/theme_apply.py apply IN.csx|.csz --theme ID --pre PRE [-o] [--dry-run] [--json]` (stdlib).
  - **Lookup:** recovered TopoDroid name (`tdx_name_recover.recover`), then the target of `sign=` (catalog SignEnum → `to`), then untouched.
  - **Glyph:** spliced into `<signs><cliparts>` with the item's `data` repointed. For this, `nacrt_finish.py` gained `clipart_hash`, `clipart_data_path` and `splice_sign_clipart`, which the compass now uses too.
  - **Colour:** an inline custom solid brush plus a TightPen-like custom pen, named `tema:<id>`. Black keeps the built-ins `10`/`7`.
  - **Outline mode:** added `render: fill|outline` to `themes.py` and the themes README.
  - **Size:** a theme `size` is baked into the glyph's `csurvey:scale`. `signsize` is untouched, because cSurvey normalises every glyph to `csurvey:scale` × 1 unit (`cCliparts.vb:80-91`) and `signsize` is a discrete operator enum.
  - **Centerline:** written via `fix_imported_linetypes.apply_centerline`.
  - **Idempotency:** the design properties `CaveDossierTheme` and `CaveDossierThemeState` (JSON: glyphs added, each sign's original glyph, overwritten centerline values) let a re-run undo the previous theme first.
  - **Tests:** `tests/test_theme_apply.py` (11) and a `render` test in `test_themes.py`.
- **Result:**
  - **Hash** = SHA-1 with each byte as *unpadded* uppercase hex (`modMain.CalculateHash` `{0:X1}`). It was verified on all 4 pool entries of SB 1103; ingresso's id has 38 characters. `nacrt_finish`'s old `hexdigest().upper()` was only right by luck for compass3.
  - **SB 1103:** 2 profile blocks themed by TopoDroid name. The 2 entrances are not in the themes; one is a moved-item miss that fell back to its target.
  - **Byte-identical:** boja×2, crno-bijelo×2, boja→crno-bijelo = crno-bijelo, crno-bijelo→boja = boja (centerline restored) and outline→boja = boja. The `.csz` re-apply is also identical.
  - **cSurvey round trip:** a headless load + save keeps the markers, pens, brushes and pool. It only adds the pen's `<clipart data=""/>`, which we now write as well.
  - **Prints:** cSurvey prints all variants with the club glyph, grey in boja, black in crno-bijelo (centerline and labels too), outline as white with an outline, and no clipart_error.
  - **T1 bug:** the theme SVGs carry `csurvey:sign="53"` for blocks, which is the catalog/TopoDroid `num`, not the SignEnum 1290. It is harmless here because the item's `sign=` wins on load (`cItemSign.vb:385`), but it would mis-type the glyph if it were ever added through the gallery.
- **Evidence:** [runs/2026-10-06-t3/RUNLOG.md](runs/2026-10-06-t3/RUNLOG.md) with the PDFs and PNGs (comparison strip `SB_1103_profile_znakovi_usporedba.png`). `pytest stages/3N-nacrt` 326 passed; `check_defaults.py` OK; pipeline doctor 0 fail.
- **Next:**
  - The user judges the prints.
  - T1: fix `csurvey:sign` to emit the SignEnum.
  - Decide whether to keep the pool name as the bare file name (`blocks.svg`, the same as cSurvey's own entry; the id differs).
  - Hook into KORAK 2 / the kit (T5).
  - Phase 2: lines and areas.

### 2026-10-06 — T1 sign-number fix, pool names, zoo sample sheet (agent) ✅

- **Did:**
  - **A. `csurvey:sign` is now the SignEnum value.**
    - `make_signs_catalog.py` writes a `sign` field on every point target in `tdx-mapping-catalog.json`. The value
      comes from its static `SIGN_NAMES` table, so prod needs no cSurvey source.
    - The catalog was regenerated: it is identical apart from that field, and the HTML pages are unchanged.
    - `theme_svg.SignResolver` returns `sign` and maps the `natural` menu numbers through it.
    - Tests: stalagmite 517, blocks 1290, debris→breakdownchoke 261, air-draught 774, plus a check that every
      catalog `sign` equals its gallery SVG's `csurvey:sign`.
    - Re-split `drawing_catalogue.svg` into `findings/t1-split/` and copied the result into `production/themes/boja/`.
      The diff is only `csurvey:sign` (7 signs) and `report.json`. `theme.json` is untouched.
  - **B. Pool naming.** Glyphs that `theme_apply.py` adds to the pool are named `tema-<theme>_<file>.svg` (`pool_name`).
    Switching theme renames the entry rather than stacking it (test added). Production README updated.
  - **C. Zoo sample sheet.** Ran the zoo v3 pair through KORAK 2, then boja and crno-bijelo, and printed the plan
    headless.
- **Result:**
  - 43/43 zoo signs were recovered by name. 8 of the 12 theme signs are in the zoo, and all 8 are themed by
    TopoDroid name. 5 of them replace X-boxes (danger, debris, minus, plus, plus-minus).
  - Not in the zoo: bones, tree-trunk, vegetable-debris and water-flow:intermittent.
  - On the zoo, boja↔crno-bijelo and boja→boja give byte-identical files.
  - Odd: `water-flow:intermittent` resolves to 777 (WaterFlow), because the gallery has no 778 glyph and so the
    catalog has no 778 target. The club glyphs print larger than cSurvey's own. The air-draught arrow hangs below
    its station.
- **Evidence:** [runs/2026-10-06-zoo-sheet/RUNLOG.md](runs/2026-10-06-zoo-sheet/RUNLOG.md) (start with
  `zoo_znakovi_usporedba.png`). `pytest stages/3N-nacrt` 327 passed; `check_defaults.py` OK; pipeline doctor 0 fail.
- **Next:**
  - The user judges the colours on the sheet.
  - Build a zoo v4 with bones, tree-trunk, vegetable-debris and a water-flow:intermittent subtype.
  - Phase 2: lines and areas.

### 2026-10-07 — Round 2: outline pen off, theme mockup (zoo v4), arrow direction (agent) ✅

- **Did:**
  - **Outline pen off.** For fill signs, `theme_apply.py` now writes an inline custom pen with style None (98):
    `<pen type="99" name="tema:<id>" color="…" style="98" width="0.00" …><clipart data=""/></pen>`. This applies to
    black signs too.
    - Verified in cSurvey: `cCustomPen.pRender` sets no GDI pen (`cPen.vb:865-867`), `Render` adds the path with
      `Nothing`, and the sign path goes through `cDrawPaths.Render` → `Item.Pen.Render`.
    - The pen survives a headless load + save unchanged.
    - A new sign field `outline_pen` (default false for fill, forced true for outline) brings back the old look.
      Glyph paths with no fill vanish with the pen off, and the report notes them.
  - **`rotate`.** A new sign field `rotate`, in degrees clockwise, is baked into the glyph coordinates by
    `theme_svg.rotate_svg`. `csurvey:rotationangledelta` was tested and does nothing: no render path reads it.
  - **Theme mockup.** The new `production/tools/make_theme_mockup.py` generates zoo v4. It contains everything in
    zoo v3 plus every key of every theme (read at run time); lines are drawn straight and as a curve, and areas are
    2 × 1.5 m. The line and area rows are walled. The file is imported headlessly through `csurvey_driver recalc`,
    with no GUI step.
  - `boja`: `air-draught` gets `rotate 180` and `water-flow:intermittent` gets `rotate 90`; a `_rotate` note says why.
  - Docs: the production README, plus a "Directional signs" section in `themes/README.md`.
- **Result:**
  - All 12 theme signs are themed on the mockup. The 4 new ones (bones, tree-trunk, vegetable-debris,
    water-flow:intermittent) print with the club glyph; 3 of them replace X-boxes.
  - Name recovery is 47/47 for signs and 154/154 for other items.
  - All 4 theme switches are byte-identical to a single apply, and so is old-pen→boja.
  - The arrows now point north at orientation 0, like cSurvey's own.
- **Odd:**
  - Headless import against `C:\csurvey64` fails with HTTP 429. The cause: 101 gallery SVGs have a w3.org DTD
    DOCTYPE that .NET fetches, and w3.org rate-limits it. Run r2 used a scratch copy with the DOCTYPEs stripped. A GUI
    import may hit the same 429.
  - vegetable-debris loses its 117 stroke-only hairlines with the pen off.
  - With the pen off, a sign whose item transparency is set in cSurvey would throw a NullReference
    (`cPen.vb:1018-1020` reads `oPen.Color` when transparency ≠ 0). Untested; the default transparency is 0.
  - The importer adds +90° only to the exact names `air-draught` and `water-flow`. KORAK 1 maps
    `water-flow:intermittent` to `waterflow`, so cSurvey's own glyph for it points left too.
  - KORAK 1 converts danger, minus, plus, plus-minus and anchor to text labels, so in the real pipeline the theme
    entries for the first four never fire. Round 1 and 2 both skip KORAK 1.
- **Evidence:** [runs/2026-10-07-zoo-sheet-r2/RUNLOG.md](runs/2026-10-07-zoo-sheet-r2/RUNLOG.md) (start with
  `theme-mockup_znakovi_usporedba.png`). `pytest stages/3N-nacrt` 334 passed; `check_defaults.py` OK; pipeline doctor
  0 fail.
- **Next:**
  - The user judges the pen-off look and the colours.
  - Decide whether to map `water-flow:intermittent` → `water-flow` in KORAK 1 (through `/csurvey-defaults`); if so,
    drop its `rotate`.
  - Decide what KORAK 1 does with danger, minus, plus and plus-minus now that they have club glyphs.
  - vegetable-debris: set `outline_pen: true` or redraw the strokes as fills.
  - Phase 2: lines and areas.
