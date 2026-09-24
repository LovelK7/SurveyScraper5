# CLAUDE.md — SurveyScraper5 orientation for AI agents

SurveyScraper5 conveys raw cave-exploration data into the two final products,
the **OSZ** cave file and the **Nacrt** survey map. It is the repo where **all
work is committed**; the source projects that feed it stay outside as read-only
reference material.

**Read first:** [ARCHITECTURE.md](ARCHITECTURE.md) — the canonical pipeline map.
[STATUS.md](STATUS.md) — where the dev cycle currently stands.
[pipeline.yaml](pipeline.yaml) — the machine-readable stage list the doctor checks
everything against. [shared/glossary.md](shared/glossary.md) — Croatian domain
terms (OSZ, Nacrt, SB, SUE, izjava…); terms stay Croatian, code stays English.

> **⚠ App source referenced by the `3N-nacrt` stage lives in the read-only
> `cSurvey/` reference clone (`../cSurvey`), not in this repo.** Citations
> written `cSurvey/cSurveyPC/path.vb:123` resolve against that clone.

## The stages

One directory per pipeline stage under `stages/`, each with its own README.
**The label is `<digit><letter>`: the digit is the position in the pipeline, the
letter is the Croatian name of the thing.** So the folders list in the order data
flows, and the label says what it is without a lookup. Use these labels in docs,
STATUS, session logs and conversation — `4O` always means the OSZ builder.

| Label | Directory | What it is | Was |
|---|---|---|---|
| **0P** | [stages/0P-platform/](stages/0P-platform/README.md) | Shared spine: config, the workspace anchor, normalization, matching, the CLI | — |
| **1T** | [stages/1T-teren/](stages/1T-teren/README.md) | Field capture (PARKED) + the intake-dir contract and scanner | 1 + intake |
| **2B** | [stages/2B-baza/](stages/2B-baza/README.md) | SB (Speleo baza) master workbook + satellite tables | 2.2a + 2.2b |
| **3N** | [stages/3N-nacrt/](stages/3N-nacrt/README.md) | csx-to-survey → Nacrt PDF + dimensions; the cSurvey knowledge base | 2.1a |
| **4G** | [stages/4G-geo/](stages/4G-geo/README.md) | Locality + kota finders (DGU / RGI / DMV) | part of 2.1b |
| **4I** | [stages/4I-isjecak/](stages/4I-isjecak/README.md) | Isječak karte via georef.hr | 2.1c |
| **4O** | [stages/4O-osz/](stages/4O-osz/README.md) | OSZ builder — prefill + backfill over the v10 template | 2.1b |
| **4F** | [stages/4F-fotografije/](stages/4F-fotografije/README.md) | Entrance-photo processing | 2.1d |
| **4S** | [stages/4S-sastavnica/](stages/4S-sastavnica/README.md) | Nacrt title block for the Illustrator route | 2.1e |
| **5O** | [stages/5O-osobe/](stages/5O-osobe/README.md) | Registar osoba + izjave linkage | part of 2.1 |
| **5D** | [stages/5D-dosje/](stages/5D-dosje/README.md) | Dossier model, the two gates, `report` | 2.1 |
| **6P** | [stages/6P-predaja/](stages/6P-predaja/README.md) | Delivery + SB write-back (designed only) | M6 |

**Historical documents keep the old numbers.** `journal/SESSIONS.md`,
`docs/design-decisions.md` and `stages/3N-nacrt/decisions/` were written when
`2.1b` meant the OSZ builder; they were migrated verbatim and not rewritten. The
`Was` column above is the mapping — read old logs through it.

## The rest of the tree

| Path | What |
|---|---|
| `prod/` | **The outward-facing surface** — everything a non-developer touches. See [prod/README.md](prod/README.md) and [prod/drive-layout.md](prod/drive-layout.md). |
| `docs/` | Cross-cutting records: [design-decisions.md](docs/design-decisions.md) (the settled rationale, whole), [commands.md](docs/commands.md) (every CLI command in one place), [module-map.md](docs/module-map.md). |
| `journal/` | [SESSIONS.md](journal/SESSIONS.md) + [backlog.md](journal/backlog.md) — the active log. `/wrap-up` writes here. |
| `config.yaml`, `.env` | Committed config; per-machine facts. Workspace root. |
| `data/`, `runs/`, `sb-sync/`, `example/` | Workspace state, one of each, mostly gitignored. |
| `conftest.py`, `tests/fixtures/` | Repo-level test infra; per-stage tests live in `stages/*/tests/`. |
| `tools/pipeline_doctor.py` | The structural health check. |

## How the code is laid out

**One importable package, many source roots.** Each stage owns
`stages/<label>-<name>/src/cave_dossier/<subpackage>/`, and `import
cave_dossier.osz` works unchanged. `pyproject.toml` maps them with an explicit
`[tool.setuptools.package-dir]` table.

