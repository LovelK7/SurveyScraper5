# Implementation log: Nacrt finishing — automate the post-import manual steps and the PDF export

Brief: [brief.md](brief.md)

---

### 2026-09-20 — research: what the manual steps write, and can the exe be driven headless (agent) ✅

- **Did:** diffed the user's raw vs finished SB 1103 `_lt` file (autosave backup) to see what each
  manual step writes; three read-only digs into `cSurvey/` (compass/scale, quota/entrance/speleometrics,
  print options/centering/headless print); probed the installed `C:\csurvey64\cSurveyPC.exe` from
  Windows PowerShell 5.1 via reflection.
- **Result:** every manual step except sketch correction maps to plain XML attributes (table in
  brief §2.1). Headless `Load` → `Calculate` (Friend, reflection) → `SaveTo` works; **`frmPreview` can
  be constructed unseen and its `PrintDocument` printed to "Microsoft Print to PDF" as a file with no
  dialog** — plan and profile PDFs identical in look to the user's manual export. Recalc after
  setting the entrance yields `l=10 pl=4 pvr=1 nvr=9 es=2` — the dimensions the user records by hand.
  Confirmed limits: centering is hard-coded (only asymmetric margins move it), one design per sheet
  (compose downstream with PyMuPDF). Render quality is a `sharedsettings` value, not a preview attribute.
- **Evidence:** [findings/csurvey_headless_probe.ps1](findings/csurvey_headless_probe.ps1) (validated:
  `info`, `recalc`, `print` on the finished fixture); fixture pair in
  `example/finishing/SB_1103_golobreska_lt_{raw,finished}.csx` (gitignored); PDFs in the session scratchpad only.
- **Next:** user picks from the delegable tasks T1–T5 (brief §3.3); suggested order T4 → T1 → T2 → T3 → T5.

### 2026-09-20 — user feedback folded into the brief (user + agent) ✅

- **Did:** print Style is *Survey* (`designstyle="0"`), not Combined; plan and profile get
  **independent scales** (profile 1:200 with plan 1:100 is the common case); the composed page
  is the **4S sastavnica** A4 portrait (title block upper-left), profile primary on top, plan
  beneath or side by side; 4S to be extended with the speleometrics and a two-value `Mjerilo`
  (`profil/tlocrt: 1:200/1:100`); semi-automatic operator confirmation is acceptable. New §3.4;
  T3/T4 rewritten accordingly; task split T1–T5 confirmed.
- **Result:** brief is the agreed spec; no code yet.
- **Next:** T4 (`choose_layout()` + tests) in a separate session.

### 2026-09-20 — T4: `choose_layout()` — scale per design + page arrangement (agent) ✅

- **Did:** built `production/tools/nacrt_layout.py` (stdlib only, no repo imports, like its
  siblings): `BBox` (metres) → `Layout` with a scale per design out of 1:100 / 1:200 / 1:300 / 1:500
  (`SCALEMODE` = the `_preview.*` combo indices 1/2/4/5), an arrangement, two `Placement`s in mm on
  the A4 page, the `Mjerilo` string and a one-line Croatian note, plus up to three ranked
  alternatives for the operator menu — and a tiny CLI
  (`python nacrt_layout.py <plan_w> <plan_h> <profile_w> <profile_h>`) that prints them numbered.
  `TITLE_BLOCK_MM` is derived from the 4S cell table (outermost cells 39.85, 49.58 → 291.43, 149.94 pt)
  = **x 14.06, y 17.49, 88.75 × 35.40 mm**. The free area is the L around it: the full-width band
  below the block, plus the band to its right, which a narrow pair may use up to the top margin (a
  "raised" placement is ranked behind a natural one). Ranking, in the user's order: largest scales
  first, plan promoted when the profile's larger dimension > 1.6 × the plan's, profile primary,
  vertical unless both designs are tall and narrow, then least wasted area. 35 test cases in
  `tests/test_nacrt_layout.py` (15 named + a 20-case invariant sweep over a grid of bboxes:
  no overlaps, every placement inside the margins and clear of the title block, alternatives
  distinct, `Mjerilo` well-formed).
- **Result:** `python -m pytest stages/3N-nacrt/tests -q` → **55 passed**; `pipeline_doctor.py` 0 fail.
  SB 1103 (plan 4 × 9 m, profile 5 × 10 m) → both 1:100, vertical, `1:100`, profile 50 × 100 mm at
  (80.0, 62.9), plan 40 × 90 mm at (85.0, 172.9). A long profile 36 × 12 m with a 6 × 8 m plan →
  `profil/tlocrt: 1:200/1:100`, the common case the user described.
  **One correction to the brief's worked example:** a 40 m profile at 1:200 is 200 mm wide and the
  page offers only 210 − 2 × 10 = **190 mm**, so 40 × 12 m lands on **1:300**, not 1:200; 36 × 12 m is
  the largest profile that still makes 1:200. Both cases are tested, the 40 m one under its own name.
- **Evidence:** `production/tools/nacrt_layout.py`, `tests/test_nacrt_layout.py`, the tool table row
  in [production/tools/README.md](../../production/tools/README.md). Working tree left uncommitted
  for review.
- **Next:** T1 (`nacrt_finish.py`) imports `choose_layout` to fill `_preview.plan/profile`
  `scalemode`; T3 (`compose_a4.py`) consumes the `Placement`s and the `Mjerilo` string. Worth
  revisiting once real bboxes arrive: whether the "raised" band beside the title block is a
  placement an operator actually accepts, and whether 1.3 is the right tall-and-narrow threshold
  (SB 1103 is 2.0 / 2.25 and still wants vertical, so the tie goes to vertical by design).
