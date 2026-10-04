# Implementation log: Symbol themes

Brief: [brief.md](brief.md)

---

### 2026-10-04 — viability research (agent) ✅

- **Did:** two read-only digs — the 3N mapping pipeline/kit and cSurvey's clipart, pen and brush code; checked sign-item XML in the SB 1103 fixture.
- **Result:** viable with no cSurvey build: signs reference a hash-keyed glyph pool, and `type="98"` library pens/brushes exist in the format; the importer is hard-coded, so themes apply post-import (KORAK 2). Constraint: SVG colours are ignored — fill = item brush colour (white stays white), outlines = item pen.
- **Evidence:** brief §2.
- **Next:** user answers §3.5; user makes the T0 oracle file.

### 2026-10-04 — user answers, scope set to signs (both) ✅

- **Did:** recorded the answers (brief §3.5); checked whether the `tdxpp:` marker survives import.
- **Result:** signs first, one colour per symbol, B/W also blackens the centerline. Key = cSurvey sign name, because `tdxpp:` is absent in all 10 post-import files under `example/`. The Illustrator set is one artboard, so the recipe is one named group per symbol + an export with layer-name IDs, and T1 splits it.
- **Evidence:** brief §2.4, §3.1, §3.5.
- **Next:** T0 (user) ∥ T1.
