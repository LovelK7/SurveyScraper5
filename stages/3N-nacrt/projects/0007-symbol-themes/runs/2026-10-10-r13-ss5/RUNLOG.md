# Round r13 — the user's first feedback on the ss5 survey (2026-10-10)

- **Input:** `example/ss5_mapiranje/krkuž_uskrs-2p_v2.csx` (v2, with user lines and areas). The user's own
  `_v2_prep.csx` is again a direct import of the raw export, so it was not used. Drawing re-split (11:16 export:
  new wall:blocks, wall:debris and the blocks sign; 13 other signs changed only by the relative scale noise 1.057 → 1.060).
- **Chain:** the scratchpad `ss5_round.py` = KORAK 1 → headless import (cached under
  `<workspace>/runs/theme-round/survey-<hash>`) → KORAK 2 `--no-theme` → theme_apply boja / crno-bijelo → plan +
  profile prints → `ss5_plan_usporedba.png`, `ss5_profile_usporedba.png`. Experiment `ss5_boja-noclip.csx`: the
  boja file with `clippingtype="1"` on all 23 Borders-layer lines.
- **Code:** area `outline` field (`themes._outline`, `theme_apply._theme_area_outline`; test
  `test_area_outline_off_and_coloured_with_undo`). `pytest stages/3N-nacrt` 361 → 362 passed.

| # | Feedback (user) | Key | Change | Seen in |
|---|---|---|---|---|
| 1 | wall:blocks, wall:debris ignored (plan) | – | **cause:** cSurvey clips every Borders-layer line to the cave region (`cClipping.vb:300`), and the region is only the merged wall outline (type 4); KORAK 1 maps wall:blocks/debris/ice → border, so they are outside it and the units are cut away. With clipping off they print (`noclip` column). **Decision needed** | ss5_plan_usporedba |
| 2 | border at the entrance missing; use user? | – | same clipping; `user` is on the same layer, so it would not help. Prints with clipping off | ss5_plan_usporedba, profile |
| 3 | wall:ice thicker, like wall (plan + profile) | wall:ice | width – → 3.5 | ✅ |
| 4 | wall:underlying dashed like presumed, fewer gaps | wall:underlying | new: width 3.5, custom dash [14, 2.5] | ✅ |
| 5 | ice/snow: blue baseline → then: no area outline except water | all areas | `outline: false`; water `outline: {color: #24A9D1}` | ✅ |
| 6 | sink/spring blue, not directed; profile: turn 90° CCW | sink, spring | stock glyphs normalised into `signs/` (they point right; ours up), `rotate: -90`, `outline_pen: true`, `#24A9D1`. The importer keeps the orientation (781 has angle =); sinks are drawn at 0° | ✅ |
| 7 | water-drip larger | water-drip | size – → 1.5 | ✅ |
| 8 | air-draught larger | air-draught | size – → 1.5 | ✅ |
| 9 | survey shots: more dashes, unlike rope | centerline | `PlotPenStyle` 1 (Dash) → 2 (Dot) | ✅ (thin) |
| 10 | stalagmite area coloured like the artwork | stalagmite | read as the black baseline (pen 10) round it: `outline: false`; tile colour already the artwork's #C28935 | ⚠ confirm |
| 11 | ice/snow and water in the profile as in plan | ice, water | same entries; outline rule above | ✅ |

- **Odd:** the left edge of the plan print cuts the long label and the outside border (the headless print's page
  placement; KORAK 3 sets the real layout). The redrawn area tiles blocks/debris are #C9C9C8 in the drawing, the
  theme still uses #616262 (not asked).

**Follow-up (user's choice, same day):** option 1 → KORAK 2 rule `borders_unclipped` (default on): every imported
Borders-layer line gets `clippingtype="1"` unless one is set (23 on ss5; test
`test_border_lines_are_not_clipped_unless_the_operator_chose`). Option 3 (a hidden all-walls outline used only for
the cave area, every wall kind a line with its own look; fixes wall:presumed too) accepted in principle, not built.
Long labels: a `&#xA;` in `text=` prints as a line break, centred (`pdf_boja-wrap/label_crop.png`); automatic wrap
in KORAK 2 proposed.
