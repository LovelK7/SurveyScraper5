# Theme round r11b-blocks, 2026-10-07

Written by `production/tools/theme_round.py` ([cheatsheet](../../../../production/tools/theme_tuning_cheatsheet.md)). Command:

```text
python production/tools/theme_round.py r11b-blocks --focus areas/blocks,tree-trunk,water-flow,vegetable-debris --seeds 2
```

## Look at these first

- [`pregled.png`](pregled.png) — what changed this round, then the focus crops.
- [`theme-mockup_detalj_A00_blocks.png`](theme-mockup_detalj_A00_blocks.png) — focus A00 blocks at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_P41_tree-trunk.png`](theme-mockup_detalj_P41_tree-trunk.png) — focus P41 tree-trunk at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_P47_water-flow.png`](theme-mockup_detalj_P47_water-flow.png) — focus P47 water-flow at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L24_water-flow.png`](theme-mockup_detalj_L24_water-flow.png) — focus L24 water-flow at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_P43_vegetable-debris.png`](theme-mockup_detalj_P43_vegetable-debris.png) — focus P43 vegetable-debris at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_znakovi_usporedba.png`](theme-mockup_znakovi_usporedba.png) — znakovi, every themed slot: izvorno · boja · crno-bijelo (900 dpi crops)
- [`theme-mockup_linije_usporedba.png`](theme-mockup_linije_usporedba.png) — linije, every themed slot: izvorno · boja · crno-bijelo (800 dpi crops)
- [`theme-mockup_plohe_usporedba.png`](theme-mockup_plohe_usporedba.png) — plohe, every themed slot: izvorno · boja · crno-bijelo (600 dpi crops)
- [`theme-mockup_plohe_seedovi.png`](theme-mockup_plohe_seedovi.png) — boja areas, one row per placement seed; ink cover in RUNLOG

## Inputs

| What | Value |
|---|---|
| drawing | `drawing_catalogue.svg`, modified 2026-10-07 20:49 – not re-split |
| themes | `boja`, `crno-bijelo` |
| mockup cache | `mockup-4d4603032691` (reused) |
| cache key inputs | cSurveyPC.exe 11813888-1760291706, fix_imported_linetypes.py 1273bfa69545db9e, make_theme_mockup.py 19bb15ab6d47ebe8, tdx-mapping.json df550d655b2c2e4a, wall_orient.py e7f2d3ca6515c809 |
| cSurvey (prints) | `C:\csurvey64` |
| cSurvey (import) | DTD-free copy under the cache |
| area seeds | fixed per area (make_theme_mockup.area_seed); 2 alternative(s) |

## theme.json changes

Against [`2026-10-07-r11-butt`](../2026-10-07-r11-butt/RUNLOG.md) (copies in [`themes/`](themes/)):


`boja`:

| | Path | Before | After |
|---|---|---|---|
| - | `areas.blocks.crop` | "none" | – |
- `crno-bijelo`: no change

## Apply reports

| Theme | Signs themed | Lines themed | Areas themed | Unthemed keys | Fallbacks (target) | Skipped |
|---|---|---|---|---|---|---|
| boja | 14 / 47 | abyss-entrance 2, ceiling-step 2, floor-meander 2, overhang 2, pit 2, rope 2, slope 2, slope:sheer 2, slope:steep 2, user 2, wall:blocks 2, wall:debris 2, wall:ice 2, wall:presumed 2, water-flow 2 | blocks 1, clay 1, debris 1, ice 1, pebbles 1, snow 1, stalagmite 1, user 1, water 1 | – | – | – |
| crno-bijelo | 14 / 47 | abyss-entrance 2, ceiling-step 2, floor-meander 2, overhang 2, pit 2, rope 2, slope 2, slope:sheer 2, slope:steep 2, user 2, wall:blocks 2, wall:debris 2, wall:ice 2, wall:presumed 2, water-flow 2 | blocks 1, clay 1, debris 1, ice 1, pebbles 1, snow 1, stalagmite 1, user 1, water 1 | – | – | – |

- `boja`: vegetable-debris: 117 stroke-only path(s) in the glyph do not print with the pen off (outline_pen false)
- `crno-bijelo`: vegetable-debris: 117 stroke-only path(s) in the glyph do not print with the pen off (outline_pen false)

## Ink cover per area

Share of the inner 1.88 × 1.38 m of each 2 × 1.5 m sample that is ink, at 900 dpi (any pixel with a channel under 160; red station marks excluded, so a light solid fill such as izvorno's water counts as ink); `empty` = bare cells of 12 (0.47 m). s0 is the mockup's fixed seed, s1… the alternatives.

| Slot | Area | izvorno | boja s0 | crno-bijelo s0 | boja s1 | boja s2 |
|---|---|---|---|---|---|---|
| A00 | blocks | 6.6 % (4 empty) | 30.4 % | 31.1 % | 44.8 % | 32.3 % |
| A01 | clay | 7.8 % | 15.5 % | 16.0 % | 15.4 % | 16.7 % |
| A02 | debris | 32.4 % | 19.0 % | 19.7 % | 18.8 % | 20.6 % |
| A03 | ice | 0.1 % (11 empty) | 13.3 % | 14.8 % | 8.0 % (2 empty) | 11.5 % (1 empty) |
| A04 | pebbles | 23.1 % | 28.9 % | 30.9 % | 27.5 % | 30.2 % |
| A06 | snow | 0.0 % (12 empty) | 11.0 % (3 empty) | 11.3 % (3 empty) | 13.0 % (1 empty) | 10.9 % (2 empty) |
| A07 | stalagmite | 0.0 % (12 empty) | 2.2 % | 12.3 % | 2.2 % | 2.4 % |
| A08 | user | 0.0 % (12 empty) | 2.4 % | 13.0 % | 2.4 % | 2.6 % |
| A09 | water | 100.0 % | 11.2 % | 11.5 % | 11.2 % | 11.2 % |

## Files

| File | What |
|---|---|
| [`pregled.png`](pregled.png) | overview: changes on top, focus crops |
| [`theme-mockup_detalj_A00_blocks.png`](theme-mockup_detalj_A00_blocks.png) | focus A00 blocks at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_P41_tree-trunk.png`](theme-mockup_detalj_P41_tree-trunk.png) | focus P41 tree-trunk at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_P47_water-flow.png`](theme-mockup_detalj_P47_water-flow.png) | focus P47 water-flow at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L24_water-flow.png`](theme-mockup_detalj_L24_water-flow.png) | focus L24 water-flow at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_P43_vegetable-debris.png`](theme-mockup_detalj_P43_vegetable-debris.png) | focus P43 vegetable-debris at 2000 dpi: izvorno · boja · crno-bijelo |
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

`.csx` files are gitignored; the round re-creates them from the mockup cache (`<workspace>/runs/theme-round/mockup-4d4603032691`).

## Timings

| Step | s |
|---|---|
| themes.py check | 0.1 |
| theme_apply × 2 | 1.2 |
| headless print × 4 (parallel) | 22.4 |
| comparison sheets | 4.3 |
| focus details × 5 | 1.7 |
| ink cover + seed sheet | 2.3 |
| pregled.png | 0.4 |
| RUNLOG | 0.0 |
| **total** | **32.5** |

## Feedback → change

_To be filled by the session: the user's words on this round, and the theme.json change each one led to (see the cheatsheet)._

| # | Feedback (user) | Key | Change | Seen in |
|---|---|---|---|---|
| 1 | … | … | … | … |
