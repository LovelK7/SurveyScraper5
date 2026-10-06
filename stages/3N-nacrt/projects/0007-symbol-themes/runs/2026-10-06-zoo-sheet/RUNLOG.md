# Zoo sample sheet: themes on the symbol zoo, 2026-10-06

This is the colour-iteration printout. Every TopoDroid symbol is printed with its name next to it, once without a
theme, once in `boja` and once in `crno-bijelo`.

**Look at this first:** [`zoo_znakovi_usporedba.png`](zoo_znakovi_usporedba.png). It shows the 8 themed signs zoomed
in, in three columns: izvorno · boja · crno-bijelo. The red station labels are faded so the signs are easier to read.
They are still black in `crno-bijelo`, because the theme also blackens the centerline.

## Input and procedure

The fixture is the symbol-zoo pair from project 0002,
`projects/0002-tdx-symbol-mapping/runs/2026-07-19-symbol-zoo/`:

- `step-03-zoo-v3.csx` is the pre-import file. It has every TopoDroid symbol, with station labels that name it.
- `step-04-after-import.csx` is the same file after cSurvey's import.
- The layout is in that folder's `zoo-key-v3.md`: 20 slots per row, with points P00–P44, lines L00–L19 and areas
  A00–A08.

The `.csx` files are gitignored. Only the PDFs and PNGs are kept here.

```text
python production/tools/fix_imported_linetypes.py <zoo>/step-04-after-import.csx -o zoo_izvorno.csx     # KORAK 2
python production/tools/theme_apply.py apply zoo_izvorno.csx --theme boja|crno-bijelo \
    --pre <zoo>/step-03-zoo-v3.csx -o zoo_<theme>.csx
CSURVEY_DIR=C:\csurvey64 python production/tools/csurvey_driver.py print zoo_<theme>.csx -o <this dir> --design Plan
```

- The `zoo_*_plan.png` files are page 1 at 110 dpi, rendered with PyMuPDF.
- The `*_znakovi*.png` files are crops of the same PDFs: 500 dpi for the comparison and 700 dpi for each theme.
- They were made with a scratch script that is not kept.

## Name recovery and theming

- Name recovery (`tdx_name_recover`) gives 43/43 sign items recovered, plus 105 other items recovered and 1 exact.
- Of the 43 signs, 8 were themed, all by their TopoDroid name. The other 35 have no theme entry.
- Before theming, 5 of the 8 printed as X-boxes, because these TopoDroid names have no cSurvey sign without the
  KORAK 1 mapping: danger, debris, minus, plus and plus-minus. The theme glyph replaces the X-box.
- **Idempotency on the zoo** (checked with `cmp`, byte-identical): boja→crno-bijelo = crno-bijelo,
  crno-bijelo→boja = boja, boja→boja = boja.
- **Pool entries** are named `tema-boja_<file>.svg` / `tema-crno-bijelo_<file>.svg`: 8 added per theme.

| Theme sign key | In the zoo | Themed | Method |
|---|---|---|---|
| air-draught | yes (P00) | yes | TopoDroid name |
| blocks | yes (P04) | yes | TopoDroid name |
| continuation | yes (P06) | yes | TopoDroid name |
| danger | yes (P09, X-box before) | yes | TopoDroid name |
| debris | yes (P10, X-box before) | yes | TopoDroid name |
| minus | yes (P20, X-box before) | yes | TopoDroid name |
| plus | yes (P27, X-box before) | yes | TopoDroid name |
| plus-minus | yes (P28, X-box before) | yes | TopoDroid name |
| bones | no | – | – |
| tree-trunk | no | – | – |
| vegetable-debris | no | – | – |
| water-flow:intermittent | no. The zoo has only the plain `water-flow` point (P44), which stays unthemed | – | – |

In total, 8 of the 12 theme signs appear in the zoo and all 8 are themed. No sign needed the target fallback. The zoo
has no subtypes and no `bones`, `tree-trunk` or `vegetable-debris` points, so those 4 still need a fixture. A
zoo v4 with them would close the gap.

**Lines and areas are not themed yet (phase 2).** The report only counts what a theme would reach:
- lines: floor-meander, overhang, pit, slope and water-flow, 1 each;
- areas: blocks, clay, debris, ice and pebbles, 1 each.

They print the same in all three sheets.

## Things to notice in the renders

- **Colours.** In `boja`, blocks and debris are grey (#78787A) and the other 6 are black, through the built-in
  pen and brush. In `crno-bijelo`, all 8 are black, and so are the centerline, the station triangles and the
  labels.
- **Size.** The club glyphs come out noticeably larger and heavier than cSurvey's own at the same `signsize`, most
  visibly for blocks. This is the `csurvey:scale` relative to the median sign. If it looks too big, it can be tuned
  with a theme `size`.
- **Anchor.** The `air-draught` glyph hangs below the station, while cSurvey's own hangs from it. The club arrow's
  tail sits at the top.
- **Overlap.** On this synthetic sheet, the station labels (P00 …) overlap the signs. That comes from the zoo layout,
  not the theme. In `crno-bijelo` the labels are black, so the overlap is more visible.
- **X-boxes.** All 8 themed signs render with the club glyph and no X-box. The X-boxes that remain in all three
  sheets are unthemed zoo symbols with no glyph in this cSurvey build, the same in izvorno: anchor,
  archeo-material, clay, gradient, ice, mud, sand, snow, user, water and water-drip (project 0002, step-02).
