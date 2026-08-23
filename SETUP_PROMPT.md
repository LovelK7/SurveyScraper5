# SurveyScraper5 — first-session setup prompt

> Paste the block below into a fresh Claude Code session opened **in this
> `SurveyScraper5` workspace**. It is self-contained — the new session needs no
> prior chat context. Before starting, add the two reference repos as working
> directories (`/add-dir C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey` and
> `/add-dir C:\Users\Lovel.IZRK-LK-NB\Programming\crospeleo-automation`), or let
> the agent create the multi-root workspace file in step 1 and reopen.

---

You are setting up a brand-new, almost-empty repo: **SurveyScraper5** (the
"superapp") at `C:\Users\Lovel.IZRK-LK-NB\Programming\SurveyScraper5`. Your job
is to scaffold it and migrate one existing body of work into it as a single
feature. Work only inside SurveyScraper5 — the other two repos are read-only
reference material.

## Mental model

SurveyScraper5 is an **umbrella "superapp"** that will unify several
cave-survey / Croatian-speleology tools. Two existing projects feed it. They
overlap on a shared **domain** (caves, surveys, catalog records, file formats
like `.csx`/`.csz`/`.th`) but have **different tech stacks**, so what they share
is specs / data / domain knowledge — **not code**.

**Read-only reference repos** (NEVER edit them, NEVER git-commit into them — all
work lands in SurveyScraper5):

1. `C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey` — VB.NET / .NET Framework 4.8
   desktop cave-survey app (~320k LOC). It is an **upstream GitHub clone the user
   does NOT own**; the user's own work lived only in its `dev/` subfolder. Because
   we no longer commit here, upstream can be pulled cleanly. The deep TopoDroid /
   cSurvey architecture knowledge base is `cSurvey\dev\reference\`.
2. `C:\Users\Lovel.IZRK-LK-NB\Programming\crospeleo-automation` — Python
   automation for Croatian cave-catalog (CroSpeleo / SpeleoFlow) submissions. Its
   own repo, its own workspace.

The **first feature** of SurveyScraper5 is the TopoDroid → finished-map pipeline
work that currently lives in `cSurvey\dev\`. In SurveyScraper5 it becomes **one
feature named `csx-to-survey-pipeline`** — it is NOT the foundation of the
superapp, just its first module.

## Tasks

1. **Multi-root workspace.** Create `SurveyScraper5.code-workspace` at the repo
   root with three folders: this repo (SurveyScraper5), `../cSurvey` (labeled
   "cSurvey (read-only reference)"), and `../crospeleo-automation` (labeled
   "crospeleo-automation (read-only reference)").

2. **Migrate dev/ as a feature.** Copy (do NOT move) the entire contents of
   `C:\Users\Lovel.IZRK-LK-NB\Programming\cSurvey\dev\` into
   `features\csx-to-survey-pipeline\` in this repo, preserving its internal
   structure (the four zones `reference/ production/ projects/ decisions/`, plus
   `sessions/`, `backlog/`, and its `README.md`). **Clean start — do NOT preserve
   git history. Leave the original `cSurvey\dev` untouched.** Note: some dev/
   docs reference gitignored folders (`dev/literature/`, `dev/example/`) that
   won't exist in a fresh clone — don't try to recreate them.

3. **Fix path citations (the main gotcha).** The copied docs were written
   relative to the *cSurvey repo root*, so they cite app source as
   `cSurveyPC/cSurvey.vb:10` and use markdown links like `[x](cSurveyPC/...)`.
   Those files now live under `features\csx-to-survey-pipeline\` in a **different
   repo where `cSurveyPC/` does not exist**. Establish and document ONE
   convention — all app-source citations resolve against the read-only `cSurvey`
   reference clone — and rewrite the citations/links accordingly. Also honor the
   known doc aliases from cSurvey's own CLAUDE.md:
   - `dev/example/` paths actually mean `cSurveyPC/data/`
     (e.g. `dev/example/buless.csz` = `cSurveyPC/data/buless_test1.csz`).
   - `dev/reference/` citations are grounded in `cSurveyPC/...`.
   Add a prominent note at the top of the feature's README and in the superapp
   CLAUDE.md: **"App source referenced by this feature lives in the read-only
   `cSurvey/` reference clone, not in this repo."**

4. **Write the superapp `CLAUDE.md`** at the repo root, covering: what
   SurveyScraper5 is (umbrella superapp); the feature list (just
   `csx-to-survey-pipeline` for now, with room for more under `features/`); the
   two read-only reference repos, their roles, and the **hard rule that they are
   never edited or committed into**; the shared-domain note (shared = speleology
   domain / formats / specs, NOT code, because the stacks differ — distill shared
   material into `shared/` as it proves necessary); and a pointer to
   `features/csx-to-survey-pipeline/` (esp. its `reference/`) for the deep
   TopoDroid/cSurvey architecture knowledge. Do not duplicate cSurvey's whole
   CLAUDE.md — point to the migrated docs instead.

5. **`.gitignore`.** Seed sensible ignores (mirror the useful ones from
   `cSurvey/dev`: survey snapshots in `projects/*/runs/`, `literature/`, plus
   OS/editor cruft). Do not ignore the tracked logs (SESSIONS.md, per-project
   `log.md`, RUNLOG, inspector JSON) — the user runs a logging discipline.

6. **git init + one commit.** `git init`, stage everything, single initial
   commit: `Initial SurveyScraper5 scaffold: csx-to-survey-pipeline migrated from cSurvey/dev`.

7. **Verify.** Spot-check 5–10 rewritten citations by opening the referenced
   files in the `cSurvey` reference clone and confirming they resolve to real
   `path:line` locations. Report any that didn't resolve.

## Hard rules (do not violate)

- `cSurvey` and `crospeleo-automation` are **READ-ONLY**. Never edit them, never
  run git write commands in them. All work lands in **SurveyScraper5**.
- **Non-destructive:** copy, don't move. The original `cSurvey\dev` stays intact
  until the user verifies the migration.
- `dev/` becomes **one feature** (`csx-to-survey-pipeline`), not the repo root /
  foundation.
- Preserve the migrated content's internal structure and its logs verbatim.

## When done

Report: the final tree of SurveyScraper5, how many citations you rewrote and the
convention you chose, any citations that failed to resolve, and a suggested next
step (e.g. whether to delete `cSurvey\dev` now that the copy is verified, and
whether crospeleo-automation should later become a second `features/` module or
stay a standalone reference repo).
