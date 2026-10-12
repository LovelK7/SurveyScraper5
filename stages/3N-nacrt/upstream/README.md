# Upstream — reports and fixes for cSurvey

Bugs and wishes we find in **cSurvey** itself go back to its author as a pull request (when we have a fix)
or an issue (when we don't). One folder per report, numbered, so nothing found here gets lost in a session
log.

| # | Report | Kind | Status | Workaround meanwhile |
|---|---|---|---|---|
| [0001](0001-gallery-path-case/PR.md) | Lowercased file paths: the sign gallery crashes when cSurvey runs from a shared Google Drive folder, and a double-clicked `.csx` there is not found | PR (2 files) | written 2026-10-12, not yet sent | cSurvey runs from a local copy (`production/tools/csurvey_local.py`); the dashboard opens surveys with `filename=` |

## Where things are

| What | Where |
|---|---|
| Upstream (the author's repo) | [github.com/cepelabs/cSurvey](https://github.com/cepelabs/cSurvey), branch `master` |
| Your fork | [github.com/LovelK7/cSurvey](https://github.com/LovelK7/cSurvey) = the `../cSurvey` clone (`origin`) |
| One report | `upstream/NNNN-short-name/` — `PR.md` (or `ISSUE.md`) + `fix.patch` |
| Blank report | [TEMPLATE.md](TEMPLATE.md) |

## How a report is made

1. **Agent (in this repo):** finds the cause in `../cSurvey` (read only), copies [TEMPLATE.md](TEMPLATE.md)
   to the next free `NNNN-short-name/PR.md`, fills it in, writes `fix.patch` against **upstream's** current
   file (below), and adds a row to the table above.
2. **User:** applies the patch in the fork, builds, runs the steps under "How to reproduce", ticks
   "Tested", and opens the PR (below). Agents never write in `../cSurvey` (CLAUDE.md, hard rule), so this
   step is always yours.
3. **When the author answers:** update the row's status. When a fixed cSurvey is on the shared Drive,
   say whether the workaround can go, and remove it in a normal change here.

## Making the patch (agent)

The patch is made against upstream `master`, not the local clone (the clone can be behind and has
different line endings):

```bash
gh api "repos/cepelabs/cSurvey/contents/cSurveyPC/<file>.vb?ref=master" --jq .content | base64 -d > a.vb
cp a.vb b.vb   # edit b.vb, keep the file's line endings and BOM
git diff --no-index a.vb b.vb   # then fix the two path lines to a/cSurveyPC/<file>.vb, b/cSurveyPC/<file>.vb
```

## Sending it (user)

From `../cSurvey` (your fork):

```bash
git fetch https://github.com/cepelabs/cSurvey.git master
git switch -c fix/<short-name> FETCH_HEAD
git apply --ignore-whitespace ../SurveyScraper5/stages/3N-nacrt/upstream/NNNN-short-name/fix.patch
# build and test, then:
git commit -am "<the PR title>"
git push -u origin fix/<short-name>
gh pr create --repo cepelabs/cSurvey --base master --head LovelK7:fix/<short-name> \
  --title "<the PR title>" --body-file ../SurveyScraper5/stages/3N-nacrt/upstream/NNNN-short-name/PR.md
```

If `git apply` refuses (line endings), make the change by hand: every patch here is a few lines and the
PR text quotes them. Afterwards `git switch` back to the branch you were on; the clone is reference
material for the agents and should stay on upstream code.
