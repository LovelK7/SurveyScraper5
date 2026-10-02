# Implementation log: Entrance dimensions

Brief: [brief.md](brief.md)

---

### 2026-10-02 — feasibility on SB 1220 and SB 1103 (agent) ✅

- **Did:** traced how the finished `_lt_fin.csx` encodes the entrance station, the stations'
  plan/profile coordinates and the Borders walls; found in cSurvey's source that a Borders item is
  stroked per `B`-sequence but filled as one polygon with straight joins between sequences
  (`cItemFreeHandArea.vb:193-195`); wrote `findings/entrance_dims_proto.py` (ray-cast across the
  passage at the entrance station in plan, vertically in profile; drawn wall first, short fill
  bridge as fallback; splay LRUD cross-check; pit branch).
- **Result:** SB 1220 (horizontal, entrance 4): width **0.64 m** from the walls vs 0.57 m from the
  surveyor's left/right splays; height **1.49 m** (0.69 m floor drawn, 0.81 m ceiling from a fill
  bridge, flagged) vs 1.37–1.75 m up-splays. SB 1103 (pit, entrance 2): 1.47 × 1.68 m plan opening
  at the station; no ceiling, correctly. The naive "nearest fill bridge" first gave 0.05 m of
  ceiling on SB 1220 — the item's 15 m closing edge — hence the 5 m bridge cap.
- **Evidence:** `findings/SB_1220_report.json`, `findings/SB_1103_report.json`,
  `findings/SB_1220_entrance.png`, `findings/SB_1103_entrance.png`, `findings/SB_1220_profile_sequences.png`.
- **Found on the way:** `nacrt_finish.read_stations` takes the direct `<t><p>` whose `d` is always
  `0`; the real profile distance is in `<tcon><p>`. Its profile-side entrance-sign witness
  therefore compares against x = 0. Not fixed here (phase 3).
- **Next:** the user's call on brief §3 phase 2 (source precedence, entrance plane, pit pair,
  format); then a corpus of caves with vouched entrance sizes.

### 2026-10-02 (later) — the four rules settled and applied (user + agent) ✅

- **Did:** the user answered brief §3 phase 2: splays first (pick the best-aligned one per
  direction), walls as fallback at the narrowest point, pits from the splay cloud with
  small × large ordering, whole metres. Rewrote the prototype around them; recorded the rules in
  `docs/design-decisions.md`.
- **Result:** SB 1220 → 0.57 × 1.37 m from splays 4(71)/4(72)/4(80) → **1 × 1**; SB 1103 →
  1.08 × 1.71 m from twelve splays → **1 × 2**. The wall fallback agrees on SB 1220 (0.63 × 1.49)
  and over-reads the pit (its footprint, 1.39 × 4.42). Caught on the rerun: "narrowest within
  ±0.5 m" looked outward into SB 1220's converging porch (0.29 m) — the window is now cave-side only.
- **Evidence:** `findings/SB_1220_report.json`, `findings/SB_1103_report.json`, the two PNGs.
- **Next:** caves with a vouched entrance size; then phase 3 (fold into `nacrt_finish.py`,
  fix `read_stations`, carry via `_dimenzije.json` to 4O).
