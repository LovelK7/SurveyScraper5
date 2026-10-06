# T3 run: themes applied to SB 1103, 2026-10-06

Input: `example/finishing/SB_1103_golobreska_lt_fin.csx` (after KORAK 2 and 3). Pre-import file:
`SB_1103_golobreska_tdx_raw.csx`. The `.csx` outputs are gitignored. Only PDFs and PNGs are kept here.

```text
python production/tools/theme_apply.py apply example/finishing/SB_1103_golobreska_lt_fin.csx \
    --theme boja|crno-bijelo --pre example/finishing/SB_1103_golobreska_tdx_raw.csx -o runs/.../SB_1103_<theme>.csx
python production/tools/csurvey_driver.py print <out> -o runs/2026-10-06-t3      # C:\csurvey64, headless
```

## Name recovery

There are 23 items. 15 are recovered exactly or within tolerance, 1 is mixed (merged wall + wall:presumed), 3 are native (drawn in cSurvey) and 1 sign is a miss: the plan entrance, which the user moved.

Of the 4 sign items:

- the 2 profile `blocks` are themed by TopoDroid name;
- the profile `entrance` is recovered, but no theme entry matches it;
- the plan `entrance` is a miss, falls back to the target `entrance`, and has no theme entry either.

## Themed

| Theme | Signs themed | Glyph | Coloured | Black built-in | Pool | Centerline |
|---|---|---|---|---|---|---|
| boja | 2 (blocks) | 2 | 2 (#78787A) | 0 | +1 `2825C49B…3DFB` blocks.svg | 0 |
| crno-bijelo | 2 | 2 | 0 | 2 | +1 (same id) | 6 colours → black |

Phase 2 would also touch 8 lines (overhang 2, pit 1, slope:steep 5) and 6 areas (blocks 4, debris 2). It is reported only.

## Idempotency (all `cmp` byte-identical)

- boja→boja = boja, and crno-bijelo→crno-bijelo = crno-bijelo.
- boja→crno-bijelo = crno-bijelo. The previous theme is undone first, the unused theme glyph is removed from the pool and re-added, and nothing is left over.
- crno-bijelo→boja = boja, including the 6 centerline colours restored to their KORAK 2 values.
- boja-obrub (outline, size 1.5)→boja = boja.
- `.csz`: applying the same theme twice gives identical zips.

## cSurvey round trip (headless `recalc`, load + save)

`SB_1103_boja.csx` → saved by cSurvey: no change except the view/`<sm>` churn. The design properties
`CaveDossierTheme`/`CaveDossierThemeState`, the `tema:boja` pens and brushes, and the pool entry all survive. The first
version left out the pen's empty `<clipart data=""/>`, which cSurvey adds on save. It is now written too. Re-theming
the cSurvey-saved file to crno-bijelo works (undo 2, pool −1/+1).

## Prints

The `*_plan.pdf` / `*_profile.pdf` files are 1:1 cSurvey headless prints. Each `.png` is page 1 at 110 dpi.
`SB_1103_profile_znakovi_usporedba.png` shows the two profile blocks at 300 dpi, left to right:
izvorno · boja · crno-bijelo · cb-obrub · boja-obrub · boja (.csz).

- `izvorno`: the input, with cSurvey's own blocks glyph.
- `boja`: the club glyph in grey, fill and outline in one colour.
- `crno-bijelo`: the same glyph in black. The centerline, station triangle and label "2" are black too.
- `cb-obrub` (scratch theme: crno-bijelo + `blocks: render outline`): a white fill with black outlines.
- `boja-obrub` (scratch theme: boja + `blocks: outline, size 1.5`): grey outlines, 1.5× larger.
- `boja_csz`: the same as boja, from a `.csz` container.

No clipart_error X-boxes in any print.
