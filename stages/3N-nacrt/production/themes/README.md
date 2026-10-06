# Symbol themes

A theme decides how cSurvey draws the club's signs, lines and areas: which SVG glyph, tile or
decoration unit each one uses, in which colour, and with which pen and brush numbers. It is
applied after import, in KORAK 2, by `../tools/theme_apply.py` (project 0007 T3; phase 1 = signs and the centerline, see [the production README](../README.md#applying-a-theme)). The design is in
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
- [Adding a theme](#adding-a-theme)
- [Known limits](#known-limits)

## The themes

| Id | Name | What |
|---|---|---|
| `boja` | Boja | The user's drawing (`drawing_catalogue.svg`, split by `theme_svg.py`): 12 signs, 10 lines (9 with a decoration unit, plus the plain red `rope`), 6 area tiles. Colours are the artwork's own colours, one per piece |
| `crno-bijelo` | Crno-bijelo | `boja` with every colour, the centerline and the station labels forced to black |

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
| `signs` | key → `{svg, color, size, render, outline_pen, rotate}`. `size` multiplies the glyph's `csurvey:scale` (baked in by `theme_apply.py`; the item's `signsize` is left alone). `render` is `fill` (default) or `outline`: the brush white and the pen in the colour, so a filled shape reads as its outline (brief §3.8). `outline_pen` (default `false` for fill, always `true` for outline): whether cSurvey's pen is traced round every path of the glyph; off, only the fills paint. `rotate`: degrees clockwise as drawn, baked into the glyph's coordinates — see [Directional signs](#directional-signs) |
| `lines` | key → `{svg, color, width, style, dash, decoration, decoration_color}` |
| `areas` | key → `{svg, color, background_color, density, zoom, angle_mode, angle, position}`, or `{solid: true, color}` for a plain fill such as water |
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
draws only the decoration; this is the double-line meander. The decoration needs an `svg`, and
missing fields take cSurvey's defaults:

| `decoration` field | Default | cSurvey attribute |
|---|---|---|
| `spacing_pct` | 100 | `decorationspacepercentage` |
| `scale` | 1 | `decorationscale` |
| `alignment` | `outer` (`center`, `inner`) | `decorationalignment` |
| `distance_pct` | 0 | `decorationdistancepercentage` |
| `position` | `behind` (`above`) | `decorationposition` |

`decoration_color` defaults to the line colour.

**Areas.** A scatter tile takes `density` 1, `zoom` 1, `angle_mode` `random`, `angle` 0 and
`position` `random` unless set. `background_color` is optional and is **not** forced by
`monochrome`.

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
turns it by the item's angle (`cItemSign.vb:276-331`). The angle is TopoDroid's `orientation`, and for the exact
point names `air-draught` and `water-flow` the importer adds **+90°** (`cImportTopoDroidHelper.vb:331-333`).
cSurvey's own arrows (`corrente d'aria.svg`, `acqua.svg`) are therefore drawn **pointing left (−x), horizontal**,
and come out pointing up (north) at orientation 0, as in TopoDroid.

- **Draw arrow glyphs pointing left**, head on the left, tail on the right, centred: the middle of the bounding
  box lands on the station point.
- `csurvey:rotationangledelta` (which cSurvey's stock glyphs carry) does **not** turn anything: cSurvey keeps it
  as clipart metadata and no render path reads it (checked on a print, run r2).
- Art drawn another way is fixed with the sign's `rotate`, which `theme_apply.py` bakes into the coordinates.
  `boja` uses `rotate: 180` on `air-draught` (drawn pointing right).
- `water-flow:intermittent` reaches cSurvey as `waterflow` (KORAK 1 mapping) or unchanged; neither gets the
  +90°, so a left-pointing glyph points left. `boja` uses `rotate: 90` for it; drop that if the mapping is changed
  to `water-flow`.

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
  `decorationspacepercentage` of 0 as 100 (`cPen.vb:434-435`) and saves it with one decimal. So T3
  must write a small positive value of at least `0.1` for `floor-meander`'s butted rails.
- `monochrome` turns a `solid` area such as water into solid black. A B/W theme that has one should
  override that entry.
- Numbers (density, zoom, spacing, scale) are cSurvey's defaults until T7 harvests tuned values.
