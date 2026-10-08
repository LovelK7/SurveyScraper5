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

### 2026-10-07 — Round 3: phase 2, lines and areas themed; artwork refresh (agent) ✅

- **Did:**
  - `theme_apply.py`: lines get **library pens** (`<pens>`, `type="98"`, one per theme key and built-in pen type),
    areas **library brushes** (`<brushes>`: scatter tile, solid, or parametric pattern), written as cSurvey's
    `SaveTo` writes them; items are re-pointed in place (`type="98" id=…`, the brush `<seed>` kept). Width written
    out from the built-in pen; decoration unit inline, fill only, on the built-in pen's side (`alignment: auto`,
    flipped for Inner pens, the KORAK 1 target's side for a plain pen). Merged items take the majority TopoDroid
    name (a tie is reported). Undo state extended (library ids + built-in types); `<pens>`/`<brushes>` removed again
    if we created them. Signs: automatic −90° for points that reached the importer as `air-draught`/`water-flow`;
    `outline_pen` unset = auto (on for a stroke-only glyph, reported).
  - `themes.py`: area `pattern` (type, angle, density, zoom, pen_style) and `crop`; one look per area (tile / solid /
    pattern); decoration `alignment: auto` + `flip`; spacing default 3000.
  - `theme_svg.py`: strokes outlined into fills in line units and area tiles; even-odd conflict warning;
    `transform_svg` / `flip_svg` / `compact_svg`.
  - Re-split the 20:19 `drawing_catalogue.svg` (findings/t1-split, themes/boja). `boja`: rotates dropped, `water-flow`
    and `water-drip` signs, line scales/spacings, tile zooms/densities, rope red 0.1, water-flow as a dash pen.
    `crno-bijelo`: water → 45° line pattern.
  - Docs: themes README (what is written, line decorations, tiles, known limits), production README, brief §3.2.
- **Result:** on the mockup every theme line (10 keys, 20 items) and area (6 + water) is themed by TopoDroid name;
  rope prints red, ice teal, pebbles/clay ochre, triangles on the stock side, B/W water as 45° lines. Re-apply and
  theme switches are byte-identical; a cSurvey load + save keeps all pens and brushes unchanged.
- **Odd (cSurvey):** User pens with width 0 are hairlines; decoration spacing is counted in rasterised 0.01 m points
  (direction-dependent); decorations and tiles paint fills only; overlapping units cancel even-odd. The double-line
  meander therefore cannot be continuous on curves.
- **Evidence:** [runs/2026-10-07-mockup-r3/RUNLOG.md](runs/2026-10-07-mockup-r3/RUNLOG.md) (start with
  `theme-mockup_linije_usporedba.png`). `pytest stages/3N-nacrt` 347 passed; `check_defaults.py` OK; pipeline doctor
  0 fail.
