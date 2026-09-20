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

### 2026-09-20 — T4 review: the drawn proposals, and four rule changes (user + agent) ✅

- **Did:** rendered eight cases through `choose_layout()` onto the real A4 sastavnica page (an
  artifact page, one sheet per case with its three alternatives) so the proposals could be judged
  by eye rather than from console text. The user reviewed them and settled four open questions.
- **Result:** all four folded into `nacrt_layout.py`, its tests, the tool README and §3.1/§3.4 above.
  1. **The strip beside the sastavnica is out.** Placing a narrow pair in the 87 mm band right of
     the title block bought a scale step but left half the sheet empty — rejected on sight. The
     free area is now just the full-width band below the block (190 × 224.1 mm) and `_Free` lost
     its L shape, so every drawing starts at y 62.9.
  2. **1:250 is on the ladder** (`scalemode` 3): `SCALES = (100, 200, 250, 300, 500)`. A 40 m
     profile misses 1:200 by 10 mm and now lands on 1:250 (160 mm) instead of 1:300.
  3. **At most one step between the two scales.** Implemented as `MAX_SCALE_RATIO = 2.0` rather
     than adjacency in `SCALES`: a factor of 2 *is* one step of the ladder as it stood when the
     user decided this (1:200 with 1:100, the blessed common case), and it keeps its meaning now
     that 1:250 sits between the rungs, where counting index positions would not. So the old
     `1:300/1:100` proposals are gone; a long profile now pulls the plan to `1:300/1:200`.
  4. **Top-packed and centred stays** — the leftover page collects at the bottom of the sheet.
- **Evidence:** `python -m pytest stages/3N-nacrt/tests -q` → **57 passed** (new tests: 1:250 is
  used, 1:300 only when 1:250 misses, the one-step cap holds across best *and* alternatives,
  nothing is ever placed beside the title block); `pipeline_doctor.py` 0 fail. Review page:
  https://claude.ai/code/artifact/d41299c3-e175-4393-83f4-59652cadf819 (republished with the new
  proposals). Working tree still uncommitted.
- **Next:** unchanged — T1 imports `choose_layout` for the `_preview.*` scale, T3 consumes the
  placements. The chooser's remaining unknown is real bboxes: every case here but SB 1103 is synthetic.

### 2026-09-20 — T4 reviewed and polished after the user's read of the handoff (agent) ✅

- **Did:** "one step" is one rung of the ladder, not a factor of 2 (`MAX_STEP = 1` replaces
  `MAX_SCALE_RATIO`); 1:400 added (`SCALES` six rungs; it has no combo entry in cSurvey's print
  dialog, so it is written as `scalemode="99"` + `scale="400"` — `frmPreview.vb:694-700/1160`
  honour that pair); alternatives are Pareto-pruned per arrangement (`_dominated`) so the menu
  no longer lists pointless downscales. Tests, brief §3.1/§3.4, tool README and the T4 handoff
  amended. T1 prompt gained the **entrance-sign witness**: TopoDroid's entrance symbol survives
  import as `<item type="6" sign="263">` (`cIItemSign.vb:44`), bound to a segment and 1.75 m from
  station `2` on SB 1103 — nearest-station search in design coordinates (plan = `<p x y>`,
  profile = `(d, z)`) is a few lines, and the sign wins over "highest station" when they disagree.
- **Result:** `python -m pytest stages/3N-nacrt/tests -q` green (see the commit for the count);
  SB 1103 menu is now the proposal + one side-by-side alternative; 6 × 8 / 50 × 30 ⇒ `1:300/1:250`.
- **Evidence:** this commit; `python nacrt_layout.py 6 8 58 20` shows the 1:400 custom case.
- **Next:** T1 (prompt in `tasks/T1-nacrt-finish.md`, updated).

### 2026-09-20 — T1: `nacrt_finish.py`, the XML finisher (agent) ✅

- **Did:** built `production/tools/nacrt_finish.py` — the six edits of the T1 prompt on a corrected
  `_lt.csx`/`.csz`, output `<name>_lt_fin.<same ext>` + `<name>_lt_fin.layout.json`, input never
  touched. Entrance from **two independent witnesses** (`witness_highest`, `witness_sign`, each
  with its own tests, combined in `decide_entrance` — the sign wins a disagreement and both go
  into the sidecar); Dislivello at the profile's max-y Borders point relative to that station;
  HorizontalScale bar right of the plan bbox; compass `m="1"` with the `compass3.svg` clipart
  spliced in from a shipped asset; `_preview.*` + `<sharedsettings>` print options with the scale
  from `nacrt_layout.choose_layout()` (T4) and a numbered menu (`--yes` / `--layout N` /
  `--dry-run`); sidecar JSON for T3. CLI shaped like `fix_imported_linetypes.py`, `--sb` via
  `sb_select`, Croatian console text without diacritics.
