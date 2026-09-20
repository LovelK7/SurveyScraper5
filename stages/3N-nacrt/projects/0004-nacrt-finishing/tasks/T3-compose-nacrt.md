# T3 — `cavedossier nacrt <broj>`: compose plan + profile onto the sastavnica page

Paste everything below the line into a fresh Claude Code session opened in
`SurveyScraper5`. Report the result back in the research session (project 0004). T4, T1 and
T2 are committed; this task produces the finished Nacrt PDF for the cSurvey route.

---

You are working in the SurveyScraper5 repo (read `CLAUDE.md` first; sibling repos are
read-only and not needed). This is task **T3** of project 0004. Read, in this order:
`stages/3N-nacrt/projects/0004-nacrt-finishing/brief.md` §3.1 rows 5 and 8b, §3.2, §3.4 and
the T3 entry of §3.3; `tasks/T4-handoff.md` §6 (T3 paragraph); then the 4S stage:
`stages/4S-sastavnica/README.md`, `docs/sastavnica-design.md` (cell geometry, decisions),
`src/cave_dossier/sastavnica/{addresses,render,prefill}.py` and `tests/test_sastavnica.py`
(this task extends that package and follows its conventions: PyMuPDF via the `[sastavnica]`
extra, the resolved Myriad Pro font, the `SB_<broj>_<x>.pdf` delivery into the intake leaf
with the "ours or refuse" collision rule, a `SastavnicaResult`-style sidecar). Use
`/feature-dev` rules: fail-soft, dev/prod portability, docs are part of the work.

**Architecture decision already taken (research session, 2026-09-20):** the composition lives
in the 4S package as `cave_dossier.sastavnica.compose`, exposed as `cavedossier nacrt <broj>`,
because 4S already owns the page, the font, PyMuPDF and the delivery convention. The 3N tools
stay stdlib and only *produce* the inputs. Register the new command wherever
`cmd_sastavnica` is (`stages/0P-platform/src/cave_dossier/cli/__init__.py`), add it to
`pipeline.yaml` (stage 4S `commands`), `docs/commands.md`, and the 4S README.

## Inputs (all in the cave's intake leaf `SB_<broj>_…`, produced by KORAK 3 T1/T2)

- `<name>_plan.pdf`, `<name>_profile.pdf` — one A4 portrait page each, printed by cSurvey at a
  fixed scale, drawing centred on the page, nothing else on the page (no gadgets: T1 turns
  `drawscale/drawcompass/drawbox` off). Vector, from "Microsoft Print to PDF".
