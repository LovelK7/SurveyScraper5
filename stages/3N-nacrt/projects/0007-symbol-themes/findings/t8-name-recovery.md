# T8 — recovering TopoDroid names after import

Spike T8 of [brief.md](../brief.md) (§3.1 addendum, §3.6). Tool:
[`production/tools/tdx_name_recover.py`](../../../production/tools/tdx_name_recover.py), tests:
[`tests/test_tdx_name_recover.py`](../../../tests/test_tdx_name_recover.py). 2026-10-06.

**Verdict: TopoDroid-first keying works.** On every pre/post pair in the repo, 100 % of points,
lines and areas get their TopoDroid name back, all by exact coordinate match, with no ambiguity.
That includes a real cave and the KORAK 2 output, where walls are merged into one item.

- [1. What the import does to geometry](#1-what-the-import-does-to-geometry)
- [2. Match method](#2-match-method)
- [3. Pairs and results](#3-pairs-and-results)
- [4. How it degrades when the file is edited](#4-how-it-degrades-when-the-file-is-edited)
- [5. Open risks](#5-open-risks)

## 1. What the import does to geometry

Read from `cSurvey/cSurveyPC/cImportTopoDroidHelper.vb` (`ConvertItem`, `pConvertItem`) and
`cPoints.vb:496` (`Parse`), then checked item by item on the zoo and rupe pairs:

- **Coordinates are copied as they are.** `Points.Parse` reads the raw `x y` values, and the
  saved file writes back the same 2-decimal values. There is no transform in the main designs.
  Cross-section items get `MoveBy(Location)`, but `Location` is always `0,0` in this build, and
  no file in the repo has cross-section items.
- **The point order is reversed** (`Points.Revert()`) unless the item has `reversed="1"`.
- **`closed="1"`** only re-flags the sequence (`CloseSequences`). No point is added, and the point
  count is equal on every pair (rupe: 1073 → 1073).
- **The flags are re-encoded.** TopoDroid's `B` becomes `B[P][T#][L][S<segment guid>]`, and
  later points get `S`/`S<guid>` segment bindings. This is why the raw `data` strings never
  compare equal, even though the coordinates do.
- **No spline conversion at import.** `LineType` is forced to `Lines`. KORAK 2 then flips the
  `linetype` attribute to 1 but leaves the points alone.
- **Item count is kept, but the kind and layer change.** `wall`, `wall:presumed` and `rock-border`
  lines become areas (type 4/3), and items are regrouped into the six layers. The layer order is
  the creation order within each layer, not the source order.
- **KORAK 2 (`wall_orient.py`) merges** every open cave-pen wall stroke of a design into one
  Borders item, with one sequence per stroke, and may reverse any of them. A hand Merge in
  cSurvey does the same (`ReorderSequences`). Item counts then differ (zoo 155 → 149 items,
  still 155 sequences).
- Every imported item keeps a `<datarow>TopoDroid|…</datarow>` stamp. Items drawn in cSurvey
  don't have one.

## 2. Match method

The unit matched is the **sequence**, not the item, so merged walls resolve stroke by stroke.

1. **Exact.** The key is `(design, set of coordinates rounded to 1 cm)`. A set ignores order,
   reversal and any duplicated closing point. Duplicate keys are accepted only when every
   candidate has the same name. Otherwise the sequence is reported `ambiguous`.
2. **Tolerant**, for what is left, within the same design and class (point or path):
   - Points match their nearest neighbour within `--tol` (default 0.05 m).
   - Paths are scored by mutual coverage: the share of each side's vertices that lie within
     `--tol` of the other polyline, taking the smaller of the two shares. A path is accepted at
     `--min-score` 0.5 or above.
   - In both cases the match is refused as `ambiguous` if a differently named runner-up is within
     `--margin` 0.15.
   - Pairs are assigned greedy best-first, one-to-one.
3. **Leftovers are reported, never guessed.** A stamped sequence with no source is a `miss`, an
   unstamped one is `native` (drawn in cSurvey), and pre-import sequences that were never used
   are listed as `unused_sources`.

The name is taken from the `tdxpp:` marker when KORAK 1 renamed the item, otherwise from the item's
`name` attribute. Both name fields are reported: `tdx_name` is the original and `prep_name` is the
name after KORAK 1. Unrenamed items keep their TopoDroid `name` in the `_prep` file, so a raw
export works as PRE too.

## 3. Pairs and results

There is no real-cave `_prep` → user-saved `_postp`/`_lt` pair in the repo. The Golobreška, Hrđava
and 272-2p `_pp_lt` files have no pre-import file beside them. The KORAK 2 output was therefore
produced here by running `fix_imported_linetypes.py` on the post-import saves (scratch copies,
not committed).

| Pair (pre → post) | Kind of data | Items pre/post | Points | Lines | Areas | Other |
|---|---|---|---|---|---|---|
| zoo `step-00` → `step-01-after-import` | synthetic, raw | 74/74 | 44/44 | 21/21 | 9/9 | – |
| zoo `step-03-zoo-v3` → `step-04-after-import` | synthetic | 155/155 | 121/121 | 25/25 | 9/9 | – |
| zoo v3 → KORAK 2 of `step-04` | synthetic, walls merged | 155/149 | 121/121 | 25/25 | 9/9 | 7 strokes in 1 item |
| rupe `01b` → `02b-after-import` | real TopoDroid export (test cave) | 67/67 | 34/34 | 23/23 | 10/10 | – |
| rupe `01b` → `03b-native-compare` | + 1 line drawn in cSurvey | 67/68 | 34/34 | 23/23 | 10/10 | 1 native |
| rupe `01c` → `02c`, `01d` → `02d`, `01d` → `03d-final` | real export | 67/67 | 34/34 | 23/23 | 10/10 | – |
| rupe `01d` → KORAK 2 of `02d` | real export, walls merged | 67/66 | 34/34 | 23/23 | 10/10 | – |
| bunker_studena `_pp` (0003 run) → `example/csx_entrances/…_pp.csx` | **real cave** | 39/41 | 22/22 | 14/14 | 3/3 | 2 native (entrance signs added in cSurvey) |
| bunker_studena `_pp` → KORAK 2 of that | real cave, walls merged | 39/38 | 22/22 | 14/14 | 3/3 | 2 native |

Every sequence was matched exactly, with **0 ambiguities and 0 misses** on every pair. The
names come back distinct for one cSurvey target. For example, on rupe `abyss-entrance`,
`chimney` and `overhang` are all `type=1 cat=3`, and so are `slope` and `slope:shallow`, and
`floor-step` and `pit`. `danger` and `anchor` (labels) and `debris` and `breakdown-choke`
(both sign 261) are also told apart. The three `user` points come back as `user`.

## 4. How it degrades when the file is edited

These edits were simulated on the rupe KORAK 2 output (67 sequences), with the true names known
from the unedited run:

| Edit | Result | Wrong names |
|---|---|---|
| none | 67 exact | 0 |
| every vertex jittered ±2 cm | 65 tolerant + 2 exact | 0 |
| ±4 cm | 66 tolerant, 1 point miss | 0 |
| ±8 cm (beyond tol) | 33 paths: 29 tolerant, 4 miss; 34 points: 9 tolerant, 25 miss | 0 |
| 30 % of each path's vertices moved 0.3 m | 32/33 paths recovered, 1 miss | 0 |
| 60 % of vertices moved 0.3 m | 11/33 paths recovered, 22 miss | 0 |
| half the vertices deleted (re-simplified) | 33/33 tolerant | 0 |
| 5 whole sequences moved 0.5 m | those 5 miss, rest exact | 0 |
| 5 sequences deleted | rest exact, 5 `unused_sources` | 0 |
| whole design scaled 0.5 % (≈ a re-warp) | paths 33/33, points 32/34 | 0 |
| scaled 2 % | paths 21/33, points 13/34 | 0 |

The failure mode is always a reported miss, never a wrong name. Added items are `native`.

## 5. Open risks

- **Edits before the theme runs.** The theme step runs in KORAK 2, right after import, before any
  hand editing, so the exact phase covers it. If a theme is re-applied to a hand-edited `_postp`,
  local reshaping still matches, but moved, redrawn or warped items become misses. They then fall
  back to the cSurvey target key, which is the brief's planned fallback.
- **Re-warp after survey changes.** When shots change, cSurvey moves the bound points, and
  everything drifts together. A 2 % drift loses most points. A future fix is to fit a per-design
  similarity transform from the confident matches first. Not built.
- **Hand-split or joined strokes.** Matching is one-to-one. A stroke cut in two in cSurvey gives
  the name to at most one half, the one that covers at least 50 % of the source. The other half
  is a miss. Two strokes joined into one sequence are a miss.
- **Copy/paste of an imported item** keeps the datarow stamp and exact coordinates. The copy
  and the original share one source, so the second one is a `miss`, not a duplicate name.
- **The PRE file must be the one that was imported.** A re-run of KORAK 1 with another mapping
  changes only names, so geometry still matches. A re-export from the phone after more drawing
  gives new items, which are reported.
- **Cross-section items** (`<crosssection>` inside section points) are parsed on the pre side,
  but no file has them, and where cSurvey puts them after import is unverified.
