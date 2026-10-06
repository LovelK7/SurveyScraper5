# Theme mockup, round 4: tuning from the user's r3 review, 2026-10-07

Same procedure as [round 3](../2026-10-07-mockup-r3/RUNLOG.md) (r2 procedure: mockup → headless import on the
DTD-free scratch copy → KORAK 2 → `theme_apply` boja / crno-bijelo → headless print on `C:\csurvey64`; comparison
sheets as in r3). Only `theme.json` values changed, no code.

**Look at:** [`theme-mockup_linije_usporedba.png`](theme-mockup_linije_usporedba.png) (L04, L14, L15, L24) and
[`theme-mockup_plohe_usporedba.png`](theme-mockup_plohe_usporedba.png) (A07, A09).

| # | Key | Before → after | On the print |
|---|---|---|---|
| 1 | `ceiling-step` (boja) | `distance_pct` 0 → **40** (gap = 40 % of the tick height, `cClipartOnPath.pDrawRotatedClipart`) | ticks stand off the line with a small gap; pit unchanged, ticks on the line |
| 2 | `slope:sheer` (boja) | alignment auto (resolved to slope's *center*, flipped) → **`inner` + `flip: true`** (abyss-entrance's side); `spacing_pct` 3000 → **5000** | triangles sit on the line, same side as abyss-entrance; gap ≈ 4 unit widths instead of 2 (6000 tried first: 2.5×, too sparse) |
| 2 | `slope:steep` (boja) | alignment auto → **`inner` + `flip: true`**; `scale` 2 → **6.5** | on the line; triangle ≈ abyss-entrance's size (2.31 × 6.5 ≈ 7.76 × 2 drawing units high) |
| 3 | `water-flow` (boja) | `dash` [26, 8] → **[6, 3]** (× pen width 5.35; colour and width kept) | straight sample: 6 gaps instead of 1 |
| 4 | `stalagmite` area (boja) | `angle_mode` random → **`fixed`**, `angle` **0** | every mark horizontal as drawn |
| 5 | `water` pattern (crno-bijelo) | `density` 1 → **0.33** | 2 → 6 lines in the sample pool (3×) |

**Pattern density:** `Objects/Patterns/basepatterns.xml` "Lines" steps `Painter.Density` = `patterndensity ×
patternzoomfactor` (`cBrush.vb:242-245`), i.e. the line spacing in metres, so 1/3 gives 3× the lines. Below 0.1
cSurvey refuses ("Brush pattern too dense", `cBrush.vb:2426`).

**Odd:** on a straight run the first decoration unit starts about one pitch in from the line start, so the sparser
`slope:sheer` shows an empty lead-in (cSurvey placement, not the theme).

`.csx` files are gitignored; regenerate them with the procedure above.
