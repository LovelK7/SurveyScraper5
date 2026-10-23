---
name: publish
description: Publish to prod (the registry Drive) — the one fixed procedure. Run the pipeline doctor and the tests, bump the version, commit, build and deploy the prod bundle behind SurveyScraper5.bat (the dashboard launcher), then verify what landed on the Drive. Use whenever the user asks to publish, deploy, release or "push to prod".
---

# /publish [one-line note]

The **only** way anything reaches `!!!Digitalizacija/SurveyScraper5/` on the
Drive. That folder is what the society's non-developer operators double-click,
so every publish follows the same steps in the same order. When the user runs
`/publish`, that is the go-ahead to write to the Drive. Nothing else is.

There is one thing to publish: the **prod bundle** behind `SurveyScraper5.bat`,
the dashboard launcher (since 2026-10-22). The `csurvey_*` drag-and-drop kit is
retired: `build_csx_kit.py --publish` refuses, and its tools ride in the bundle
as `csx-alati/`.

| Builder | Version lives in | Ships (a change here needs a publish) |
|---|---|---|
| `prod/build_prod.py --version X.Y` | the `--version` argument; the Drive's `VERZIJE.txt` records each publish | `stages/*/src/cave_dossier/` (the dashboard included), `stages/3N-nacrt/production/tools/` + `production/themes/` (as `csx-alati/`), `prod/prod_templates/`, `BUNDLE_FILES` (`pyproject.toml`, `config.yaml`, …), `data/people/`, `prod/build_prod.py`, and the `TOOLS` list in `prod/build_csx_kit.py` |

## Guards (all before step 1)

- The repo root has both `pipeline.yaml` and `.cavedossier-workspace`, and the
  branch is `main`. Anything else: stop and ask.
- `LOCAL_DRIVE_ROOT` in `.env` resolves and
  `<root>/!!!Digitalizacija/SurveyScraper5/` exists. If Drive is not mounted:
  stop. Never publish somewhere else.
- `git check-ignore prod/dist data runs example sb-sync` covers all five.

## 1 — Decide whether to publish

Read what is live from the Drive: the last line of `VERZIJE.txt`.

Then run `git diff --stat <that commit>..HEAD` plus `git status --short`
(uncommitted work counts, because it will be committed in step 4) and check the
result against the "Ships" column. Tell the user in one line which files
changed. If nothing changed, say so and stop. Do not republish the same
content under a new number.

## 2 — Doctor (the gate)

`python tools/pipeline_doctor.py`. **Any FAIL stops the publish.** Show the
FAIL lines and offer to fix them. Do not publish around a failure, even one the
publish didn't cause. WARN and STALE lines are not blockers; mention them in
one line.

## 3 — Tests (the gate)

With the repo venv (`.venv\Scripts\python -m pytest -q`):
- always: `prod/tests` and `stages/0P-platform/tests/test_gui.py`
- `stages/3N-nacrt/tests` when the 3N tools or themes changed
- the `tests/` of every stage whose `src/` changed since the live commit

Any failure stops the publish. Show the output as it is.

## 4 — Bump the version and commit

Versions are `major.minor`. The default bump is **minor** (2.0 → 2.1). A major
bump only happens when the user asks for one. The next version is one minor
above the highest of the last `VERZIJE.txt` line and `prod/dist/prod/v*`. It
is only an argument; nothing in the repo changes for it. Update the
published-version mentions in `STATUS.md` ("prod vX.Y published").

Then **commit on `main` before building**. The builder stamps
`git rev-parse HEAD` into what they ship, so an uncommitted build carries a
commit that doesn't contain its own code. Message:

```
publish: prod vX.Y — <note>
```

It ends with the attribution lines. Push. The auto-commit hook would otherwise
fold this into a `chore(auto):` checkpoint.

## 5 — Build and deploy

```powershell
python prod\build_prod.py --version X.Y --publish    # add --skip-geo unless data/geo changed
```

Use `--skip-geo` unless `data/geo/` changed since the live commit. The ~280 MB
sync is incremental either way, but it is slow over Drive. If the builder fails
partway, stop and report. The staged copy stays in `prod/dist/`. Never
hand-copy files to the Drive.

## 6 — Verify on the Drive

Read what landed. Don't just trust the builder's exit code:
- the last `VERZIJE.txt` line is the new version with the step-4 commit;
- `SurveyScraper5.bat` names `vX.Y\bootstrap.ps1`, and `vX.Y/bundle.zip` and
  `vX.Y/bootstrap.ps1` are present;
- the folder holds only `SurveyScraper5.bat`, `PROCITAJ_ME.txt`, `VERZIJE.txt`,
  `vX.Y/`, `podaci/`, `_arhiva/` (plus Drive's `desktop.ini`). A retired
  `.bat` or `csurvey_alati/` still at the top means the sweep failed (a locked
  file): say so;
- import-check the bundled 3N tools. Extract `csx-alati/` from the published
  `bundle.zip` into a scratch dir and run `python <dir>/nacrt_finish.py --help`,
  and the same for `csurvey_driver.py`, `fix_imported_linetypes.py` and
  `preprocess_tdx_csx.py`. A missing sibling module would otherwise only show
  up on an operator machine.

## 7 — Report

In a few lines: what was published and at which version, the commit, what
changed for operators (in their terms, e.g. "KORAK 3 no longer asks which
file"), and anything operators need to be told. Example: a new version means
the next double-click reinstalls (a few minutes) and restarts an open
dashboard. The session's `/wrap-up` records it in the journal.
