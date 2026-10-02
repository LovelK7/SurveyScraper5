# Task brief: Entrance dimensions — read the entrance width and height off the finished survey

- **ID:** 0005-entrance-dimensions
- **Status:** `research` — feasibility shown 2026-10-02 on SB 1220 (horizontal entrance) and SB 1103 (pit); prototype + plots under `findings/`. Next: the user's verdict on the source precedence (§3, phase 2) and a corpus of caves with known entrance sizes to validate against
- **Owner:** both
- **Opened:** 2026-10-02 · **Closed:** —
- **Read first:** [the superapp CLAUDE.md](../../../../CLAUDE.md), [README.md](../../README.md), [0004-nacrt-finishing/brief.md](../0004-nacrt-finishing/brief.md) (the entrance-station decision this builds on), `production/tools/nacrt_finish.py` (`decide_entrance`, `wall`/`item_points` helpers)

> This brief is self-contained: a fresh session can pick it up from cold and know exactly what to do
> and where the work stands, without inheriting any prior conversation.

---

## 1. Problem — what's wrong / missing, and why it matters

The OSZ has two fields for the entrance opening, *Širina ulaza* and *Visina/duljina ulaza*
(4O writes them as `sirina_ulaza` / `visina_duljina_ulaza`, `stages/4O-osz/.../addresses.py:57-58`).
Today they are typed by hand or left empty — SB 1220's OSZ has both blank. The numbers are on the
Nacrt already: the **width** is the gap between the two walls either side of the entrance in the
**plan**, the **height** is the gap between floor and ceiling at the entrance in the **profile**.
For a **pit** the opening is a hole in the plan and the two numbers are its two plan extents
(1 × 2 is the same as 2 × 1); for a **horizontal** entrance width and height are distinct.

The pipeline already decides *which station is the entrance* (project 0004, `decide_entrance`:
surface leg › drawn entrance sign › highest station). What is missing is turning that station
plus the drawn walls into two numbers, so `_dimenzije.json` can carry them to the OSZ.

## 2. Context — what's already known

All verified 2026-10-02 on `Hrđava_špilja-1s_pp_lt_fin.csx` (SB 1220) unless stated.

**The entrance station is already decided and written.** `nacrt_finish.py` writes
`entrance="2"` on the trigpoint; SB 1220's sidecar says station `4`, decided by the surface leg
4→5 (`decide_entrance`, witnesses in `*_lt_fin.layout.json`). The prototype reads the trigpoint
flag and falls back to `decide_entrance` for an unfinished file.

**Station coordinates.** `<calculate><ts><t n="4">` has a direct `<p x y z d="0">` *and* one
`<p>` per `<tcon>` — only the `tcon/p` copies carry the real profile distance `d`
(`d="15.884"` for station 4). Plan design coordinates are `(x, y)`, y growing south (screen
coordinates); profile design coordinates are `(d, z)`, z positive downward.
⚠ `nacrt_finish.read_stations` reads the direct `<p>` and so gets `d=0` for every station — its
profile-side sign witness compares the sign against `(0, z)`. Latent bug, harmless so far
because the plan witness answered first; logged in [log.md](log.md).

**Walls.** The Borders layer (`LAYER_BORDERS = "5"`) holds `type="4"` area items. One item's
`<points data>` is a sequence of sub-paths: a point flagged `B` (BeginSequence,
`cSurvey/cSurveyPC/cPoints.vb:564`) starts a new one. SB 1220's plan item (289 points) is three
sequences; the profile item (129 points) is ten. **cSurvey strokes each sequence separately but
fills the item as one polygon**, inserting a straight line from the end of each sequence to the
start of the next (`cItemFreeHandArea.vb:193-195`, the `oBorderPath` handed to the brush) and
GDI+ closes the last back to the first. Those invisible joins are the pink area's edges in the
user's screenshot where no wall was drawn — on SB 1220 the "ceiling" over station 4 in the
profile is exactly such a join (sequence end at (14.20, −2.49) → next start at (16.56, 0.10)),
and the long diagonal "white line" across the profile is the item's closing edge.

**Raw TopoDroid files** (pre-import `_pp.csx`, e.g. SB 1312) carry the walls as
`<item type="line" name="wall" outline="1">`, so the same measurement could run before the cSurvey
import if ever needed. Not pursued: the finished `_lt_fin` file is the natural input.

**cSurvey computes nothing like this.** Its speleometrics are whole-design bounds; the per-shot
`planpd` / `profilepd` splay-left/right/up/down fields are unset (equal to the station) in our files.

**Splays** at the entrance station are the surveyor's own LRUD-style measurement and the natural
cross-check. SB 1220 station 4: 0.24 m @189°, 0.37 m @349° (left/right), 1.38 m @ +81°, 1.85 m @ +71°
(up), nothing down.

## 3. Approach — phases

**Phase 1 — feasibility (done 2026-10-02).** `findings/entrance_dims_proto.py`:

