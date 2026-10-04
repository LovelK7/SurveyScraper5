# Implementation log: Symbol themes

Brief: [brief.md](brief.md)

---

### 2026-10-04 — viability research (agent) ✅

- **Did:** two read-only digs — the 3N mapping pipeline/kit and cSurvey's clipart, pen and brush code; checked sign-item XML in the SB 1103 fixture.
- **Result:** viable with no cSurvey build: signs reference a hash-keyed glyph pool, and `type="98"` library pens/brushes exist in the format; the importer is hard-coded, so themes apply post-import (KORAK 2). Constraint: SVG colours are ignored — fill = item brush colour (white stays white), outlines = item pen.
- **Evidence:** brief §2.
- **Next:** user answers §3.5; user makes the T0 oracle file.
