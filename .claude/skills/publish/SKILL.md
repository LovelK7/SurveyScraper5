---
name: publish
description: Publish to prod (the registry Drive) — the one fixed procedure. Run the pipeline doctor and the tests, bump the version, commit, build and deploy the csurvey TDX kit and/or the cavedossier prod bundle, then verify what landed on the Drive. Use whenever the user asks to publish, deploy, release or "push to prod".
---

# /publish [csx | prod | both] [one-line note]

The **only** way anything reaches `!!!Digitalizacija/SurveyScraper5/` on the
Drive. That folder is what the society's non-developer operators double-click,
so every publish follows the same steps in the same order. When the user runs
`/publish`, that is the go-ahead to write to the Drive. Nothing else is.

There are two kits. Both publish into the same Drive folder, and each has its
own version:

| Kit | Builder | Version lives in | Ships (a change here needs a publish) |
|---|---|---|---|
| **csx** — csurvey TDX kit | `prod/build_csx_kit.py` | `KIT_VERSION` constant in the builder, plus a history comment above it | the `TOOLS` list in the builder (from `stages/3N-nacrt/production/tools/`), `prod/csx_templates/`, the builder itself |
| **prod** — cavedossier launchers + bundle | `prod/build_prod.py --version X.Y` | the `--version` argument; the Drive's `VERZIJE.txt` records each publish | `stages/*/src/cave_dossier/`, `prod/prod_templates/`, `BUNDLE_FILES` (`pyproject.toml`, `config.yaml`, …), `data/people/`, the builder itself |

## Guards (all before step 1)

- The repo root has both `pipeline.yaml` and `.cavedossier-workspace`, and the
  branch is `main`. Anything else: stop and ask.
- `LOCAL_DRIVE_ROOT` in `.env` resolves and
  `<root>/!!!Digitalizacija/SurveyScraper5/` exists. If Drive is not mounted:
  stop. Never publish somewhere else.
- `git check-ignore prod/dist data runs example sb-sync` covers all five.

## 1 — Decide what to publish

Read what is live from the Drive:
- csx: the `commit:` line of `csurvey_alati/KIT_VERSION.txt`
- prod: the last line of `VERZIJE.txt`

Then run `git diff --stat <that commit>..HEAD` plus `git status --short`
(uncommitted work counts, because it will be committed in step 4) and check the
result against the "Ships" column. Tell the user in one line which kits changed
and which files changed.
- If the user named a kit, publish that kit. If the other kit changed too, say
  so.
- If no kit was named, publish every kit that changed. If nothing changed,
  say so and stop. Do not republish the same content under a new number.

## 2 — Doctor (the gate)

`python tools/pipeline_doctor.py`. **Any FAIL stops the publish.** Show the
FAIL lines and offer to fix them. Do not publish around a failure, even one the
publish didn't cause. WARN and STALE lines are not blockers; mention them in
one line.

## 3 — Tests (the gate)

With the repo venv (`.venv\Scripts\python -m pytest -q`):
- always: `prod/tests`
- csx: `stages/3N-nacrt/tests`
- prod: the `tests/` of every stage whose `src/` changed since the live commit

Any failure stops the publish. Show the output as it is.

## 4 — Bump the version and commit

Versions are `major.minor`. The default bump is **minor** (1.5 → 1.6). A major
bump only happens when the user asks for one.
- **csx**: set `KIT_VERSION` in `prod/build_csx_kit.py` and add one history
  comment above it: `# vX.Y (YYYY-MM-DD): <what changed, operator's view>`.
- **prod**: the next version is one minor above the highest of the last
  `VERZIJE.txt` line and `prod/dist/prod/v*`. It is only an argument; nothing
  in the repo changes for it.
- Update the published-version mentions: the kit row(s) in `STATUS.md`
  ("prod vX.Y + csx kit vX.Y published").

Then **commit on `main` before building**. Both builders stamp
`git rev-parse HEAD` into what they ship, so an uncommitted build carries a
commit that doesn't contain its own code. Message:

```
publish: csx kit vX.Y[, prod vX.Y] — <note>
```

It ends with the attribution lines. Push. The auto-commit hook would otherwise
fold this into a `chore(auto):` checkpoint.

## 5 — Build and deploy

In the order below. The prod bundle goes first because KORAK 3 of the csx kit
calls `cavedossier_nacrt_v*.bat`:

```powershell
python prod\build_prod.py --version X.Y --publish    # add --skip-geo unless data/geo changed
python prod\build_csx_kit.py --publish
```

Use `--skip-geo` for prod unless `data/geo/` changed since the live commit. The
~280 MB sync is incremental either way, but it is slow over Drive. If a builder
fails partway, stop and report. The staged copy stays in `prod/dist/`. Never
hand-copy files to the Drive.

## 6 — Verify on the Drive

Read what landed. Don't just trust the builder's exit code:
- csx: `csurvey_alati/KIT_VERSION.txt` shows the new version and the step-4
  commit. Then import-check the Drive copies:
  `python "<drive>/csurvey_alati/nacrt_finish.py" --help` and the same for
  `csurvey_driver.py`, `fix_imported_linetypes.py` and `preprocess_tdx_csx.py`.
  This check exists because a missing sibling module only shows up on an
  operator machine.
- prod: the last `VERZIJE.txt` line is the new version with the step-4 commit.
  `cavedossier_*_vX.Y.bat` exists for every `PROD_COMMANDS` entry, the older
  launchers moved to `_arhiva/`, and `vX.Y/bundle.zip` and `vX.Y/bootstrap.ps1`
  are present.

## 7 — Report

In a few lines: what was published and at which version, the commit, what
changed for operators (in their terms, e.g. "KORAK 3 no longer asks which
file"), and anything operators need to be told. Example: a launcher was renamed,
or a first run reinstalls. The session's `/wrap-up` records it in the journal.
