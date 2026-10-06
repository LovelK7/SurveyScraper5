# Theme mockup, round 5: tuning from the user's r4 review + redrawn area tiles, 2026-10-07

Same procedure as [round 4](../2026-10-07-mockup-r4/RUNLOG.md) / [round 3](../2026-10-07-mockup-r3/RUNLOG.md)
(mockup → headless import on the DTD-free scratch copy → KORAK 2 → `theme_apply` boja / crno-bijelo → headless print
on `C:\csurvey64`; comparison sheets as in r3). No code changed: `theme.json` values plus a re-split of the
21:37 `drawing_catalogue.svg`.

**Look at:** [`theme-mockup_linije_usporedba.png`](theme-mockup_linije_usporedba.png) (L04, L07, L14, L15),
[`theme-mockup_plohe_usporedba.png`](theme-mockup_plohe_usporedba.png) and
[`theme-mockup_plohe_4-seeda.png`](theme-mockup_plohe_4-seeda.png) (boja areas, four placement seeds, one per row).

## Lines (boja; crno-bijelo inherits)

| # | Key | Before → after | On the print |
|---|---|---|---|
| 1 | `ceiling-step` | `distance_pct` 40 → **0** (default, ticks on the line); `spacing_pct` 3000 → **4500** | ticks on the line; straight 6 ticks vs pit's 9, curve 3 vs 6: "T T T T", clearly sparser than pit (6000 tried first: 4 / 2, too sparse on the curve) |
| 1 | `pit` | unchanged | unchanged |
| 2 | `overhang` | `spacing_pct` 3000 (default) → **1700** | straight 6 → 11 triangles, curve 4 → 7 (≈ 1.8×); pitch ≈ 0.25 m for the 0.14 m triangle, no overlap |
| 3 | `slope:steep` | own unit, `scale` 6.5, spacing 3000 → **`svg` `lines/slope@sheer.svg`, `scale` 2, `inner` + `flip`, `spacing_pct` 5000** (= slope:sheer) | L15 prints identical to L14 (3 triangles straight, 2 on the curve) |
| 5 | `floor-meander` | unchanged | – |

## Areas: re-split and densities

The 21:37 export re-split with `theme_svg.py split` into `findings/t1-split/` and copied into
`production/themes/boja/{signs,lines,areas}` + `report.json`. Changed: **all six area tiles** (signs and the line units
are byte-identical). Colours unchanged (same flattened colours), so no colour edits. The `water-flow` line piece is
gone from the drawing (the theme already reads it as a dash pen, `svg: null`); `slope@steep.svg` stays in the
folder unused (test updated).

Tile size at zoom 0.05 (m) and density (grid step, m; cSurvey places one tile per cell, turned and shifted at random,
`cBrush.pRenderClipart`):

| Area | Tile r4 → r5 | Density before → after | Why |
|---|---|---|---|
| blocks | 2.16 × 1.15 → 1.52 × 0.80, same stones scaled ≈ 0.7 | 1.8 → **0.9** | at 1.8 most of the area was bare; 1.2 still bare patches; 0.75 overlapping clumps |
| clay | 0.38 × 0.40 → 0.52 × 0.62, fewer, smaller dots | 0.6 → **0.45** | 0.6 left a bare vertical strip; 0.52 / 0.48 holes on some seeds |
| debris | 2.35 × 1.33 → 1.55 × 0.88 | 1.0 → **0.75** | 1.0 / 0.85 bare vertical strips on 2 of 4 seeds |
| ice | 0.55 × 0.30 → 0.81 × 0.44 | 0.6 (kept) | even |
| pebbles | 0.60 × 0.54 → 0.87 × 0.76, smaller rings and dots | 0.75 → **0.6** | 0.75 / 0.65 holes and a vertical gap |
| stalagmite | 0.61 × 0.13 → 0.70 × 0.53, 11 marks scattered | 0.7 → **0.6** | 0.7 left horizontal bare bands (fixed angle) |

Densities were judged on four placement seeds (scratch copies with the `<seed>` values changed, printed headless).
At the final values clay, debris, pebbles, ice and stalagmite read even on every seed; **blocks is still uneven on
some seeds** (bare centre on the mockup's own seed, a clump on another): a large tile with uneven stones, turned at
random. Denser only makes the stones overlap.

## Checks

`themes.py check` OK; `pytest stages/3N-nacrt` 347 passed; `check_defaults.py` OK; pipeline doctor 0 fail.

## Odd

- `ice` and `stalagmite` items in the mockup have no `<seed>` after import, so cSurvey picks a new placement on every
  load and print (the other four keep theirs). Their r5 sheets show one random draw.
- crno-bijelo `blocks`: the stones are outlines at full resolution, but in black the thick outlines read crowded
  (they look filled in the overview); the grey of boja carries the 0.9 step better.

`.csx` files are gitignored; regenerate them with the procedure above.
