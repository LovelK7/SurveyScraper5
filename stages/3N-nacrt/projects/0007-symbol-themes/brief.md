# Task brief: Symbol themes — custom SVG signs, pens and brushes, chosen per cave in Mapiranje simbola

- **ID:** 0007-symbol-themes
- **Status:** `proposal` — viability researched 2026-10-04 (two read-only digs: the 3N pipeline and the cSurvey clipart/pen/brush code). **Verdict: viable without a cSurvey build**, as a post-import step in KORAK 2. One hard constraint: cSurvey ignores the SVG's own colours (§2.3). Awaits the user's answers in §3.5 and the hand-made oracle file (T0).
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

Illustrator recipe (proposed): one artboard per symbol, named by its theme key, and then
*Export for Screens → SVG*, which gives one file per artboard. Before exporting:

- *Object › Expand Appearance* and *Outline Stroke*, so stroke widths become fills;
- turn text into outlines;
- release symbols and clipping masks;
- export with Styling = *Presentation attributes* and 2-3 decimals.

A normaliser (T1) can do the rest automatically: `ellipse`→path, skew baking, colour flattening, and
adding `xmlns:csurvey` + `csurvey:sign`/`scale`.

## 3. Approach

### 3.1 Theme = a folder of content files, applied in KORAK 2

```
production/themes/<id>/
  theme.json        name, extends?, colours, per-key glyph/pen/brush specs, centerline overrides
  signs/*.svg       normalised glyphs (T1 output)
  lines/*.svg       pen decoration cliparts
  areas/*.svg       brush hatch cliparts
```

Sketch of `theme.json`:

```json
{ "name": "Boja", "extends": null,
  "points": { "water-flow": {"svg": "signs/water-flow.svg", "color": "#1F6FD1"},
              "danger":     {"svg": "signs/danger.svg",     "color": "#D12F1F"} },
  "lines":  { "pit":   {"decoration": "lines/pit.svg", "spacing": 40, "color": "#000000", "width": 0.1} },
  "areas":  { "water": {"clipart": "areas/water.svg", "density": 1.0, "zoom": 1.0, "color": "#1F6FD1"} },
  "centerline": { "PlotPenColor": "…" } }
```

A black-and-white theme is `{"extends": "boja", "monochrome": "#000000"}`.

**Key choice (*assumed*, confirm in §3.5):** points are keyed by the **TopoDroid name**, read from
the `tdxpp:` marker. If the marker is missing, the `SignEnum` name is used instead. Keying by the TopoDroid name lets
the 29 speleo-2 points that have no cSurvey sign get their own glyph, sitting on a carrier `SignEnum`
chosen by the mapping. Mapping (*what it is*) and theme (*what it looks like*) stay orthogonal.

### 3.2 What `apply_theme` writes (post-import, idempotent)

- **Signs:** add each used glyph to `<signs><cliparts>` (hash id, base64; zip entry in a `.csz`,
  reusing the `nacrt_finish.py` splice), repoint the item's `data`, and replace
  `<pen type="10"/><brush type="7"/>` with library references carrying the theme colour.
- **Lines:** one `type="98"` library pen per theme line key in `<pens>`, with items repointed.
  `wall_orient.py` copies `<pen>` elements as they are, so it must run *before* the theme, or it must be
  checked that it copies the library reference unchanged.
- **Areas:** one `type="98"` library brush per theme area key in `<brushes>`, with items repointed.
  The theme also fixes the matrix's degradations: clay drawn with the sand brush, and ice, snow and user areas drawn as blank soil.
- **Centerline / labels:** merge the theme's overrides over `postimport.centerline`.
- Record `theme=<id>` in the file (e.g. a `<datarow>` or `properties` note) so a re-run can detect it.

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

### 3.5 Questions for the user

1. Is **one colour per symbol (plus white)** acceptable for the colour theme? If not, which symbols
   truly need two colours?
