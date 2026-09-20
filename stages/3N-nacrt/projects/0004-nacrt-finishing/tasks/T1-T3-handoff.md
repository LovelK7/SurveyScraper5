# T1–T3 — handoff to the orchestrating session

**Status: the cSurvey route delivers a finished Nacrt. T4, T1, T2 and T3 are built and green;
T5 is the only task left, and it is blocked on one user decision.**

Written 2026-09-20 by the session that ran T1, T2, T3 and the user's two review rounds.
Companion to [T4-handoff.md](T4-handoff.md), which covers the chooser. Brief:
[../brief.md](../brief.md). Every claim here is in [../log.md](../log.md) with its evidence.

This file exists so the next session can write the T5 prompt, and answer "what does KORAK 3
actually do now", without re-reading four modules and six log entries.

## Contents

- [1. What landed](#1-what-landed)
- [2. The pipeline, end to end](#2-the-pipeline-end-to-end)
- [3. The contracts between the three steps](#3-the-contracts-between-the-three-steps)
- [4. What the user decided during the reviews](#4-what-the-user-decided-during-the-reviews)
- [5. What the orchestrator has to do](#5-what-the-orchestrator-has-to-do)
- [6. Paste-in facts for the T5 prompt](#6-paste-in-facts-for-the-t5-prompt)
- [7. Open, and deliberately not decided here](#7-open-and-deliberately-not-decided-here)
- [8. What is still unproven](#8-what-is-still-unproven)

## 1. What landed

| File | State | What |
|---|---|---|
| `stages/3N-nacrt/production/tools/nacrt_finish.py` | **new** (T1) | the XML finisher: entrance, Dislivello, scale bar, compass, print options, sidecar |
| `stages/3N-nacrt/production/tools/nacrt_finish_compass.xml` | **new** (T1) | the `compass3.svg` clipart element, spliced in when a survey lacks it |
| `stages/3N-nacrt/production/tools/csurvey_headless.ps1` | **new** (T2) | drives the installed cSurvey by reflection: `info` / `recalc` / `print` / `dimensions` |
| `stages/3N-nacrt/production/tools/csurvey_driver.py` | **new** (T2) | the Python face: timeout, exit-code mapping, `finish_and_print()` |
| `stages/4S-sastavnica/src/cave_dossier/sastavnica/compose.py` | **new** (T3) | pure geometry: ink bbox, placement, the refusals |
| `stages/4S-sastavnica/src/cave_dossier/sastavnica/nacrt.py` | **new** (T3) | orchestrator for `cavedossier nacrt` |
| `stages/3N-nacrt/tests/test_nacrt_finish.py` · `test_csurvey_driver.py` · `stages/4S-sastavnica/tests/test_compose.py` | **new** | 156 tests across the three tasks |
| `sastavnica/{addresses,render,prefill,fonts,models}.py` | modified | per-cell authored size, two-line cells, stubs, the dimensions source, the font fix |
| `sastavnica/templates/sastavnica_blank_v1.pdf` + `template-workbench/templates/!SUE_sastavnica.pdf` | modified | **template v1.0**, re-authored by the user in Microsoft Sans Serif |
| `cli/__init__.py` · `pipeline.yaml` · `ARCHITECTURE.md` · `docs/commands.md` | modified | `cavedossier nacrt` registered; new bridge **B14** |
| `prod/build_csx_kit.py` | modified | `TOOLS` gained all five KORAK 3 files |
| `.env.example` | modified | `CSURVEY_DIR`, `CSURVEY_PRINTER` |

Verification, both re-runnable from the repo root:

```powershell
python -m pytest -q                  # 578 passed
python tools/pipeline_doctor.py      # 0 fail - 3 warn (all pre-existing, historical links)
```

**T1, T2 and T3 are committed** (`4c43ba8`, `76f36a5`, and T3 inside the auto-commit checkpoints).
The **two review rounds are not** — `git status` lists twelve modified paths. The first thing to
decide is whether to commit them deliberately with a real message.

## 2. The pipeline, end to end

```
<survey>_pp_lt.csx          the operator corrects the sketch in cSurvey and saves
   │
   │  python nacrt_finish.py <file>_lt.csx  [--yes | --layout N | --dry-run]
   ▼
<survey>_lt_fin.csx  +  <survey>_lt_fin.layout.json
   │
   │  python csurvey_driver.py finish <file>_lt_fin.csx -o <cave leaf>
   │     (recalc -> print plan+profile -> dimensions, all headless)
   ▼
<name>_plan.pdf  +  <name>_profile.pdf  +  <name>_dimenzije.json
   │
   │  cavedossier nacrt <broj>
   ▼
SB_<padded>_nacrt.pdf        in the cave's intake leaf
```

Validated end to end on SB 1103, three times over two review rounds. The acceptance check from
brief §3.3 holds exactly: **a 5 m scale bar measures 50.00 mm** on the delivered page at 1:100.

Two halves, deliberately kept apart: the 3N tools are **stdlib only** and travel into the operator
kit; the composition lives in the **4S package** because 4S already owns the page, the font,
PyMuPDF and the delivery convention. They meet only through files.

## 3. The contracts between the three steps

### `<name>_lt_fin.layout.json` (T1 → T2)

`entrance`, `entrance_witnesses`, `warnings`, `plan_bbox_m` / `profile_bbox_m`,
`plan_size_m` / `profile_size_m` (padded), `plan_scale` / `profile_scale`, `mjerilo`,
`arrangement`, `plan_mm` / `profile_mm` (`{x, y, width, height}`, millimetres from the A4
top-left), `pad_m`, `pvr_m` / `nvr_m` / `vertical_from`, `chosen`, plus `dislivello`,
`scale_bar` and `compass` detail blocks.

### `<name>_dimenzije.json` (T2 → T3, and to 4S/5D)

cSurvey's per-cave speleometrics — `l`, `pl`, `ml`, `pvr`, `nvr`, `drop`, `vr`, `qmx`, `qmn`,
`es`, `caves`, `calculated` — **merged with** `csurvey_driver.LAYOUT_KEYS` out of the sidecar
above: `mjerilo`, `plan_scale`, `profile_scale`, `arrangement`, `plan_mm`, `profile_mm`, `pad_m`,
`pvr_m`, `nvr_m`, `vertical_from`. One file, so 4S and the compositor never read two.

**`pvr_m` / `nvr_m` are the finisher's own, and they win.** cSurvey's `pvr`/`nvr` come from the
profile design's *whole* bounding box (`cCalculate.Plot.cSpeleometrics.vb:88-96`), so a symbol
drawn above the entrance counts as cave — SB 1103's entrance sign made a cave that does not rise
above its entrance report `pvr = 1 m`. Both travel so the disagreement stays auditable.

### Exit codes

`csurvey_headless.ps1`: 0 ok · 2 usage · 3 reflection · 4 load · 5 calculate · 6 print, one line
on stderr each. **A clean run may still write to stderr** (therion's `cavern` missing) — judge by
the exit code. `csurvey_driver.py` maps all of them onto one `DriverError`.
`cavedossier nacrt`: the house convention, 99 on `ComposeError` / `SastavnicaError`.

## 4. What the user decided during the reviews

Everything here is implemented, tested and in the docs with the date. Do not re-litigate.

| # | Decision | Where it lives |
|---|---|---|
| 1 | **Height and depth are bounded by the boundary wall or a shot — never by a symbol** | `nacrt_finish.vertical_extent`; brief §2.2 amended |
| 2 | **No cell is delivered empty**: `?` for unknown, `/` for Broj pločice and Ekipa (no plaque; surveyed solo) | `addresses.STUB_UNKNOWN` / `STUBS` |
| 3 | **Template v1.0 in Microsoft Sans Serif** — Myriad Pro could not be resolved by Illustrator | `fonts.py`, `render.use_postscript_font_name` |
| 4 | **Size is per cell** (10 / 9 / 8 by row), baseline lift 4.3 — both re-measured off v1.0 | `Cell.size`, `addresses.BASELINE_LIFT` |
| 5 | **Ekipa wraps onto two lines** rather than being set below 8 pt; Mjerilo wraps in its two-scale form | `render.MULTILINE` |
| 6 | **Istražili: one society written out, two or more abbreviated** (`SUE, SOV`) | `core.people.society_shorthand` |
| 7 | North arrow **centred on the scale bar** (`textalignment="0"` is Center, not 1) | `nacrt_finish.add_compass` |
| 8 | `designstyle="0"` (*Survey*), splays off, page gadgets off, A4 portrait | `nacrt_finish.PREVIEW_COMMON` |

## 5. What the orchestrator has to do

1. **Review and commit the twelve modified paths** from the two review rounds — one commit, repo
   style, e.g. `3N/0004: review fixes — template v1.0, stubs, wall+shot extents, centred compass`.
2. **Get the user's answer on the KORAK 3 numbering clash** ([§7](#7-open-and-deliberately-not-decided-here)).
   T5 cannot ship a launcher until one of the two KORAK 3s moves.
3. **Write the T5 prompt** using [§6](#6-paste-in-facts-for-the-t5-prompt). T5 is the last task of
   the project.
4. **Decide whether to close the project** after T5, or keep it open for the two things
   [§8](#8-what-is-still-unproven) names.

## 6. Paste-in facts for the T5 prompt

> **T5 spans two kits, and that is the thing to get right.** The finisher and the driver are
> **csurvey-kit** tools — `prod/build_csx_kit.py` copies them into `csurvey_alati/` beside the
> `.bat` launchers, and its `TOOLS` list already carries all five (`nacrt_layout.py`,
> `nacrt_finish.py`, `nacrt_finish_compass.xml`, `csurvey_headless.ps1`, `csurvey_driver.py`).
> But `cavedossier nacrt` is a **cavedossier** command: it lives in the prod bundle
> (`prod/build_prod.py`), needs the `[sastavnica]` extra and SB access, and is NOT in the csx kit.
> Both kits publish into the same Drive folder (`!!!Digitalizacija/SurveyScraper5/`), so a KORAK 3
> `.bat` can call the cavedossier bootstrap — but `sastavnica` is the only 4S entry in
> `PROD_COMMANDS` today, and `nacrt` has to be added there **and** given a branch in
> `prod_templates/bootstrap.ps1.template`'s `switch ($Command)`.
>
> The launcher itself is generated from `prod/csx_templates/*.bat.template`; copy the shape of
> `csurvey_2_dovrsi_uvoz.bat.template` — the five-rung `set "TOOLS="` search, the `@VERSION@` /
> `@DATE@` / `@COMMIT@` / `@PAYLOAD@` / `@TOOLS@` tokens, the Croatian header without diacritics,
> the runtime "what to do next" footer. The flow is: SB prompt (`sb_select`) → pick the corrected
> `_lt` file → `nacrt_finish.py` → `csurvey_driver.py finish` → `cavedossier nacrt <broj>` →
> report the delivered `SB_<broj>_nacrt.pdf`.
>
> `csurvey_0_PROCITAJ_ME.txt.template` needs a KORAK 3 paragraph in the same plain Croatian as the
> others (that file keeps real diacritics; the `.bat` files must not). The protocol doc
> `production/tdx-processing-protocol.md` already carries a KORAK 3 step marked *in validation* —
> promote it and drop the numbering-clash note once the user has ruled.
>
> Two environment facts the launcher must survive: cSurvey may not be installed (every driver call
> then raises `DriverError` with one readable line, and the operator still has a finished `.csx` to
> open and print in two clicks), and the finisher's layout menu is interactive — pass `--yes` or
> surface the menu, do not let it block on a double-clicked window nobody is watching.

## 7. Open, and deliberately not decided here

- **The KORAK 3 numbering clash — the blocker.** The rescue launcher is already
  `csurvey_3_oporavi_iz_zipa.bat` and the finishing step is also "KORAK 3" (brief §3.2). One of
  them has to move: rename the rescue to KORAK 4, or make the finisher `3b`. Flagged in the
  protocol doc; the brief lists it as a user decision and it is still unanswered.
- **The plan sits left of centre on the sheet.** Its ink bbox includes the scale bar and the north
  arrow, which sit a metre to the right of the drawing, so centring the *ink* puts the cave itself
  left with the furniture balancing it. Raised twice, not answered. The alternative is to centre on
  the cave's own bbox (the Borders layer) and let the furniture hang right — a change in
  `compose.placements`, not in the finisher.
- **Which cells should read `/` beyond the two settled.** `addresses.STUBS` is the one-line place
  to add another.

## 8. What is still unproven

- **A second machine.** The definition of done asks for the driver printing on one operator
  machine, to prove the `CSURVEY_DIR` / printer portability and that `powershell -STA` is there.
  Everything so far is the dev machine.
- **Any cave but SB 1103.** Every rule in T1 and T4 has met exactly one real cave. The thresholds
  most likely to want tuning on the second: `nacrt_layout.TALL_ASPECT` (1.3) and `DRASTIC_RATIO`
  (1.6), `nacrt_finish.PAD_M` (0.5 m — it predicted the printed ink to ~3 mm on SB 1103),
  `QUOTA_BAND_M` (0.5 m) and `COMPASS_ABOVE_M` (1.0 m). All are single constants at the top of
  their module, for exactly this reason.
- **Illustrator resolving the embedded font.** The delivered page's three fonts all read
  `…+MicrosoftSansSerif` now, and the `/BaseFont` carries the PostScript name rather than the
  display name that broke before — but nobody has opened the new file in Illustrator. That is a
  ten-second check and it is the whole point of decision 3.