Three rules that are easy to get wrong:

1. **Never use `packages.find` with `where = [several roots]`.** It is not a
   union — setuptools collapses every root onto `cave_dossier` and the last one
   silently wins; `pip install -e .` succeeds and the import then fails. The
   explicit `package-dir` map is the only form that works.
2. **There is no `cave_dossier/__init__.py`.** PEP 420 namespace; adding one
   makes that root win and the others vanish.
3. **Adding a subpackage means editing `pyproject.toml` and `pipeline.yaml`.**
   The doctor fails if a subpackage exists that no stage claims.

**Paths.** Never re-derive a root with `parents[N]`. Use
`cave_dossier.core.paths`: `workspace_root()` for config and mutable state
(`config.yaml`, `.env`, `data/`, `runs/`, `sb-sync/`), `repo_root()` only for
dev-only sibling-repo reaches (it returns `None` in prod), and
`Path(__file__).parent` for package assets that ship with their code.

## Read-only reference repos (HARD RULE)

Two sibling repos are **reference material only. NEVER edit files in them, NEVER
run git write commands (commit/push/checkout/reset/…) in them.** All work —
code, docs, logs — lands in SurveyScraper5.

| Repo | Role |
|---|---|
| `../cSurvey` | VB.NET desktop cave-survey app (~320k LOC). **Upstream GitHub clone the user does not own** — kept clean so upstream can be pulled freely. `3N-nacrt`'s `path:line` citations resolve here. |
| `../crospeleo-automation` | Python automation for Croatian cave-catalog submissions. The **downstream consumer** of this repo's Drive delivery dirs. **Porting rule:** code may be COPIED from it and adapted freely — log every copy in [stages/0P-platform/docs/PORTING.md](stages/0P-platform/docs/PORTING.md); never edit the source repo. |

Open [SurveyScraper5.code-workspace](SurveyScraper5.code-workspace) to get all
three folders in one VS Code window.

## Dev vs prod

This repo is the **dev** half; **prod is the registry Google Drive** — the shared
folders where the society's non-developer users work and where every tool's
outputs already land. The contract, the dirs and the standing portability rules
are in [prod/README.md](prod/README.md) and [prod/drive-layout.md](prod/drive-layout.md).

The workspace root is deliberately shaped like the extracted prod bundle, so one
`workspace_root()` rule serves dev and an operator's
`%LOCALAPPDATA%\CaveDossier\v<X>` alike.

## Shared domain, not shared code

The source projects overlap on the **speleology domain** — caves, surveys,
catalog records, file formats — but their tech stacks differ (VB.NET vs Python).
What they share is **specs / data / domain knowledge, NOT code.** Stages
integrate via **artifacts** (files), never cross-stage imports of each other's
orchestrators. Distill shared material into `shared/` only as it proves
necessary.

## Documentation audience split

Established by the user 2026-08-30, and unchanged by the restructure:

- **`stages/*/README.md`** — what that stage does, how to run it, how it works,
  where its code and assets are. The one place to look to understand a segment.
- **`docs/design-decisions.md`** — the decision record: what was settled once and
  why. Stage READMEs link into it rather than restating it.
- **`prod/`** — the operator-facing surface.

When a session settles a design question it goes into the decision record, not a
README. Large documents get a linkable table of contents at the top.

## Logging discipline

Commits are automated: [`.claude/hooks/auto-commit.sh`](.claude/hooks/README.md)
commits and pushes to GitHub on a throttled checkpoint and at session end, tagged
`chore(auto):`. Those are a backup safety net, not the record. **The hook only
ever acts on `main`** — working on a branch makes it inert, which is the
supported way to do a risky migration.

**Development runs through `/feature-dev`** (`.claude/skills/feature-dev/SKILL.md`):
standing build rules (SB never auto-written, hand-managed Drive dirs, fail-soft +
offline, dev/prod portability), the test protocol, and the documentation
close-out checklist. It ends by running `python tools/pipeline_doctor.py`.
Doc updates are part of the work, not a follow-up request.

**Publishing to prod goes only through `/publish`** (`.claude/skills/publish/SKILL.md`):
doctor and tests as gates, version bump, commit, build + deploy, verify on the
Drive. Never run `build_prod.py --publish` / `build_csx_kit.py --publish` outside it.

**End every working session with `/wrap-up`** (`.claude/skills/wrap-up/SKILL.md`):
it updates [STATUS.md](STATUS.md), appends a block to
[journal/SESSIONS.md](journal/SESSIONS.md), captures ideas into
[journal/backlog.md](journal/backlog.md), and commits on `main`.

Survey snapshots (`.csz`/`.csx`) are gitignored and never committed. Before any
change that moves files, check `git check-ignore` still covers `data/`, `runs/`,
`example/` and `sb-sync/` — the auto-commit hook runs `git add -A`.
