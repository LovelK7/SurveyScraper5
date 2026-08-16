# CLAUDE.md — SurveyScraper4 orientation for AI agents

SurveyScraper4 is an **umbrella "superapp"** that unifies several cave-survey /
Croatian-speleology tools: it conveys raw cave-exploration data into the two final
products, the **OSZ** cave file and the **Nacrt** survey map. It is the repo where
**all work is committed**; the source projects that feed it stay outside as
read-only reference material.

**Read first:** [ARCHITECTURE.md](ARCHITECTURE.md) — the canonical pipeline map and
part numbering (1, 2.1a/b/c, 2.2). [STATUS.md](STATUS.md) — where the dev cycle
currently stands. [shared/glossary.md](shared/glossary.md) — Croatian domain terms
(OSZ, Nacrt, SB, SUE, izjava…); terms stay Croatian, code stays English.

> **⚠ App source referenced by the `csx-to-survey-pipeline` feature lives in the
> read-only `cSurvey/` reference clone (`../cSurvey`), not in this repo.**
> Citations written `cSurvey/cSurveyPC/path.vb:123` resolve against that clone.

## Features

Each feature is a self-contained module under `features/`. A feature is a unit of
work with its own docs, tools, and logs — not necessarily sharing code with the
others.

| Feature | Pipeline part | What it is |
|---|---|---|
| [features/csx-to-survey-pipeline/](features/csx-to-survey-pipeline/README.md) | 2.1a | Migrated 2026-08-16 from `cSurvey/dev/`: the TopoDroid → finished-map (Nacrt) pipeline — architecture knowledge base, the operational TDX→CSX processing toolkit, project work items, and decision/session logs. Start at its [README.md](features/csx-to-survey-pipeline/README.md). |
| [features/cave-dossier/](features/cave-dossier/README.md) | 2.1, 2.1b, 2.1c, 2.2 | Python package `cave_dossier` (CLI `cavedossier`): SB (Speleo baza) communication, per-cave dossier builder with warning/blocker gating, OSZ builder, isječak karte. |

Room for more features later — add new folders under `features/`, one per module.
Features integrate via **artifacts** (files), never cross-feature imports.

## Read-only reference repos (HARD RULE)

Two sibling repos are **reference material only. NEVER edit files in them, NEVER
run git write commands (commit/push/checkout/reset/...) in them.** All work —
code, docs, logs — lands in SurveyScraper4.

| Repo | Role |
|---|---|
| `../cSurvey` | VB.NET / .NET Framework 4.8 desktop cave-survey app (~320k LOC). **Upstream GitHub clone the user does not own** — kept clean so upstream can be pulled freely. The `csx-to-survey-pipeline` feature's `path:line` citations resolve here. Its own `CLAUDE.md` is the one-page orientation to that codebase. (Its `dev/` folder is the pre-migration original of our first feature; treat it as frozen history.) |
| `../crospeleo-automation` | Python automation for Croatian cave-catalog (CroSpeleo / SpeleoFlow) submissions. Own repo, own workspace. It is the **downstream consumer** of SurveyScraper4's delivery dirs (it submits finished dossiers to the national cadastre). **Porting rule:** code may be COPIED from it into this repo and adapted freely — log every copy in `features/cave-dossier/docs/PORTING.md`; never edit the source repo. |

Open [SurveyScraper4.code-workspace](SurveyScraper4.code-workspace) to get all
three folders in one VS Code window (reference repos labeled read-only).

## Shared domain, not shared code

The source projects overlap on the **speleology domain** — caves, surveys,
catalog records, file formats (`.csx`/`.csz`/`.th`) — but their tech stacks
differ (VB.NET vs Python). What they share is **specs / data / domain
knowledge, NOT code.** Distill shared material into `shared/` only as it proves
necessary; don't force it up-front.

## Where the deep knowledge is

The deep TopoDroid / cSurvey architecture knowledge base is
[features/csx-to-survey-pipeline/reference/](features/csx-to-survey-pipeline/reference/README.md)
— subsystem docs grounded with `cSurvey/cSurveyPC/...` `path:line` citations,
adversarially fact-checked. Read the relevant doc before working in a subsystem.
Current project state and strategy:
[features/csx-to-survey-pipeline/decisions/roadmap-decisions.md](features/csx-to-survey-pipeline/decisions/roadmap-decisions.md).
This file deliberately does **not** duplicate cSurvey's architecture notes — see
`cSurvey/CLAUDE.md` and the migrated docs.

## Path conventions (established at migration)

- `cSurvey/cSurveyPC/...` (or any `cSurvey/...` path) → the read-only reference
  clone at `../cSurvey`.
- Inside a feature, bare zone paths (`reference/…`, `production/…`,
  `projects/…`, `decisions/…`, `sessions/…`, `backlog/…`) are relative to that
  feature's root.
- Historical logs (`sessions/SESSIONS.md`, per-project `log.md`, `RUNLOG.md`)
  were migrated **verbatim** and may still contain pre-migration `dev/...` and
  bare `cSurveyPC/...` paths — map them mentally via the two rules above.
- Doc aliases inherited from cSurvey: `example/` (gitignored, present locally
  only) mirrors sample surveys whose tracked originals are
  `cSurvey/cSurveyPC/data/` (`example/buless.csz` =
  `cSurvey/cSurveyPC/data/buless_test1.csz`); `literature/` (gitignored) holds
  manuals + the TopoDroid symbol repo.

## Logging discipline

The repo runs a logging discipline — keep it up. **End every working session with
`/wrap-up`** (`.claude/skills/wrap-up/SKILL.md`): it updates [STATUS.md](STATUS.md),
appends a session block to the touched feature's `sessions/SESSIONS.md`, captures
new ideas into the feature's `backlog/`, and commits everything on `main` (single
branch, single history — the user is the sole developer). Per-project `log.md` and
run `RUNLOG.md` files are tracked ground truth (survey snapshots `.csz`/`.csx` are
gitignored, never committed).
