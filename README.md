# SurveyScraper4

Umbrella "superapp" unifying several cave-survey / Croatian-speleology tools.
This repo is where **all your work is committed**; the source projects that feed
it are kept as **read-only reference** siblings.

Setup done 2026-08-16 per [SETUP_PROMPT.md](SETUP_PROMPT.md): the first feature
(`csx-to-survey-pipeline`) is migrated from `cSurvey/dev`. Orientation for AI
agents: [CLAUDE.md](CLAUDE.md).

## Layout

| Path | What it is |
|---|---|
| `ARCHITECTURE.md` | Canonical pipeline map + part numbering (1, 2.1a/b/c, 2.2). |
| `STATUS.md` | Where the dev cycle stands (maintained by `/wrap-up`). |
| `features/csx-to-survey-pipeline/` | Part 2.1a: TopoDroid → finished-map (Nacrt) pipeline (migrated from `cSurvey/dev`). |
| `features/cave-dossier/` | Parts 2.1/2.1b/2.1c/2.2: SB communication, dossier builder, OSZ builder (CLI `cavedossier`). |
| `shared/` | Shared speleology domain material — starts with the [glossary](shared/glossary.md). |
| `SurveyScraper4.code-workspace` | Multi-root workspace: this repo + the two read-only reference repos. |

## Read-only reference repos (never edited / committed into)

- `../cSurvey` — VB.NET desktop cave-survey app (upstream clone; pull upstream freely).
- `../crospeleo-automation` — Python CroSpeleo/SpeleoFlow catalog-submission automation.