2. Scope of the first cut: **signs only**, or signs + line decorations + area fills?
3. Should the B/W theme also make the centerline and station labels black?
4. Key points by TopoDroid name (§3.1) or by cSurvey sign?
5. How many symbols are in the Illustrator file, and is it one artboard per symbol already?

### 3.6 Delegable tasks (each a self-contained prompt for a separate, cheap session)

Fixture: `stages/3N-nacrt/example/finishing/SB_1103_golobreska_lt_raw.csx` (gitignored). Order: T0 → T1 ∥ T2 → T3 → T4 → T5 → T6.

**T0 — oracle file (user, ~10 min in cSurvey).** Open the SB 1103 `_lt` file and do four things:

- (a) on one sign, change the brush colour to blue;
- (b) on the water area, create a user brush with *hatch = clipart* from any SVG and add it to the library;
- (c) on one pit line, create a user pen with a custom SVG decoration;
- (d) replace one sign's glyph via *Replace with…*.

Save as `…_oracle.csx`. *Accept:* the diff against the input shows the exact XML for all four. This
replaces guessing serialisation details (§2.2) with ground truth.

**T1 — `theme_svg.py check|normalize`.**

- *Input:* a folder of Illustrator SVG exports.
- *Output:* normalised SVGs (ellipse→path, skew baked, gradients/opacity rejected, fills flattened to
  black/white, `xmlns:csurvey` + `csurvey:sign`/`scale` added from a key→enum table) and a report listing every
  unsupported construct per file.
- *Accept:* every SVG in `C:\csurvey64\Objects\Cliparts\Signs` passes `check` unchanged, and a
  hand-made Illustrator export with an ellipse, a gradient and a stroke is fixed or reported.
  Stdlib only (`xml.etree`).

**T2 — theme format + loader.** `themes.py`:

- load `theme.json` with `extends` / `monochrome`;
- resolve paths;
- validate keys against `tdx-mapping-catalog.json`;
- hook it into `check_defaults.py`.

*Accept:* unit tests for inheritance, monochrome and a missing file.

**T3 — `apply_theme` in KORAK 2.**

- *Input:* a post-import `.csx` or `.csz` and a theme id.
- *Output:* the file with glyphs, library pens and brushes, and colours as in §3.2, modelled on the T0 oracle.
- *Accept:* idempotent (two runs give a byte-identical file); opens in cSurvey with no `clipart_error`;
  the headless print (`csurvey_headless.ps1`) renders the themed glyphs in both the colour and the
  B/W theme; the PDFs are checked by eye.

**T4 — Mapiranje simbola: Tema dropdown.** `mapping.js` and `gui/mapping.py`:

- add a theme select stored as `"theme"` in the override;
- take pictures from the theme SVGs.

*Accept:* save → reload round-trips; reset removes it.

**T5 — kit.** `build_csx_kit.py` copies `production/themes/` → `csurvey_alati/teme/`. KORAK 2's
launcher passes the cave's theme. Update the operator guide template. *Accept:* `KIT_VERSION`
bumped, and a dry-run build lists the theme files.

**T6 — first two themes** from the user's Illustrator file. *Input:* the user's per-artboard SVG export.
*Output:* `themes/boja/` and `themes/crno-bijelo/`. *Accept:* the user signs off on SB 1103 printed
in both themes.

## 4. Definition of done

- [ ] T0 oracle captured, and §2.2 corrected wherever it disagrees.
- [ ] SB 1103 prints in two themes from one `_lt` file, chosen on Mapiranje simbola, with no X-boxes.
- [ ] The kit ships the themes, and nothing is installed into the cSurvey folder.
- [ ] `check_defaults.py` validates themes, and `pipeline_doctor.py` is green.
- [ ] The decision (post-import theme, not install-folder glyphs) is recorded in `docs/design-decisions.md`.

## 5. Outputs (fill in on close)

- **Production:** —
- **Reference:** —
- **Decisions:** —
- **Follow-ups:** —
