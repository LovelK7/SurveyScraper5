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
