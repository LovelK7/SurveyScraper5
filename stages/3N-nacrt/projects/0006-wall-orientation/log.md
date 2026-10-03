# Implementation log: Wall orientation

Brief: [brief.md](brief.md)

---

### 2026-10-03 — interior protocol + orient/reorder prototype on the corpus (agent) ✅

- **Did:** read how cSurvey imports, merges, reverses and fills wall sequences (`../cSurvey`,
  citations in the brief §2); wrote `findings/wall_side_proto.py` (which side of each wall the
  survey is on), `findings/orient_walls_proto.py` (reverse the minority, gate on the fill,
  optional reorder), `findings/draw_fill.py` (renders the fill as cSurvey chains it, before/after),
  `findings/run_corpus.py`.
- **Result:** Golobreška `_fin_backup` → reverses exactly profile sequence 2 (the entrance hook
  the user reversed by hand); output equals the user's `_fin` but for one coordinate cSurvey
  re-rounded on save; fill joins 2.90 → 2.19 m. Hrčava (`_lt` and `_lt_backup` alike) → piece 9
  turned to agree and moved between sequences 4 and 5, joins 35.1 → 7.1 m. Every other corpus
  file: no change. Round-trip parse → serialize of every `<points data>` in the corpus: byte-exact.
- **Found on the way:**
  - A global convention (cave on the right) is wrong for merged items that run consistently the
    other way (272 plan, Hrčava plan): per-stroke reversal broke their chains (joins ×16 and ×7). Rule
    changed to "agree with the item's own majority".
  - Profile splays are unreliable interior unless cut at the first wall: left/right splays
    project through the walls; the entrance station's fan goes into the sky.
  - Hrčava's 22:09 save has piece 9 reversed relative to its 14:05 backup; the protocol sides
    with the backup, and the real defect there was the order.
  - cSurvey's `ReorderSequences` (run by every Merge) reverses by endpoint proximity — the root of
    the coin flip at entrance mouths.
- **Evidence:** `findings/_out/*_sides.png` (blue = cave on the left of the drawing direction,
  orange = right), `findings/_out/Golobreška…_fin_backup_profile_fill.png`,
  `findings/_out/Hrđava…_lt_profile_fill.png`, `findings/_out/corpus_sides.json`.
- **Next:** the user picks where it runs (brief §3 phase 2), then phase 3.

### 2026-10-03 (later) — into KORAK 2 (user + agent) ✅

- **Did:** the user settled it: the merge is the culprit, walls are merged while checking the `_pp`
  import, so the fix belongs in KORAK 2. `findings/merge_sim.py` emulated cSurvey's
  `ReorderSequences` on the finished items (500 shuffles each): orienting the strokes before the merge
  does not survive it (Golobreška 49 % → 26 %, Hrčava 20 % → 18 %). Promoted the prototype to
  `production/tools/wall_orient.py` (stdlib), called by `fix_imported_linetypes.py` behind
  `postimport.wall_orientation` / `wall_reorder`; kit file list, guide, dashboard switches, docs.
- **Result:** identical to the prototype on all 22 corpus files (≤ 0.2 s per cave); the user's
  repaired `Hrđava_…_lt_fixed.csx` is left unchanged; 9 new tests, suite 754 passed. The installed
  cSurvey (`csurvey_driver.py recalc`) loads and re-saves the Golobreška and Hrčava outputs with
  every wall point and flag identical; running the fix on the re-saved files changes nothing.
- **Next:** `/publish`, then the user runs it on the next real cave.
