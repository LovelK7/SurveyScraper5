# Theme tuning cheatsheet

What to change in `production/themes/<id>/theme.json` for the feedback a theme round usually gets
(project 0007, rounds r3–r7). Run a round with `python production/tools/theme_round.py <label> [--focus key,…]`;
it prints and writes `projects/0007-symbol-themes/runs/<date>-<label>/` (sheets, `pregled.png`, RUNLOG). The
mechanics behind each row are in [themes/README.md](../themes/README.md). Edit `boja`; `crno-bijelo` inherits
everything and only blacks the colours (`monochrome`).

## Contents

- [Lines](#lines)
- [Areas](#areas)
- [Signs](#signs)
- [Colour and B/W](#colour-and-bw)
- [Limits (no field fixes these)](#limits-no-field-fixes-these)
- [Artwork rules for the drawing](#artwork-rules-for-the-drawing)
- [Round workflow](#round-workflow)

## Lines

`lines.<key>`; decoration fields live under `decoration`.

| Feedback | Field | Direction | Precedent |
|---|---|---|---|
| "more gap between the symbols" / "too dense" | `decoration.spacing_pct` | ↑. Raw `decorationspacepercentage`: pitch ≈ 0.01 × unit width × (1 + spacing/10) m, so +50 % spacing ≈ +50 % pitch. 990 butts the units, 3000 = cSurvey's stock (≈ 2 widths of gap) | slope:sheer 3000 → 5000 (r4); 6000 was 2.5× gaps, too sparse |
| "symbols closer together" | `decoration.spacing_pct` | ↓ (never below ~990 unless overlap is wanted: overlaps print **white**, even-odd) | overhang 3000 → 1700 (r5, ≈ 1.8× as many) |
| "the first symbol starts late" | – | cSurvey places the first unit about one pitch in; denser spacing shortens it | r4 |
| "the symbol should sit on the line / crosses the line" | `decoration.alignment` `outer`·`center`·`inner` + `flip` | `inner` + `flip: true` puts a base-down unit on the line on abyss-entrance's side; `center` straddles it | slope:sheer / slope:steep (r4) |
| "ticks on the other side" / "⊤ instead of ⊥" | `decoration.flip` (or `alignment` `outer` ↔ `inner`) | toggle | ceiling-step `outer`, `flip: false` (r6) |
| "ticks should stand off the line" / "ticks back on the line" | `decoration.distance_pct` | ↑ = gap of that % of the unit height; 0 = on the line | ceiling-step 0 → 40 (r4) → 0 (r5) |
| "bigger / smaller symbol" | `decoration.scale` | unit size = SVG units × scale / 40 m. All units are drawn at 0.05 m per drawing unit (scale 2); change both scale and spacing together, spacing is relative to the unit width | slope 0.8 (the drawn arrow is 4× the triangles, r3); ceiling-step 2 → 1.5 (r7) |
| "same look as another line" | `svg` → the other's file, copy its `decoration` | – | slope:steep = slope:sheer (`svg: lines/slope@sheer.svg`, r5) |
| "dashed line" | `style: custom` + `dash: [a, b]` | multiples of the pen `width`; more gaps per length → smaller numbers | water-flow [26, 8] → [6, 3] (r4) |
| "each dash with its own tick" (⊤ ⊤ ⊤) | one **unit** that holds dash + tick, `style: none` (base off) | a dash pattern and decoration spacing are independent; only a combined unit keeps them in step | ceiling-step `lines/ceiling-step@T.svg` (r7); [10, 5] dash read as hooks (r6) |
| "no base line, only the symbols" | `style: none` | decoration only | floor-meander, ceiling-step |
| "thicker / thinner line" | `width` | pen width (unset = the built-in pen's own; a User pen at 0 is a hairline) | rope 0.1 (r3) |
| "plain coloured line, no symbols" | `svg: null`, `color`, `width`, `style` | – | rope red `#EF5553` (r3) |
| "line colour" / "symbol colour different from the line" | `color` / `decoration_color` | hex | – |

## Areas

`areas.<key>`. A tile is scattered on a grid of `density` m, one tile per cell, randomly turned and shifted.

| Feedback | Field | Direction | Precedent |
|---|---|---|---|
| "area too dense" | `density` | ↑ (grid step in m). Check `--seeds 2`+ and the ink-cover table: aim near izvorno's cover where cSurvey has a pattern | r6: blocks 0.9 → 1.8, debris 0.75 → 1.25, ice 0.6 → 0.85 |
| "area too sparse / bare patches" | `density` | ↓ — but **a step wider than the tile leaves bare stripes** (the tile no longer reaches the next cell): keep `density` ≲ tile width × `zoom`. If it still clumps, ask for a smaller, evener tile | clay 0.55/0.6 striped with a 0.47 m tile (r6); 0.5 kept |
| "uneven: one seed bare, another clumped" | the tile itself | a big tile (≥ the sample) turned at random cannot be even; redraw smaller/evener, or accept | blocks 2.9 × 1.5 m tile (r6) |
| "don't rotate the marks" | `angle_mode: fixed`, `angle: 0` | – | stalagmite (r4) |
| "marks bigger / smaller" | `zoom` | m per SVG unit (0.05 everywhere); change `density` in step | – |
| "stones cut at the edge look wrong" | `crop` `none`·`subitems`·`full` | `subitems` (default) keeps whole shapes; `none` clips at the edge; `full` only whole tiles | blocks `none` (outlined stones) |
| "parallel lines instead of a fill" | `pattern: {type: lines, angle: 45, density: m}` | `density` = line spacing in m (min 0.1); `crossed` for a grid | water 0.33 (r4/r6) |
| "more water lines" | `pattern.density` | ↓ (1/3 = 3× the lines) | 1 → 0.33 (r4) |
| "plain fill" | `solid: true`, `color` | – | – |
| "background colour under the tile" | `background_color` | not blacked by `monochrome` | – |

## Signs

`signs.<key>`.

| Feedback | Field | Direction | Precedent |
|---|---|---|---|
| "bigger / smaller sign" | `size` | factor on the glyph's `csurvey:scale` (relative sizes come from the drawing) | – |
| "arrow points the wrong way" | first the artwork: **draw arrows pointing up**; `rotate` only for art drawn otherwise | theme_apply undoes cSurvey's +90° for air-draught / water-flow itself | r3 convention, settled r6 |
| "same glyph as another sign" | `svg: signs/<file>` | – | water-drip = water-flow:intermittent |
| "too heavy / outlined" vs "lost detail" | `outline_pen` false/true | false = fills only (default); true = cSurvey's pen round every path; stroke-only hairlines print only with the pen | vegetable-debris stays fills-only (r6) |
| "show only the outline" | `render: outline` | brush white, pen in the colour | – |
| "use cSurvey's own glyph" | `svg: null` | – | – |

## Colour and B/W

| Feedback | Where | How |
|---|---|---|
| "different colour" | `boja` entry `color` (`#RRGGBB`) | crno-bijelo follows automatically (black) |
| "only the B/W print should change" | `crno-bijelo/theme.json` own entry for that key | an entry there overrides boja's; `null` drops the inherited one. Remove the override to inherit again (water, r6) |
| "B/W can't tell X from Y" | crno-bijelo override: a `pattern`, a `dash`, `render: outline` | colour carried the meaning (brief §3.8) |
| "centerline / station labels colour" | `centerline` overrides | crno-bijelo blacks them via `monochrome` |

## Limits (no field fixes these)

- **Transparency / invisible pen**: item transparency + a style-None pen (every themed sign, `style: none` lines)
  crashes cSurvey. Do not set transparency on them; there is no "invisible but present" pen.
- **Meander on curves**: units are straight chords placed on a rasterised path; the double-rail meander butts on
  straight runs (990) but breaks up on curves. Same reason short curves get few units (ceiling-step: 2 T's on the
  mockup sine).
- **Overlapping units / tiles print white** (even-odd fill of one path).
- **Stroke-only artwork does not paint** in line units and area tiles (the split outlines strokes; check the
  split summary for `STROKE-ONLY`).
- **`spacing_pct` 0** reads back as 100; theme_apply writes ≥ 0.1.
- Pattern `density` < 0.1 is refused by cSurvey.

## Artwork rules for the drawing

For the user's Illustrator file (`drawing_catalogue.svg`, Export As SVG, Object IDs = Layer Names):

- **One named group per piece**, named exactly the theme key (`slope:steep`, `water-flow:intermittent`). An unnamed
  group exports as `_x3C_Group_x3E_` and is skipped (the round warns with `!!`). Duplicate names: only the first counts.
- **Layers**: `Znakovi` (signs), `Linije` (line units), `Plohe` (area tiles). A layer starting with `_` is ignored.
- **Fills only.** Strokes are outlined by the split for units and tiles, but outline them yourself for the drawn
  width. No gradients, clipping masks, images, text or opacity — they are flattened or dropped.
- **No padding** around a piece: the bounding box is the size and the centre (signs are centred on their bbox).
- **Line units**: drawn pointing away from the line, the line along the unit's bottom edge.
- **Area tiles small and even**: a tile larger than the area it fills cannot look even; ≲ 1 m at 0.05 m per unit.
- **Arrows pointing up** (as at TopoDroid orientation 0).
- Colours: one dominant colour per piece; it becomes the theme `color` (the SVG itself is flattened to black).

## Round workflow

1. User feedback → the table above → edit `theme.json` (keep a `_note` with the reason and the round).
2. New artwork → `theme_round.py <label> --split` (warnings first; new keys need a theme.json entry).
3. `python production/tools/themes.py check` (the round runs it too; `--no-print` validates only).
4. `theme_round.py <label> --focus <changed keys>` (≈ 15 s from cache; `--seeds 2` when densities change).
5. Fill the RUNLOG's "Feedback → change" table; add a dated entry to the project log.
