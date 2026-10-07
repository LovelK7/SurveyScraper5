# Theme round r9-feedback, 2026-10-07

Written by `production/tools/theme_round.py` ([cheatsheet](../../../../production/tools/theme_tuning_cheatsheet.md)). Command:

```text
python production/tools/theme_round.py r9-feedback --focus vegetable-debris,slope,ceiling-step,abyss-entrance,snow,P01,L17,L22 --seeds 2
```

## Look at these first

- [`pregled.png`](pregled.png) — what changed this round, then the focus crops.
- [`theme-mockup_detalj_P43_vegetable-debris.png`](theme-mockup_detalj_P43_vegetable-debris.png) — focus P43 vegetable-debris at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L13_slope.png`](theme-mockup_detalj_L13_slope.png) — focus L13 slope at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L04_ceiling-step.png`](theme-mockup_detalj_L04_ceiling-step.png) — focus L04 ceiling-step at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L00_abyss-entrance.png`](theme-mockup_detalj_L00_abyss-entrance.png) — focus L00 abyss-entrance at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_A06_snow.png`](theme-mockup_detalj_A06_snow.png) — focus A06 snow at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_P01_anchor.png`](theme-mockup_detalj_P01_anchor.png) — focus P01 anchor at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L17_wall.png`](theme-mockup_detalj_L17_wall.png) — focus L17 wall at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L22_wall@presumed.png`](theme-mockup_detalj_L22_wall@presumed.png) — focus L22 wall:presumed at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_znakovi_usporedba.png`](theme-mockup_znakovi_usporedba.png) — znakovi, every themed slot: izvorno · boja · crno-bijelo (900 dpi crops)
- [`theme-mockup_linije_usporedba.png`](theme-mockup_linije_usporedba.png) — linije, every themed slot: izvorno · boja · crno-bijelo (800 dpi crops)
- [`theme-mockup_plohe_usporedba.png`](theme-mockup_plohe_usporedba.png) — plohe, every themed slot: izvorno · boja · crno-bijelo (600 dpi crops)
- [`theme-mockup_plohe_seedovi.png`](theme-mockup_plohe_seedovi.png) — boja areas, one row per placement seed; ink cover in RUNLOG

## Inputs

| What | Value |
|---|---|
| drawing | `drawing_catalogue.svg`, modified 2026-10-07 20:06 – not re-split |
| themes | `boja`, `crno-bijelo` |
| mockup cache | `mockup-9d5fcd4f59f2` (built this round) |
| cache key inputs | cSurveyPC.exe 11813888-1760291706, fix_imported_linetypes.py 1273bfa69545db9e, make_theme_mockup.py 19bb15ab6d47ebe8, tdx-mapping.json df550d655b2c2e4a, wall_orient.py e7f2d3ca6515c809 |
| cSurvey (prints) | `C:\csurvey64` |
| cSurvey (import) | DTD-free copy under the cache |
| area seeds | fixed per area (make_theme_mockup.area_seed); 2 alternative(s) |

## theme.json changes

Against [`2026-10-06-r8-repeat`](../2026-10-06-r8-repeat/RUNLOG.md) (copies in [`themes/`](themes/)):


`boja`:

| | Path | Before | After |
|---|---|---|---|
| + | `areas.snow` | – | {"_note": "the same as ice (user, r9)", "color": "#468FA0", "density": 0.85, "svg": "areas/ice.svg", "zoom": 0.05} |
| + | `lines.abyss-entrance.decoration.spacing_pct` | – | 1700 |
| ~ | `lines.ceiling-step.decoration.spacing_pct` | 1400 | 1100 |
- `crno-bijelo`: no change

## Apply reports

| Theme | Signs themed | Lines themed | Areas themed | Unthemed keys | Fallbacks (target) | Skipped |
|---|---|---|---|---|---|---|
| boja | 14 / 47 | abyss-entrance 2, ceiling-step 2, floor-meander 2, overhang 2, pit 2, rope 2, slope 2, slope:sheer 2, slope:steep 2, water-flow 2 | blocks 1, clay 1, debris 1, ice 1, pebbles 1, snow 1, stalagmite 1, water 1 | – | – | – |
| crno-bijelo | 14 / 47 | abyss-entrance 2, ceiling-step 2, floor-meander 2, overhang 2, pit 2, rope 2, slope 2, slope:sheer 2, slope:steep 2, water-flow 2 | blocks 1, clay 1, debris 1, ice 1, pebbles 1, snow 1, stalagmite 1, water 1 | – | – | – |

- `boja`: vegetable-debris: 117 stroke-only path(s) in the glyph do not print with the pen off (outline_pen false)
- `crno-bijelo`: vegetable-debris: 117 stroke-only path(s) in the glyph do not print with the pen off (outline_pen false)

## Ink cover per area

