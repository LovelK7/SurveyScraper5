# Task brief: Symbol themes — custom SVG signs, pens and brushes, chosen per cave in Mapiranje simbola

- **ID:** 0007-symbol-themes
- **Status:** `validation` — signs, lines and areas are themed end to end on the mockup (`boja` + `crno-bijelo`), tuned with the user over rounds r1–r7 (2026-10-07). TopoDroid-name keys work (T8). T4 done 2026-10-07 (Tema card on Mapiranje simbola, saved as `"theme"` in the cave override, theme previews). Tuning rounds r9–r11 done the same day. T5 done 2026-10-07: KORAK 2 themes the `_postp` with the cave's theme (`theme_apply.korak2_step`), the kit (v1.7, not yet published) ships `csurvey_alati/teme/`. T9 done 2026-10-07 (labels → theme glyphs in the theme step; anchor stays `f`). Next: SB 1103 printed in both themes for the user's sign-off (T6), `/publish` csx kit v1.7, close-out. T7 superseded by `/theme-round`. See "State at session end" in §3.6.
- **Owner:** both
- **Opened:** 2026-10-04 · **Closed:** —
- **Read first:** [the superapp CLAUDE.md](../../../../CLAUDE.md), [README.md](../../README.md), [backlog/custom-sign-palette.md](../../backlog/custom-sign-palette.md) (the parked predecessor idea), [production/tdx-symbol-matrix.md](../../production/tdx-symbol-matrix.md), [reference/data-model-and-file-format.md](../../reference/data-model-and-file-format.md), [.claude/skills/csurvey-defaults/SKILL.md](../../../../.claude/skills/csurvey-defaults/SKILL.md)

> This brief is self-contained: a fresh session can pick it up from cold and know exactly what to do
> and where the work stands, without inheriting any prior conversation.

---

## 1. Problem — what's wrong / missing, and why it matters

Today the look of a Nacrt from the cSurvey route is fixed. KORAK 1 only **renames** TopoDroid items.
cSurvey's importer then picks a built-in `SignEnum` glyph from the install's
`Objects\Cliparts\Signs` folder, plus a built-in pen and brush type number. The user has a
complete vector symbol set prepared in Adobe Illustrator and wants to:

1. choose a **set of graphics** (signs, line decorations, area fills) instead of the single built-in one;
2. choose a **theme**, e.g. *colour* vs *black and white*, per cave on the dashboard's
   3N › *Mapiranje simbola* page.

Side benefits: the 8 mapped signs that have no glyph in the installed build (X-boxes, see the
symbol matrix) and the 29 speleo-2 points with no cSurvey sign could all get real artwork. The
mapping page's pictures, which today exist only on a developer machine, would come from the
theme folder that ships in the kit.

## 2. Context — what's already known (verified 2026-10-04 unless marked *assumed*)

### 2.1 What the pipeline writes today

- **Mapping.** `production/tools/tdx-mapping.json` holds the shared default; the per-cave diff is
  `SB_<broj>_…/tdx-mapping-objekt.json` (`tdx_mapping.py:33,80-102`). The dashboard page is
  `0P gui/static/mapping.js` with `gui/mapping.py`.
- **KORAK 1** `preprocess_tdx_csx.py:235-310` only edits attributes. It keeps the original name
  as `options="… tdxpp:<name>"` (`:230-232`).
- **KORAK 2** `fix_imported_linetypes.py` changes only built-in type numbers. Its one brush write
  is water `2→6` (`:461-464`).
- **The only custom graphic we inject** is the KORAK 3 north arrow. `nacrt_finish.py:1047-1106`
  splices `compass3.svg` into `<signs><cliparts>` and references it by id. That proves the
  splice-a-clipart route works, in `.csx` and `.csz`.
- **A sign item as cSurvey saves it** (SB 1103, `example/finishing/…_finished.csx`):
  ```xml
  <item layer="6" type="6" category="80" data="90E3FB04…87BE" dataformat="2" sign="263" signsize="3" angle="49.60">
    <pen type="10" /><brush type="7" />
  ```
  `data` is the content hash of the glyph in the `<signs><cliparts>` pool, and `sign` is the `SignEnum`.
  Glyph and semantics are therefore **independent**: we can swap the glyph without touching `sign`.

### 2.2 What cSurvey supports (all `cSurvey/cSurveyPC/…`, compiled root-level files)

- **Everything is an SVG clipart**: signs, rock and concretion cliparts, clipart-hatch area brushes,
  and pen decorations. cSurvey uses its own parser (`cDrawPaths.vb` `cDrawClipArt`), with no external SVG library.
- **Sign glyph pool:** `<signs><cliparts><clipart id="{sha1}" name="x.svg" data="{base64}"/>`. In a
  `.csz` the `data` is the zip path `_data\cliparts\{hash}.svg` (`cCliparts.vb:486-504`). An item can
  also carry the SVG inline (`dataformat="0"`) or as a file path (`dataformat="1"`)
  (`cItemSign.vb:368-424`). The `SignEnum` comes from the SVG root's `csurvey:sign`, and an item-level
  `sign=` overrides it (`cItemSign.vb:249-260`).
- **Library pens and brushes:** a file-level `<pens>` / `<brushes>` holds full definitions with
  `type="98"` (User) and `id`. Items reference them with `<pen type="98" id="…"/>`
  (`cPen.vb:1435-1475`, `cBrush.vb:3074-3112`, `cSurvey.vb:1362-1381,1817,1821`). `type="99"` is an
  inline per-item custom pen or brush.
- **Custom brush** (`cBrush.vb:1561-1620`): `color`, `backgroundcolor`, `hatchtype` (0 none,
  1 solid, 2 clipart, 3 pattern, 4 texture), an inline `<clipart data="&lt;svg…"/>`, `clipartdensity`,
  `clipartzoomfactor`, `clipartanglemode`/`clipartangle`, `clipartposition` (random or fixed),
  `clipartcrop`, `clipartalternativecolor` and a `<seed>`.
- **Custom pen** (`cPen.vb:484-536`): `color`, `width`, `style`, `decorationstyle` (0-17 built-in,
  99 custom), `decorationspacepercentage`, `decorationalignment`, `decorationscale`, the decoration's
  own pen and brush (`clipartpen*`, `clipartbrush*`), and an inline `<clipart>`.
