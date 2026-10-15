# Round r14 — the hidden cave area (2026-10-12)

Code round, not a theme.json round: [findings/walls-and-clipping.md §4](../../findings/walls-and-clipping.md#4-the-cave-area-from-every-wall-kind-and-the-pit-rings)
built in KORAK 2. No theme was changed.

- **Input:** r13's `ss5_izvorno.csx` (imported) + `ss5_prep.csx` beside it → KORAK 2 `--no-theme` → three plan +
  profile prints: the old KORAK 2 output (`ss5_izvorno_k2.csx` from r13), the new one, the new one with
  `ClipBorder` = 2 (no clipping).
- **KORAK 2 said:** plan – outline of 8 strokes, 3 of them special walls; 2 special walls not next to the outline
  (an island round a loose wall stroke) left out; 1 abyss-entrance ring (open, closed with a chord). Profile – 12
  strokes, 4 special.

| Image | What |
|---|---|
| [ss5_plan_podrucje.png](ss5_plan_podrucje.png), [ss5_profile_podrucje.png](ss5_profile_podrucje.png) | grey = the visible wall outline's area, green = what the hidden outline adds (plan +8 %: the passage walled only by wall:blocks/debris; profile +2 %). Black = walls, blue = Borders-layer lines |
| [ss5_plan_razlika.png](ss5_plan_razlika.png), [ss5_profile_razlika.png](ss5_profile_razlika.png) | the cSurvey prints: green = printed now, cut before; red = still cut (vs. no clipping); magenta = lost vs. before (0 in plan; 23 px of area-tile noise in profile) |

**Seen:** nothing of the hidden items prints (pen None); the ceiling-step's start at station 2 now prints. Still red:
slope/overhang tails drawn past the walls – the trimming that clipping is kept for. On ss5 the plan ring lies inside
the walls already, so the ring adds nothing there; the ring case is covered by tests.

## Feedback → change

| # | Feedback (user) | Key | Change | Seen in |
|---|---|---|---|---|
| 1 | implement the §4 clipping; the abyss-entrance keeps what it contains from being cut | – | KORAK 2 `cave_area` (default on): hidden, locked cave-border items (pen None, merge Add, name `obris spilje (KORAK 2)`) – one outline of every wall kind where special walls exist, one per `abyss-entrance` ring; replaced on a re-run; never themed | ss5_plan_razlika ✅ |