- **Next:** the user judges lines/areas; decide the meander (gaps on curves vs cSurvey's meander vs another unit);
  water pattern density; then T7 (tune in cSurvey, harvest).

### 2026-10-07 — Round 4: tuning from the user's r3 review (agent) ✅

- **Did:** `theme.json` values only, no code. boja: `ceiling-step` `distance_pct` 0 → 40; `slope:sheer` alignment
  auto (resolved to slope's centre) → `inner` + `flip`, `spacing_pct` 3000 → 5000; `slope:steep` → `inner` + `flip`,
  `scale` 2 → 6.5; `water-flow` dash [26, 8] → [6, 3]; area `stalagmite` `angle_mode` fixed, angle 0. crno-bijelo:
  `water` pattern `density` 1 → 0.33 (basepatterns.xml Lines: spacing = density × zoom, in m).
- **Result:** all five points hold on the print: ceiling-step ticks stand off the line (pit unchanged), sheer and
  steep triangles sit on the line on abyss-entrance's side, sheer gaps ≈ 2×, steep triangles ≈ abyss-entrance size,
  water-flow 6 gaps on the straight sample, stalagmite marks horizontal, B/W water 3× the lines.
- **Odd:** the first decoration unit starts about one pitch in, so sparse sheer shows an empty lead-in (cSurvey).
- **Evidence:** [runs/2026-10-07-mockup-r4/RUNLOG.md](runs/2026-10-07-mockup-r4/RUNLOG.md). `pytest stages/3N-nacrt`
  347 passed; `check_defaults.py` OK; pipeline doctor 0 fail.
- **Next:** the user judges r4; meander decision; T7.

### 2026-10-07 — Round 5: tuning from the user's r4 review; area tiles redrawn (agent) ✅

- **Did:** `theme.json` values plus a re-split, no code. boja: `ceiling-step` `distance_pct` 40 → 0 (ticks back on
  the line), `spacing_pct` 3000 → 4500 ("T T T T", sparser than pit); `overhang` `spacing_pct` 3000 → 1700;
  `slope:steep` = `slope:sheer` (its svg, scale 2, inner + flip, spacing 5000). Re-split the 21:37
  `drawing_catalogue.svg` into `findings/t1-split/` and `themes/boja/`: all six area tiles changed (smaller, sparser),
  colours the same; the `water-flow` line piece is gone from the drawing (unused anyway). Area densities to about the
  new tile size: blocks 1.8 → 0.9, clay 0.6 → 0.45, debris 1.0 → 0.75, pebbles 0.75 → 0.6, stalagmite 0.7 → 0.6,
  ice 0.6 kept — judged on four placement seeds. `test_themes`: unused svg is now `lines/slope@steep.svg`.
- **Result:** on the full-resolution crops ceiling-step ticks sit on the line, 6 vs pit's 9 (straight); overhang ≈ 1.8×
  the triangles, no overlap; steep prints identical to sheer; clay/debris/pebbles/ice/stalagmite even on all seeds.
- **Odd:** blocks stays uneven on some seeds (large tile turned at random; denser only overlaps). `ice` and
  `stalagmite` mockup items have no `<seed>`, so their placement changes on every load.
- **Evidence:** [runs/2026-10-07-mockup-r5/RUNLOG.md](runs/2026-10-07-mockup-r5/RUNLOG.md). `pytest stages/3N-nacrt`
  347 passed; `check_defaults.py` OK; pipeline doctor 0 fail.
- **Next:** the user judges r5 (blocks evenness, B/W blocks weight); meander decision; T7.

### 2026-10-07 — Round 6: tuning from the user's r5 review; area tiles sparser (agent) ✅

- **Did:** `theme.json` values plus a re-split, no code. boja: `ceiling-step` solid → custom dash [4, 2] (× width 3;
  [10, 5] read as hooks), alignment auto (inner + flipped, pit's side) → `outer`, `flip` false (inverted T), spacing
  4500 kept; new area `water` = 45° line pattern, density 0.33, `#24A9D1`. crno-bijelo: own `water` entry removed —
  it inherits boja's pattern and `monochrome` blacks it. Re-split the 22:03 `drawing_catalogue.svg` into
  `findings/t1-split/` and `themes/boja/`: all six area tiles changed (clay 30 → 12 shapes, pebbles 41 → 30, blocks
  and debris spread over larger tiles). Densities relaxed toward cSurvey's own coverage, judged on four seeds:
  blocks 0.9 → 1.8, clay 0.45 → 0.5, debris 0.75 → 1.25, ice 0.6 → 0.85, pebbles 0.6 → 0.7, stalagmite 0.6 → 0.72.
  Recorded (no behaviour change): arrows drawn up with the automatic −90° stay; `vegetable-debris` stays
  fills-only. `test_themes`: water in both themes, black in crno-bijelo; ceiling-step custom + outer.
- **Result:** on the full-resolution crops ceiling-step is dashed with ticks hanging on the side opposite pit's;
  area ink cover roughly halved against r5 (e.g. pebbles 50 % → 27–30 %, clay 46 % → 14–16 %), close to izvorno
  where cSurvey has a pattern; boja water prints as blue 45° lines, crno-bijelo as black.
- **Odd:** blocks stays seed-dependent (2.9 × 1.5 m tile: one seed has a bare quarter); `ice` / `stalagmite` mockup
  items still have no `<seed>`.
- **Evidence:** [runs/2026-10-07-mockup-r6/RUNLOG.md](runs/2026-10-07-mockup-r6/RUNLOG.md). `pytest stages/3N-nacrt`
  347 passed; `check_defaults.py` OK; pipeline doctor 0 fail.
- **Next:** the user judges r6 (ceiling-step dash, area densities, blue water); meander decision; T7.

### 2026-10-07 — Round 7: ceiling-step as a row of ⊤ units (agent) ✅

- **Did:** user on r6: every dash must carry its own tick ("⊤ ⊤ ⊤ ⊤"), not a dash pattern with independently spaced
  ticks. New unit `production/themes/boja/lines/ceiling-step@T.svg`: the split tick (0.829 × 5.083) with a bar
  12.707 × 0.829 along its foot, one fill-only path, normalised and checked with `theme_svg.py`. boja
  `ceiling-step`: `svg` → that unit, `style` custom dash [4, 2] → **none** (base off, like floor-meander),
  `scale` 2 → **1.5**, `spacing_pct` 4500 → **1400**, `outer` + `flip` false kept. crno-bijelo inherits; pit unchanged.
  `test_themes`: ceiling-step style none + the T svg; `lines/ceiling-step.svg` now unused (kept as split output).
- **Result:** every T has its bar on the line path and its stem on the side opposite pit's ticks; gaps 0.5–0.7 bar
  lengths; 4 T's on the straight, 2 on the curve (boja and crno-bijelo identical). Scale 2 gave a 0.64 m bar and only
  2 T's on the straight; spacings 1200/1280 left gaps under half a bar, 1500 fewer T's.
- **Odd:** on the mockup's short sine only 2 T's land (units are straight chords; placement quantised). The r7 boja
  PDF was locked by another process on the final print; the identical scratch print (same `.csx`, byte-compared) was
  copied in.
- **Evidence:** [runs/2026-10-07-mockup-r7/RUNLOG.md](runs/2026-10-07-mockup-r7/RUNLOG.md). `pytest stages/3N-nacrt`
  347 passed; `check_defaults.py` OK; pipeline doctor 0 fail.
- **Next:** the user judges r7 (T size / density); meander decision; T7.

### 2026-10-06 — theme_round.py: one tuning round in one command (agent) ✅

- **Did:** `production/tools/theme_round.py LABEL [--split] [--themes] [--focus] [--seeds N] [--fresh-mockup] [--no-print]`
  replaces the hand procedure of r2–r7 and the scratchpad helpers (compose3 sheets, crop/zoom details, seedrun,
  measure.py ink cover, harvested into the tool). `--split` re-splits the drawing into `findings/t1-split/` and
  refreshes `themes/boja/` artwork (never `theme.json`, never deletes), with a change summary and loud `!!` warnings
  (unnamed groups, `_x3C_Group` ids, duplicates, stroke-only pieces, new keys without an entry). The mockup import
  (DTD-free cSurvey copy, KORAK 2, fixed seeds, izvorno print) is cached in the gitignored
  `<workspace>/runs/theme-round/` keyed by the symbol lists + generator/KORAK 2/mapping/cSurvey hashes. Prints run in
  parallel. Each run folder gets comparison sheets per kind (izvorno · themes, per-slot crops at fixed dpi), focus
  details at 2000 dpi, a seed sheet + ink-cover table, `pregled.png`, theme.json copies (diffed against the previous
  round) and an auto-written `RUNLOG.md` with an empty "Feedback → change" table.
  `make_theme_mockup.py`: `seed_areas` / `--seed-imported` give every area item a fixed seed after import (fixes the
  ice/stalagmite random placement of r5/r6). New `production/tools/theme_tuning_cheatsheet.md` (feedback → field →
  direction, limits, artwork rules). `tests/test_theme_round.py` (7 tests).
- **Result:** [r8-baseline](runs/2026-10-06-r8-baseline/RUNLOG.md) (`--fresh-mockup --focus ceiling-step,water
  --seeds 2`): 33.6 s (42 s the very first time, with the 175 MB cSurvey copy); [r8-repeat](runs/2026-10-06-r8-repeat/RUNLOG.md)
  from cache: 15.1 s, theme.json "no change" against r8-baseline, all 20 area crops pixel-identical between the two
  rounds (ice and stalagmite included). Name recovery and themed counts equal r7's. `--split` on the 22:03 drawing:
  0 changes (no-op on tracked files).
- **Evidence:** `pytest stages/3N-nacrt` 354 passed; `check_defaults.py` OK; pipeline doctor 0 fail.
- **Next:** drive rounds from a skill with the cheatsheet; T7.

### 2026-10-07 — Round 9: user's r8 feedback (agent) ✅

- **Did:** re-split (vegetable-debris and slope redrawn); `abyss-entrance` spacing 1700; `ceiling-step` 1400 → 1100;
  `snow` = ice's tile; `wall:presumed` at wall's thickness (width 3.5, dash [14, 5]; r9b–r9f measured 3/5/4/3.5).
  P01: the anchor → label "f" mapping already exists (KORAK 1); the mockup skips KORAK 1, so it shows the glyph.
  Evidence: [r9-feedback](runs/2026-10-07-r9-feedback/RUNLOG.md), [r9f-wall](runs/2026-10-07-r9f-wall/RUNLOG.md).
- **r10:** new entries wall:blocks / wall:debris / wall:ice / user (line + area); stalagmite's svg pinned (group left the
  drawing). wall:presumed verified on PDF vectors (0.127 mm = wall). Open: tile outline = cSurvey's brush pen
  (`BrushLinesScaleFactor`, needs a theme_apply feature); debris/blocks exported as grey fills (redraw); mud → sand is a
  mapping change. [r10-new](runs/2026-10-07-r10-new/RUNLOG.md).- **r11:** user area upright; wall:blocks / wall:debris / wall:ice / user units butted (990); wall:blocks and
  wall:debris with no base line; wall:ice line in ice blue; stalagmite = user's tile. Blocks printed as rings: `crop: none`
  merges a tile into one even-odd path, and each stone is drawn as outer + inner fill → dropped crop none (r11b, filled).
  Split fix: `theme_svg.close_subpaths` closes filled open polylines (SVG fills them as closed). [r11-butt](runs/2026-10-07-r11-butt/RUNLOG.md),
  [r11b-blocks](runs/2026-10-07-r11b-blocks/RUNLOG.md).
- **r12 (tile outline):** user asked for a thinner tile outline on ice. `BrushLinesScaleFactor` 0.02 written into
  the survey's and then every `<options>` profile's designproperties: the PDF outline stayed 0.375 pt (one device
  pixel at 192 dpi, the floor). Change reverted, no theme field. Fix is thinner ice arms in the drawing. Debris stones
  stay solid (user). [r12b-outline](runs/2026-10-07-r12b-outline/RUNLOG.md).

### 2026-10-07 — T4, T5, T9; mud → sand (agent) ✅

- **T4:** Tema card on Mapiranje simbola; `"theme"` in the cave override (`tdx_mapping.diff/merge`); theme previews
  served by `GET /api/mapping-theme/<id>`; line sides via `theme_apply.side_for`.
- **T5:** KORAK 2 themes the `_postp` (`theme_apply.korak2_step`, `find_pre`, fail-soft, `--no-theme`); kit v1.7
  ships the theme tools and `csurvey_alati/teme/`. Real cave (bunker_studena): 22 signs, 9 lines, 2 areas; headless
  print OK; run from the staged kit OK.
- **T9:** labels `!` `+` `-` `+/-` → theme glyphs, `anchor` `f` stays; undo restores byte for byte; theme switch
  boja → crno-bijelo → boja byte-identical (after moving undo before name recovery). Mockup through KORAK 1 printed
  three ways: labels / club glyphs / club glyphs.
- **Mapping:** `mud` → `sand` (shared default, `/csurvey-defaults`, commit d5b76fe).
- **Next:** SB 1103 in both themes for sign-off (T6), `/publish`, close-out. T7 superseded by `/theme-round`.
- **T6 prints:** SB 1103 (`example/finishing/…_lt_fin.csx`) themed boja + crno-bijelo and printed plan + profile
  next to the original: [runs/2026-10-07-t6-sb1103/pregled.png](runs/2026-10-07-t6-sb1103/pregled.png). Awaiting sign-off.