- **Importer has no hook.** `cImportTopoDroidHelper.ConvertItem` is a hard-coded `Select Case`. A
  point gets the *first* gallery SVG whose `csurvey:sign` matches, which makes "drop a file into the
  install folder" fragile and global. **The theme must therefore be applied after import (KORAK 2), not
  through the install folder.**

### 2.3 The hard constraint: colour comes from the item, not the SVG

`cDrawPaths.Render` (`cDrawPaths.vb:1238-1245`) keeps the **geometry only**:

- any shape whose `fill` is not `none` is painted with the **item's brush colour**;
- **pure white stays white**, which is the only second colour;
- every outline is drawn with the **item's pen** (its colour and width). The SVG's stroke colour and
  stroke-width are not read.

Clipart-hatch brushes behave the same way, two-tone (`cBrush.vb:1822-1837,1987-2000`). There is
**no** general black-and-white or grayscale print option in cSurvey; only the centerline and
"combine" grey switches exist (`cOptions.vb:282,314`).

Consequences:

- A **colour theme** means *one colour per symbol* (plus white), set on the item's pen and brush. A
  multi-colour Illustrator symbol cannot keep its colours. It would have to be split into stacked
  sign items, which is not recommended.
- A **black-and-white theme** is simply the same glyphs with every colour set to black. It should also
  turn the red centerline and the station-label colours (`postimport.centerline`) to black or grey.
  So a theme bundles colour overrides as well as glyphs.

### 2.4 SVG subset the parser accepts → rules for the Illustrator export

| Accepted | Not accepted (lost or wrong) |
|---|---|
| `g`, `path`, `polyline`, `polygon`, `line`, `circle`, `rect`, `text` | `ellipse`, `use`/symbols, `image`, clip paths, masks |
| path commands M L H V C S Q T Z | arcs `A` |
| `matrix`/`translate`/`scale`/`rotate` | skew |
| inline `style`/`fill`, `<defs><style>` classes (naive parser) | gradients, opacity, stroke colour, stroke-width |

The geometry is shifted to its bounding box, and signs are normalised to a unit box, scaled by `csurvey:scale`
(`cCliparts.vb:80-92`, `cDrawPaths.vb:192-205`). So the artboard's padding does **not** carry
relative size. All glyphs come out the same size unless `csurvey:scale` says otherwise.

**Illustrator recipe (settled 2026-10-04).** The user's set is many symbols on **one artboard in one
file**, so the workflow keeps it that way: no re-layout into artboards.

