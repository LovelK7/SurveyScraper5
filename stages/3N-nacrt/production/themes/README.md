# Symbol themes

A theme decides how cSurvey draws the club's signs, lines and areas: which SVG glyph, tile or
decoration unit each one uses, in which colour, and with which pen and brush numbers. It is
applied after import, in KORAK 2, by `../tools/theme_apply.py` (project 0007: signs, lines, areas and the centerline, see [the production README](../README.md#applying-a-theme)). The design is in
[project 0007's brief](../../projects/0007-symbol-themes/brief.md) §2.3–§3.3.

`../tools/themes.py` loads and validates themes. `check_defaults.py` (the `/csurvey-defaults`
skill) validates every theme here on each run.

```text
python tools/themes.py list
python tools/themes.py check [ID]                 # all themes if ID is omitted; exit 1 on a problem
python tools/themes.py show ID [--kind signs|lines|areas|centerline|scale_rules]
```

## Contents

- [The themes](#the-themes)
- [Folder layout](#folder-layout)
- [theme.json](#themejson)
- [Keys and lookup](#keys-and-lookup)
- [Directional signs](#directional-signs)
- [What gets written](#what-gets-written)
- [Line decorations](#line-decorations)
- [Area tiles and patterns](#area-tiles-and-patterns)
- [Adding a theme](#adding-a-theme)
- [Known limits](#known-limits)

## The themes

| Id | Name | What |
|---|---|---|
| `boja` | Boja | The user's drawing (`drawing_catalogue.svg`, split by `theme_svg.py`): 14 signs (`water-drip` reuses the `water-flow:intermittent` glyph), 10 lines (8 with a decoration unit, `water-flow` as a blue dash pen, the plain red `rope`), 6 area tiles, and `water` as cSurvey's own 45° line pattern in the water-flow blue `#24A9D1`. Colours are the artwork's own colours, one per piece |
| `crno-bijelo` | Crno-bijelo | `boja` with every colour, the centerline and the station labels forced to black; `water` inherits boja's 45° line pattern, so it prints as black lines (brief §3.8) |

## Folder layout

```text
themes/<id>/
  theme.json
  signs/  lines/  areas/     theme_svg.py split output, dropped in as is
    index.json               key -> file name (':' in a key is '@' in a file name)
  report.json                the split report (provenance, not read)
```

A theme that only changes colours, like `crno-bijelo`, needs nothing but `theme.json`.

## theme.json

Keys that start with `_` are comments, at any level.

| Field | Meaning |
|---|---|
| `name` | Display name, required |
| `extends` | Another theme id. The two are deep-merged and the child wins. A cycle is an error |
| `monochrome` | A colour forced on every sign, line, decoration and area colour, and on every centerline colour (centerline, station points, labels, notes) |
| `default_color` | Colour of an entry that names none. Default black |
| `signs` | key → `{svg, color, size, render, outline_pen, rotate}`. `size` multiplies the glyph's `csurvey:scale` (baked in by `theme_apply.py`; the item's `signsize` is left alone). `render` is `fill` (default) or `outline`: the brush white and the pen in the colour, so a filled shape reads as its outline (brief §3.8). `outline_pen` (always `true` for outline; unset = *auto*): whether cSurvey's pen is traced round every path of the glyph; off, only the fills paint. Auto is off, except for a glyph with strokes and no fills, which gets the pen in the sign's colour (reported). `rotate`: extra degrees clockwise as drawn, baked into the glyph's coordinates — see [Directional signs](#directional-signs) |
| `lines` | key → `{svg, color, width, style, dash, decoration, decoration_color}` |
| `areas` | key → one of three looks, mutually exclusive: a scatter tile `{svg, color, background_color, density, zoom, angle_mode, angle, position, crop}`; a plain fill `{solid: true, color}`; a parametric hatch `{pattern: {type, angle, density, zoom, pen_style}, color, background_color}` |
| `centerline` | Overrides merged over `tdx-mapping.json` `postimport.centerline`. Names from `fix_imported_linetypes.CENTERLINE_TYPES` |
| `scale_rules` | Per print scale (`100`, `200`, `250`, `300`, `400`, `500`): design-property multipliers, e.g. `{"500": {"DesignSoilScaleFactor": 0.7}}`. Allowed names: `themes.SCALE_RULE_PROPERTIES` |

**Colours** are `"#RRGGBB"`, `"#AARRGGBB"` or a signed 32-bit ARGB int, the convention
`postimport.centerline` uses (red = `-65536`). Everything is normalised to that int.

**`svg`** is a path relative to the theme's folder. If it is left out, the entry takes
`<kind>/index.json[key]`, when the key is listed there. `null` means no artwork: a sign keeps
cSurvey's built-in glyph, a line has no decoration, an area has no tile. Within `extends`, each
path resolves against the folder of the theme that wrote it, so a child that only recolours keeps its
parent's files.

**Lines.** The base stroke is `color`, `width` (left out = keep the item's width) and `style`.
`style` is `solid`, `dash`, `dot`, `dashdot`, `dashdotdot`, `custom` (requires `dash`) or `none`.
`dash` is `[dash, gap, …]` in multiples of the pen width. `none` switches the base stroke off and
draws only the decoration; this is the double-line meander, and `ceiling-step`'s row of ⊤ units (`lines/ceiling-step@T.svg`: the split tick with a bar along its foot, hand-built in r7 — a re-split does not touch it). The decoration needs an `svg`, and
missing fields take cSurvey's defaults:

| `decoration` field | Default | cSurvey attribute |
|---|---|---|
| `spacing_pct` | 3000 (cSurvey's own overhang/cliff pens) | `decorationspacepercentage`, raw — see [Line decorations](#line-decorations) |
| `scale` | 1 | `decorationscale`: the unit is drawn at (SVG units × scale / 40) m |
| `alignment` | `auto` (`outer`, `center`, `inner`) | `decorationalignment`; auto = the side the item's built-in pen uses |
| `flip` | auto | mirror the unit across the line; auto flips it for an Inner built-in pen |
| `distance_pct` | 0 | `decorationdistancepercentage` |
| `position` | `behind` (`above`) | `decorationposition` |

**Draw a unit pointing away from the line**, the line along its bottom edge (a triangle with its base down,
an arrow pointing up). `decoration_color` defaults to the line colour.

**Areas.** A scatter tile takes `density` 1, `zoom` 1, `angle_mode` `random`, `angle` 0, `position`
`random` and `crop` `subitems` unless set. `density` is the grid step in metres and `zoom` the metres per SVG
unit (both × the survey's `DesignSoilScaleFactor`). A `pattern` takes `type` `lines` (`crossed`), `angle` 45,
`density` 1 (line spacing in metres), `zoom` 1 and `pen_style` `solid` (`dash`, `dot`, `dashdot`) — cSurvey's own
Water brush. `background_color` is optional and is **not** forced by `monochrome`.

A child may set an entry to `null` to drop the one it inherits.

## Keys and lookup

A key in `signs`, `lines` or `areas` is one of two things. It may be a **TopoDroid name** of that kind
(`tdx-mapping-catalog.json` `tdx[*].name`, subtypes included: `slope:steep`). It may also be a
**cSurvey target** (`targets.<kind>[*].to`; point targets compare without `-` and `_`, so
`waterflow` and `water-flow` are the same). Any other key is an error.

Per item, `themes.resolve(theme, kind, tdx_name, target_name)` tries:

1. the TopoDroid name recovered by `tdx_name_recover.py`;
2. then the cSurvey target;
3. then nothing, which means the built-in look.

So `slope:sheer` can look different from the other slopes, and an item drawn in cSurvey, which has
no TopoDroid name, still takes the target's look.

## Directional signs

cSurvey has no anchor point in a sign glyph: it centres the glyph's **bounding box** on the item's point and then
turns it by the item's angle (`cItemSign.vb:276-331`). The angle is TopoDroid's `orientation`, and for points that
reach the importer named exactly `air-draught` or `water-flow` it adds **+90°** (`cImportTopoDroidHelper.vb:331-334`);
cSurvey's own arrows are drawn pointing left for that reason.

- **Draw every glyph as it should look at TopoDroid orientation 0 — arrows pointing up (north)**, centred: the
  middle of the bounding box lands on the station point. (Changed in run r3, 2026-10-07: the r2 rule was "draw
  pointing left".)
- `theme_apply.py` undoes the importer's +90° itself, per item: when the name that reached the importer (the
  `--pre` file's name, i.e. after KORAK 1) is `air-draught` or `water-flow`, the glyph is turned −90° (a second
  pool entry `…_r270.svg`). Without `--pre`, signs 774/777 are assumed to have had it.
- So `water-drip` (KORAK 1: → `water-flow`, orientation +180) points down in a real cave, and
  `water-flow:intermittent` (→ `waterflow`, no +90°) points up — with the same glyph and no `rotate`.
- **Settled (user, r6):** arrows are drawn pointing up and the automatic −90° stays; no `rotate` in `boja`.
- `rotate` stays for art drawn some other way. `csurvey:rotationangledelta` does **not** turn anything (no render
  path reads it, run r2).

## What gets written

| Kind | Where | Item reference |
|---|---|---|
| sign | glyph in `<signs><cliparts>`; inline `type="99"` pen (style None) and brush named `tema:<id>` | `data=` repointed |
| line | library pen in the root `<pens>`, one per (key, built-in pen type): `type="98" id="tema-<theme>-line-<key>-<type>" name="tema:<theme>:<key>/<type>"` | `<pen type="98" id="…"/>` |
| area | library brush in `<brushes>`, one per (key, built-in brush type) | `<brush type="98" id="…">`, the item's `<seed>` kept |

Pens and brushes are written attribute for attribute as `cCustomPen.SaveTo` / `cCustomBrush.SaveTo` write them; a
headless cSurvey load + save of the r3 mockup returns all 10 pens and 6 brushes, clipart text included,
unchanged. The decoration unit or tile is the theme SVG as one line of text in `<clipart data="&lt;svg …"/>`.
A User pen with width 0 would be a hairline (`GetPenDefaultWidth` has no case for it), so an unset `width` is written
as the built-in pen's own (`BaseMediumLinesScaleFactor` from the file, else 3; heavy 8; ultralight 0.1).
Undo state (library ids with each one's built-in type, whether `<pens>`/`<brushes>` were created) is in
`CaveDossierThemeState`; switching themes and re-applying are byte-identical.

## Line decorations

How cSurvey lays units along a line (`cClipartOnPath.vb`; every imported line is a spline after KORAK 2):

- The unit is scaled by `decorationscale × DesignTerrainLevelScaleFactor / 40` (SVG units → metres).
- On a spline the path is rasterised into points 0.01 m apart along the major axis and the unit is placed every
  `W × (1 + spacing/10)` *points*, W being the unit's width in metres (min 0.1 m): pitch ≈ `0.01 × W ×
  (1 + spacing/10)` m on a horizontal or vertical run, up to 41 % more on a diagonal. So spacing 990 butts the
  units, 3000 (cSurvey's own) leaves about two widths of gap, and cSurvey's bare default 100 piles them up.
  `spacing_pct` is this raw number (what T7 will harvest), and theme_apply writes at least 0.1.
- All units of a line are one path filled **even-odd**: where two units overlap, the overlap prints white.
- The unit is painted by its fills only (`clipartpenstyle` None). Strokes in a unit are outlined into fills by
  `theme_svg.py split`.

## Area tiles and patterns

- A tile is scattered on a `density` m grid, randomly turned and shifted, scaled by `zoom` m per SVG unit; only
  filled paths paint (a stroke would not — `split` outlines them). `crop subitems` (default) keeps only whole
  shapes, `none` clips at the area edge (used for the outlined `blocks` stones), `full` keeps only whole tiles.
- The placement seed lives on the item (`<seed>` under its brush); an area with none gets a random one at each load.
  cSurvey's importer seeds only areas whose built-in brush is a clipart, so the theme mockup gets fixed seeds
  after import (`make_theme_mockup.py --seed-imported`, done by `theme_round.py`): every round prints the same
  placement, and `theme_round.py --seeds N` adds N alternatives.
- `pattern` is cSurvey's parametric hatch: spacing `density` m, angle in degrees, a hairline pen.

The theme mockup (`tools/make_theme_mockup.py`) has every themed sign, at orientation 0, for checking this on a
print.

## Adding a theme

1. Draw in Illustrator per the brief §2.4. Export the SVG and run
   `python tools/theme_svg.py split export.svg themes/<id>`.
2. Write `themes/<id>/theme.json`, with at least `name`. List each key you want themed and give it a
   colour. The SVG paths come from the `index.json` files.
3. A variant of an existing theme needs only `{"name": …, "extends": "<base>", …overrides}`.
4. `python tools/themes.py check <id>` must print `OK`. Then run
   `python .claude/skills/csurvey-defaults/check_defaults.py`.

## Known limits

- **`spacing_pct` 0 does not survive cSurvey on its own.** cSurvey reads a stored
  `decorationspacepercentage` of 0 as 100 (`cPen.vb:434-435`); theme_apply writes at least `0.1`.
- **The double-line meander cannot be made continuous.** Its rails are chains of units; on a spline the pitch
  varies with direction (up to +41 % on diagonals) and with point rounding at segment ends
  (`pGetLinePoints` stops at 0.1 m rounding), and overlaps cancel even-odd. Spacing 990 butts them on straight
  runs; curves show gaps (run r3, `theme-mockup_meander_detalj.png`). A cSurvey limitation.
- **Item transparency + a style-None pen crashes cSurvey**: `cCustomPen.Render` reads `oPen.Color` when the
  item's transparency is set (`cPen.vb:1021-1023`), and a style-None pen has no GDI pen. Applies to themed signs
  and the meander. Do not set transparency on them.
- **Widths and scales are frozen per pen.** A library pen's width is a number, so a per-scale
  `BaseMediumLinesScaleFactor` scale rule no longer reaches it; `BaseLineWidthScaleFactor` and
  `DesignTerrainLevelScaleFactor` still do (the latter also changes decoration spacing).
- `monochrome` turns a `solid` area such as water into solid black, and leaves KORAK 2's light-blue
  non-standard water alone if the theme does not list `water`. Both shipped themes list it as a line pattern
  (blue in `boja`, black in `crno-bijelo` through `monochrome`; run r6).
- **`vegetable-debris` prints its fills only** (settled, user r6): its 117 stroke-only hairlines do not print with
  the pen off (`outline_pen` auto = off, reported by `theme_apply`); kept that way, no outline pen.
- Numbers (density, zoom, spacing, scale) are cSurvey's defaults until T7 harvests tuned values.