- **Result:** on the SB 1103 fixture pair, from the raw `_lt`, the tool reproduces the manual
  result: entrance station `2` by **both** witnesses (`origin` says `1`, so the sign + min-z pair is
  what gets it right), a `quotatype="3"` item in the profile bound to `2`, a `quotatype="6"` and a
  `type="15" m="1"` item in the plan, `pageformat="A4"` + `scalemode="1"`/`scale="100"` on both
  designs, `preview.designquality="2"`. Every attribute of our three items equals the oracle's bar
  `text` (cSurvey fills that at paint time) — asserted test-side against
  `…_lt_finished.csx`. The whole-file diff of input vs output is **34 lines**: three items, one
  clipart, and the five lines we edit.
- **Three things the prompt had slightly wrong, now amended in the brief with the date:**
  a Quota carries **no** `<pen>`/`<brush>` (`cItemQuota` HavePen/HaveBrush `False`, so both would
  be dropped on the next save — §2.1); `quotarelativetrigpoint` stays **empty** on the scale bar,
  not the entrance (§3.1 row 2); and the bar's length and the plan's scale are **mutually
  dependent** — the tool picks a provisional scale from the untouched bboxes, sizes the bar, then
  re-chooses for real and warns if the two disagree (§3.1 row 2). Also recorded in §2.1: profile
  design coordinates are `(<p d>, <p z>)`, and a `.csz` clipart's `@data` path needs **backslashes**
  while its zip entry needs forward slashes — a forward-slash `@data` would crash cSurvey on load.
- **Evidence:** `python -m pytest stages/3N-nacrt/tests -q` → **103 passed** (44 of them new:
  the two witnesses separately and their disagreement, tie and `origin` warnings, the entrance
  constant vs. the station name, Dislivello placement + Borders fallback, bar length by scale,
  the clipart spliced in / reused, print options, the `scalemode="99"` custom scale, the no-fit
  `scalemode="0"` fallback, `--layout N`, a `.csz` round-trip that keeps every zip entry,
  line-ending and declaration fidelity, byte-exact idempotence, `--dry-run` writing nothing);
  `python tools/pipeline_doctor.py` → **0 fail · 3 warn** (the same pre-existing historical links).
  Tool row added to [production/tools/README.md](../../production/tools/README.md). Working tree
  left uncommitted, as the prompt asked.
