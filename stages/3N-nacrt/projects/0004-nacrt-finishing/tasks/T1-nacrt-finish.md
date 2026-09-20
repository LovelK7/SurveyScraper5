# T1 — `nacrt_finish.py`: the XML finisher for a corrected `_lt` survey

Paste everything below the line into a fresh Claude Code session opened in
`SurveyScraper5`. Report the result back in the research session (project 0004). T4 is done
and committed; this is the task that consumes it.

---

You are working in the SurveyScraper5 repo (read `CLAUDE.md` first; the `../cSurvey` and
`../crospeleo-automation` sibling repos are **read-only** — you may grep `../cSurvey/cSurveyPC`
to confirm an attribute name, never edit there). This is task **T1** of project 0004. Read, in
this order: `stages/3N-nacrt/projects/0004-nacrt-finishing/brief.md` (§2.1, §3.1 rows 2–4b and 6,
§3.2, §3.4), `tasks/T4-handoff.md` §2 and §6 (the chooser you import), and skim
`stages/3N-nacrt/production/tools/fix_imported_linetypes.py` (the tool whose shape you copy:
argparse, `--sb` via `sb_select`, `.csz`/`.csx` container handling in `load_root`/`write_root`,
in-place item rewriting) and `inspect_survey.py` `inspect_design` (how a design's bbox is read
from `<points data>`). Pure Python + stdlib, no cSurvey, no PowerShell, no PDF in this task.

## What to build

`stages/3N-nacrt/production/tools/nacrt_finish.py` — takes a corrected `<name>_lt.csx|csz`
(after KORAK 2) and writes `<name>_lt_fin.<same ext>` plus a sidecar
`<name>_lt_fin.layout.json`. Never modifies the input. Every other byte of the survey is
preserved (for `.csz` re-zip every entry like `write_root` does; keep the XML declaration and
attribute order stable so a diff stays readable).

CLI: files or an intake folder with `--sb <broj>` (exactly like the sibling tools; reuse
`sb_select`), `--dry-run` (report only), `--yes` (accept the proposed layout without the menu),
`--layout N` (pick alternative N non-interactively). Console text in Croatian without diacritics
(it runs in a cp852 `.bat` window — see `csurvey_0_PROCITAJ_ME.txt.template` for tone).

### The six edits, in this order

1. **Entrance.** Among stations in `<calculate><ts><t n="…">` whose name has no `(` (splays are
   `0(12)`), pick the one with **minimum** `z` in `<p x y z>` (Z is positive downward, so min z =
   highest). Set `entrance="2"` on its `<trigpoints><trigpoint name="…">` (remove `entrance` from
   any other trigpoint). **Warn** (do not stop) when that station differs from
   `<properties origin="…">` or when another non-splay station is within 0.5 m of it in z.
   Fixture oracle: SB 1103 ⇒ station `2`.
2. **Dislivello quota** in `<profile>`: find the lowest floor point = the maximum `y` over all
   `<points data>` of items in the profile's layer `type="5"` (Borders) — fall back to all
   profile layers if Borders is empty. Append to the profile's layer `type="6"` (Signs)
   `<items>` an item exactly shaped like the one in brief §2.1 / T4-handoff:
   `layer="6" cave="<cave>" branch="<branch>" type="10" category="82" text="" quotaalign="2"
   quotatextposition="1" quotaformat="" quotatype="3" quotavalue="0" quotavaluetype="0"
   quotarelativetrigpoint="<entrance>"`, children `<pen type="10"/>`, `<brush type="7"/>`,
   `<font type="0"/>`, `<points data="X Y X+0.35 Y+0.35 "/>` where (X, Y) is that lowest point
   shifted 0.3 m right. `cave`/`branch` = the values the Borders items carry. Skip (warn) if a
   `quotatype="3"` item already exists.
3. **Horizontal scale** in `<plan>` Signs layer: a `quotatype="6"` item (same base attributes as
   above but `quotatype="6" quotatickfrequency="1.00" quotaticklabelfrequency="5.00"
   quotaticksize="0.30"`, points from `(bbox.maxx + 1.0, bbox.maxy)` to `(bbox.maxx + 1.0 + L,
   bbox.maxy)`), where the plan bbox is computed as in `inspect_design` over all plan items, and
   `L` = 5 m when the plan's chosen scale is 1:100, else 10 m (ticks 2 / labels 10 for 10 m).
   Skip if one exists.
