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

Rehearsed 2026-10-15. Works from any PowerShell window; it uses a throwaway folder `C:\pr`, never
`../cSurvey`, and needs only `git` and `gh` (already logged in as LovelK7). Replace `NNNN-short-name`
and the branch name `fix/short-name`; the title is the first line of `PR.md`.

```powershell
# 1. a fresh copy of the AUTHOR's code (your fork's master has your own commits)
git -c core.autocrlf=false -c core.longpaths=true clone --filter=blob:none https://github.com/cepelabs/cSurvey.git C:\pr\cSurvey
cd C:\pr\cSurvey
git config core.autocrlf false
git config core.longpaths true

# 2. a branch with the fix
git switch -c fix/short-name
git apply "C:\Users\Lovel.IZRK-LK-NB\Programming\SurveyScraper5\stages\3N-nacrt\upstream\NNNN-short-name\fix.patch"
git diff --stat            # must list only the files the PR names
git commit -am "<the PR title>"

# 3. upload the branch to your fork and open the PR to the author
git push https://github.com/LovelK7/cSurvey.git fix/short-name
gh pr create --repo cepelabs/cSurvey --base master --head LovelK7:fix/short-name `
  --title "<the PR title>" `
  --body-file "C:\Users\Lovel.IZRK-LK-NB\Programming\SurveyScraper5\stages\3N-nacrt\upstream\NNNN-short-name\PR.md"
```

`gh pr create` prints the PR's link: put it in the table above. Afterwards `C:\pr` can be deleted. If
`git apply` refuses, tell the agent: the patch is regenerated against the author's current code. We
can't build cSurvey here (it needs the paid DevExpress 24.2), so "Tested" says what was checked
instead and the author builds it.