- **Next:** T2 (`csurvey_headless.ps1` + `csurvey_driver.py`) can now run `recalc` → `print` on a
  `_lt_fin` file; T3 composes from the sidecar without recomputing. Two things only a real print
  will settle: whether the bar at `bbox.maxx + 1 m` / `bbox.maxy` reads well on the page (cSurvey
  put SB 1103's at `3.43` where our rule says `2.90`), and whether `PAD_M = 0.5` is enough room for
  station labels — both are single constants at the top of the tool. Also unverified until T2: that
  the generated file opens in cSurvey and the profile prints `-9 m`.

### 2026-09-20 — T1 reviewed: first real print of a finisher-made file (agent) ✅

- **Did:** ran `nacrt_finish.py --yes` on the raw SB 1103 fixture, then the headless probe
  (`recalc` → `print`) on its output — the first time a file authored by our tools went through
  cSurvey end to end.
- **Result:** cSurvey loads the file, recalculates (`pvr=1 nvr=9 es=2`) and prints both designs:
  the plan with the 5 m bar and a plain `N`, the profile with `-9 m` computed by cSurvey at paint
  time. One placement flaw found and fixed: the Dislivello sat inside the floor debris when placed
  0.3 m right of the lowest point; it now goes 0.3 m right of the profile's rightmost point at
  that depth, which is where the user had put it by hand. Style *Survey* prints without area fill,
  as wanted. The bar at `bbox.maxx + 1 m` and `PAD_M = 0.5` read fine on this cave — left as is.
- **Evidence:** this commit (103 tests green, doctor 0 fail); PDFs in the session scratchpad only.
- **Next:** T2 — productionize the driver (`tasks/T2-csurvey-driver.md`).

### 2026-09-20 — T2: the production driver, and the first end-to-end Nacrt (agent) ✅

- **Did:** promoted `findings/csurvey_headless_probe.ps1` into
  `production/tools/csurvey_headless.ps1` (every reflection poke kept verbatim and still asserted
  by name; `info` / `recalc` / `print` / new `dimensions`; `-Design Plan|Profile|Both`;
  `-CSurveyDir` / `-Printer` from `CSURVEY_DIR` / `CSURVEY_PRINTER`; optional `-ScaleMode`
  / `-Scale` / `-Landscape` overrides applied to the in-memory `_preview.*` and never saved back;
  exit codes 0/2/3/4/5/6, one line on stderr each; PDFs named `<cave>_plan.pdf` after the
  `_lt_fin`/`_lt`/`_pp` chain is stripped) and wrote `production/tools/csurvey_driver.py` beside
  it — `run` / `info` / `recalc` / `print_pdfs` / `dimensions` / `finish_and_print`, exit codes
  mapped onto one `DriverError`, the timeout the script cannot enforce on itself, and
  `CSURVEY_*` read from the environment then the workspace `.env` (marker walk, no
  `cave_dossier` import, so it travels into the kit).
- **Result: the chain runs end to end and the Nacrt is real.** On a fresh copy of the SB 1103
  raw `_lt`: `nacrt_finish.py --yes` → `finish_and_print` → two A4-portrait PDFs
  (`SB_1103_golobreska_plan.pdf` 19.8 KB, `..._profile.pdf` 15.9 KB) and
  `SB_1103_golobreska_dimenzije.json`. `dimensions` reads
  `{"l": 10, "pl": 4, "ml": 102, "pvr": 1, "nvr": 9, "drop": 10, "vr": 10, "qmx": 7.53,
  "qmn": -2.06, "es": "2", "caves": 1, "calculated": true}` — exactly the numbers brief §2.2
  predicted, with `es` the station **T1 chose**, so the two halves of KORAK 3 agree.
- **T1's last open acceptance is now closed.** Rendering the printed profile shows the
  Dislivello label `-9 m`, computed by cSurvey at paint time from our `quotavalue="0"` + entrance
  `2`; the plan shows the 0–5 m scale bar with 1 m ticks and a north arrow labelled a plain **`N`**
  (Manual + Geographic, not Auto's `Nm 2024`). Measured ink: plan 101.6 × 58.2 mm against the
  sidecar's predicted 101.2 × 61.0 mm, profile 67.9 × 121.2 mm against 70.9 × 122.2 mm — so T1's
  bbox + `PAD_M = 0.5` model predicts the printed extent to a couple of millimetres, which is what
  T3 will place by.
- **Brief §2.2 amended (dated):** *a therion failure does not fail the calculation.* This machine
  has `therion.path` set and Therion installed but no Survex `cavern` at all; therion's run dies
  with `'cavern' is not recognized` on **stderr** and `Calculate(True)` still returns `Result=True`
  with a correct `<sms>`. Hence the driver's rule: judge by the exit code, never by stderr being
  empty. Two further notes for whoever reads the JSON: `cSpeleometric.VerticalRange` **is**
  `pvr + nvr` once an entrance exists (cSpeleometric.vb:166-225) and is not written to `<sms>`, so
  it ships as `vr` — a free cross-check on `drop`; and `pvr`/`nvr`/`es` exist **only** on the
  per-cave row, never on the whole-complex or per-branch ones, so `caves` ships too and a
  multi-cave survey gets a stderr warning instead of a silently wrong row.
- **Two deliberate deviations from the T2 prompt.** (a) The prompt's parameter list omitted the
  `-ScaleMode`/`-Landscape` overrides that §3.3 asks for; they are in, because
  `cOptionsPreview.ScaleMode`/`Scale`/`PageLandscape` are **public** and the preview form reads
  them in its constructor, so it costs no new reflection surface. (b) The dimensions JSON is named
  `<cave>_dimenzije.json` (matching the PDFs) and not §3.2's `SB_<broj>_dimenzije.json`: the driver
  is handed a file, not a Redni broj. **T5 renames on delivery into the cave leaf** — it is the
  step that knows the number.
- **Also:** `.ps1` is ASCII-only with a UTF-8 BOM (PowerShell 5.1 reads a BOM-less script in the
  ANSI codepage and an em dash in a comment is a parse error — it bit us once), and it sets
  `[Console]::OutputEncoding` to UTF-8 so a Croatian cave name survives the pipe.
  `.env.example` gained `CSURVEY_DIR`/`CSURVEY_PRINTER`; `prod/build_csx_kit.py` `TOOLS` gained all
  five KORAK 3 files; the probe's header says it is superseded.
- **Evidence:** `python -m pytest stages/3N-nacrt/tests -q` → **138 passed** (35 new: exit-code
  mapping per code, a hang killed and named, stderr-on-success is not a failure, JSON parsing incl.
  a stray line, the `.env` fallback, suffix stripping, a silent printer caught, recalc-before-print
  ordering, the sidecar merge — plus one live end-to-end against the installed cSurvey, which runs
  on this machine and skips where cSurvey or the fixture is absent);
  `python tools/pipeline_doctor.py` → **0 fail · 3 warn** (the same pre-existing historical links).
- **Next:** T3 (`compose_a4.py`) — it now has everything it needs: two vector PDFs at a known true
  scale, the placements in millimetres, and `Mjerilo`/lengths/depth for the 4S sastavnica cells,
  all in `<cave>_dimenzije.json`. Then T5 wires KORAK 3 into a launcher. Still unproven: the driver
  on a **second** machine (definition of done), and any cave but SB 1103.

### 2026-09-20 — T3: `cavedossier nacrt` — the Nacrt exists (agent) ✅

- **Did:** built the composition in the 4S package, as the research session decided —
  `sastavnica/compose.py` (pure geometry: ink bbox, placement, the refusals) and
  `sastavnica/nacrt.py` (orchestrator), exposed as **`cavedossier nacrt <broj>`** with the same
  `--offline/--local/--force` flags and the same ours-or-refuse delivery as `sastavnica`, under its
  **own** metadata stamp so a nacrt and a sastavnica can never overwrite each other. Each printed
  page is cropped to its ink and dropped *at its own size*, centred on the rectangle T4 reserved;
  an ink that overruns its rectangle by more than the padding, or that would cross the title block,
  the margin or the other drawing, **refuses with the millimetres** instead of shrinking.
  `prefill` gained one opt-in source (`use_dimensions=True`): the KORAK 3 `<name>_dimenzije.json`
  outranks the zapisnik and SB for the three dimension cells and fills Mjerilo with the scale
  actually printed. `render` gained `MULTILINE = {"mjerilo"}` for the two-line
  `profil 1:200` / `tlocrt 1:100` form.
- **Result: the cSurvey route produces a finished Nacrt.** On SB 1103, from the leaf's own KORAK 3
  files: profile on top, plan below, both at 1:100, the title block reading
  `10 m` / `4 m` / `-9/+1 m` / `1:100` — every one of those measured off the survey being composed,
  not typed. **The acceptance check passes exactly: the 5 m scale bar measures 141.72 pt = 50.00 mm
  on the delivered page**, and the file is 101 KB (< 500 KB). Ink vs. the reserved rectangles:
  profile 67.9 × 121.2 mm in 70.9 × 122.2, plan 101.6 × 58.2 mm in 101.2 × 61.0 — T1's
  bbox + `PAD_M = 0.5` model predicts the printed extent to about 3 mm, which is what makes
  "centre the ink in the rectangle" honest.
- **Decisions taken while building, all in the docs with the date:**
  - **Decision 3 is superseded on the cSurvey route only.** `cavedossier sastavnica` still writes
    the `1:` stub and is byte-for-byte unchanged; the new source is reachable only through
    `run_prefill(use_dimensions=True)`, which only `nacrt` sets. Recorded in the decision table.
  - **The combined Dubina (`-9/+1 m`) is used only while it stays legible** — `MIN_COMBINED_SIZE
    = 7 pt`. Shrink-to-fit floors at 6 pt, so without that bar a four-digit cave would print both
    numbers at the floor where the depth alone would have sat at the authored 10 pt.
  - **The empty-cells note is route-aware**: "popuni u Illustratoru" is an instruction an operator
    on this route cannot follow, so with measured numbers present it reads "dopuni prije predaje".
  - **`pad_m` now travels** in the dimensions JSON (added to `csurvey_driver.LAYOUT_KEYS`), with the
    finisher's own `*.layout.json` and then 0.5 as fallbacks, so a file written before this change
    still composes.
- **Evidence:** `python -m pytest stages/4S-sastavnica/tests stages/3N-nacrt/tests -q` →
  **213 passed** (42 new in `test_compose.py`: ink bbox, centring, no-rescale proven from the
  placed XObjects' sizes, each refusal separately, the trio found by stem so two runs can never
  mix, `pad_m` recovery, the two-line Mjerilo inside its cell rules, the single-value form
  unchanged, the dimensions source outranking the zapisnik, `sastavnica` untouched, delivery +
  stamp + refusal + `--local`, and one live composition of the real SB 1103 outputs that asserts
  the 50 mm bar); `python tools/pipeline_doctor.py` → **0 fail · 3 warn** (the same pre-existing
  historical links). `nacrt` registered in `pipeline.yaml` (4S), `docs/commands.md`, the 4S README
  and ARCHITECTURE's bridge catalog as **B14**.
- **Two things for the user to look at:**
  1. **The plan sits left of centre on the sheet.** Its ink bbox includes the scale bar and the
     north arrow, which T1 places a metre to the right of the drawing, so centring the *ink* puts
     the cave itself off to the left with the furniture balancing it. It reads fine, but it is a
     composition choice nobody has approved — the alternative is to centre on the cave's own bbox
     and let the furniture hang right.
  2. **The KORAK 3 numbering clash.** The rescue launcher is already
     `csurvey_3_oporavi_iz_zipa.bat` and this step is also "KORAK 3". Flagged in the protocol doc;
     T5 cannot ship a launcher until one of them moves. Still a user decision.
- **Next:** T5 — the `csurvey_3_dovrsi_nacrt.bat` launcher (SB prompt → finisher → driver →
  `cavedossier nacrt`), the `PROCITAJ_ME` paragraph, and that renaming. Still unproven: a second
  machine, and any cave but SB 1103.

### 2026-09-20 — user review of the first Nacrt: six fixes (agent) ✅

The user opened `SB_1103_nacrt.pdf` in Illustrator and in a viewer and came back
with six things. All six are done; two of them changed a rule rather than a number.

- **No cell is delivered empty.** An empty cell in Illustrator is not an empty text box — it is
  *no* text box, so filling it in means drawing one first. Every cell no source could fill now
  carries a stub: `?` where somebody could still record the value, `/` where there is nothing to
  record (`addresses.STUB_UNKNOWN` / `STUB_NOT_APPLICABLE`, `STUBS` for the per-cell override).
  Stubs are `source="stub"` and are **not** counted as filled fields on the run. *Open:* which
  cells should read `/` rather than `?` — the tool cannot derive that, so `STUBS` is empty and
  everything is `?` until the society says.
- **Template v1.0 + Microsoft Sans Serif.** The delivered PDF's values opened in Illustrator as
  `Myriad#20Pro#20Regular*` — a missing font, red-underlined, not editable. Two causes, both
  fixed: (a) PyMuPDF writes the face's *display* name into `/BaseFont` while the descendant
  CIDFont carries the PostScript name, so nothing installed answers to it — `render.
  use_postscript_font_name` now rewrites it from the face's own `name` table after subsetting
  (which PDF 32000-1 §9.7.6.1 asks for anyway); (b) Myriad Pro is only on a machine because
  Illustrator put it there. The user supplied `!SUE_sastavnica_v1.0.pdf`, re-authored in
  **Microsoft Sans Serif**; it is installed as the authored template and the blank rebuilt from
  it. Its geometry is identical to the old one — all 59 vector paths match to the hundredth of a
  point — so `addresses.py` is untouched.
  Found on the way: **`build_blank.py` wrote the blank into the workbench, not into the package**,
  where the runtime actually reads it. Since the stage restructure any rebuild silently left the
  real asset stale. Fixed.
- **North arrow closer to the scale bar** — `COMPASS_ABOVE_M` 2.0 → 1.0 m (10 mm at 1:100).
- **Dislivello label closer to the profile** — it now clears only what is drawn **within 0.5 m of
  the floor's depth** (`right_of_depth`, `QUOTA_BAND_M`) instead of the whole design's right edge,
  which on SB 1103 was a ceiling 5 m higher and a metre further out. 4.64 m → 3.64 m.
- **`pvr` must be 0, not 1** — *the one that changed a rule.* cSurvey's `pvr`/`nvr` come from the
  profile design's **whole bounding box** (`cCalculate.Plot.cSpeleometrics.vb:88-96` takes
  `oProfileBounds.Top/Bottom`), so SB 1103's entrance *symbol*, drawn 1.4 m above station `2`,
  made a cave that does not rise above its entrance report `pvr = 1 m`. The user's rule: **only a
  boundary wall or a shot may bound the height or the depth.** `nacrt_finish.vertical_extent`
  computes it that way — min/max over the profile Borders layer and the non-splay stations,
  relative to the entrance — and ships `pvr_m` / `nvr_m` / `vertical_from` in the sidecar, through
  `csurvey_driver.LAYOUT_KEYS`, into the dimensions JSON, where the sastavnica prefers them over
  cSurvey's. SB 1103 now reads `pvr_m 0.18 / nvr_m 8.96` beside cSurvey's `pvr 1 / nvr 9`, and the
  Dubina cell prints **`-9 m`** where it printed `-9/+1 m`. Both numbers travel so the disagreement
  stays auditable.
- **Two-line Mjerilo re-done on font metrics.** The fixed "a third and two thirds of the cell
  height" baselines put the two lines 0.9 pt into each other once the face changed; they are now
  derived from the face's own ascent and descent (`_multiline`, `MULTILINE_PADDING`), and the
  block is re-centred on the size the lines actually reached.
- **Evidence:** the whole chain re-run on SB 1103 into the Drive leaf — finisher → driver →
  `cavedossier nacrt`. The 5 m bar still measures **50.00 mm**; the delivered page's three fonts
  are now all `…+MicrosoftSansSerif`; Mjerili and Ekipa read `?`; Dubina reads `-9 m`.
  `python -m pytest -q` → **556 passed** (13 new: the symbol-above-the-entrance case, a shot
  outside the drawing, the label's band, stubs on every cell and not counted as data, the
  PostScript name, whole-metre depths); `python tools/pipeline_doctor.py` → **0 fail · 3 warn**.
- **Two things still open for the user**, both flagged before and both now sharper:
  1. **Ekipa wants two lines too.** v1.0's own example sets it over two, because Microsoft Sans
     Serif is wider: our fitter puts a three-person team at **6.75 pt** where the drafter chose 8.
     `MULTILINE` is ready for it, but a word-wrap rule is not the same thing as Mjerilo's
     two-value split, so it is not guessed at here.
  2. **The plan still sits left of centre**, because its ink bbox includes the scale bar and the
     arrow and the composition centres the ink.

  **The two open questions, answered by the user the same day and implemented:**
  - **`/` for Broj pločice and Ekipa**, `?` for everything else — "Ekipa might genuinely be empty
    since some caves can be soloed". `addresses.STUBS` carries the two.
  - **Ekipa wraps onto two lines**, like Mjerilo. It takes the second line only when one would
    have to go below 8 pt — the drafter's own size for that cell — so a two-person team still
    sits at 10 pt on one line while a three-person one goes from 6.75 pt on one line to 8.33 pt on
    two. The break is at a comma, the comma stays on the first line, and the halves are chosen by
    measured width so one long name pulls the break. Both lines take one size, the tighter one's.

### 2026-09-20 — second review: the block matches the template, the arrow sits on the bar (agent) ✅

- **The sastavnica was bigger than the template it copies.** Two causes, both re-measured off the
  v1.0 authored file. (a) **Size is per cell, not one ceiling**: the drafter sets row 1 at 10 pt,
  rows 2-4 at 9 and row 5 at 8 — they were all 10 under Myriad, and the renderer had a single
  `MAX_FONT_SIZE = 10` for every cell. `Cell.size` now carries the authored size and shrink-to-fit
  starts there. (b) **`BASELINE_LIFT` 4.6 → 4.3**: v1.0's baselines cluster at 4.11-4.59 below the
  cell's bottom rule (median 4.34), so every value had been sitting a quarter-point high. All
  fifteen cells now reproduce the drafter's own size exactly.
- **Istražili abbreviates a list.** One society stays written out (`SU Estavela`); two or more go
  to the form a caver writes anyway (`SUE, SOV`), because the cell is 55 pt wide and two written
  out do not fit at a readable size. `core.people.society_shorthand` implements the
  `<type-prefix><named-entity-initial>` rule — the prefix table and the parent-acronym skip
  (`SO PDS Velebit` → `SOV`) are adapted from crospeleo-automation's
  `services/organization_alias_generator.py`; logged in
  [PORTING.md](../../../0P-platform/docs/PORTING.md). A name outside the four caving-org patterns
  is never abbreviated, which is also what keeps a single canonical's `, <Grad>` tail from
  counting as a second society.
- **The north arrow now sits on the scale bar.** `textalignment="1"` is **Left**, not Center
  (`cIItemText.vb:50-54`: Center 0, Left 1, Right 2) — cItemCompass.vb:398-404 offsets the glyph
  by half its width only for Center and by nothing for Left, so the arrow was anchored at its own
  left edge and stood 1.19 mm right of the bar's midpoint. cSurvey's own UI writes Left, and this
  tool had copied that from the fixture. Writing `textalignment="0"` centres it: measured offset
  on the re-printed plan is **0.00 mm**.
- **Evidence:** chain re-run on SB 1103 into the Drive leaf. `python -m pytest -q` → **578 passed**
  (14 new: the per-cell authored size against all fifteen v1.0 values, the re-measured baseline,
  the shorthand rule and its non-matches, the one-vs-many Istražili rule, two societies fitting
  the cell once abbreviated); `python tools/pipeline_doctor.py` → **0 fail · 3 warn**.

- **Handoff written:** [tasks/T1-T3-handoff.md](tasks/T1-T3-handoff.md) — what landed, the three
  file contracts, the eight review decisions, the paste-in facts for T5 (it spans **two** kits:
  the finisher and driver ride in `csurvey_alati/`, but `cavedossier nacrt` needs an entry in
  `build_prod.PROD_COMMANDS` and a branch in the bootstrap's `switch`), and what is still
  unproven. Linked from brief §3.3.

### 2026-09-20 — T1–T3 handoff reviewed; T5 unblocked (agent) ✅

- **Did:** re-ran 3N + 4S tests (248 green) and the doctor; checked the delivered
  `SB_1103_nacrt.pdf` (title block v1.0 filled, profile top with `-9 m`, plan beneath with bar +
  `N`, 5 m bar = 50 mm). The review rounds were already swept into the checkpoint commits
  (`5d6118e`, `5fc3cbc`, `c494efb`) — tree clean. Put the two open decisions to the user.
- **Result:** user ruled — finisher is KORAK 3, rescue moves to KORAK 9; plan placement stays.
  T5 prompt written (`tasks/T5-launcher.md`) incl. the `nacrt` prod launcher wiring.
- **Evidence:** this commit.
- **Next:** T5 in a separate session; then the second-machine and second-cave checks before close.

### 2026-09-20 — T5: the KORAK 3 launcher, and the rescue moves to KORAK 9 (agent) ✅

- **Did:** built `prod/csx_templates/csurvey_3_dovrsi_nacrt.bat.template` (the shape of KORAK 2:
  same five tokens, the five-rung `TOOLS` search, Croatian without diacritics) and renamed
  `csurvey_3_oporavi_iz_zipa.bat.template` → `csurvey_9_…` per the user's ruling. Kit **v1.1**.
  Flow: Redni broj → `nacrt_finish.py --sb <broj> --force` (**menu shown** — a double-clicked
  window has someone in front of it) → `csurvey_driver.py finish --sb <broj>` →
  `cavedossier_nacrt_v*.bat <broj>`, found beside the launcher in the shared prod folder. Dragged
  files take the unattended path (`--yes`, the Redni broj read out of the `SB_<broj>_…` folder
  name). `cavedossier nacrt` gained its `PROD_COMMANDS` entry and its `switch ($Command)` branch,
  so `build_prod.py` now publishes a `cavedossier_nacrt_v<X>.bat` beside the other three.
- **`--force` on the finisher, not "skip what exists"** (the T5 prompt guessed the latter):
  `nacrt_finish.py` refuses an existing `_fin` without it and returns 1, which would stop the chain
  on every re-run. KORAK 2 passes `--force` for the same reason and a `_fin` is regenerable.
- **Fail-soft, twice.** No cSurvey ⇒ the driver's one-line `DriverError` is caught and the launcher
  prints the manual recipe (open `_lt_fin`, File › Print, plan and profile, Microsoft Print to PDF,
  don't touch the settings) and exits 0. No published `cavedossier_nacrt_v*.bat` ⇒ it says so and
  stops with the PDFs in the leaf. The closing summary **only promises `SB_<broj>_nacrt.pdf` when
  step 3 actually ran** — caught on the first dry run, where it promised a file that was not there.
- **Docs:** protocol step 5 promoted out of *in validation* into the standing protocol (and its
  mangled `stagesN-nacrt\production\tools\…` paths rewritten), the numbering-clash note dropped,
  the rescue renumbered everywhere (`prod/README.md`, `prod/drive-layout.md`, the protocol, the
  `PROCITAJ_ME` guide, `production/README.md`, `production/tools/README.md`,
  `tdx_zip_to_csx.py`'s docstring, `docs/commands.md`). The guide gained a KORAK 3 section in plain
  Croatian and the rescue moved to the bottom as KORAK 9, "a repair, not a step".
- **Evidence:** new `prod/tests/test_build_csx_kit.py` (9 tests: render/ASCII/tokens, the rescue
  gone under its old name and present under the new, the KORAK 3 chain and both fail-soft strings,
  the five KORAK 3 tools in `TOOLS`, the guide's BOM + diacritics + section order, `PROD_COMMANDS`
  and the bootstrap branch). `python -m pytest -q` → **586 passed**; `python tools/pipeline_doctor.py`
  → **0 fail · 3 warn** (the pre-existing historical links).
  Dry run on SB 1103 from a `cmd` window, staged kit, with the intake junctioned beside it so the
  relative `..\!Za digitalizirat` resolved as it does on the Drive (junction removed afterwards):
  both the typed-`1103` path and the dragged-`_lt` path ran steps 1 and 2 for real — finisher
  re-wrote `_lt_fin` (entrance station 2, both witnesses agreeing, 1:100 vertical), driver
  reprinted both PDFs and `_dimenzije.json` — and step 3 hit the honest
  "no `cavedossier_nacrt_v*.bat` in this folder" branch, because `nacrt` has only just been added
  to `PROD_COMMANDS` and no prod version has been published yet. Run directly,
  `cavedossier nacrt 1103` delivered `SB_1103_nacrt.pdf` (vertical, 1:100/1:100, profile
  58.0 × 116.0 mm, plan 100.8 × 56.9 mm), so the chain itself is whole.
- **Next (not done here, deliberately):** publish — `python prod\build_prod.py --version 1.5
  --publish` (this is what puts `cavedossier_nacrt_v1.5.bat` in the folder and lets KORAK 3 finish
  on an operator machine) then `python prod\build_csx_kit.py --publish`. Then the second-machine
  and second-cave checks, then close the project.

### 2026-09-20 — published; second cave (SB 1256) through the whole chain (agent) ✅

- **Did:** `build_prod.py --version 1.5 --publish` (adds `cavedossier_nacrt_v1.5.bat`) and the csx
  kit (v1.1 → 1.3 after two fixes below); archived the stale `csurvey_3_oporavi_iz_zipa.bat` into
  `_arhiva/` on the Drive. Ran KORAK 3 end to end on **SB 1256 Paralelka** (plan 6 × 13 m,
  profile 14.6 × 15 m): entrance `4` by both witnesses, depth 13.65 m from Borders + stations
  (cSurvey `qmn` −13.49), both designs at 1:200 vertical, `SB_1256_nacrt.pdf` delivered.
- **Result:** two rules moved on the second cave, both now tested: (1) the scale bar was sized
  for the *provisional* 1:100 while the widened plan ended at 1:200 — replaced the one-shot
  provisional pass with a fixed point (`settle_plan_scale`, converges in ≤ 2 rounds); (2) the
  Dislivello 0.3 m right of the drawing collided with station `0`'s label at the profile's end —
  `QUOTA_SHIFT_M` is 1.0 m. `TALL_ASPECT`, `DRASTIC_RATIO`, `PAD_M`, `QUOTA_BAND_M`,
  `COMPASS_ABOVE_M` did not need to move. 267 tests green, doctor 0 fail.
- **Evidence:** this commit; `runs/sastavnica/1256/SB_1256_nacrt.pdf`; Drive folder listing
  (`csurvey_1/2/3/9_*.bat`, `cavedossier_*_v1.5.bat`, `csurvey_alati/KIT_VERSION.txt` = v1.3).
- **Next:** the second-machine check (backlog, deferred by the user); then close.
