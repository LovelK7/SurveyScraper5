# Task brief: Symbol themes — custom SVG signs, pens and brushes, chosen per cave in Mapiranje simbola

- **ID:** 0007-symbol-themes
- **Status:** `proposal` — viability researched 2026-10-04: **viable without a cSurvey build**, as a post-import step in KORAK 2; cSurvey ignores the SVG's own colours (§2.3). The user answered the same day (§3.5): one colour per symbol is fine, **signs first**, B/W blackens the centerline, and the Illustrator set is one artboard. Next: T0 (user's oracle file) and T1 (splitter), in parallel.
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

1. **One group per symbol, not one layer per symbol.** All symbols can stay on a single layer
   (e.g. `Simboli`). Select one symbol's shapes, press `Ctrl+G`, and in the *Layers* panel rename
   the resulting `<Group>` (double-click its name) to its theme key, i.e. the cSurvey sign name as
   the mapping page shows it (`water-flow`, `danger`, …). A symbol that is already one group only
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
  "signs": { "water-flow": {"svg": "signs/water-flow.svg", "color": "#1F6FD1"},
             "danger":     {"svg": "signs/danger.svg",     "color": "#D12F1F"},
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

**Phase 2 (later):** lines become `type="98"` library pens with clipart decorations, and areas become `type="98"`
library brushes with clipart hatches. `wall_orient.py` copies `<pen>` elements as they are, so the
order matters. Phase 2 also fixes the matrix's area degradations (clay drawn with the sand brush, ice, snow and user
drawn as blank soil).

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

**T0 — oracle file (user, ~5 min in cSurvey).** Open the SB 1103 `_lt` file and:

- (a) on one sign, change its colour to blue (pen and brush);
- (b) on a second sign, replace its glyph with any SVG via *Replace with…*;
- (c) on a third sign, change its colour *and* replace its glyph;
- (d) select all signs once and change their colour together, to see whether cSurvey writes one library entry or N inline ones.

Save as `…_oracle.csx`. *Accept:* the diff against the input shows the exact sign pen/brush/glyph
XML. This replaces guessing (§2.2) with ground truth.

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
