# Task brief: Entrance dimensions — read the entrance width and height off the finished survey

- **ID:** 0005-entrance-dimensions
- **Status:** `closed` 2026-10-03 — phase 3 shipped: `production/tools/entrance_dims.py` inside KORAK 3a, `entrance_size` through `_dimenzije.json`, `osz prefill` fills Broj / Širina / Visina ulaza. §5 lists what was promoted; Sopača's station stays an optional look
- **Owner:** both
- **Opened:** 2026-10-02 · **Closed:** 2026-10-03
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

**Phase 2 — rules (settled by the user 2026-10-02; the decision record has the whole).**

1. *Source precedence:* **splays first** — the surveyor shot them at the entrance on purpose; the
   job is to pick the right one. Per direction (left/right across the axis in the plan, up/down in
   the profile) the splay best aligned with it, within a 40° cone, measured by its length along
   that direction. An up splay with no down splay = the station is on the floor (down = 0).
   Walls only when no splay serves a side.
2. *Entrance plane:* the wall fallback takes the **narrowest** opening within 0.5 m of the station,
   **on the cave side only** (outward, SB 1220's drawn porch converges to 0.3 m in the profile).
3. *Pits:* two plan extents from the **splay cloud** (min/max Feret), the wall footprint as
   fallback; **Širina = the smaller, Visina/duljina = the larger** (1 × 2, never 2 × 1). For a
   horizontal entrance width stays the plan and height the profile.
4. *Format:* **one decimal** (2026-10-03; the first call was whole metres).
5. *No size without a witnessed entrance* (user, 2026-10-03): the drawn entrance sign, the finisher's
   trigpoint flag, a surface leg or the operator's word name the station; a station picked only
   because it is the highest is a guess and gets a warning ("nacrtaj znak ulaza") instead of a number.

Applied (prototype rerun, `findings/SB_*_report.json`):

| Cave | From splays | From walls (fallback, unused) | OSZ |
|---|---|---|---|
| SB 1220 | 0.57 wide (4(71) 0.22 + 4(72) 0.35), 1.37 high (4(80) up, no down shot) | 0.63 × 1.49 (ceiling = fill join) | **0,6 × 1,4** |
| SB 1103 pit | 1.08 × 1.71 (12 splays) | 1.39 × 4.42 (the footprint, too wide) | **1,1 × 1,7** |

Still open: multiple entrances (only the main one is measured) and splines vs the control polygon
(centimetres, below the rounding).

### Corpus run — `example/csx_entrances/` (11 surveys, 2026-10-03)

`findings/run_corpus.py <folder>` runs every `.csx`/`.csz` in a folder; the reports and key plots are
copied to `findings/corpus/` because `example/` is gitignored. Numbers in metres, OSZ = one decimal.

| Survey | State | Kind (why) | Entrance (how) | OSZ Š × V/D | Source | Read it as |
|---|---|---|---|---|---|---|
| 272 | `_lt` | pit (shot 85°) | 4 (highest + sign) | **1.6 × 3.3** | splays (walls: 4.1 × 7.2 = whole chamber) | plausible — the rim station's splays span the mouth |
| Golobreška (SB 1103) | `_lt_fin` | pit (88°) | 2 (flag) | **1.1 × 1.7** | splays | as before |
| Sopača | `-1p` imported | pit (70°) | 5 (highest + sign) | **13.6 × 17.5** | splays; walls absent around 5 | **check** — station 5 sits outside the drawn plan with 11 flat splays up to 17 m: a doline rim, or a surface station? |
| bezdanka iznad Lalica | imported | pit (6 of 16 splays dive > 45°) | 5 (highest + sign) | **4.7 × 8.4** | splays (walls 6.8 × 11.2) | plausible; was `horizontal` before the splay-based pit test |
| kilavčev cepavpic | `_pp` | pit (80°) | 4 (highest only) | **—** | declined: no entrance sign, no surface leg | the splays would say 1.1 × 2.4 — draw the sign and it is measured |
| kilavčeva pljeskavica | `_pp` | **pit (registry; geometry said horizontal: shot 35°, 7 flat splays)** | 3 (flag) | **4.7 × 8.5** | splays (walls 3.7 × 10.8) | the user: it is a pit; the rim station's flat splays span the hole, like 272 — the type must come from SB / OSZ, not from geometry |
| krk_27 | **raw** | pit (87°) | 3 (highest only — correct, the user confirmed after first mixing it up with krk_37) | **—** | declined: no entrance sign | with the sign on 3 it reads **3.5 × 4.8** from the rim splays (walls 7.2 × 8.8) |
| krk_37 | **raw** | horizontal (40°) | 0 (highest only — correct per the user) | **—** | declined: no entrance sign | with the sign on 0 the walls give 0.9 × 1.4 (no splays at 0) |
| sp7 Brad/Kosa/Plazibat špilja | imported | horizontal (22°) | 9 (highest-ties + sign) | **2.7 × 2.2** | splays (walls 3.1 × 2.3) | plausible; station 10 is 3.3 m higher — a side entrance or surface point? |
| špilja Bunker (Studena) | `_pp` | horizontal (11°) | 5 (sign; highest is 1) | **2.6 × 1.5** | splays (walls 2.4 × 1.4) | plausible, sources agree |
| Tavnjak (Mune) | imported | pit (86°) | **8** (profile sign + highest; plan sign at 7 overruled) | **2.0 × 6.2** | splays (walls 3.2 × 6.0) | plausible once the entrance is 8; station 7 is a ledge 20 m down the shaft; **confirmed by the user 2026-10-03** (the plan sign was attached to the wrong station) |

What the corpus changed in the prototype:

- **Pit test by splays too:** a station whose splays mostly dive (at least a third steeper than 45°, none
  steeper up) is a pit rim even when the first shot is flatter than 60° (bezdanka).
- **One source per opening:** both sides from splays, else both from walls — never one of each
  (pljeskavica had splay 0.49 + wall 0.11 = 0.6; the walls alone say 0.9).
- **Raw TopoDroid exports** work: stations traversed from the shots (`direction="1"` = extend left,
  as the SB 1220 CSV confirms), splays from the splay segments, walls from the `wall` /
  `wall:presumed` lines (no sequences, no fill bridges).
- **Sign tie-break (proposed for `nacrt_finish.decide_entrance`):** when the plan and profile signs
  disagree, the one that agrees with the highest station wins; today the plan wins and Tavnjak's
  entrance lands on a ledge. Also surfaced: the prototype had passed station *names* instead of
  `Station` objects to `decide_entrance` (sp7 crashed) — the finisher itself does it right.
- A warning when the entrance lies more than 2 m below the highest station.
- **`--entrance <station>` / `entrances.json`** let the operator state the entrance station outright.
- **The cave's type comes from the registry.** `analyse(path, kind=...)` / `--kind pit|horizontal`; the
  corpus runner reads `<folder>/kinds.json` as a stand-in for SB's type / the OSZ's *Vrsta objekta*. Geometry
  (steep first shot, diving splays) is only the fallback and the report says when the two disagree.
  In production the type is one SB lookup away (4O already reads SB for the OSZ prefill).

**Phase 3 — productionize (validation).** Move the measurement into `nacrt_finish.py` (it already
holds the station, the walls and the item helpers; fix `read_stations` to take `d` from `tcon/p` on
the way), write `ulaz_sirina_m` / `ulaz_visina_m` + `ulaz_kind` + warnings into the
`_lt_fin.layout.json` sidecar, let `csurvey_driver.finish` carry them into `_dimenzije.json`, and let
4O's prefill fill `sirina_ulaza` / `visina_duljina_ulaza` from there. Tests: SB 1220 and SB 1103
fixtures with the numbers above; a unit test per rule (B-split, bridge cap, drawn-first).

## 4. Definition of done

- [x] The user has settled phase 2 questions 1–4 (recorded in `docs/design-decisions.md`, 2026-10-02).
- [ ] Validated on ≥ 5 caves with an entrance size the user vouches for (SB 1220, 1103, + three
      more as they come through the intake), each within 0.1 m of the vouched width/height or with a
      warning that explains the miss.
- [ ] `nacrt_finish.py` emits the numbers + warnings; `_dimenzije.json` carries them; 4O prefills
      the two OSZ fields; `pipeline_doctor.py` green; tests green.
- [ ] All runs logged under `runs/`; contradictions with `reference/` fed back into the docs.

## 5. Outputs (fill in on close)

- **Production:** `production/tools/entrance_dims.py` (ported from `findings/entrance_dims_proto.py`),
  `nacrt_finish.py` (calls it; `entrance_count`; the sign tie-break in `decide_entrance`;
  `read_stations` reads `d` from `<tcon><p>`), `csurvey_driver.py` (`entrance_size` travels into
  `_dimenzije.json`), `prod/build_csx_kit.py` (the kit ships the new module); 4O
  `osz/prefill.py` (`entrance_values`, `entrance_kind_from_ticks`, `_apply_entrance_kind`,
  `_same_measurement` at a tenth) + `osz/models.py`. Tests: `tests/test_entrance_dims.py`,
  `test_nacrt_finish.py` (tie-break), `4O-osz/tests/test_osz_prefill.py` (entrance cells).
- **Reference:** the Borders sequence / fill-join rendering fact (`cItemFreeHandArea.vb:193-195`)
  is documented in `entrance_dims.py` and the decision record; a `reference/` page is still open
  (backlog).
- **Decisions:** `docs/design-decisions.md` → "3N entrance dimensions: splays first, walls as
  fallback (2026-10-02)" with the phase 3 wiring appended.
- **Follow-ups:** Sopača's station 5 (outside the drawn plan) — the user's eye, optional; a
  `reference/` page on how cSurvey fills a Borders item.
