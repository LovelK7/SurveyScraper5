# Theme mockup, round 3: lines and areas themed (phase 2), 2026-10-07

Round 3 of the colour-iteration printout ([round 2](../2026-10-07-zoo-sheet-r2/RUNLOG.md)). What changed:

- **Lines and areas are themed** (user, 2026-10-06 evening: "I don't see any of the lines implemented … ice is empty,
  colours are not implemented … rope is not coloured red?"). Library pens and brushes, [themes/README.md](../../../../production/themes/README.md#what-gets-written).
- **Artwork refresh** from `drawing_catalogue.svg` (20:19 export; re-split into `findings/t1-split/` and
  `production/themes/boja/`). New sign `water-flow`; reworked `water-flow:intermittent`, `air-draught` (now
  pointing up), `bones` (outline drawn as compound paths with holes), `blocks` sign (fills). The `blocks` AREA tile
  is stroke-only: the split now outlines strokes into fills for line units and area tiles. `_rest` layer skipped; no
  unnamed groups left.
- **Arrow convention changed**: glyphs are drawn as they look at orientation 0 (pointing up); `theme_apply`
  undoes cSurvey's +90° for `air-draught` / `water-flow` itself. `boja` has no `rotate` any more.
- `boja`: new `water-drip` (the intermittent glyph), `water-flow` sign; `crno-bijelo`: `water` as a 45° line pattern.

**Look at these first:**

1. [`theme-mockup_linije_usporedba.png`](theme-mockup_linije_usporedba.png) — the 10 themed lines, straight (top) and
   curved (bottom): izvorno · boja · crno-bijelo.
2. [`theme-mockup_plohe_usporedba.png`](theme-mockup_plohe_usporedba.png) — the themed areas (6 + B/W water).
3. [`theme-mockup_znakovi_usporedba.png`](theme-mockup_znakovi_usporedba.png) — the 14 themed signs.
4. [`theme-mockup_meander_detalj.png`](theme-mockup_meander_detalj.png) — the double-line meander up close.

| File | What |
|---|---|
| `theme-mockup_{znakovi,linije,plohe}_usporedba.png` | per kind, every themed slot: izvorno · boja · crno-bijelo (crops of the PDFs at 500–900 dpi; red station marks faded) |
| `theme-mockup_meander_detalj.png` | L06 floor-meander at 1400 dpi |
| `theme-mockup_<izvorno\|boja\|crno-bijelo>_plan.pdf` (+ `.png` page at 110 dpi) | cSurvey headless plan prints |
| `report_boja.json`, `report_crno-bijelo.json` | `theme_apply.py --json` |
| `theme-mockup-key.md`, `theme-mockup-layout.json` | slots (station = slot tag) and world coordinates |

`.csx` files are gitignored; regenerate them with the r2 procedure (unchanged:
[r2 RUNLOG, Procedure](../2026-10-07-zoo-sheet-r2/RUNLOG.md#procedure)); the headless import used the DTD-free
scratch copy of `C:\csurvey64` again, prints the real install. KORAK 1 skipped as in r1/r2.

## Results per key

Name recovery 47/47 signs, 154/154 other items. Every theme key below was found by its TopoDroid name.

### Lines (library pen `tema-<theme>-line-<key>-<built-in type>`)

| Key | Built-in pen (izvorno) | boja | crno-bijelo | Notes |
|---|---|---|---|---|
| abyss-entrance | 2 plain border | triangles, inner side + flipped (target overhang's side), scale 2 | black | side taken from the KORAK 1 target, since the raw name gives a plain pen |
| ceiling-step | 2 plain border | ticks, chimney's side | black | |
| floor-meander | 21 meander | base off, butted double-rail unit, centre, spacing 990 | black | **rails break up on the curve** — see below |
| overhang | 12 overhang (Inner) | user triangles, same side as cSurvey's | black | matches stock spacing and size |
| pit | 5 cliff down | user ticks | black | |
| rope | 2 plain border | **red #EF5553, width 0.1** (thin) | black, plain | |
| slope | 7 gradient down | user arrows, centred, flipped like the stock down arrow; scale 0.8 | black | the drawn arrow is 4× the triangles; scale 0.8 gives cSurvey's 0.4 m |
| slope:sheer | 2 plain | user triangles, slope's side | black | |
| slope:steep | 2 plain | small triangles | black | 0.07 m units: barely visible at A4 |
| water-flow | 2 plain | blue #42B4C0 dash pen, width 5.35, dash 26/8 (the drawn unit read as a dash) | black dashed | the unit file stays unused |

### Areas (library brush `tema-<theme>-area-<key>-<built-in type>`)

| Key | izvorno | boja | crno-bijelo |
|---|---|---|---|
| blocks | big debris (black outlines) | outlined grey stones (#616262), crop none, density 1.8 | black |
| clay | sand brush | ochre dot clusters | black |
| debris | small debris | grey pieces | black |
| ice | blank soil (white) | **teal tile** (#468FA0) | black |
| pebbles | pebbles | ochre clusters | black |
| stalagmite | blank soil | black dash marks | black |
| water | light-blue non-standard (KORAK 2) | unchanged (not in boja) | **45° lines** (cSurvey's Water brush values) |

`snow` and `user` areas have no theme entry and stay blank.

### Signs

All 14 themed: the arrows (air-draught, water-flow, water-flow:intermittent, water-drip) point up; air-draught and
water-flow through the automatic −90° (pool entries `…_r270.svg`). `bones` prints hollow (its contours wind
opposite ways, so even-odd and nonzero agree). `vegetable-debris` still loses its 117 stroke-only hairlines (pen
off, reported). `water-drip` points up here because KORAK 1 is skipped; in a real cave KORAK 1 sends it as
`water-flow` + 180°, which then points down.

## Checks

- `theme_apply` boja→boja, boja→crno-bijelo, crno-bijelo→boja: byte-identical to a single apply.
- Headless cSurvey load + save of `theme-mockup_boja.csx`: all 10 library pens and 6 brushes (clipart text included)
  and the 26 item references come back identical; re-theming the saved file to crno-bijelo gives the same
  libraries and references as a direct apply.

## What cSurvey did unexpectedly (from its source)

- **A User (98) pen with width 0 is a hairline**: `GetPenDefaultWidth` has no case for it (`cOptions.vb:1394-1426`).
  theme_apply writes the built-in pen's width out.
- **Decoration spacing is counted in rasterised points**, not metres (`cClipartOnPath.pDrawClipart`): pitch
  ≈ 0.01 × W × (1 + spacing/10) m on axis-aligned runs, more on diagonals and at segment ends; cPen's bare default
  100 would pile units up. The theme default is now 3000 (cSurvey's own).
- **Decoration units and brush tiles paint only filled paths**; a stroke-only path is never drawn. Hence the split
  now outlines strokes in line units and tiles.
- **Even-odd everywhere**: all units of one line form one path filled even-odd, so overlapping units print white.
- The meander: spacing 990 butts the rails on straight runs (a few 1-point gaps from integer rounding); on the
  sine they break into separate pieces. Not fixable by spacing — a cSurvey limitation.
- Brush tiles are placed on a randomly jittered grid, so a small area can come out unevenly covered (A00 blocks).

## Open

- Meander: keep the double-rail unit with gaps on curves, go back to cSurvey's own meander pen, or draw a unit
  without rails (ticks only on one centred rail = base stroke on)?
- Water pattern spacing: cSurvey's own density 1 (1 m between lines) reads sparse on small pools; 0.3 would read as
  water at A4. Kept at cSurvey's value as asked.
- Sizes/spacings/densities are first guesses until T7 (tune in cSurvey, harvest).
