# Sample sheet, round 2: the theme mockup (zoo v4), 2026-10-07

Round 2 of the colour-iteration printout ([round 1](../2026-10-06-zoo-sheet/RUNLOG.md)). What changed since round 1:

- **Outline pen off** (user, 2026-10-06): themed sign glyphs no longer get cSurvey's pen traced round every path.
- **New fixture:** the theme mockup, a zoo v4 that is now the permanent test case for themes (it replaces SB 1103
  there). It has all 12 theme signs, including the 4 that zoo v3 lacked: bones, tree-trunk, vegetable-debris and
  water-flow:intermittent.
- **Arrow direction** fixed with the new sign field `rotate`.

**Look at this first:** [`theme-mockup_znakovi_usporedba.png`](theme-mockup_znakovi_usporedba.png). It shows the 12
themed signs, zoomed, in three columns: izvorno · boja · crno-bijelo. Red station marks are faded.

| File | What |
|---|---|
| `theme-mockup_znakovi_usporedba.png` | the 12 themed signs: izvorno · boja · crno-bijelo (500 dpi crops) |
| `theme-mockup_obrub_staro-novo.png` | boja with the old outline pen (TightPen) next to the new pen-off look |
| `theme-mockup_strelice_rotate.png` | arrow direction: izvorno · boja art as drawn · + `csurvey:rotationangledelta` only · boja with `rotate` |
| `theme-mockup_pregled.pdf` | 3 overview pages, one per kind (znakovi, linije, plohe), each with izvorno / boja / crno-bijelo stacked; also as `theme-mockup_pregled_1…3_*.png` |
| `theme-mockup_<izvorno\|boja\|crno-bijelo>_plan.pdf` | full cSurvey headless plan prints (A4, fit); the `.png` beside each is page 1 at 110 dpi |
| `theme-mockup-key.md`, `theme-mockup-layout.json` | the slot table (station = slot tag) and the world coordinates of every slot |
| `report_boja.json`, `report_crno-bijelo.json` | `theme_apply.py --json` reports |

The `.csx` files are gitignored. Regenerate them with the procedure below.

## The mockup

`production/tools/make_theme_mockup.py` writes a raw TopoDroid `.csx`. It contains every symbol of the 0002 zoo v3,
plus every key of every theme, read at run time, so adding a symbol to a theme adds it to the mockup. It has 49 signs,
25 lines and 10 areas in three labelled sections: ZNAKOVI, LINIJE and PLOHE.

- **Signs** sit 1.2 m north of their station, with the name below.
- **Lines** are drawn twice: a straight 3 m stroke and a full sine wave.
- **Areas** are 2 × 1.5 m rectangles.
- Every line and area row is enclosed in a closed `wall` loop. Without one, cSurvey would not print them (0002 RUNLOG
  step-04).
- Station names are the slot tags (P00…, L00…, A00…). Every item has a label "P05 bones".

## Procedure

```text
python production/tools/make_theme_mockup.py <run>                                   # theme-mockup.csx (pre-import)
CSURVEY_DIR=<DTD-free copy, see below> python production/tools/csurvey_driver.py recalc <run>/theme-mockup.csx -o <run>/theme-mockup_imported.csx
python production/tools/fix_imported_linetypes.py <run>/theme-mockup_imported.csx -o <run>/theme-mockup_izvorno.csx   # KORAK 2
python production/tools/theme_apply.py apply <run>/theme-mockup_izvorno.csx --theme boja|crno-bijelo \
    --pre <run>/theme-mockup.csx -o <run>/theme-mockup_<theme>.csx --json <run>/report_<theme>.json
CSURVEY_DIR=C:\csurvey64 python production/tools/csurvey_driver.py print <run>/theme-mockup_<theme>.csx -o <run> --design Plan
```

As in round 1, KORAK 1 is skipped, so the TopoDroid names reach the import unchanged.

**The import is headless now, with no GUI step.** For a file whose `creatid` is TopoDroid and which has not been
post-processed, `cSurvey.Load` runs the TopoDroid conversion itself (`cSurvey.vb:943-944, 1566-1569` →
`cImportTopoDroidHelper.ConvertItem`), so the driver's `recalc` (Load → Calculate → SaveTo) is the import.

- **Check against the GUI import:** v3 imported this way was compared with the 2026-07 GUI import
  (`step-04-after-import.csx`). The items match 155/155, with the same type, sign, pen and brush. Only the glyph hashes
  differ. The installed build also has glyphs for anchor, ice, snow, water, clay, archeo-material, sand and gradient,
  which the July build lacked.