1. **One group per symbol, not one layer per symbol.** All signs can stay on a single layer
   `Znakovi` (line units go on `Linije`, area tiles on `Plohe`; see below). Select one symbol's shapes, press `Ctrl+G`, and in the *Layers* panel rename
   the resulting `<Group>` (double-click its name) to its theme key, i.e. the cSurvey sign name as
   the mapping page shows it (`waterflow`, `entrance`, …; the exact names are in §3.7). A symbol that is already one group only
   needs renaming. Anything not meant to be a symbol (labels, frames, notes) goes on a layer whose name starts
   with `_`, and that layer is skipped. (Putting a symbol on its own sublayer named the same way
   also works, because it exports the same `<g id>`; it's just more clicks.)
2. Prepare the artwork: *Object › Expand Appearance*, *Object › Path › Outline Stroke* (stroke widths
   are ignored otherwise), *Type › Create Outlines*, release clipping masks and symbol instances.
3. *File › Export › Export As… › SVG*: Styling = *Presentation Attributes*, Font = *Convert to
   outline*, Images = *Embed* (none expected), **Object IDs = *Layer Names***, Decimal = 3,
   *Minify* off, *Responsive* off. Result: one `symbols.svg` where each group carries `id="<key>"`.
4. The splitter/normaliser (T1) cuts that file into one SVG per group. It bakes the group's
   transforms, so position on the artboard doesn't matter, and fixes or reports the rest
   (`ellipse`→path, skew, gradients/opacity, colours flattened to black/white), adding
   `xmlns:csurvey` + `csurvey:sign`/`scale`.

Illustrator mangles some names in IDs (spaces become `_`, a duplicate gets `_1`, leading digits are
escaped as `_x31_…`). T1 decodes these and rejects duplicates. Fallback with no tooling: drag each
symbol into *Window › Asset Export*, name it, and export all as SVG (one file per asset).

**Areas and lines (phase 2, recipe settled 2026-10-04): export the repeating unit, never the
expanded result.** cSurvey builds fills and decorated lines itself from one small clipart, so the
artwork is a *tile*, not a finished pattern:

- **Area = one scatter tile.**
  - The custom brush (`hatchtype=2`) scatters one clipart over the area, controlled by `clipartdensity`,
    `clipartzoomfactor`, random or fixed angle, and random or fixed position.
  - The stock tiles in `C:\csurvey64\Objects\Cliparts\Brushes\` are small clusters: `pebbles1.svg` has
    5 shapes, `sand.svg` has 9 and `debrits1.svg` has 21.
  - So for gravel or soil you export *one cluster of a few grains/stones*, not a filled rectangle and not
    an Illustrator pattern swatch.
  - Variety comes from cSurvey's random rotation and placement. There is one tile per brush, so you cannot mix variants.
  - Pure line hatching (e.g. diagonal lines for clay) needs no artwork: `hatchtype=3` is cSurvey's
    parametric pattern.
- **Line = base stroke + one decoration unit.**
  - The custom pen draws the continuous line itself (colour, width, dash pattern) and repeats a single
    decoration clipart along it, controlled by spacing %, alignment (outer, centre or inner), scale and above/below.
  - The stock units in `Objects\Cliparts\Pens\` are a single tick, triangle or arrow. `arrowdown.svg` is a
    vertical line from y=0 to y=15 with the head at the bottom. So you export *one tick*, not the line.
  - Illustrator *pattern brush*: drag its side tile out of the Brushes panel onto the artboard, outline it,
    group it and name it. Corner/start/end tiles have no equivalent in cSurvey.
  - Illustrator *art brush* (art stretched along the path): no equivalent. It cannot be reproduced.
  - **How units are placed** (`cClipartOnPath.vb`, compiled):
    - The unit is drawn with the line running **horizontally** through it, rotated to follow the line.
      Its geometry bbox width is along the line and its height is across it.
    - Units are **centred** at steps of `pitch = width × (1 + space%/100)` (`pDrawClipart:122`; the
      straight-segment variant `pDrawClipartOnLines:83` scales space% differently, so tune by eye in T7).
      The default `decorationspacepercentage` is 100, i.e. a gap equal to the unit's width.
    - Across the line, `decorationalignment` decides the placement (`pDrawRotatedClipart:160-167`):
      - Outer: the unit's **bottom edge sits on the line**, so the unit is on one side;
      - Center: the unit is centred on the line;
      - Inner: the unit's top edge sits on the line, on the other side.
    - `decorationdistancepercentage` pushes it further off, as a share of its height.
    - So **never pad the unit with invisible shapes** (e.g. a mirrored blank triangle to push the
      baseline down). The bbox is computed from all geometry, and a no-fill shape is still outlined by
      the pen, so it would print. Draw the triangle alone and use alignment Outer.
  - **Double-line symbols** (two parallel rails with ticks; user sketch 2026-10-05):
    - cSurvey has no double-line pen. The 18 built-in decorations (`DecorationStylesEnum`, `cPen.vb:1261`)
      are ticks, triangles and arrows, and the base stroke always runs along the path centre
      (`cPen.vb:1102-1103`).
    - **Chosen build (user, 2026-10-05): centred.** A meander marks a narrow passage, so the
      symbol must straddle the drawn line rather than sit beside it.
      - The unit is **both rails plus the ticks**, alignment Center, `decorationspacepercentage` 0, so
        the rail segments butt into continuous rails.
      - The base stroke is **switched off natively**: pen `style` = None (`PenStylesEnum.None = 98`)
        makes `pRender` set `oPen = Nothing` (`cPen.vb:865-867`), and the decoration is still drawn.
        No transparent-colour hack is needed.
      - The decoration then needs its own paint: `clipartpenmode` = Custom (`cPen.vb:917`) for the outline,
        or its style None for fill-only artwork, which also removes the thin outline around filled
        shapes, plus `clipartbrushmode` = Custom for the fill colour.
    - Known artefacts, all *unverified* (to be checked on curved lines in the T7 sample sheet):
      - both rails are chains of straight chords, so they kink at tight bends;
      - the rails stop up to one unit short of the line's ends, because units are placed only where
        they fit whole (`cClipartOnPath.vb:91-98`);
      - possible gaps at vertices on non-spline lines.
    - **Shorter units bend better.** Draw one rhythm period: one tick up, one tick down, as short as
      the design allows.
    - Rejected alternative: the base pen as one rail with the unit beside it (alignment Outer). It is
      smoother, but it offsets the symbol by its width.
  - **Size variants of the same unit are one drawing.** The user's three triangle rows (abyss-entrance,
    overhang, slope:sheer) are one triangle with three `decorationscale` values. That needs keys finer
    than the cSurvey target (§3.1 addendum).
  - **Dashes are a pen setting, never artwork.**
    - `cPen` has `style` (`PenStylesEnum`, `cPen.vb:1241`: Solid, Dash, Dot, DashDot, DashDotDot, three
      LargeDash variants, Custom) and, for Custom, `stylepattern`. This is the GDI+ dash pattern: alternating
      dash and gap lengths in multiples of the pen width, saved via `PenStylePatternToString` (`cPen.vb:496-497`).
    - The decoration's own outline has the same pair, `clipartpenstyle`/`clipartstylepattern`.
    - So a dashed wall is `"style": "custom", "dash": [4, 2]` in `theme.json`.
    - Do not draw dash + blank-rectangle units. A shape with no fill is still outlined by the pen, so a
      "blank" rectangle would print as a box. Gaps between decoration units come from
      `decorationspacepercentage`.
  - **Do not** apply a brush to a path and expand it. That freezes the decoration onto one specific
    shape, and cSurvey needs it to follow every cave's own lines.
  - Orientation convention (which way is "along the line" and which is "outward") is *unverified*. Derive it
    from the stock `Pens/*.svg` plus a T0-style oracle before authoring many units.
- **Kind by layer.** Sign, line and area names collide (`water`, `pebbles`, `sand`, `clay`, `ice` are
  both signs and areas). So the Illustrator file gets three layers, **`Znakovi`**, **`Linije`** and
  **`Plohe`**, and the splitter routes each group by its layer into `signs/`, `lines/` and `areas/`.
  The user's file names the area layer **`Površine`**; the splitter accepts `Plohe` and `Površine` alike.
  Because SVG ids must be unique, Illustrator suffixes a repeated name (`debris` sign + `debris` area →
  `debris-2`). The splitter strips a trailing `-<n>` when the layer already fixes the kind.

**Tuning density, size and spacing: numbers, not artwork (verified in source 2026-10-04).** One
tile or unit per kind. Everything about *how* it repeats is a parameter on the brush or pen, applied
in three multiplying layers:

1. **Per brush or pen** (stored in `theme.json`, written into the csx):
   - brushes: `clipartdensity`, `clipartzoomfactor`, angle and position mode;
   - pens: `decorationspacepercentage`, `decorationscale`, `width`, `decorationalignment`.
2. **Per design property** (global multipliers):
   - area cliparts: `cBrush.GetPaintZoomFactor` (`cBrush.vb:1671-1686`) multiplies both density and
     zoom by `DesignSoilScaleFactor` (`:1809,1874`);
   - pens: `DesignTerrainLevelScaleFactor` (`cPen.vb:824-832`);
   - signs: `DesignSignScaleFactor`.
3. **Per print scale:** `GetCurrentDesignPropertiesValue` (`cOptions.vb:1336-1338`) resolves a name as
   design options → **the current scale rule** (`<scalerules><scalerule scale="…">`, `cScaleRules.vb:131,410`)
   → the survey's design properties. So "pebbles smaller at 1:500" or "overhang ticks denser at
   1:100" is one scale-rule entry, **not a second piece of artwork**. SB 1103 already carries
   `scalerule` elements, cSurvey's defaults.

Consequences:

- **Never draw size or density variants.** One overhang unit and one pebble cluster serve every scale.
- **Tune in cSurvey, then harvest** (T7, phase 2). Tuning by eye in a JSON file is blind, and the mapping
  page's previews are not real cSurvey rendering. The loop is:
  1. a tool generates a **sample sheet** `.csx`: one test area per theme area and one test line per theme
     line, at a realistic size, with the theme already applied;
  2. the user opens it in cSurvey and adjusts density, zoom and spacing in the brush and pen property
     panels with a live preview, checks print preview at 1:100 / 1:200 / 1:500, and saves;
  3. `theme_harvest.py` reads the tuned values back from the saved file into `theme.json`, including any
     per-scale `scalerule` overrides.

  The artwork stays in Illustrator; the numbers come from cSurvey.
- Redraw the tile itself only when its *shape* is wrong. Examples: stones too uniform, or a cluster
  with a visible edge when scattered. Density is never a reason to redraw.

Relative size: because cSurvey normalises every glyph to a unit box, the splitter computes
`csurvey:scale` from each group's size relative to a reference symbol. That way, sizes drawn in one
file stay proportional (*assumed* to be what the user wants; it can be a theme setting
`"keep_relative_size": true`).

## 3. Approach

### 3.1 Theme = a folder of content files, applied in KORAK 2

```
production/themes/<id>/
  theme.json        name, extends?, monochrome?, per-sign glyph + colour, centerline/label overrides
  signs/*.svg       normalised glyphs (T1 output)
  lines/, areas/    phase 2 only (pen decorations, brush hatches)
```

Sketch of `theme.json` (phase 1, signs only):

```json
{ "name": "Boja", "extends": null,
  "default_color": "#000000",
  "signs": { "waterflow":  {"svg": "signs/waterflow.svg", "color": "#1F6FD1"},
             "entrance":   {"svg": "signs/entrance.svg",   "color": "#D12F1F"},
             "stalagmite": {"svg": "signs/stalagmite.svg"} },
  "centerline": { "…": "…" } }
```

The black-and-white theme is `{"name": "Crno-bijelo", "extends": "boja", "monochrome": "#000000"}`.
`monochrome` forces every sign colour to that value and turns the centerline and station labels black
(decision 3, §3.5). A sign the theme does not list keeps the built-in cSurvey glyph and only gets
recoloured.

**Key decision (2026-10-04): signs are keyed by the cSurvey sign name, the mapping target.** This is
the name *Mapiranje simbola* shows as the target, and it maps to the `SignEnum` in the item's `sign=`.
Keying by TopoDroid name was rejected: the `tdxpp:<name>` marker KORAK 1 writes **does not survive cSurvey's
import**. Ten post-import files in `example/` (`finishing/`, `csx_entrances/`) contain zero
`tdxpp:` occurrences, so after import only `sign=` is reliable. Consequence for the 29 speleo-2 points
without a cSurvey sign: to get its own glyph, such a symbol must be mapped to a **distinct carrier
`SignEnum`** that is otherwise unused, and the theme then draws the club's glyph on it. Choosing those
carriers is a mapping question for phase 2, not for this brief.

**Addendum (2026-10-05): the TopoDroid name may be recoverable after all.** The user wants different
looks for TopoDroid lines that share one cSurvey target: abyss-entrance and overhang both become
`overhang`, and slope:sheer becomes `slope` like every slope subtype. A theme keyed only by target cannot
tell them apart. Evidence for recovering the name by **matching geometry against the KORAK 1 output**
(`…_pp.csx`, which still carries `tdxpp:`), from the symbol-zoo run
`projects/0002-…/runs/2026-07-19-symbol-zoo/` (`step-03-zoo-v3.csx` → `step-04-after-import.csx`):

- the import keeps the item count (155 → 155);
- **every point item matches 1:1 by its exact coordinates** (121/121, no duplicate keys);
- lines and areas do *not* match exactly, because the import re-encodes their point lists (control
  points, the `BS<guid>` sequence markers). They need a tolerant match, e.g. on the sorted set of
  anchor points or on bbox + point count. *Unverified.*

**T8 result (2026-10-06): it works. Keys are TopoDroid name first, cSurvey target as the fallback.**

- `production/tools/tdx_name_recover.py` recovered **100 % of points, lines and areas, all exact**, on
  every pre/post pair in the repo, including a real cave (bunker_studena: 22/22 points, 14/14 lines,
  3/3 areas). Only items drawn in cSurvey come back unnamed, and they are reported as `native`.
- Lines looked unmatched only because the import re-flags the `data` string. The coordinates are copied
  unchanged, and only the order may be reversed.
- Details and degradation tests: [findings/t8-name-recovery.md](findings/t8-name-recovery.md).
- **Theme lookup per item:**
  1. the recovered TopoDroid name (`slope:steep`, `abyss-entrance`, `rope`, `bones`…);
  2. else the cSurvey target name;
  3. else built-in.
- **New precondition for `apply_theme`:** it needs the **pre-import file** (KORAK 1 output, or the raw
  TopoDroid export) next to the `_lt` file.
- If the user later reshapes or moves items in cSurvey, those items become reported misses and fall back
  to the target key. Small edits still match.
- So the Illustrator group names may be TopoDroid names (the user's file already uses them) or target
  names (§3.7). Carrier signs for symbols without a cSurvey sign are no longer needed for *looks*; the
  mapping only decides what cSurvey thinks the item *is*.


### 3.2 What `apply_theme` writes (post-import, idempotent)

**Phase 1, signs (the scope the user chose, 2026-10-04):**

- for every sign item whose `sign=` has a theme glyph: add the glyph to `<signs><cliparts>` (hash
  id, base64; zip entry in a `.csz`, reusing the `nacrt_finish.py` compass splice) and repoint the item's
  `data`;
- for every sign item: set its pen and brush colour to the theme colour. The exact XML (inline
  `type="99"` vs a `type="98"` library entry) comes from the T0 oracle;
- merge the theme's centerline/label overrides over `postimport.centerline`;
- record `theme=<id>` in the file so a re-run replaces rather than stacks.

Runs in KORAK 2 after `fix_imported_linetypes.py`'s size step (signsize must not be clobbered).
The KORAK 3 north arrow is untouched: it is `type="15"`, not a sign.

**Phase 2 (implemented 2026-10-07, run r3):** lines become `type="98"` library pens in the root `<pens>`
(one per theme key and built-in pen type; width written out from the built-in pen, the decoration unit inline as
one-line SVG text, painted by fill only, placed on the built-in pen's side), and areas become `type="98"` library
brushes in `<brushes>` (scatter tile, solid, or the parametric 45° pattern for the B/W water); items keep their own
`<seed>`. Areas cSurvey draws as blank soil (ice, snow, stalagmite, user) are themed by TopoDroid name, and rope is
reached the same way. Undo, theme switching and re-applying are byte-identical; a cSurvey load + save keeps every
pen and brush unchanged. Order: after KORAK 2 (`wall_orient.py` only copies `<pen>` references, and a KORAK 2 re-run
leaves `type="98"` alone). Known cSurvey limits (meander rails not continuous on curves, even-odd overlaps, item
transparency with a style-None pen): [themes/README.md](../../production/themes/README.md#known-limits).

### 3.3 Where the user chooses

`tdx-mapping-objekt.json` gets a top-level `"theme": "<id>"`, and the shared default sets one too.
*Mapiranje simbola* gets a **Tema** dropdown, and its symbol pictures come from the selected theme's SVGs,
falling back to the catalog. Changing the shared default theme still goes through
`/csurvey-defaults`, and `check_defaults.py` validates `theme.json`.

### 3.4 Shipping

`prod/build_csx_kit.py` copies a flat `TOOLS` list (`:93-121`, no subdirectories). It needs a
directory copy for `csurvey_alati/teme/<id>/…`. Nothing has to be installed into
`C:\csurvey64`, because the glyphs travel inside each `.csx`. That is the main reason to prefer this route over
the install-folder route in [custom-sign-palette.md](../../backlog/custom-sign-palette.md): it survives
cSurvey upgrades and is per-cave.

### 3.5 The user's answers (2026-10-04)

1. **One colour per symbol (plus white):** accepted for now.
2. **Scope:** signs first. Lines and areas are phase 2.
3. **B/W theme also blackens the centerline and station labels:** yes.
4. **Key:** left to the agent. Decided: cSurvey sign name (§3.1, with the evidence).
5. **The Illustrator file:** "quite a few" symbols, all on **one artboard in one file**. Hence the
   group-per-symbol + splitter recipe in §2.4.

### 3.6 Delegable tasks (each a self-contained prompt for a separate, cheap session)

Fixture: `stages/3N-nacrt/example/finishing/SB_1103_golobreska_lt_raw.csx` (gitignored). Order: T0 ∥ T1 → T2 → T3 → T4 → T5 → T6.

**T0 — oracle file (user, ~5 min in cSurvey). Reduced 2026-10-06 to the colour only.**

- Open the SB 1103 `_lt` file, give **one sign** a custom colour (Properties → pen/brush → **Custom** →
  colour; the user chose blue), and save it as `…_oracle.csx` in `example/finishing/`.
- *Accept:* the diff shows the exact inline custom pen/brush XML on a sign.
- Dropped parts:
  - **(b) glyph replace.** cSurvey's only route is the Clipart gallery → *Survey* → **Replace with...**, which
    swaps the shared pool entry for every sign using it. In 2.15.2858 it **crashes** with a
    NullReferenceException in `cDockClipart.btnReplaceWith_ItemClick` (user, 2026-10-06): `oClipart` is
    `Nothing` when the survey's clipart list holds no object identical (`Is`) to the gallery item's
    (`DockControl/cDockClipart.vb:503-520`). It is not needed: the splice route (new pool entry +
    repointed `data`) is already proven by the KORAK 3 compass.
  - **(c)** depended on (b).
  - **(d) multi-select recolour.** A multi-selection exposes no pen or brush (`cItemItems.vb:249-258`), so
    there is nothing to observe.

**T1 — `theme_svg.py split|check|normalize`.**

- *Input:* the user's single `symbols.svg` (Illustrator *Export As*, Object IDs = Layer Names), or a
  folder of per-symbol SVGs.
- *Output:* one normalised SVG per symbol group, named by the decoded group id. A symbol group is
  a direct child `<g id>` of a layer `<g>` (any layer not starting with `_`), or a named sublayer
  that holds the symbol directly. Unnamed groups (`<Group>`, which exports with no id or with `_x3C_Group_x3E_`)
  are reported, not guessed. Normalisation
  means: transforms baked, `ellipse`→path, skew baked, gradients/opacity/images/masks rejected, fills
  flattened to black/white, `xmlns:csurvey` + `csurvey:sign` (from the catalog's name→enum) + a relative
  `csurvey:scale`. Also a report: per symbol, what was fixed and what was rejected, plus any unknown keys
  (group ids that are not a cSurvey sign name) and catalog signs with no glyph.
- *Real fixture:* `drawing_catalogue.svg` in this folder, the user's first export (2026-10-05, 28 groups),
  reviewed in [findings/drawing-catalogue-review.md](findings/drawing-catalogue-review.md). It needs arc conversion,
  ellipse conversion, stroke outlining, invisible-rect removal and translate baking.
- *Accept:* every SVG in `C:\csurvey64\Objects\Cliparts\Signs` passes `check` unchanged. A hand-made
  test export (three groups: one with an ellipse, one with a gradient, one with a stroke-only path,
  plus a `_notes` layer) splits into exactly three files with the right fixes and reports. Stdlib only
  (`xml.etree`).

**T2 — theme format + loader.** `themes.py`:

- load `theme.json` with `extends` / `monochrome`;
- resolve paths;
- validate `signs` keys against the catalog's point targets;
- hook it into `check_defaults.py`.

*Accept:* unit tests for inheritance, monochrome and a missing SVG.

**T3 — `apply_theme` (signs) in KORAK 2.**

- *Input:* a post-import `.csx` or `.csz` and a theme id.
- *Output:* as §3.2 phase 1, with the XML modelled on the T0 oracle.
- *Accept:* idempotent (a second run, and a run with a different theme, never stack glyphs or
  colours); opens in cSurvey with no `clipart_error`; the headless print (`csurvey_headless.ps1`)
  shows the themed glyphs, coloured in *boja* and black in *crno-bijelo* (centerline included); PDFs
  are checked by eye.

**T4 — Mapiranje simbola: Tema dropdown.** `mapping.js` and `gui/mapping.py`:

- add a theme select stored as `"theme"` in the override;
- take point pictures from the theme SVGs, tinted with the theme colour.

*Accept:* save → reload round-trips; reset removes it.

**T5 — kit.** `build_csx_kit.py` copies `production/themes/` → `csurvey_alati/teme/`. KORAK 2's
launcher passes the cave's theme. Update the operator guide template. *Accept:* `KIT_VERSION`
bumped, and a dry-run build lists the theme files.

**T6 — first two themes.**

- *User:* prepare the Illustrator file per §2.4 (one named group per symbol) and export `symbols.svg`.
- *Agent:* run T1, write `themes/boja/theme.json` (colours agreed with the user) and
  `themes/crno-bijelo/theme.json`.
- *Accept:* the user signs off on SB 1103 printed in both themes.

**T7 — sample sheet + harvest (phase 2, lines and areas).**

- `theme_sample.py <theme>` writes `uzorak_<theme>.csx`: one rectangle-ish area per theme area key,
  one line per theme line key (straight and curved), labelled, on a dummy survey, with the theme applied.
- `theme_harvest.py <saved.csx> <theme>` writes the tuned brush and pen parameters and any per-scale
  `scalerule` design properties back into `theme.json`, and prints a diff.
- *Accept:* sample → tune one value in cSurvey → harvest → regenerate gives the tuned look.

### 3.7 Drawing checklist (the Illustrator to-do list)

**How to read it.** Since T8, a group may also be named by its **TopoDroid name** (e.g. `slope:steep`), which wins over the target name for items that came from that TopoDroid symbol. The tables below list target names; the "Reached from" column gives the TopoDroid names that can be used instead.



- **Group name** is the exact name to give the group in Illustrator. It is the catalog's target id
  (`tdx-mapping-catalog.json`), so it has no dashes: `waterflow`, not `water-flow`.
- Tick **Nacrtati** only for what you will draw. Anything left unticked keeps cSurvey's own glyph,
  recoloured by the theme.
- **Stock** shows whether cSurvey's installed glyph is usable:
  - ✅ usable;
  - ❌ **X-box**: the install has no artwork, so this is drawn first;
  - — not applicable.
- **Reached from** lists the TopoDroid symbols that land on this target under the current shared mapping
  (2026-10-04). `*` means it arrives by the same name, with no mapping entry. "—" means nothing reaches it
  today: draw it only if you plan to map something to it.

The list was generated from the catalog and `tdx-mapping.json` on 2026-10-04. If the mapping changes, the
"Reached from" column can drift; the group names cannot.

#### Znakovi (signs) — phase 1, layer `Znakovi`

**Priority: the X-boxes.** These render as an error box today, so they come first:

| Nacrtati | Group name | cSurvey label | Stock | Reached from |
|---|---|---|---|---|
| [ ] | `water` | Water | ❌ | water* |
| [ ] | `sand` | Sand | ❌ | sand*, clay |
| [ ] | `clay` | Clay | ❌ | flowstone, mud |
| [ ] | `ice` | Ice | ❌ | ice* |
| [ ] | `snow` | Snow | ❌ | snow* |
| [ ] | `gradient` | Gradient | ❌ | gradient* |
| [ ] | `archeomaterial` | ArcheoMaterial | ❌ | archeo-material* |
| [ ] | `anchor` | Anchor | ❌ | — (TopoDroid `anchor` is mapped to the text label "f") |

**Morphology and passage ends**

| Nacrtati | Group name | cSurvey label | Stock | Reached from |
|---|---|---|---|---|
| [ ] | `entrance` | Entrance | ✅ | entrance* |
| [ ] | `continuation` | Continuation | ✅ | continuation* |
| [ ] | `narrowend` | NarrowEnd | ✅ | narrow-end* |
| [ ] | `lowend` | LowEnd | ✅ | low-end* |
| [ ] | `breakdownchoke` | BreakdownChoke | ✅ | breakdown-choke*, debris |
| [ ] | `flowstonechoke` | FlowstoneChoke | ✅ | flowstone-choke* |
| [ ] | `blocks` | Blocks | ✅ | blocks* |
| [ ] | `pebbles` | Pebbles | ✅ | pebbles* |
| [ ] | `anastomosis` | Anastomosis | ✅ | anastomosis* |
| [ ] | `karren` | Karren | ✅ | karren* |
| [ ] | `scallop` | Scallop | ✅ | scallop* |
| [ ] | `flute` | Flute | ✅ | flute* |
| [ ] | `dig` | Dig | ✅ | dig* |

**Speleothems**

| Nacrtati | Group name | cSurvey label | Stock | Reached from |
|---|---|---|---|---|
| [ ] | `stalactite` | Stalactite | ✅ | stalactite*, stalactites |
| [ ] | `stalagmite` | Stalagmite | ✅ | stalagmite*, stalagmites |
| [ ] | `pillar` | Pillar | ✅ | pillar* |
| [ ] | `curtain` | Curtain | ✅ | curtain* |
| [ ] | `sodastraw` | SodaStraw | ✅ | soda-straw* |
| [ ] | `helictite` | Helictite | ✅ | helictite* |
| [ ] | `flowstone` | FlowStone | ✅ | — (TopoDroid `flowstone` is mapped to `clay`) |
| [ ] | `wallcalcite` | WallCalcite | ✅ | wall-calcite* |
| [ ] | `moonmilk` | Moonmilk | ✅ | moonmilk* |
| [ ] | `popcorn` | Popcorn | ✅ | popcorn* |
| [ ] | `cavepearl` | CavePearl | ✅ | cave-pearl* |
| [ ] | `disk` | Disk | ✅ | disk* |
| [ ] | `aragonite` | Aragonite | ✅ | aragonite* |
| [ ] | `crystal` | Crystal | ✅ | crystal* |
| [ ] | `gypsum` | Gypsum | ✅ | gypsum* |
| [ ] | `gypsumflower` | GypsumFlower | ✅ | gypsum-flower* |
| [ ] | `raft` | Raft | ✅ | raft* |
| [ ] | `raftcone` | RaftCone | ✅ | raft-cone* |
| [ ] | `rimstonepool` | RimstonePool | ✅ | rimstone-pool* |
| [ ] | `rimstonedam` | RimstoneDam | ✅ | rimstone-dam* |
| [ ] | `claytree` | ClayTree | ✅ | clay-tree* |

**Water and air**

| Nacrtati | Group name | cSurvey label | Stock | Reached from |
|---|---|---|---|---|
| [ ] | `waterflow` | WaterFlow | ✅ | water-flow*, water-flow:intermittent |
| [ ] | `waterflowpaleo` | WaterFlowPaleo | ✅ | — |
| [ ] | `waterfall` | Waterfall | ✅ | — (TopoDroid `water-drip` goes to `waterflow` turned 180°) |
| [ ] | `spring` | Spring | ✅ | spring* |
| [ ] | `sink` | Sink | ✅ | sink* |
| [ ] | `airdraught` | AirDraught | ✅ | air-draught* |

**Organic, finds, people**

| Nacrtati | Group name | cSurvey label | Stock | Reached from |
|---|---|---|---|---|
| [ ] | `guano` | Guano | ✅ | guano* |
| [ ] | `root` | Root | ✅ | root* |
| [ ] | `vegetabledebris` | VegetableDebris | ✅ | vegetable-debris*, tree-trunk |
| [ ] | `paleomaterial` | PaleoMaterial | ✅ | paleo-material* |
| [ ] | `camp` | Camp | ✅ | camp* |

**Text labels today; a glyph needs a carrier sign (phase 2, §3.1).** These TopoDroid points
currently become a text label, because cSurvey has no sign for them. Draw them now if you like, named
by the TopoDroid name. They will only be used once each is mapped to a free carrier sign:

| Nacrtati | Group name | Today | Note |
|---|---|---|---|
| [ ] | `danger` | label "!" | |
| [ ] | `plus` | label "+" | |
| [ ] | `minus` | label "-" | |
| [ ] | `plus-minus` | label "+/-" | |
| [ ] | `anchor` | label "f" | could use the `anchor` glyph above instead of a carrier, by mapping TopoDroid `anchor`→`anchor` |

The backlog also names a further speleo-2 set without a proper cSurvey sign (29 points,
`journal/backlog.md:389-390`). Its first-pass mapping is still to be drafted. Extend this table when
that draft exists.

#### Linije (line decoration units) — phase 2, layer `Linije`

Draw **one repeating unit** per line (§2.4), not the line itself. Plain lines need no artwork; their
look is width, dash and colour in `theme.json`.

| Nacrtati | Group name | Unit needed? | Reached from |
|---|---|---|---|
| [ ] | `overhang` | yes | overhang*, chimney, abyss-entrance, pit-chimney |
| [ ] | `pit` | yes | pit, floor-step |
| [ ] | `chimney` | yes | ceiling-step |
| [ ] | `slope` | yes | slope*, slope:shallow*, slope:sheer*, slope:steep* |
| [ ] | `floor-meander` | yes | floor-meander* |
| [ ] | `ceiling-meander` | yes | ceiling-meander* |
| [ ] | `rock-border` | check the stock pen first | rock-border* |
| [ ] | `water-flow` | check the stock pen first (arrows?) | water-flow:intermittent* |
| — | `wall`, `wall:presumed`, `presumed`, `border`, `section` | no, plain line (style only) | wall + its subtypes, border + ~35 generic lines, … |

#### Plohe (area scatter tiles) — phase 2, layer `Plohe`

Draw **one small cluster** per area (§2.4).

| Nacrtati | Group name | Stock | Reached from |
|---|---|---|---|
| [ ] | `pebbles` | ✅ `pebbles1.svg` (5 stones) | pebbles* |
| [ ] | `debris` | ✅ `debrits1.svg` (21 pieces) | debris* |
| [ ] | `sand` | ✅ `sand.svg` (9 grains) | sand*, sand-area* |
| [ ] | `clay` | ⚠ drawn with the sand brush today, so this is the first area to draw | clay*, clay-area |
| [ ] | `blocks` | ✅ | blocks* |
| — | `water` | solid fill, no tile (a colour in `theme.json`) | water* |
| [ ] | `ice` | ❌ no cSurvey area type; falls back to generic soil | needs a carrier area type (phase 2 question) |
| [ ] | `snow` | ❌ no cSurvey area type; falls back to generic soil | needs a carrier area type (phase 2 question) |

**T8 — spike: recover TopoDroid names after import.**

- *Input:* the symbol-zoo pair above, plus one real cave's `_pp.csx` / `_lt.csx`.
- *Output:* `tdx_name_recover.py` mapping each post-import item to its `tdxpp:` / TopoDroid name.
  Points match by exact coordinates; lines and areas use a tolerant match.
- *Accept:* 100 % of points and ≥ 95 % of lines and areas recovered on both files, with every
  ambiguity reported, never guessed.
- If it passes, switch the theme key to TopoDroid-first (§3.1 addendum) and add TopoDroid-name rows to §3.7.

### 3.8 The black-and-white theme is its own design, not "colour → black" (user, 2026-10-06)

`monochrome` alone is wrong. A B/W map needs different *encodings* where colour carried the meaning:
water becomes 45° parallel lines (as cSurvey's own water already is), and a solid brown tree-trunk becomes an
outline. So `crno-bijelo` stays `extends: boja` + `monochrome: #000000`, but it **overrides per piece**
with one of three tools, cheapest first:

1. **Recolour only.** The default for everything not overridden: monochrome forces black.
2. **A different render, same artwork.** No drawing needed:
   - **outline mode for signs:** the item brush becomes white and the pen stays black. cSurvey's pen
     outlines every path of the glyph (§2.3), so a filled shape reads as its outline;
     **only for solid shapes** (seen in the T3 print, 2026-10-06): a line-drawing glyph whose lines are thin
     outlined fills, like `blocks`, turns into double lines, because both edges of every stroke get traced. Fine for
     `tree-trunk`, wrong for `blocks`/`debris`;
   - **pattern hatch for areas:** `hatchtype="3"`, `patterntype` 0 = parallel lines or 1 = crossed lines,
     `patternangle`, `patterndensity`, `patternzoomfactor`, `patternpenstyle` (`cBrush.vb:2649-2664`). The
     T0 oracle shows the exact XML on a sign brush:
     `<brush type="99" color="…" backgroundcolor="…" hatchtype="3" patterntype="1" patternpenstyle="0"
     patterndensity="1.00" patternzoomfactor="1.0000" patternanglemode="0" patternangle="0.00"><parameters/></brush>`;
   - **a pen dash for lines,** e.g. rope as a black dashed line instead of red.
3. **New artwork,** only where 1 and 2 fail. It goes on a **second artboard in the same Illustrator
   document**, with the same three layers and only the pieces that differ, exported with *Use Artboards*
   into `drawing_catalogue_cb.svg`. T1 splits it into `themes/crno-bijelo/`, and anything missing is
   inherited from `boja`.

Schema additions for T2/T3: signs `render: "fill"|"outline"`; areas `pattern: {type: lines|crossed,
angle, density, zoom, pen_style}` (mutually exclusive with `svg` tile / `solid`).

Proposed per-piece B/W treatment (**awaiting the user's call**; to be judged on the printed sample sheet):

| Kind | Piece | boja | crno-bijelo proposal |
|---|---|---|---|
| sign | tree-trunk | brown fill + white cracks | outline mode (test); new art if the cracks get messy |
| sign | vegetable-debris | many colours | outline mode (test) |
| sign | water-flow:intermittent | blue | recolour |
| sign | blocks, debris (grey) | grey | recolour |
| sign | all black ones | black | unchanged |
| line | water-flow (blue unit) | blue | recolour; or a dashed base stroke if it clashes with walls |
| line | rope | red plain line | black, dashed |
| area | water (not drawn yet) | blue solid | **pattern: lines, 45°** |
| area | ice (teal) | teal tile | recolour, or a pattern if it reads as debris |
| area | pebbles, clay, debris | ochre/grey tiles | recolour; maybe a lower density |
| area | blocks, stalagmite | black | unchanged |

**Colour iteration for `boja`** (user: the colours are not right yet): judged on a printed **sample sheet**,
never in JSON. T3 prints SB 1103 in both themes and T7 adds a synthetic sheet with every piece. The user
then adjusts colours either in Illustrator (re-export → T1 picks the dominant colour again) or directly
in `theme.json`.

**T9 — labels → themed signs in the theme step (user decision 2026-10-07, option b).**

- The shared mapping keeps `danger`, `plus`, `minus` and `plus-minus` as **text labels** (`!`, `+`, `-`,
  `+/-`), so they are readable right away with no theme. `anchor` stays the label `f` and is never themed.
- `theme_apply` converts such a label into a sign item carrying the theme glyph, but only when the active
  theme has a glyph for it. Without a theme, the label stays.
- The label's TopoDroid name is recovered by T8 (the `tdxpp:` marker / raw export name).
- Undo restores the label.
- *Accept:* on the mockup run through KORAK 1, the four print as club glyphs in `boja` and `crno-bijelo`,
  and as labels with no theme.

**State at session end (2026-10-08) — read this first in the next session.**

- Done 2026-10-07/08: T4 (Tema card), T5 (KORAK 2 theme step + kit v1.7 staged, **not published**), T9 (labels →
  glyphs, anchor `f` stays), tuning rounds r9–r12, `mud` → `sand` (shared default, committed), T6 prints of SB 1103
  ([runs/2026-10-07-t6-sb1103](runs/2026-10-07-t6-sb1103/RUNLOG.md)). The user did **not** sign off: more iteration.
- **Next (user):** a new, firm test survey drawn for the purpose — as many TopoDroid points, lines and areas as
  possible — to replace the generated mockup / SB 1103 as the reference for tuning. Expect a TopoDroid export (and
  later its cSurvey save) dropped into the repo; run it through KORAK 1 → headless import → KORAK 2 (with theme) and
  print, the way `runs/2026-10-07-t6-sb1103` and the T9 check were made (`csurvey_driver.recalc` with
  `runs/theme-round/csurvey-nodtd`, then `print_pdfs`). Consider teaching `theme_round.py` to use it as its mockup.
- **Next (user, drawing):** debris/blocks stones with a white inside — recipe in the cheatsheet ("White-filled
  pieces"): white fill + coloured stroke → Outline Stroke, keep the compound path. Verified 2026-10-08 with a probe
  tile (prints as rings, white inside). Ice arms thinner in the drawing (the tile outline is a 1-px floor, r12).
- **Open findings:** in `crno-bijelo` the dotted shot line on SB 1103 stays orange-brown (not one of the centerline
  colours `monochrome` blackens) – trace which cSurvey setting draws it; debris may be too heavy in B/W at small scale.
- **Then:** sign-off on the new survey (T6), `/publish` csx kit v1.7, close-out (§4, §5; T7 superseded by `/theme-round`).

**State at session end (2026-10-07).**

- Done: T0 (oracle), T1, T2, T3 (signs + lines + areas), T8, the mockup generator, and tuning rounds r1–r7
  (`runs/`).
- Next session: **T4** (the Tema dropdown on Mapiranje simbola), **T5** (themes in the kit + the theme step
  in the KORAK 2 launcher, then `/publish`), **T9**, then T7 (tune in cSurvey + harvest) if more tuning is
  wanted.
- Known risks:
  - the HTTP 429 DTD fetch on import (cSurvey gallery SVGs reference w3.org);
  - a style-None pen plus item transparency crashes cSurvey;
  - the meander rails break on curves (accepted);
  - `blocks` scatter is uneven on some seeds.

## 4. Definition of done

- [ ] T0 oracle captured, and §2.2 corrected wherever it disagrees.
- [ ] SB 1103 prints in *boja* and *crno-bijelo* from one `_lt` file, chosen on Mapiranje simbola, with the club's sign glyphs and no X-boxes (phase 1).
- [ ] The kit ships the themes, and nothing is installed into the cSurvey folder.
- [ ] `check_defaults.py` validates themes, and `pipeline_doctor.py` is green.
- [ ] The decision (post-import theme, not install-folder glyphs) is recorded in `docs/design-decisions.md`.

## 5. Outputs (fill in on close)

- **Production:** —
- **Reference:** —
- **Decisions:** —
- **Follow-ups:** —
