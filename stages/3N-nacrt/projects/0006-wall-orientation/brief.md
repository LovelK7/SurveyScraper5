# Task brief: Wall orientation — know where the cave is, and fix the walls that run the wrong way

- **ID:** 0006-wall-orientation
- **Status:** `validation` — in KORAK 2 since 2026-10-03 (`production/tools/wall_orient.py`, called by `fix_imported_linetypes.py`): it **merges** a fresh import's wall strokes into one cave border per design and turns/orders the sequences of every merged border, the cave's side voted by the survey. Built, tested, cSurvey-verified, **published in csx kit v1.6 (2026-10-03)**; closes when the user has run it on a real cave.
- **Owner:** both
- **Opened:** 2026-10-03 · **Closed:** —
- **Read first:** [the superapp CLAUDE.md](../../../../CLAUDE.md), [README.md](../../README.md), [production/tdx-processing-protocol.md](../../production/tdx-processing-protocol.md) (KORAK 1–3), [0005-entrance-dimensions/brief.md](../0005-entrance-dimensions/brief.md) (§2: how a Borders item is stroked per sequence but filled as one polygon)

> This brief is self-contained: a fresh session can pick it up from cold and know exactly what to do
> and where the work stands, without inheriting any prior conversation.

---

## 1. Problem

After KORAK 2 the operator merges the imported wall strokes into cave-border items in cSurvey.
The fill of a merged item is wrong whenever one stroke runs the "wrong way": cSurvey joins the end
of each sequence to the start of the next with a straight line, so a reversed stroke makes that
join cut across the passage. The operator then has to find the exact stroke and press
*Revert sequence* — many times per cave. Golobreška nanoekspedicija (2026-10-03, user's
screenshot): the fill ran from the top of the left wall to the middle of the right wall's
entrance hook instead of lip to lip.

A caver sees at once which side of a wall is the cave; the computer needs a rule for it. The
task: (1) a protocol that decides the interior side of every drawn wall, (2) a correction that
reverses the sequences facing the wrong way.

## 2. Context — what's known (verified 2026-10-03)

**Where the bad direction comes from** (cSurvey source, `../cSurvey/cSurveyPC/`):
- The TopoDroid import joins nothing: every stroke stays its own item
  (`cImportTopoDroidHelper.vb:54-58`, `ConvertItem` per `<item>`), reversed once by
  `Points.Revert()` when `reversed=0` (`:68-77`). The corpus agrees: fresh imports (sp7,
  tavnjak, krk_37) have one sequence per item; only hand-merged files have more.
- *Merge* on a selection (`cItemItems.SelfCombine`, `cItemItems.vb:1078-1090`) and
  *Merge with…* (`cItem.Combine`, `cItem.vb:1002-1053`) append the items and run
  `ReorderSequences` (`cPoints.vb:1084-1145`): sequence 0 is kept, then greedily the
  remaining sequence whose First **or Last** point is nearest the current end is taken —
  **reversed** if its Last is nearer. At an entrance mouth both ends of a stroke are about
  equally far (Golobreška: 1.77 vs 1.81 m), so that step flips a coin. Pre-orienting strokes
  before the merge is therefore pointless: the merge re-reverses by proximity.
- The fill: `cItemFreeHandArea.vb:186-209` / `cDesign.GetCaveClippingPaths`
  (`cDesign.vb:360-376`) chain the sequences end→start and close last→first. For a simple
  loop the winding is irrelevant; it matters only through which ends get joined.
- *Revert sequence* = `cSequence.Reverse` (`cSequence.vb:229-242`): point order flipped, the
  B/P/T prefix (begin flag, own pen, line type) moves to the new first point.

**Convention.** TopoDroid's guide asks for walls drawn counterclockwise, cave on the left
(`literature/topodroid/TopoDroidAndCSurvey.pdf` p.1-2; manual p.39), and the import reverses
the stroke — so in a cSurvey file a wall drawn by the book has the cave on its **right**. The
corpus shows surveyors do not follow it: fresh imports are roughly half and half. It does not
matter for the fill (only agreement inside one item does), see §3.

**Which items may be reversed.** Borders items of `type="4"` with a cave pen —
`cPen.PenTypeEnum` 1 Cave, 8 PresumedCave, 25 TooNarrowCave, 26 UnderlyingCave
(`cPen.vb:1164-1167`) — have no one-sided decoration. Pit (CliffDown), overhang and chimney
lines do (`cPens.vb:346-409`, `cPen.vb:1284-1288`): their direction is meaning and they are
never touched. Each sequence can carry its own pen (`BP…` flag + a `<pen>` child of
`<points>`, in sequence order, `cPoints.vb:567-571`) — judged per sequence.

**File details a rewrite must respect.** Point flags are `[B[P][T<n>]][L][S[guid]]`
(`cPoints.vb:496-599`); a bare `S` means "bound to the same segment as the previous point", so
bindings are resolved before reversing and re-serialized after. Point joins
(`<pointsjoins><pointsjoin data="layer,item,point …">`, `cPoint.vb:181-195`) reference point
indices and are remapped. Parse → serialize round-trips byte-exactly on every corpus file.

