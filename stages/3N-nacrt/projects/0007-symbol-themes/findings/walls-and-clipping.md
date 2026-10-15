# Walls, the cave area and clipping (2026-10-10 / 12)

Found while tuning the themes on the ss5 reference survey. Short version: **cSurvey cuts most of a drawing to "the
cave area", and today that area comes only from the plain walls.** Anything a surveyor draws outside the plain
walls — special wall kinds, borders outside the cave, the rim of a pit entrance — can disappear.

## Contents

- [1. How cSurvey clips](#1-how-csurvey-clips)
- [2. What goes wrong today](#2-what-goes-wrong-today)
- [3. Done (KORAK 2, 2026-10-10/12)](#3-done-korak-2-2026-10-1012)
- [4. The cave area from every wall kind and the pit rings (built 2026-10-12)](#4-the-cave-area-from-every-wall-kind-and-the-pit-rings)

## 1. How cSurvey clips

- **The cave area** is the union of the cave-border items (type 4, "inverted free-hand area") on the Borders layer
  (`cDesign.GetCaveClippingRegions`, `cDesign.vb:411-470`). After KORAK 2 there is one such item per view: the
  merged wall outline. KORAK 2 merges only lines drawn with cSurvey's cave pens: wall, presumed wall, too narrow,
  underlying wall (`wall_orient.SAFE_PENS`).
- **What gets cut to it** (`cClipping.GetClip`, `cClipping.vb:296-345`), for an item with the default clipping:
  - every item on the layers below Borders: floor areas, water, floor lines (pit, slope, overhang …), ceiling lines;
  - every line on the Borders layer itself, except the merged outline.
- **Never cut:** signs, labels and the centerline (layers above Borders).
- **Per item** `clippingtype`: 0 default, **1 none**, 2 inside the border, 3 outside. **Per survey** the design
  property `ClipBorder`: 0 don't clip the Borders layer, 1 clip (default), 2 no clipping at all.

## 2. What goes wrong today

Evidence: [ss5_plan_odrezano.png](../runs/2026-10-10-r13-ss5/ss5_plan_odrezano.png) — the ss5 plan printed normally
and with `ClipBorder` = 2; **red is what clipping removes** (red flecks inside areas are only a different random tile
placement, not cutting).

| Drawn as | Becomes after import | Problem |
|---|---|---|
| `wall:blocks`, `wall:debris`, `wall:ice` | `border` line (KORAK 1 mapping) | not part of the cave area: their stones/ticks on the outer side are cut, and a passage walled only by them is outside the cave, so floor items in it are cut too (the ceiling-step at the ss5 entrance) |
| `border` outside the cave (e.g. the surface round an entrance) | `border` line | cut away completely |
| `abyss-entrance` | `overhang` line on the floor layer | the pit-mouth ring is wider than the bottom's walls, so most of it is cut; anything drawn on the ledge between rim and bottom too |
| `wall:presumed` next to `wall` | merged into the one outline | the outline has one pen: presumed stretches lose their dash (plan: majority wall; profile: a tie, not themed) |

**Clipping cannot simply be switched off.** The small red tails at the walls in the evidence image are slope and
overhang lines drawn a little past the wall; clipping is what trims those today.

## 3. Done (KORAK 2, 2026-10-10/12)

Both are `postimport` switches in `tdx-mapping.json` (defaults in `fix_imported_linetypes.load_rules`); an item that
already has a `clippingtype` (set by the operator in cSurvey) is left alone.

- **`borders_unclipped`** (default on): every imported line on the Borders layer gets clipping none. Fixes the
  border outside the cave and the wall:blocks/debris/ice decorations (23 lines on ss5).
- **`unclipped_lines: ["abyss-entrance"]`**: lines whose recovered TopoDroid name is in the list get clipping none.
  The name comes from the `_prep` / phone export beside the file (`theme_apply.find_pre` + `recovered_names`); without
  that file KORAK 2 says so and the ring stays cut. Keeps the pit ring whole (1 on ss5).

Not fixed by these: floor items inside a passage walled only by special walls, items on a pit ledge, and the lost
`wall:presumed` dash.

## 4. The cave area from every wall kind and the pit rings

Accepted by the user 2026-10-10/12, **built 2026-10-12 (round r14,
[runs/2026-10-12-r14-cave-area](../runs/2026-10-12-r14-cave-area/RUNLOG.md))** as KORAK 2 switch `cave_area`
(default on; `cave_area_walls: ["wall"]`, `cave_area_rings: ["abyss-entrance"]`; `wall_orient.build_cave_area`).

- **Hidden items.** A cave-border item (type 4) with pen None still gives cSurvey's clip its outline but draws nothing
  (`cPen.Render`, `cPen.vb:1014-1015`: type None → `AddBorder(path, Nothing, wireframe)`, and the clip takes the
  wireframe-outlined paths). Merge mode Add, so cSurvey unions them with the visible outline. They are marked
  `name="obris spilje (KORAK 2)"` and `locked="1"` (cSurvey saves both, `cItem.vb:552,563`).
- **All wall kinds.** Only in a design that has special walls (a recovered name `wall` or `wall:*` on a line): on a
  throw-away copy of the file the merged wall outline is split back into strokes, the special walls join as wall
  strokes, and the fresh-import merge (orientation by the survey, shortest-join chain) makes one outline. A special
  wall joins only if one of its ends lies within 1 m (`LINK_TOL`) of an end of the outline, directly or through other
  special walls: on ss5 two debris pieces drawn round a loose wall stroke were chained in across the cave and added
  four crossing joins.
- **Rings.** Each `abyss-entrance` line is copied as one hidden item. An open ring is closed by cSurvey with a straight
  chord (KORAK 2 says so). The ring itself keeps its clipping None (§3).
- **Re-run.** KORAK 2 first removes the marked items (point joins of later items follow), then builds them again.
  The theme step never themes them.
- **The visible walls are unchanged.** Splitting them into separate lines with their own pens (to keep the
  wall:presumed dash) was **not** built; the merged outline still has one pen.

Still open:

- **Stale after edits.** The hidden outline is built from the walls as KORAK 2 saw them. If the operator edits walls
  in cSurvey afterwards, the cave area does not follow until KORAK 2 is re-run on the edited file. KORAK 3 does not
  rebuild it, because it has no name recovery for the special walls.
- Without a `_prep` or phone export beside the file there are no names, and so no hidden items (KORAK 2 says so).
- The wall:presumed dash (the visible-walls split above).
