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
| `features/csx-to-survey-pipeline/` | First feature: TopoDroid → finished-map pipeline (migrated from `cSurvey/dev`). |
| `shared/` | Shared speleology domain material (specs/formats/fixtures), distilled out as it proves necessary. Stacks differ, so shared = domain, not code. |
| `SurveyScraper4.code-workspace` | Multi-root workspace: this repo + the two read-only reference repos (created during setup). |

## Read-only reference repos (never edited / committed into)

- `../cSurvey` — VB.NET desktop cave-survey app (upstream clone; pull upstream freely).
- `../crospeleo-automation` — Python CroSpeleo/SpeleoFlow catalog-submission automation.
