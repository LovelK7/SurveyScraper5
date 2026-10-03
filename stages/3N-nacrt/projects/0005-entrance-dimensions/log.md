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

### 2026-10-03 — rule 4 reversed: one decimal (user) ✅

- **Did:** `round_osz` now rounds to 0.1 m instead of whole metres; reports, decision record and brief updated.
- **Result:** SB 1220 → **0,6 × 1,4**, SB 1103 → **1,1 × 1,7**.
- **Next:** unchanged — a vouched corpus, then phase 3.

### 2026-10-03 — corpus of 11 surveys (agent) ✅

- **Did:** ran the prototype over `example/csx_entrances/` (raw TopoDroid → `_pp` → `_lt` → `_lt_fin`);
  added `findings/run_corpus.py`; fixed what the corpus broke: raw exports (stations traversed from the
  shots, `wall` lines as walls), the pit test by diving splays, one source per opening, the sign tie-break
  toward the highest station, the `Station`-objects bug in my own `decide_entrance` call (sp7).
- **Result:** table in brief §3 "Corpus run": 9 of 11 plausible, 2 flagged (Sopača 13.6 × 17.5 from a
  station outside the drawn plan; pljeskavica height unknown — profile not drawn to the entrance).
  Pits consistently read smaller from splays than from the walls (walls = the chamber below the mouth).
- **Evidence:** `findings/corpus/*.json`, `findings/corpus/_overview.png` and four entrance plots.
- **Next:** the user vouches/corrects per cave; decide the sign tie-break for `nacrt_finish`; phase 3.

### 2026-10-03 (later) — Tavnjak confirmed, pljeskavica is a pit (user + agent) ✅

- **Did:** the user confirmed Tavnjak's entrance is 8 (the plan sign was attached to the wrong station) and that
  pljeskavica is a pit. Added the registry-type override (`--kind`, `kinds.json` in the corpus runner); the runner
  skips cSurvey's `*_backup.csx` copies.
- **Result:** pljeskavica → **4.7 × 8.5** from its seven flat rim splays (walls 3.7 × 10.8). Geometry alone
  called it horizontal (35° first shot, no diving splays), so the type has to come from SB / OSZ.
  The sign tie-break toward the highest station is accepted for `decide_entrance` (phase 3).
- **Evidence:** `findings/corpus/kilavceva_pljeskavica-1p_pp.json`, `findings/corpus/kinds.json`.
- **Next:** Sopača's verdict; phase 3.

### 2026-10-03 (later) — krk_27: the highest station was a blind aven (user + agent) ◐

- **Did:** the user: krk_27's entrance is station 0, not 3. Traced why 3 was chosen: no sign, no surface
  leg, so the highest station won — and the data really does put 3 at the top: the 2→3 leg is +86.6°,
  every splay at 2 points up (51–86°), the profile walls reach 26 m above station 1. cSurvey's
  `direction` attribute is the profile extend side (Right 0 / Left 1 / Vertical 2, cSurvey.vb:71), not a
  reversed shot. The drawing closes the aven 0.2 m above 3 (`wall:presumed`). Added the blind-dome guard
  (a drawn roof within 1 m above a highest-station-only choice → the survey's first station, warn) and the
  `--entrance` / `entrances.json` override.
- **Result:** krk_27 now lands on 0 with warnings, but the numbers at 0 (7.2 × 9.3 as horizontal, 8.6 × 12.9
  as pit) are the chamber: a drawn ceiling 9.5 m above 0 and 33 splays to the chamber walls, nothing that
  describes the opening. Honest output here is "entrance at 0, size unknown" — needs the user's word on
  what the entrance at 0 looks like (skylight above? passage in?) before a rule can be written.
- **Evidence:** `findings/corpus/krk_27-1p.json`, `example/csx_entrances/_out/krk_27_items.png` (plan + profile with every symbol).
- **Next:** the user describes krk_27's entrance; Sopača's verdict; phase 3.

### 2026-10-03 (evening) — rule 5: no size without a witnessed entrance (user + agent) ✅

- **Did:** the user's rule: the entrance sign is a requirement for the entrance size, otherwise a warning and
  no number. Implemented as `entrance_witnessed` (sign, finisher flag, surface leg, operator = yes; highest
  station or first station = no) plus, for pits, a roof test (a profile wall drawn > 0.3 m straight above the
  station = not on the rim; the 0.3 m skips the floor/surface line drawn through the station itself).
- **Result:** 7 measured, 4 declined with a Croatian warning: cepavpic, krk_27, krk_37 (no sign) and Sopača
  (roof 1.1 m above station 5 — which also sits outside the drawn plan; its 13.6 × 17.5 is withdrawn). krk_27
  forced to station 0 is declined too (roof 9.6 m above). Nothing left to vouch.
- **Evidence:** `findings/corpus/*.json` refreshed.
- **Next:** phase 3 — fold into `nacrt_finish.py` with the sign tie-break, the blind-dome guard, the registry
  type and rule 5; `_dimenzije.json`; 4O prefill.
