# T2 — `csurvey_headless.ps1` + `csurvey_driver.py`: the production driver

Paste everything below the line into a fresh Claude Code session opened in
`SurveyScraper5`. Report the result back in the research session (project 0004). T4 and T1
are committed; this task turns the proven probe into the tool the launcher will call.

---

You are working in the SurveyScraper5 repo (read `CLAUDE.md` first; `../cSurvey` is a
**read-only** reference clone — grep it to confirm a member name, never edit it). This is task
**T2** of project 0004. Read: `stages/3N-nacrt/projects/0004-nacrt-finishing/brief.md` §2.2, §3.1
rows 5 and 7, §3.2, §3.3 (T2); then the **working** probe
`stages/3N-nacrt/projects/0004-nacrt-finishing/findings/csurvey_headless_probe.ps1` — every
reflection poke in it is verified on the installed `C:\csurvey64\cSurveyPC.exe` (2.0.0.0,
2025-12-10, x64) and must be kept exactly, including the `Assert-NotNull` on each non-public
member. Also skim `nacrt_finish.py` (T1: what it writes into `_preview.*`, and the sidecar JSON
it emits) and `sb_select.py` (the `--sb` convention).

## What to build

### 1. `stages/3N-nacrt/production/tools/csurvey_headless.ps1`

Promote the probe to a tool. Same three commands plus one, same bootstrap:

- `info` — as in the probe.
- `recalc -Out <file>` — as in the probe; wrap `Calculate` so a therion failure or a
  `cActionResult.Result = False` exits non-zero with the exception text on stderr.
- `print -Out <dir>` — as in the probe, **but** the two PDFs are named
  `<name>_plan.pdf` / `<name>_profile.pdf` where `<name>` strips a trailing `_lt_fin` / `_lt` /
  `_pp` chain (so `X_lt_fin.csx` → `X_plan.pdf`). Add `-Design Plan|Profile|Both` (default Both).
- `dimensions` — new: print a JSON object to stdout, nothing else on stdout, from the per-cave
  speleometric row (`Survey.Calculate.Speleometrics`, the entry whose `Cave` is non-empty and
  `Branch` is empty; fall back to the whole-complex row when there is exactly one cave):
  `{"cave": ..., "l": 10, "pl": 4, "ml": 102, "pvr": 1, "nvr": 9, "drop": 10, "qmx": 7.53,
  "qmn": -2.06, "es": "2", "calculated": true}` — numbers as JSON numbers with `.` decimals
  (the host culture uses `,` — format with `[Globalization.CultureInfo]::InvariantCulture`),
  `drop = pvr + nvr` (null when either is missing), `calculated` false when the row is empty.
- Parameters: `-Survey`, `-Command`, `-Out`, `-Design`, `-CSurveyDir` (default from env var
  `CSURVEY_DIR`, else `C:\csurvey64`), `-Printer` (default from env var `CSURVEY_PRINTER`, else
  `Microsoft Print to PDF`). Exit codes: 0 ok, 2 usage, 3 bootstrap/reflection failure (name the
  member), 4 load failure, 5 calculate failure, 6 print failure (printer missing / no file
  written), always with one line on stderr. Keep the STA check; keep variables distinct from
  parameter names (`$Survey` vs `$srv` — PowerShell names are case-insensitive).
- Guard `Calculate` with a 60-s watchdog (run it on a `[Threading.Thread]`? No — the domain is
  single-threaded; instead start the whole script under `Start-Process -Wait` from the Python
  wrapper with a timeout, see below) — so in the .ps1 just document that the caller enforces
  the timeout.

### 2. `stages/3N-nacrt/production/tools/csurvey_driver.py`

Stdlib-only Python wrapper (subprocess), same folder, importable by the launcher and by T3:

```python
def run(command, survey, *, out=None, design="Both", timeout=180, csurvey_dir=None, printer=None) -> DriverResult
def recalc(survey, out, **kw) -> DriverResult
def print_pdfs(survey, out_dir, **kw) -> dict   # {"plan": path|None, "profile": path|None}
def dimensions(survey, **kw) -> dict            # parsed JSON
def finish_and_print(fin_survey, out_dir, **kw) -> dict   # recalc → print → dimensions, one call
```

Runs `powershell -STA -NoProfile -ExecutionPolicy Bypass -File csurvey_headless.ps1 …` with
`subprocess.run(..., timeout=…)`, maps exit codes to a `DriverError` with the stderr line,
reads `CSURVEY_DIR` / `CSURVEY_PRINTER` from the environment and, if unset, from the
workspace `.env` (plain `KEY=VALUE` lines; find the workspace root by walking up to the
`.cavedossier-workspace` marker — do **not** import `cave_dossier`, this tool travels into the
operator kit). `finish_and_print` writes `<name>_dimenzije.json` beside the PDFs:
the `dimensions` JSON merged with the finisher's sidecar keys `mjerilo`, `plan_scale`,
`profile_scale`, `arrangement`, `plan_mm`, `profile_mm` when `<fin>.layout.json` exists next to
the survey. CLI: `python csurvey_driver.py <command> <survey> [-o OUT] [--design …]`, plus
`--sb <broj>` on an intake folder like the sibling tools (`sb_select`, candidates = `*_lt_fin.*`).

### 3. Tests

`stages/3N-nacrt/tests/test_csurvey_driver.py`: unit-test the wrapper with a **fake
PowerShell** (monkeypatch `subprocess.run` to return canned stdout/stderr/exit codes) for: exit
code → `DriverError` mapping, JSON parsing, `.env` fallback, output naming, timeout →
`DriverError`. Mark the real end-to-end test `@pytest.mark.skipif` unless
`C:\csurvey64\cSurveyPC.exe` (or `CSURVEY_DIR`) exists **and** the fixture
`stages/3N-nacrt/example/finishing/SB_1103_golobreska_lt_raw.csx` exists; that test runs
`nacrt_finish.py --yes` on a tmp copy, then `finish_and_print`, and asserts: both PDFs exist and
are > 10 KB, `dimensions` gives `l == 10`, `pl == 4`, `nvr == 9`, `es == "2"`, and the
`_dimenzije.json` carries `mjerilo == "1:100"`. Run `python -m pytest stages/3N-nacrt/tests -q`
(green, including the live test on this machine) and `python tools/pipeline_doctor.py` (0 fail).

### 4. Docs (part of the work)

- Rows for both tools in the *Nacrt finishing (KORAK 3)* table of
  `stages/3N-nacrt/production/tools/README.md`; note the two `.env` keys and the STA requirement.
- Add `CSURVEY_DIR` and `CSURVEY_PRINTER` (commented, with defaults) to `.env.example`.
- `prod/build_csx_kit.py` has an explicit `TOOLS = [...]` list of files copied into
  `csurvey_alati/` — add `csurvey_headless.ps1`, `csurvey_driver.py`, `nacrt_layout.py`,
  `nacrt_finish.py`, `nacrt_finish_compass.xml` so the KORAK 3 launcher (T5) will find them.
  Do not build the launcher itself.
- Mark `findings/csurvey_headless_probe.ps1` as superseded in its header comment (one line
  pointing at the production tool); leave it in place as the record.
- Append a dated entry to `stages/3N-nacrt/projects/0004-nacrt-finishing/log.md` (Did / Result /
  Evidence / Next).

Do **not** commit. Finish by printing: the `dimensions` JSON for the finished SB 1103 file, the
`finish_and_print` return value, the pytest summary line, and the doctor's last line.
