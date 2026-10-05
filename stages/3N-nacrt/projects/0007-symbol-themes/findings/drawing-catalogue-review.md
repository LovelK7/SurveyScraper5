# Review: `drawing_catalogue.svg` (user's first export, 2026-10-05)

The file is checked against the cSurvey SVG subset (brief §2.3–§2.4). This is a hand-run preview of what T1
`check` will report.

## Structure: correct

- Exported with layer-name IDs; no `<style>` block, so presentation attributes are used.
- Three layers: `Znakovi` (12 groups), `Linije` (10) and `Površine` (6), each holding one named group per piece.
- Group names are **TopoDroid names** (`slope:steep`, `water-flow:intermittent`, `tree-trunk`). The colons
  survived the export. This fits the TopoDroid-first key that T8 would enable.
- Two names carry Illustrator's uniqueness suffix: `debris-2` and `blocks-2`, the areas named like the signs.
  The splitter strips the suffix.

## Whole-file issues (all fixable automatically by T1, no redraw)

| Issue | Where | Fix in T1 |
|---|---|---|
| **Arc commands (`a`/`A`) in paths.** cSurvey's parser has no arc case, so these shapes would break | 12 groups, 213 paths (every circle, dot and rounded shape: `!`, `?`, ⊕, ⊖, bones, tree-trunk, pebbles, clay…) | convert arcs to cubic Béziers |
| **Strokes.** cSurvey ignores stroke width and colour and draws outlines with its own pen width | 17 groups (see below) | outline to fills (stroke→polygon offset), or keep and let the pen width rule; T1 reports which |
| **Invisible rectangles** (`fill="none"`, no stroke, at `x=0.5`, far left of the artboard). cSurvey outlines *every* shape, so these would print as boxes and stretch the symbol's bbox across the page | plus, minus, plus-minus, airdraught, continuation, vegetable-debris, clay, debris-2, blocks-2, ice | drop shapes with neither fill nor stroke |
| `<ellipse>` | pebbles (1) | ellipse → path |
| `translate(…)` / `rotate(…)` transforms | 291 elements | bake into coordinates (no skew present) |

## Per piece

✅ = ready after the automatic fixes. ⚠ = a decision or a redraw is needed.

### Znakovi

| Group | Verdict | Note |
|---|---|---|
| `danger` | ✅ | stroked triangle + filled `!` |
| `blocks` | ✅ | grey outlines only, so the theme colour replaces the grey |
| `plus`, `minus`, `plus-minus` | ✅ | stroked circle/ellipse + bars |
| `airdraught` | ✅ ⚠ name | the TopoDroid name is `air-draught`; `airdraught` is the cSurvey name. Both resolve, but pick one style |
| `continuation` | ✅ | |
| `debris` | ✅ | TopoDroid `debris` maps to `breakdownchoke` today, so this glyph needs the TopoDroid key (T8) |
| `bones` | ✅ | white fill + outline, exactly the allowed two-tone. TopoDroid `bones` has no cSurvey sign today (X-box), so it needs T8 or a carrier |
| `tree-trunk` | ✅ | one brown + white, no strokes. Ideal |
| `vegetable-debris` | ⚠ **redraw or accept** | 45 gradients, about 20 colours, 117 strokes. It will collapse into one-colour silhouettes. Needs a one-colour + white version |
| `water-flow:intermittent` | ✅ | two blue fills |

### Linije

| Group | Verdict | Note |
|---|---|---|
| `abyss-entrance`, `overhang`, `slope:steep`, `slope:sheer` | ✅ | one filled shape each, no baseline. The per-subtype looks need T8 |
| `pit`, `ceiling-step` | ✅ | a single stroked tick; outline it or let the pen width rule |
| `floor-meander` | ✅ | 4 stroked lines (rails + ticks), to be centred with the base pen off (brief §2.4) |
| `slope:shallow` | ✅ | |
| `water-flow` | ✅ | one blue fill. Note: the TopoDroid `water-flow` line maps to `presumed` today |
| `rope` | ⚠ | a single red rectangle. If rope is meant to be a dashed red line, that is a pen dash style, not a unit. A rectangle repeated with gaps *is* a dash, but the pen dash bends with curves, and repeated rectangles do not |

### Površine

| Group | Verdict | Note |
|---|---|---|
| `pebbles` | ✅ ⚠ size | about 50 pebbles in one patch (stock: 5). It works, but one large patch shows its own repetition and outer edge. Consider a cluster of 5–8 |
| `clay` | ✅ | dots |
| `debris-2`, `blocks-2` | ✅ ⚠ colour | grey fill + darker outline. Whether fill and outline can differ in colour on an area brush is **unverified** (T0/T7). Until then, plan for one colour + white |
| `stalagmite` | ⚠ phase 2 | no cSurvey area type; TopoDroid `stalagmite` area falls back to generic soil today, so it needs a carrier area |
| `ice` | ⚠ phase 2 | same: no cSurvey area type |

## Second pass (user's fixed export, 2026-10-05 21:17)

**Fixed:** strokes are outlined in `danger`, `plus`, `minus`, `plus-minus`, `continuation` and `bones`
(black + white now); the invisible rects are gone from `plus-minus` and `air-dr…`; `pebbles` is down from
104 to 41 shapes with no strokes.

**Still open:**

| Group | Issue |
|---|---|
| `air-drought` | **typo**: the TopoDroid name is `air-draught` |
| `block` (sign) | renamed from `blocks`. `block` is a *different* TopoDroid point (geo set, "blocco", X-box today); `blocks` is the speleo one. Intended? |
| `slope` (line) | was `slope:shallow`. Now it is the generic slope, so `slope:shallow` has no unit. Intended? |
| `debris-2`, `blocks` (areas) | outlines outlined into **dark-grey fills** (`#616262`) next to the light-grey faces (`#c9c9c8`). cSurvey paints *every* non-white fill one colour, so outline and face merge into solid blobs. Make the faces **pure white `#FFFFFF`**. `blocks` still has 55 strokes |
| `pit`, `ceiling-step`, `floor-meander` | still strokes only. Outline them, or accept cSurvey's pen width |
| invisible rects | still in `plus`, `minus`, `continuation`, `vegetable-debris`, `clay`, `debris-2`, `blocks`, `ice` (8 left). T1 drops them anyway |
| `vegetable-debris` | unchanged: 45 gradients and 63 colours (decision pending) |
| `rope` | unchanged: a single red rectangle (decision pending) |

Arcs remain everywhere. That is expected: T1 converts them, and they are not for the user to fix.
