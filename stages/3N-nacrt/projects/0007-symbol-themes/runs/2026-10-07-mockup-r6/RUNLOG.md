# Theme mockup, round 6: tuning from the user's r5 review + sparser area tiles, 2026-10-07

Same procedure as [round 5](../2026-10-07-mockup-r5/RUNLOG.md) / [round 3](../2026-10-07-mockup-r3/RUNLOG.md)
(mockup → headless import on the DTD-free scratch copy → KORAK 2 → `theme_apply` boja / crno-bijelo → headless print
on `C:\csurvey64`; comparison sheets as in r3; four placement seeds as in r5). No code changed: `theme.json` values,
a re-split of the 22:03 `drawing_catalogue.svg`, one test assertion and docs.

**Look at:** [`theme-mockup_ceiling-step_detalj.png`](theme-mockup_ceiling-step_detalj.png) (L04 next to pit L08,
1400 dpi; top boja, bottom crno-bijelo), [`theme-mockup_plohe_4-seeda.png`](theme-mockup_plohe_4-seeda.png) (boja
areas, four seeds, one per row), [`theme-mockup_plohe_usporedba.png`](theme-mockup_plohe_usporedba.png) and
[`theme-mockup_voda_detalj.png`](theme-mockup_voda_detalj.png) (A09: izvorno · boja · crno-bijelo).

## 1. ceiling-step (boja; crno-bijelo inherits)

| Field | r5 → r6 | Why |
|---|---|---|
| `style` | solid → **custom**, `dash` **[4, 2]** (× pen width 3) | water-flow's 2:1 rhythm. [10, 5] tried first: one dash per tick pitch, read as a row of hooks (┐┐┐) |
| `decoration.alignment` / `flip` | auto (chimney's side: inner + flipped, as pit) → **`outer`, `flip` false** | the stem now points to the other side of the line: ⊤ instead of ⊥ |
| `spacing_pct` | 4500 (kept) | 6 ticks straight, 3 on the curve; still readable with dashes |
| pit | unchanged | solid, ticks as before |

On the print: dashed line, every tick hangs from the line on the side opposite pit's ticks, straight and on the curve.
The dashes look a touch thinner than the solid pit line at 1400 dpi (same width 3; short dashes anti-aliased).

## 2. Areas: re-split and densities

The 22:03 export re-split with `theme_svg.py split` into `findings/t1-split/` and copied into
`production/themes/boja/{signs,lines,areas}` + `report.json`. Changed: **all six area tiles**; signs and line units
byte-identical; colours unchanged.

| Tile | r5 → r6 (paths; size at zoom 0.05, m) |
|---|---|
| blocks | 489 → 489; 1.52 × 0.80 → **2.87 × 1.51** (same stones spread out) |
| clay | 30 → **12**; 0.52 × 0.62 → 0.47 × 0.57 |
| debris | 30 → 30; 1.55 × 0.88 → **2.48 × 1.41** (spread out) |
| ice | 4 → 4; 0.81 × 0.44 → 0.97 × 0.59 |
| pebbles | 41 → **30**; 0.87 × 0.76 → 0.87 × 0.78 |
| stalagmite | 11 → 11; 0.70 × 0.53 → 0.76 × 0.52 |

Density (grid step, m) and measured ink cover of the 2 × 1.5 m sample (900 dpi, inner 1.88 × 1.38 m; range over the
four seeds; izvorno = cSurvey's own brush on the same item):

| Area | Density r5 → r6 | Ink r5 | Ink r6 (4 seeds) | izvorno | Notes |
|---|---|---|---|---|---|
| blocks | 0.9 → **1.8** | 44 % (68 % with the new tile) | 23–39 % | 7 % (3 stones) | still uneven: one seed has a bare quarter (2.1: two seeds bare; 1.6: 30–43 %, too dense) |
| clay | 0.45 → **0.5** | 46 % | 14–16 % | 8 % | 0.55/0.6 left bare vertical strips (step > tile width 0.47) |
| debris | 0.75 → **1.25** | 31 % | 22–26 % | 33 % (thick outlines) | even |
| ice | 0.6 → **0.85** | 20 % | 10–13 % | 0 (blank) | even |
| pebbles | 0.6 → **0.7** | 50 % | 27–30 % | 28 % | one seed has a small bare patch (tile has an open middle) |
| stalagmite | 0.6 → **0.72** | 22 % | 13–16 % | 0 (blank) | 0.78 left bare bands on one seed |

Iterations (all on four seeds): a) 1.8 / 0.6 / 1.05 / 0.83 / 0.79 / 0.78; b) 2.1 / 0.55 / 1.25 / 0.85 / 0.72 / 0.78;
c) 1.6 / 0.48 / 1.25 / 0.85 / 0.7 / 0.78; d) the final values. Measuring script and seed copies stayed in the
session scratchpad.

## 3. Water

| Theme | r5 → r6 |
|---|---|
| boja | KORAK 2's light-blue solid (not themed) → **`pattern` lines, 45°, density 0.33, colour `#24A9D1`** (the water-flow sign blue) |
| crno-bijelo | own `water` pattern entry → **removed**: inherits boja's pattern; `monochrome` makes it black (`report_crno-bijelo.json`: `water (tdx, pattern)`) |

On the print: boja water is blue hairlines at 45°, crno-bijelo the same lines in black, izvorno still the solid fill.

## 4. Decisions recorded (no behaviour change)

Arrows drawn pointing up with the automatic −90° stay; `vegetable-debris` stays fills-only (no outline pen) —
`production/themes/README.md` (Directional signs, Known limits) and the `boja/theme.json` notes.

## Checks

`themes.py check` OK; `pytest stages/3N-nacrt` 347 passed (`test_starter_themes_content`: water now in both themes,
black in crno-bijelo; ceiling-step custom + outer); `check_defaults.py` OK; pipeline doctor 0 fail.

## Odd

- `ice` and `stalagmite` mockup items still have no `<seed>`, so each print is a new random draw (as r5).
- Blocks: with the 2.9 × 1.5 m tile, a 2 × 1.5 m area sees one or two tiles; evenness depends on the seed whatever the step.

`.csx` files are gitignored; regenerate them with the procedure above.
