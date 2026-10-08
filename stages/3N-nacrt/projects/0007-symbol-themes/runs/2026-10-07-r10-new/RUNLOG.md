# Theme round r10-new, 2026-10-07

Written by `production/tools/theme_round.py` ([cheatsheet](../../../../production/tools/theme_tuning_cheatsheet.md)). Command:

```text
python production/tools/theme_round.py r10-new --focus wall:blocks,wall:debris,wall:ice,lines/user,areas/user,ice,blocks,debris --seeds 2
```

## Look at these first

- [`pregled.png`](pregled.png) — what changed this round, then the focus crops.
- [`theme-mockup_detalj_L18_wall@blocks.png`](theme-mockup_detalj_L18_wall@blocks.png) — focus L18 wall:blocks at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L20_wall@debris.png`](theme-mockup_detalj_L20_wall@debris.png) — focus L20 wall:debris at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L21_wall@ice.png`](theme-mockup_detalj_L21_wall@ice.png) — focus L21 wall:ice at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_L16_user.png`](theme-mockup_detalj_L16_user.png) — focus L16 user at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_A08_user.png`](theme-mockup_detalj_A08_user.png) — focus A08 user at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_A03_ice.png`](theme-mockup_detalj_A03_ice.png) — focus A03 ice at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_P04_blocks.png`](theme-mockup_detalj_P04_blocks.png) — focus P04 blocks at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_A00_blocks.png`](theme-mockup_detalj_A00_blocks.png) — focus A00 blocks at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_P11_debris.png`](theme-mockup_detalj_P11_debris.png) — focus P11 debris at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_detalj_A02_debris.png`](theme-mockup_detalj_A02_debris.png) — focus A02 debris at 2000 dpi: izvorno · boja · crno-bijelo
- [`theme-mockup_znakovi_usporedba.png`](theme-mockup_znakovi_usporedba.png) — znakovi, every themed slot: izvorno · boja · crno-bijelo (900 dpi crops)
- [`theme-mockup_linije_usporedba.png`](theme-mockup_linije_usporedba.png) — linije, every themed slot: izvorno · boja · crno-bijelo (800 dpi crops)
- [`theme-mockup_plohe_usporedba.png`](theme-mockup_plohe_usporedba.png) — plohe, every themed slot: izvorno · boja · crno-bijelo (600 dpi crops)
- [`theme-mockup_plohe_seedovi.png`](theme-mockup_plohe_seedovi.png) — boja areas, one row per placement seed; ink cover in RUNLOG

## Inputs

| What | Value |
|---|---|
| drawing | `drawing_catalogue.svg`, modified 2026-10-07 20:49 – not re-split |
| themes | `boja`, `crno-bijelo` |
| mockup cache | `mockup-4d4603032691` (built this round) |
| cache key inputs | cSurveyPC.exe 11813888-1760291706, fix_imported_linetypes.py 1273bfa69545db9e, make_theme_mockup.py 19bb15ab6d47ebe8, tdx-mapping.json df550d655b2c2e4a, wall_orient.py e7f2d3ca6515c809 |
| cSurvey (prints) | `C:\csurvey64` |
| cSurvey (import) | DTD-free copy under the cache |
| area seeds | fixed per area (make_theme_mockup.area_seed); 2 alternative(s) |

## theme.json changes

Against [`2026-10-07-r9f-wall`](../2026-10-07-r9f-wall/RUNLOG.md) (copies in [`themes/`](themes/)):


`boja`:

| | Path | Before | After |
|---|---|---|---|
| + | `areas.user` | – | {"_note": "new artwork (user, r10); density first guess = the 0.75 m tile width", "color": "#C28935", "density": 0.75, "zoom": 0.05} |
| + | `lines.user` | – | {"_note": "new artwork (user, r10): line and units in the drawing's colour; first guess spacing 1500", "color": "#C28935", "decoration": {"scale": 2, "spacing_pct": 1500}, "style": "solid"} |
| + | `lines.wall:blocks` | – | {"_note": "new artwork (user, r10): black wall line, grey stone units outside it; first guess spacing 1300 for the 1.4 m unit", "color": "#000000", "decoration": {"scale": 2, "spacing_pct": 1300}, "decoration_color": "#ABABAB", "style": "solid"} |
| + | `lines.wall:debris` | – | {"_note": "new artwork (user, r10): as wall:blocks", "color": "#000000", "decoration": {"scale": 2, "spacing_pct": 1300}, "decoration_color": "#ABABAB", "style": "solid"} |
| + | `lines.wall:ice` | – | {"_note": "new artwork (user, r10): black wall line, ice-blue units; first guess spacing 1500", "color": "#000000", "decoration": {"scale": 2, "spacing_pct": 1500}, "decoration_color": "#468FA0", "style": "solid"} |
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
| A00 | blocks | 6.6 % (4 empty) | 20.6 % | 22.0 % | 27.7 % | 21.7 % |
| A01 | clay | 7.8 % | 15.5 % | 16.0 % | 15.4 % | 16.7 % |
| A02 | debris | 32.4 % | 19.0 % | 19.7 % | 18.8 % | 20.6 % |
| A03 | ice | 0.1 % (11 empty) | 13.3 % | 14.8 % | 8.0 % (2 empty) | 11.5 % (1 empty) |
| A04 | pebbles | 23.1 % | 28.9 % | 30.9 % | 27.5 % | 30.2 % |
| A06 | snow | 0.0 % (12 empty) | 11.0 % (3 empty) | 11.3 % (3 empty) | 13.0 % (1 empty) | 10.9 % (2 empty) |
| A07 | stalagmite | 0.0 % (12 empty) | 100.0 % | 100.0 % | 100.0 % | 100.0 % |
| A08 | user | 0.0 % (12 empty) | 2.7 % | 13.6 % | 2.8 % | 2.8 % |
| A09 | water | 100.0 % | 11.2 % | 11.5 % | 11.2 % | 11.2 % |

## Files

| File | What |
|---|---|
| [`pregled.png`](pregled.png) | overview: changes on top, focus crops |
| [`theme-mockup_detalj_L18_wall@blocks.png`](theme-mockup_detalj_L18_wall@blocks.png) | focus L18 wall:blocks at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L20_wall@debris.png`](theme-mockup_detalj_L20_wall@debris.png) | focus L20 wall:debris at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L21_wall@ice.png`](theme-mockup_detalj_L21_wall@ice.png) | focus L21 wall:ice at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_L16_user.png`](theme-mockup_detalj_L16_user.png) | focus L16 user at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_A08_user.png`](theme-mockup_detalj_A08_user.png) | focus A08 user at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_A03_ice.png`](theme-mockup_detalj_A03_ice.png) | focus A03 ice at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_P04_blocks.png`](theme-mockup_detalj_P04_blocks.png) | focus P04 blocks at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_A00_blocks.png`](theme-mockup_detalj_A00_blocks.png) | focus A00 blocks at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_P11_debris.png`](theme-mockup_detalj_P11_debris.png) | focus P11 debris at 2000 dpi: izvorno · boja · crno-bijelo |
| [`theme-mockup_detalj_A02_debris.png`](theme-mockup_detalj_A02_debris.png) | focus A02 debris at 2000 dpi: izvorno · boja · crno-bijelo |
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
| themes.py check | 0.0 |
| DTD-free cSurvey copy (reused) | 0.0 |
| mockup: generate | 0.0 |
| mockup: headless import (DTD-free copy) | 4.7 |
| mockup: KORAK 2 + 12 fixed area seeds | 0.2 |
| mockup: izvorno print | 7.5 |
| theme_apply × 2 | 0.4 |
| headless print × 4 (parallel) | 17.9 |
| comparison sheets | 6.0 |
| focus details × 10 | 3.0 |
| ink cover + seed sheet | 2.8 |
| pregled.png | 0.7 |
| RUNLOG | 0.0 |
| **total** | **43.3** |

## Feedback → change

_To be filled by the session: the user's words on this round, and the theme.json change each one led to (see the cheatsheet)._

| # | Feedback (user) | Key | Change | Seen in |
|---|---|---|---|---|
| 1 | ice gets a thick outline | ice (all tiles) | none: cSurvey fills **and** strokes every tile path with the brush pen (`cBrush.pRenderClipart` → `AddFiller(path, oPen, …)`, width `BrushLinesScaleFactor` 0.1 × line width); no theme field writes it (`scale_rules` validated only) → feature | A03 |
| 2 | wall:presumed identical to wall | wall:presumed | none this round: PDF vectors show wall 0.127 mm and r9f's wall:presumed 0.127 mm (izvorno 0.296); the user's snip was the r9-feedback sheet | r9f-wall |
| 3 | mud P23 = sand P32 symbol | – | mapping (`tdx-mapping.json` mud → clay); /csurvey-defaults, not a round | – |
| 4 | new wall:blocks, wall:debris, wall:ice, user | lines + areas | new entries: base black, units in the split colour, scale 2, spacing 1300/1300/1500/1500; area user density 0.75 | L18 L20 L21 L16 A08 |
| 5 | debris and blocks filled instead of white | artwork | the r10 export has them as grey fills with no stroke (r9 export: stroked / ring paths) → redraw | A02 L18 L20 |
| – | (split) stalagmite group gone from the drawing | stalagmite | `svg` pinned to the kept r8 tile | – |