- `<name>_dimenzije.json` (T2) — `l, pl, ml, pvr, nvr, drop, vr, qmx, qmn, es, caves,
  calculated` plus, merged from T1's sidecar, `mjerilo, plan_scale, profile_scale, arrangement,
  plan_mm, profile_mm` (`{x, y, width, height}` in **millimetres from the A4 top-left**, already
  clear of the title block and the 10 mm margins, computed for the *padded* bbox).
- `<name>_lt_fin.layout.json` (T1) — same placements plus `plan_bbox_m`, `profile_bbox_m`,
  `pad_m`, `entrance`, `warnings`.
- The SB row and the leaf's OSZ, exactly as `cavedossier sastavnica` already reads them.

`<name>` is whatever the survey file was called (e.g. `Golobreška_nanoekspedicija-1p-lk`); find
the trio by glob `*_plan.pdf` / `*_profile.pdf` / `*_dimenzije.json` in the leaf, newest first,
and refuse with a clear message when any is missing or when their stems disagree.

## What to build

### 1. `compose.py` — the page

`compose_nacrt(sastavnica_pdf_bytes, plan_pdf, profile_pdf, layout, *, gap_mm=10) -> bytes`:

- Open the plan/profile PDFs with PyMuPDF; find each page's **ink bbox** — union of
  `page.get_drawings()` rects and `page.get_text("dict")` block bboxes (station labels are text),
  ignoring nothing (the page is otherwise empty). Convert with `pt = mm × 72 / 25.4`.
- Place the *ink bbox* of each drawing so that its **centre** lands on the centre of the
  corresponding `plan_mm` / `profile_mm` rectangle from the layout, using
  `page.show_pdf_page(target_rect, src_doc, 0, clip=ink_bbox)` on the sastavnica page. **No
  scaling**: `target_rect` has exactly the ink bbox's size in points. (The layout rectangle was
  computed for the padded bbox, so it is a few mm larger than the ink; centring inside it keeps
  T4's gaps honest — T2 measured the ink within ~3 mm of the prediction.) If an ink bbox is
  larger than its layout rectangle by more than `pad_m × 1000 / scale` on a side, or would cross
  the title block, the page margin, or the other drawing, **do not fudge**: raise
  `ComposeError` with the numbers; the CLI reports it and the operator re-runs T1 with another
  layout (`--layout N`).
- Return the composed page bytes; do not touch the title block.

### 2. Sastavnica values from the dimensions JSON

Extend `prefill._resolve_fields` (or a thin sibling used by the `nacrt` command only — your
call, but do not change what `cavedossier sastavnica` prints today for a cave without KORAK 3
files) so that when `<name>_dimenzije.json` exists in the leaf it becomes the **first** source
for: `stvarna_duljina` ← `l`, `tlocrtna_duljina` ← `pl`, `dubina` ← `nvr` rendered as the
template does (`_depth`, negative for a jama; when `pvr > 0` too, render `-<nvr>/+<pvr> m`
only if it fits, else `-<nvr> m`), and `mjerilo` ← `mjerilo` (this supersedes 4S decision 3
"stub `1:`" for the cSurvey route — record that in `docs/sastavnica-design.md`'s decision
table with the date; the Illustrator route keeps the stub). Source label `"nacrt"` in the
sidecar.

**Two-value Mjerilo cell.** `profil/tlocrt: 1:200/1:100` does not fit one line at 6 pt in the
43 pt-wide cell. Render it as two lines inside `Cell("Mjerilo", 248.12, 109.82, 291.43, 129.88)`:
line 1 `profil 1:200`, line 2 `tlocrt 1:100`, each `fit_size`d, baselines at roughly one third
and two thirds of the cell height (keep `BASELINE_LIFT`'s spirit; measure on the rendered PDF
that neither touches the cell rule). The single-value form stays exactly as today. Put the
logic in `render.py` as a `MULTILINE = {"mjerilo"}` special case, tested.

### 3. `cavedossier nacrt <broj> [--offline] [--local] [--force]`

Runs the sastavnica prefill for the cave with the dimensions source enabled, composes the page,
writes the run copy under the same run dir the sastavnica uses, delivers
`SB_<broj>_nacrt.pdf` into the leaf with the same ours-or-refuse rule (stamp the PDF metadata
like `prefill.STAMP`), and prints: the three input files used, the layout (scales, arrangement),
the four values written, ink vs layout sizes in mm, and the delivered path. Exit non-zero with
one readable line on any `ComposeError`/`SastavnicaError`. Fail-soft on Drive: keep the local
copy and say so, as `sastavnica` does.

### 4. Tests (`stages/4S-sastavnica/tests/test_compose.py`)

Build the inputs synthetically with PyMuPDF (an A4 page with a rectangle + a text label at a
known place, for each design), a layout dict with known placements, and a blank sastavnica
rendered by the existing `render`. Assert: the ink lands centred on the layout rect within
0.5 mm; **no scaling** (a 50 mm-wide source rectangle is 50 mm on the composed page — measure
via `get_drawings()`); the title block's text is untouched (compare `get_text()` before/after
inside the block rect); an oversize ink raises `ComposeError`; the two-line Mjerilo renders two
text spans inside the cell; the single-value Mjerilo is byte-identical in text to today's;
dimensions JSON precedence over OSZ/SB for the three length cells; `nacrt` refuses when a file
is missing. Real-data test, skipped unless the KORAK 3 outputs for SB 1103 exist in the leaf
(`LOCAL_DRIVE_ROOT` from `.env`) — compose them and assert the file is written and < 500 KB.

Run `python -m pytest stages/4S-sastavnica/tests stages/3N-nacrt/tests -q` → green;
`python tools/pipeline_doctor.py` → 0 fail (it checks that the new command is in the 4S README
and `docs/commands.md`).

### 5. Docs (part of the work)

- 4S README: the `nacrt` command, what it needs in the leaf, the two-line Mjerilo.
- `docs/sastavnica-design.md`: decision table entry (supersession of decision 3 for the cSurvey
  route), the multiline cell rule.
- `docs/commands.md`: the new command.
- 3N `production/tdx-processing-protocol.md`: a short KORAK 3 paragraph (finish → driver →
  `cavedossier nacrt`) marked *in validation*; and a dated entry in
  `stages/3N-nacrt/projects/0004-nacrt-finishing/log.md` (Did / Result / Evidence / Next).
- Do **not** touch `prod/build_prod.py` launchers (T5).

Do **not** commit. Finish by printing: the `cavedossier nacrt 1103` console output (if the
leaf has the KORAK 3 files — the research session can produce them if not), the pytest summary
line, and the doctor's last line.