Share of the inner 1.88 × 1.38 m of each 2 × 1.5 m sample that is ink, at 900 dpi (any pixel with a channel under 160; red station marks excluded, so a light solid fill such as izvorno's water counts as ink); `empty` = bare cells of 12 (0.47 m). s0 is the mockup's fixed seed, s1… the alternatives.

| Slot | Area | izvorno | boja s0 | crno-bijelo s0 | boja s1 | boja s2 |
|---|---|---|---|---|---|---|
| A00 | blocks | 6.6 % (4 empty) | 27.8 % | 29.1 % | 38.0 % | 29.8 % |
| A01 | clay | 7.8 % | 15.5 % | 16.0 % | 15.4 % | 16.7 % |
| A02 | debris | 32.4 % | 18.8 % | 19.4 % | 18.4 % | 20.3 % |
| A03 | ice | 0.1 % (11 empty) | 13.3 % | 14.8 % | 8.0 % (2 empty) | 11.5 % (1 empty) |
| A04 | pebbles | 23.1 % | 28.9 % | 30.9 % | 27.5 % | 30.2 % |
| A06 | snow | 0.0 % (12 empty) | 11.0 % (3 empty) | 11.3 % (3 empty) | 13.0 % (1 empty) | 10.9 % (2 empty) |
| A07 | stalagmite | 0.0 % (12 empty) | 13.1 % | 13.1 % | 12.4 % | 13.4 % |
| A09 | water | 100.0 % | 11.2 % | 11.5 % | 11.2 % | 11.2 % |

## Files

| File | What |
|---|---|
| [`pregled.png`](pregled.png) | overview: changes on top, focus crops |
| [`theme-mockup_detalj_P43_vegetable-debris.png`](theme-mockup_detalj_P43_vegetable-debris.png) | focus P43 vegetable-debris at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L13_slope.png`](theme-mockup_detalj_L13_slope.png) | focus L13 slope at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L04_ceiling-step.png`](theme-mockup_detalj_L04_ceiling-step.png) | focus L04 ceiling-step at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L00_abyss-entrance.png`](theme-mockup_detalj_L00_abyss-entrance.png) | focus L00 abyss-entrance at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_A06_snow.png`](theme-mockup_detalj_A06_snow.png) | focus A06 snow at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_P01_anchor.png`](theme-mockup_detalj_P01_anchor.png) | focus P01 anchor at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L17_wall.png`](theme-mockup_detalj_L17_wall.png) | focus L17 wall at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L22_wall@presumed.png`](theme-mockup_detalj_L22_wall@presumed.png) | focus L22 wall:presumed at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_znakovi_usporedba.png`](theme-mockup_znakovi_usporedba.png) | znakovi, every themed slot: izvorno · boja · crno-bijelo (900 dpi crops) |
| [`theme-mockup_linije_usporedba.png`](theme-mockup_linije_usporedba.png) | linije, every themed slot: izvorno · boja · crno-bijelo (800 dpi crops) |
| [`theme-mockup_plohe_usporedba.png`](theme-mockup_plohe_usporedba.png) | plohe, every themed slot: izvorno · boja · crno-bijelo (600 dpi crops) |
| [`theme-mockup_plohe_seedovi.png`](theme-mockup_plohe_seedovi.png) | boja areas, one row per placement seed; ink cover in RUNLOG |
| [`theme-mockup_izvorno_plan.pdf`](theme-mockup_izvorno_plan.pdf) | cSurvey headless plan print (+ `.png` at 110 dpi) |
| [`theme-mockup_boja_plan.pdf`](theme-mockup_boja_plan.pdf) | cSurvey headless plan print (+ `.png` at 110 dpi) |
| [`theme-mockup_crno-bijelo_plan.pdf`](theme-mockup_crno-bijelo_plan.pdf) | cSurvey headless plan print (+ `.png` at 110 dpi) |
| [`report_boja.json`](report_boja.json) | `theme_apply` report |
| [`report_crno-bijelo.json`](report_crno-bijelo.json) | `theme_apply` report |
| [`themes/boja.theme.json`](themes/boja.theme.json) | theme.json as used this round |
| [`themes/crno-bijelo.theme.json`](themes/crno-bijelo.theme.json) | theme.json as used this round |
| [`theme-mockup-key.md`](theme-mockup-key.md) | slot table |
| [`theme-mockup-layout.json`](theme-mockup-layout.json) | slot world coordinates |

`.csx` files are gitignored; the round re-creates them from the mockup cache (`<workspace>/runs/theme-round/mockup-9d5fcd4f59f2`).

## Timings

| Step | s |
|---|---|
| themes.py check | 0.0 |
| DTD-free cSurvey copy (reused) | 0.0 |
| mockup: generate | 0.0 |
| mockup: headless import (DTD-free copy) | 3.4 |
| mockup: KORAK 2 + 12 fixed area seeds | 0.6 |
| mockup: izvorno print | 12.6 |
| theme_apply × 2 | 0.6 |
| headless print × 4 (parallel) | 20.6 |
| comparison sheets | 6.5 |
| focus details × 8 | 2.5 |
| ink cover + seed sheet | 3.6 |
| pregled.png | 0.7 |
| RUNLOG | 0.0 |
| **total** | **51.3** |

## Feedback → change

_To be filled by the session: the user's words on this round, and the theme.json change each one led to (see the cheatsheet)._

| # | Feedback (user) | Key | Change | Seen in |
|---|---|---|---|---|
| 1 | wall:presumed the same thickness as wall | wall:presumed | new entry: `svg null`, width 3.5 (measured equal to wall; 3 thinner, 4/5 thicker), `custom` dash [14, 5] ≈ the stock dash/gap | r9e/r9f-wall L22 |
| 2 | new vegetable symbol | vegetable-debris | re-split (new artwork); 117 stroked hairlines still do not print with the pen off | P43 |
| 3 | ceiling-step gap too far on curves | ceiling-step | `spacing_pct` 1400 → 1100; the curve still gets 3 T's (limit: chords on a rasterised path) | L04 |
| 4 | snow the same as ice | snow | new entry: `svg areas/ice.svg`, ice's colour/density/zoom | A06 |
| 5 | p01 anchor a plain label "f" | – | no change: tdx-mapping already turns anchor into label "f" in KORAK 1; the mockup imports without KORAK 1, so it shows the glyph | P01 |
| 6 | abyss-entrance denser | abyss-entrance | `spacing_pct` 3000 (default) → 1700 (as overhang) | L00 |
| 7 | thicker slope symbol | slope | re-split (redrawn artwork); stem still thin – thickness is in the artwork | L13 |