- **One snag:** against `C:\csurvey64` the load failed with *"The remote server returned an error: (429) Too Many
  Requests"*. While importing, cSurvey loads gallery SVGs from `Objects\Cliparts\Signs`, and 101 of them carry a
  `<!DOCTYPE … "http://www.w3.org/…/svg11.dtd">`. .NET fetches that DTD, and w3.org rate-limits it.
- **Workaround:** a scratch copy of `C:\csurvey64` with the DOCTYPE lines stripped from its `Objects/**/*.svg`. The
  install itself was not touched. Glyph geometry is unchanged, but the pool hashes differ from a GUI import.
- **Prints** use the real `C:\csurvey64`.

## Results

**Name recovery:** 47/47 sign items and 154 other items are recovered by TopoDroid name. Item counts are preserved
through import and KORAK 2.

All 12 theme signs are themed by TopoDroid name; none needed the target fallback. All are in the mockup.

| Sign | Slot | Before theme (izvorno) | boja | crno-bijelo |
|---|---|---|---|---|
| air-draught | P00 | stock arrow, up | club glyph, `rotate 180` → up | black |
| blocks | P04 | stock | #78787A | black |
| bones | P05 | **X-box** (new in v4) | club glyph | black |
| continuation | P07 | stock "?" | club glyph | black |
| danger | P10 | X-box | club glyph | black |
| debris | P11 | X-box | #78787A | black |
| minus, plus, plus-minus | P21, P28, P29 | X-box | club glyph | black |
| tree-trunk | P41 | **X-box** (new in v4) | #453625 | black (still solid; brief §3.8 proposes outline mode) |
| vegetable-debris | P43 | stock `#`-like glyph (new in v4) | #463524; its 117 stroke-only hairlines no longer print (see below) | black |
| water-flow:intermittent | P48 | **X-box** (new in v4) | #24A9D1, `rotate 90` → up | black |

- **Pen off.** Every themed sign has `<pen type="99" name="tema:<id>" … style="98" width="0.00" …><clipart data=""/></pen>`
  (style None). Black signs keep the built-in `<brush type="7"/>`; coloured ones get the `tema:` solid brush. The
  glyphs print visibly lighter: compare `theme-mockup_obrub_staro-novo.png`.
- **vegetable-debris loses detail.** Its glyph has 117 `fill="none"` stroke paths, which only the pen draws, and
  `theme_apply` reports them. If the user wants them back, set `outline_pen: true` on that sign, or redraw the
  strokes as fills.
- **cSurvey round trip** (headless `recalc` of `theme-mockup_boja.csx`): all 47 sign pens, brushes and `data` come
  back identical, the style-None pen included. The `CaveDossierTheme*` properties survive. Re-theming the cSurvey-saved
  file to crno-bijelo undoes 12 signs and swaps 12 pool entries.
- **Idempotency** (`cmp`, byte-identical): boja→boja, boja→crno-bijelo, crno-bijelo→boja and crno-bijelo→crno-bijelo
  all equal a single apply. An old-look file (`outline_pen: true` for every sign) re-themed to boja equals boja.
- **Arrows.** In `theme-mockup_strelice_rotate.png`, the club air-draught drawn pointing right comes out pointing
  down, and `csurvey:rotationangledelta` in the SVG changes nothing. The theme `rotate` fixes it. The same holds for
  water-flow:intermittent, which needs `rotate 90` because its name gets no +90° from the importer. The convention is
  in [themes/README.md#directional-signs](../../../../production/themes/README.md#directional-signs).
- **Lines and areas** are phase 2. They print as cSurvey draws them today, identically in all three variants;
  `report_*.json` lists what a theme would reach. Visible quirks:
  - the `water-flow` line is black, not blue;
  - `ice`, `snow`, `user` and `stalagmite` areas are blank soil;
  - `abyss-entrance`, `ceiling-step` and `rope` are plain borders.

## Scratch (not kept)

- `compose.py` (PyMuPDF + PIL) fits world→page from the wall loops round the first line row and the first area row,
  then crops.
- The arrow and old-pen variants were scratch themes:
  - `norot`: boja with `rotate` 0;
  - `rad`: boja with `csurvey:rotationangledelta` added to the two SVGs;
  - `pen`: boja with `outline_pen: true` everywhere.
