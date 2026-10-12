# ss5 baseline — the new reference survey through the real chain (2026-10-10)

- **Input:** `example/ss5_mapiranje/krkuž_uskrs-2p.csx` (TopoDroid 6.4.57 export, drawn by the user as the tuning
  reference: 38 point, 17 line and 7 area types, 136 items) → copied here as `ss5_tdx_raw.csx`.
- The user's `krkuž_uskrs-2p_prep.csx` is a direct cSurvey import of the **raw** export (no KORAK 1: `danger`/`plus`/
  `plus-minus` are not labels, and no mapping renames). It was not used.
- **Chain:** `preprocess_tdx_csx.py` → `ss5_prep.csx` (48 transformed, warnings: ice area ×2, user line) →
  `csurvey_driver.recalc` with `runs/theme-round/csurvey-nodtd` → `ss5_lt.csx` → `fix_imported_linetypes.py --no-theme`
  → `ss5_izvorno.csx` → `theme_apply.py apply --theme boja|crno-bijelo --pre ss5_prep.csx` → `ss5_<tema>.csx` →
  headless print plan + profile → `pdf_<tema>/`, `ss5_plan_usporedba.png`, `ss5_profile_usporedba.png`.
- **Name recovery:** every item matched (1 exact, 67 + 59 recovered). Themed: 38 signs (6 labels → glyphs), 33 lines,
  15 areas; library 13 pens, 7 brushes.
- **Notes from theme_apply:** KORAK 2's wall merge joins `wall` + `wall:presumed` into one outline — plan themed as
  wall (3:2 majority), profile left unthemed (4:4 tie); `vegetable-debris` glyph has 117 stroke-only paths that do not
  print with the pen off.
- **Odd:** KORAK 1 crashes on the ⚠ warning when stdout is a cp1252 pipe (Git Bash); fine in a cmd window. Ran with
  `PYTHONIOENCODING=utf-8`.
- **Verdict:** awaiting the user's feedback.