4. **Compass** in `<plan>` Signs layer: `<item layer="6" cave=… branch=… type="15" category="83"
   da="1" data="<clipart id>" dataformat="2" m="1" textalignment="1">` with `<pen type="10"/>`,
   `<brush type="7"/>`, `<font type="1"/>`, one point at `(scale_start_x + L/2, bbox.maxy - 2.0)`
   (above the scale bar). The clipart: look for `<signs><cliparts><clipart … name="compass3.svg">`
   in the input; if absent, copy that `<clipart>` element (including its inline base64 `data`
   for `.csx`; for `.csz` also the `_data/cliparts/<id>.svg` zip entry) from the finished fixture
   `stages/3N-nacrt/example/finishing/SB_1103_golobreska_lt_finished.csx` — ship that element
   as a small `nacrt_finish_compass.xml` asset next to the tool rather than reading the fixture
   at runtime. Skip if a `type="15"` item exists.
5. **Layout + print options.** Recompute both design bboxes **after** steps 2–4 (the scale bar and
   compass widen the plan; the printed page includes them), pad each by 0.5 m on every side for
   station labels, and call
   `best, alternatives, reason = nacrt_layout.choose_layout(plan_bbox, profile_bbox)` — argument
   order `(plan, profile)`. Show the numbered menu (`layout.note` per line, Enter = proposal)
   unless `--yes`/`--layout`. Then write on `<options><_preview.plan>` and `<_preview.profile>`:
   `pageformat="A4"`, remove/omit `pagelandscape`, `pagemargins="10;10;10;10"`,
   `scalemode` = `best.scalemodes[1]` / `[0]`, `scale` = the denominator, `designstyle="0"`,
   `drawsplay="0"`, `drawscale="0"`, `drawcompass="0"`, `drawbox="0"`,
   `printername="Microsoft Print to PDF"`. If `best is None`: `scalemode="0" scale="0"` on both
   and print `reason` as a warning. On `<sharedsettings><values …>` set
   `preview.designquality="2"` and `preview.manualrefresh="0"` (add the attributes if missing).
6. **Sidecar JSON** `<name>_lt_fin.layout.json`: `{ "entrance": "2", "warnings": [...],
   "plan_bbox_m": [...], "profile_bbox_m": [...], "profile_scale": 100, "plan_scale": 100,
   "mjerilo": "1:100", "arrangement": "vertical", "profile_mm": {x,y,width,height},
   "plan_mm": {...}, "chosen": "proposal" | "alternative N" | "fit-to-page" }` — T3 composes
   from this without recomputing.

`--dry-run` prints everything the run would do (entrance + warnings, the two bboxes, the
layout menu, the attributes that would change) and writes nothing.

### Tests

`stages/3N-nacrt/tests/test_nacrt_finish.py` (pytest; import trick as in
`test_nacrt_layout.py`). The real fixture pair is gitignored, so tests that need it must
`pytest.skip` when `stages/3N-nacrt/example/finishing/SB_1103_golobreska_lt_raw.csx` is absent,
and you also build a **tiny synthetic `.csx`** in the test (a few segments, `<calculate><ts>`
with 3 stations, one Borders item per design, empty Signs layers, `_preview.*` elements,
`sharedsettings`) so the logic is tested on every machine. Cover: entrance = min z non-splay,
origin-mismatch warning, tie warning, Dislivello placed at the lowest Borders point relative to
the entrance, scale-bar length by scale, compass clipart inserted when missing, print options +
sharedsettings written, `best is None` fallback, `.csz` round-trip keeps every zip entry,
idempotence (running on the output changes nothing and warns "already"), `--dry-run` writes
nothing. On the real fixture: run on `…_lt_raw.csx` and compare with `…_lt_finished.csx` —
same entrance station, a `quotatype="3"` item in the profile bound to `2`, a `quotatype="6"`
and a `type="15" m="1"` item in the plan, `_preview.*` with `pageformat="A4"` and
`scalemode="1"` on both (SB 1103 ⇒ 1:100 / 1:100 vertical per T4).

Run `python -m pytest stages/3N-nacrt/tests -q` → green; `python tools/pipeline_doctor.py` → 0 fail.

### Docs (part of the work)

- Row for `nacrt_finish.py` in the *Nacrt finishing (KORAK 3)* table of
  `stages/3N-nacrt/production/tools/README.md`, and one sentence in the tool's module docstring
  that the profile PDF's `-9 m` label is computed by cSurvey at paint time, not by us.
- Append a dated entry to `stages/3N-nacrt/projects/0004-nacrt-finishing/log.md` (Did / Result /
  Evidence / Next) and, if a brief §3.1 row turned out wrong in practice, amend the row in place
  with the date.

Do **not** commit. Finish by printing: the `--dry-run` output on the raw SB 1103 fixture (if
present), the pytest summary line, and any brief row you amended.
