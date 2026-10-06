# Theme mockup, round 7: ceiling-step as a row of ⊤ units, 2026-10-07

Same procedure as [round 6](../2026-10-07-mockup-r6/RUNLOG.md), minus the import: the mockup is unchanged, so
r6's `theme-mockup.csx` and `theme-mockup_izvorno.csx` (after KORAK 2) were copied in, then `theme_apply` boja /
crno-bijelo → headless print on `C:\csurvey64`. No code changed: one new unit SVG, `theme.json` values, one test, docs.

**Look at:** [`theme-mockup_ceiling-step_detalj.png`](theme-mockup_ceiling-step_detalj.png) — L04 ceiling-step (left)
next to pit L08 (right), straight and curve, 1400 dpi; top boja, bottom crno-bijelo.

## ceiling-step (boja; crno-bijelo inherits)

User on r6: the line must read "⊤ ⊤ ⊤ ⊤" — each dash with its own perpendicular tick at its middle, gaps between the
T's. In r6 the dash pattern and the tick spacing were independent, so most dashes had no tick.

| Field | r6 → r7 |
|---|---|
| `svg` | `lines/ceiling-step.svg` (index) → **`lines/ceiling-step@T.svg`** |
| `style` | custom, `dash` [4, 2] → **none** (base off, like floor-meander) |
| `decoration.scale` | 2 → **1.5** |
| `decoration.spacing_pct` | 4500 → **1400** |
| `alignment` / `flip` | `outer` / false (kept) |
| pit | unchanged |

The unit: the split tick (0.829 × 5.083 units) with a bar 12.707 × 0.829 (2.5 × the stem height, the stem's
thickness) centred under the stem's foot, as one fill-only path (`theme_svg.py normalize` + `check`: ok). Drawn per
the README rule (line along the bottom edge), so `outer` puts the bar on the line path and the stem on the far side.

Iterations (scale / spacing → on the print): 2 / 1700 → bar 0.64 m, 2 T's straight, 1 on the curve; 1.5 / 1200 →
4 + 3, gaps 0.3–0.5 bar; 1.5 / 1280 → 4 + 2, gaps ≈ 0.35; 1.2 / 1500 → 4 + 3 but thinner than pit's line;
1.5 / 1500 → 3 + 2, gaps 0.6–1; **1.5 / 1400 → 4 + 2, gaps 0.5–0.7 bar** (chosen). At scale 1.5 the stem is
0.19 m, the same as pit's tick.

On the print: every T has its bar on the line and its stem on the side opposite pit's ticks; empty gaps separate
the T's; boja and crno-bijelo identical.

## Checks

`themes.py check` OK; `pytest stages/3N-nacrt` 347 passed (one run had a transient `test_end_to_end_on_sb1103`
failure while the print was busy; passes on rerun); `check_defaults.py` OK; pipeline doctor 0 fail.

## Odd

- Only 2 T's on the mockup's short sine: units are straight chords and placement is quantised; longer real curves get
  more.
- The final boja print failed because `theme-mockup_boja_plan.pdf` was locked by another process; the identical
  scratch print (same `.csx`, byte-compared) was copied in.

`.csx` files are gitignored; regenerate them with the procedure above.