1. Entrance station `E` from the trigpoint flag, else `decide_entrance`.
2. Passage axis = the counted (non-surface, non-splay) shot touching `E`; **kind** = `pit` when it is
   steeper than 60°, else `horizontal`.
3. Walls = Borders sequences split on `B`, plus the fill bridges (end→next start, last→first)
   **shorter than 5 m** — longer ones are drawing-order artifacts (SB 1220's closing edge runs 15 m
   across the cave and passes 5 cm above the entrance station).
4. **Plan width:** cast a ray from `E` perpendicular to the axis, both ways; nearest **drawn** wall
   per side, fill bridge only as fallback; width = sum. A scan along the axis (−1 m outward … +1.5 m
   inward, 0.25 m steps) shows where the narrowest point is.
5. **Profile height:** same with a vertical ray at `(d, z)` of `E`; the scan runs along `d`.
6. **Pit:** width across and length along the axis in the plan, plus the min/max Feret extent of the
   smallest drawn ring enclosing the station (the footprint).
7. **Splay cross-check:** left/right = nearest flat splay (< 30°) within 0.5 m of the cross-section
   plane, per side (farthest for a pit); up/down = steepest splays (> 45°) within 0.75 m horizontally.
8. Every bridge use and every missing side becomes a warning.

Results (metres, from the drawn walls; splays in brackets):

| Cave | Kind | Entrance | Width (plan) | Height (profile) | Notes |
|---|---|---|---|---|---|
| SB 1220 Hrđava špilja | horizontal | 4 (surface leg) | **0.64** = 0.21 N + 0.42 S [0.57] | **1.49** = 0.81 up + 0.69 down [1.75 up, no down shot] | ceiling over the entrance is a fill bridge, flagged; the width scan is 0.64 → 0.67 → 0.79 inward and 3.2–3.7 outward (the drawn porch), so the narrowest point is the station itself |
| SB 1103 Golobreska | pit (1→2 at 88°) | 2 | **1.47** N–S × **1.68** E–W [1.09] | — (down 8.0 to the floor; no ceiling, correctly) | the enclosing ring is the whole footprint (1.66 × 4.79 m), not the rim — for a pit the station ray-cast is the better number |

Plots: `findings/SB_1220_entrance.png`, `findings/SB_1103_entrance.png` (magenta = hit on a drawn
wall, orange = hit on a fill bridge, grey dashed = bridges), `findings/SB_1220_profile_sequences.png`
(the ten profile sequences and their joins). Reports: `findings/SB_*_report.json`.

**Phase 2 — rules the user settles (proposal).** Open questions, with the prototype's current answer:

1. *Source precedence.* Drawn wall › short fill bridge › nothing, splays as a check only. Should a
   missing side fall back to the surveyor's splay instead of the fill edge? (On SB 1220 the bridge
   says 0.81 m up, the splays say 1.37–1.75 m.)
2. *Where is the entrance plane?* At the station, by definition. Alternative: the narrowest width
   within ±0.5 m along the axis. On SB 1220 both agree.
3. *Pits.* Two plan extents at the station (across/along the first shot), or the footprint's
   min/max Feret, or N–S × E–W? Which pair goes into *Širina* × *Visina/duljina*?
4. *Rounding / format.* OSZ text wants one decimal with a comma (`0,6`, `1,5`); the dossier JSON
   keeps two decimals.
5. *Multiple entrances / branches.* The prototype measures only the main entrance (`entrance="2"`).
6. *Splines.* cSurvey draws Borders as splines through the points; the prototype intersects the
   control polygon. Error is centimetres, below the rounding.

**Phase 3 — productionize (validation).** Move the measurement into `nacrt_finish.py` (it already
holds the station, the walls and the item helpers; fix `read_stations` to take `d` from `tcon/p` on
the way), write `ulaz_sirina_m` / `ulaz_visina_m` + `ulaz_kind` + warnings into the
`_lt_fin.layout.json` sidecar, let `csurvey_driver.finish` carry them into `_dimenzije.json`, and let
4O's prefill fill `sirina_ulaza` / `visina_duljina_ulaza` from there. Tests: SB 1220 and SB 1103
fixtures with the numbers above; a unit test per rule (B-split, bridge cap, drawn-first).

## 4. Definition of done

- [ ] The user has settled phase 2 questions 1–4 (recorded in `docs/design-decisions.md`).
- [ ] Validated on ≥ 5 caves with an entrance size the user vouches for (SB 1220, 1103, + three
      more as they come through the intake), each within 0.1 m of the vouched width/height or with a
      warning that explains the miss.
- [ ] `nacrt_finish.py` emits the numbers + warnings; `_dimenzije.json` carries them; 4O prefills
      the two OSZ fields; `pipeline_doctor.py` green; tests green.
- [ ] All runs logged under `runs/`; contradictions with `reference/` fed back into the docs.

## 5. Outputs (fill in on close)

- **Production:** —
- **Reference:** — (candidate: the Borders sequence/fill-bridge rendering fact belongs in
  `reference/` drawing docs)
- **Decisions:** —
- **Follow-ups:** `nacrt_finish.read_stations` `d=0` fix (phase 3)