## 3. Approach

**Phase 1 — the interior protocol (done, prototype).** *The survey is inside the cave.*
[`findings/wall_side_proto.py`](findings/wall_side_proto.py):
- Known interior = points every 0.1 m along every in-cave leg (flagged surface/excluded legs
  dropped) and along every splay — a splay only up to the first drawn wall it crosses (profile
  projections of left/right splays poke through walls), and an uncut splay only if its tip lands
  within 0.5 m of a wall (the entrance fan into the sky at Golobreška lands nowhere and is
  dropped). In the plan a shot's weight shrinks with cos²(inclination): Sopača's 50 m shaft
  projects across the chamber walls below.
- Every 0.15 m along a wall, the nearest interior sample the wall point can *see* (sight line
  crosses no other drawn wall — a parallel passage behind rock does not vote) votes left or
  right of the wall's local direction, weight length/(0.3 + distance), legs ×3.
- Score = signed vote share in [−1, +1]; coverage = share of the wall that saw any survey.
  Positions come from `<calculate>`: `tcon/p` per connection (x, y in plan; d, z in profile).

**Phase 1b — the correction (done, prototype).** [`findings/orient_walls_proto.py`](findings/orient_walls_proto.py):
- **Relative, not absolute.** Per merged item, the confident (|score| ≥ 0.6, coverage ≥ 0.3),
  length-weighted majority side (≥ 60 %) is "the right way"; only a confident minority is
  reversed. A global "cave on the right" rule was tried first and is wrong: 272's and Hrčava's
  plans are merged items running consistently cave-on-left, and reversing each stroke on its own
  (order kept) blew their fill joins up from 2.8 to 45.7 m and 5.1 to 36.5 m.
- **Gate.** A flip set is applied only if the fill's joins get no longer and no more of them
  cross a drawn wall; otherwise it is reported and left to the operator (272's plan, one 0.9 m
  dissenter: joins would grow 2.78 → 3.52 m).
- **Reorder** (`--reorder`): with directions settled, the sequence order with the shortest
  joins (relocation search, sequence 0 stays first, no reversals); kept only if the joins drop
  below 80 %. Hrčava's profile needs it: its far-end piece sat last in the chain but belongs
  between sequences 4 and 5 — whichever way it ran, two ~14 m joins crossed the whole cave.
- One-sequence items are left alone: they have nothing to agree with, and a later merge
  re-reverses anyway.

**Phase 2 — where it runs (settled 2026-10-03: KORAK 2).** The user merges the walls while checking the `_pp` import, before Save As, so KORAK 2 receives merged items; "the merge is the culprit". The emulation (`findings/merge_sim.py`) confirmed that orienting the separate strokes before a merge does not survive it. The options weighed were: The merge happens *after* KORAK 2, so a pass
inside today's KORAK 2 would run too early. Options:
- **A.** Automatically in KORAK 3 (`nacrt_finish.py` already rewrites `_lt` → `_lt_fin`), so
  the printed Nacrt is always right; the report lists what was flipped/reordered/left.
- **B.** A re-runnable "fix walls" pass the operator runs mid-work (merge → save → run →
  reopen), as a mode of KORAK 2 on an `_lt` file or its own launcher.
- **C.** Both (recommended): one module, called by KORAK 3 and by a mid-work entry.

**Phase 3 — promote.** `production/tools/wall_orient.py` (stdlib only — the kit runs on
operators' machines; the prototype already is), wired per phase 2; tests on synthetic items
(reversal + flags + bindings + joins, the gate, the reorder) and the corpus pairs below;
`tdx-processing-protocol.md`, the operator guide `csurvey_0_PROCITAJ_ME.txt`, the 3N README.

## 4. Definition of done

- [x] Golobreška `_fin_backup` → profile sequence 2 reversed, identical to the user's
      `_fin` (one coordinate 0.51 vs 0.50 = cSurvey's own re-rounding on save); `_fin` → no change.
- [x] Corpus dry run: no change in any file except Golobreška `_backup` and Hrčava (both).
- [x] The user's call on phase 2 (KORAK 2); the user's own repaired Hrčava (`_lt_fixed`) is left unchanged.
- [x] Promoted with tests (`tests/test_wall_orient.py`); the installed cSurvey loads and re-saves the output with identical wall points, and a second run is a no-op.
- [x] Published: csx kit v1.6 (2026-10-03).
- [ ] Run by the user on a real cave.

## 5. Outputs (fill in on close)

- **Production:** `production/tools/wall_orient.py`, wired into KORAK 2 (`postimport.wall_merge` / `wall_orientation` / `wall_reorder`), the kit file list, the operator guide, the dashboard's Mapiranje switches.
- **Decisions:** `docs/design-decisions.md` § 3N wall orientation and § 3N wall merge (2026-10-03).
- **Follow-ups:** the automatic merge was built the same day (log; decision record § 3N wall merge).
