# 3N — Nacrt

**TopoDroid survey → the finished map (Nacrt).** Route A of two: this stage is
the pipeline's own drafting route, via cSurvey. Route B is Adobe Illustrator,
which the pipeline serves at exactly one point — [4S-sastavnica](../4S-sastavnica/README.md).

Unlike the other stages this one is **not** part of the `cave_dossier` Python
package. It is a documentation knowledge base plus a standalone operator
toolkit, and it integrates with the rest of the pipeline through **artifacts**
(the Nacrt PDF and the cave dimensions), never through imports.

| Zone | What it holds |
|---|---|
| [`reference/`](reference/README.md) | How cSurvey works — subsystem docs grounded with `cSurvey/cSurveyPC/...` `path:line` citations, adversarially fact-checked |
| [`production/`](production/README.md) | The shipped surface: the TDX processing protocol, the symbol matrix, and the Python tools |
| [`projects/`](projects/README.md) | Dated R&D work items with their run logs and ground-truth snapshots |
| [`decisions/`](decisions/roadmap-decisions.md) | The append-only portfolio strategy log |
| `sessions/`, `backlog/` | **Frozen history.** The active journal is [`journal/`](../../journal/SESSIONS.md) at the repo root |

## Run it: raw TopoDroid `.csx` → `SB_<broj>_nacrt.pdf`

These are the same commands the Drive `.bat` kit runs (see
`prod/csx_templates/csurvey_{1,2,3}_*.bat.template`). Run them from the repo root
in the VS Code PowerShell terminal with the venv active (`.venv\Scripts\Activate.ps1`).
The steps alternate between the terminal and cSurvey. Each tool takes either a file
path, or the intake folder plus `--sb <Redni broj>`, which picks the file from that
cave's `SB_<broj>_…` leaf and asks which file to use if there is more than one.

```powershell
$T = "stages\3N-nacrt\production\tools"
$INTAKE = "<LOCAL_DRIVE_ROOT>\!!!Digitalizacija\!Za digitalizirat"   # LOCAL_DRIVE_ROOT from .env

# KORAK 1 — raw TDX export -> <name>_pp.csx (symbols renamed so they survive import)
python $T\preprocess_tdx_csx.py $INTAKE --sb 1103 --force
#   or: python $T\preprocess_tdx_csx.py "path\to\raw.csx" --force

# [cSurvey] open <name>_pp.csx, then File > Save As

# KORAK 2 — the saved file -> <name>_lt.csx (spline linetypes, water brush, sign sizes)
python $T\fix_imported_linetypes.py $INTAKE --sb 1103 --force
#   or: python $T\fix_imported_linetypes.py "path\to\saved.csx" --force

# [cSurvey] open <name>_lt.csx, correct the sketch, save

# KORAK 3a — _lt -> <name>_lt_fin (entrance, depth label, scale bar, north arrow, A4 print setup)
python $T\nacrt_finish.py $INTAKE --sb 1103 --force            # shows the layout menu
#   --yes accepts the proposed layout; --layout N picks menu entry N; --dry-run writes nothing

# KORAK 3b — drive cSurvey headlessly -> <name>_plan.pdf, <name>_profile.pdf, <name>_dimenzije.json
python $T\csurvey_driver.py finish $INTAKE --sb 1103
#   needs cSurvey in C:\csurvey64 (or CSURVEY_DIR in .env) and the "Microsoft Print to PDF" printer

# KORAK 3c — compose plan + profile onto the title block -> SB_1103_nacrt.pdf in the intake leaf
cavedossier nacrt 1103                 # --local keeps the output in runs/ and does not deliver it to Drive; --offline makes no network calls
```

If a drawing doesn't fit its box on the page, 3c refuses and prints the
overlap in millimetres. Re-run 3a with `--layout N`, then 3b and 3c again.
If 3b can't run cSurvey, open `_lt_fin` in cSurvey and print the plan and the
profile separately to *Microsoft Print to PDF*. Don't change the print settings.
Diagnostics: `python $T\inspect_survey.py <file>` gives read-only stats for any
`.csz`/`.csx`; `csurvey_driver.py info|recalc|dimensions <file>` runs single
cSurvey actions. The step-by-step procedure is in
[production/tdx-processing-protocol.md](production/tdx-processing-protocol.md).

The operator-facing drag-and-drop `.bat` kit that drives `production/tools/`
is generated from [`prod/csx_templates/`](../../prod/csx_templates/) — see
[`prod/README.md`](../../prod/README.md).

Everything below is the original feature charter, unchanged.

---

# csx-to-survey-pipeline — TopoDroid → finished-map pipeline

> **⚠ App source referenced by this feature lives in the read-only `cSurvey/` reference clone
> (`../../../cSurvey`, a sibling repo in the multi-root workspace), not in this repo.**
> Citations written `cSurvey/cSurveyPC/...` resolve against that clone; bare zone paths
> (`reference/…`, `production/…`, `projects/…`, …) are relative to this feature's root.
> This feature was migrated 2026-08-16 from `cSurvey/dev/` (formerly the fork's R&D workspace);
> historical logs (`sessions/`, `log.md`, `RUNLOG.md`) were kept verbatim, so paths inside them
> may still use the old `dev/...` and bare `cSurveyPC/...` forms.

This folder is everything the fork produces *around* cSurvey: the knowledge, the tools, the
work-in-progress, and the record of what was done. It is organized so that at any moment — human
or AI, fresh session or deep in a task — you can answer four questions without archaeology:

- **How does cSurvey work?** → `reference/`
- **What do we run on a real survey?** → `production/`
- **What are we building right now, and how does it work?** → `projects/`
- **Why did we decide to do it this way?** → `decisions/`

New here? Read this file, then open [projects/README.md](projects/README.md) (the work board) and
[decisions/roadmap-decisions.md](decisions/roadmap-decisions.md) (current project state).

---

## The four zones

| Zone | Question it answers | What lives here | Lifespan |
|---|---|---|---|
| **`reference/`** | *How does cSurvey work?* | Architecture docs about the **software** — data model, calculation, drawing, rendering, exports, UI, TopoDroid internals. `path:line`-grounded, adversarially checked. | Stable; changes only when we learn something new about cSurvey. |
| **`production/`** | *What do we run routinely?* | The **operational toolkit** we run on every survey — pre/post-processing scripts (`tools/`), the standing SOP (`tdx-processing-protocol.md`), reusable `methods/`, and the config/knowledge those depend on. | Stable; the "shipped" surface. |
| **`projects/`** | *What are we building, and how does it work?* | The **dev loop** — one folder per work item (`NNNN-slug/`), holding its brief, its implementation log, its instrumented runs, and its findings. This is where **R&D happens**. | In flight → closed. Each folder is a permanent record. |
| **`decisions/`** | *Why this way?* | The **portfolio-strategy log** — dated, high-altitude decisions and the findings behind them (which pipeline, why, what's verified). | Append-only history. |

Supporting folders: **`sessions/`** (chronological session journal — see Logging), **`backlog/`**
(parked ideas), **`literature/`** and **`example/`** (external manuals + sample surveys, both
gitignored).

### The one idea that keeps it clean

**R&D is a *phase*; Production and Reference are *destinations*.** They are not three peer buckets you
sort a file into. Work is *born* in a `projects/` folder (a brief), matures through research and
validation *inside* that folder, and on success **promotes its outputs outward**:

```
        ┌──────────────────── projects/NNNN-slug/  (R&D in flight) ─────────────────────┐
        │   brief  →  research  →  propose ⇄ iterate with user  →  validate             │
        └───────────────────────────────────┬───────────────────────────────────────────┘
                              on close, promote the durable outputs:
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                    ▼
         reference/  (durable "how it works")            production/  (routines we now run)
                                     │
                                     ▼
                    decisions/  (the strategic "why", if the call was load-bearing)
```

So "is this R&D or production?" is never ambiguous: if it's still being figured out, it's a project;
once it's proven and we run it for real, it's in production; once it's settled knowledge about
cSurvey, it's in reference. Nothing lingers half-classified.

---

## The dev loop (how a piece of work moves)

Every non-trivial task follows the same arc. It maps 1:1 to the states a brief moves through:

| Loop step | Brief `status` | What happens | Where it's recorded |
|---|---|---|---|
| **State the problem** | `draft` | Write the brief: problem, why it matters, what "done" means. | `projects/NNNN/brief.md` |
| **Research it** | `research` | Investigate the code/data; produce findings. Instrumented runs go under `runs/`. | `brief.md` + `log.md` + `runs/` |
| **Propose & iterate** | `proposal` | Put options to the user; converge on an approach. | `log.md` (decisions), `brief.md` (chosen approach) |
| **Validate** | `validation` | Build it; test on real data; get user acceptance. | `log.md` + `runs/` |
| **Productionize** | `closed` | Promote tools→`production/`, knowledge→`reference/`, strategy→`decisions/`. Flip the brief to `closed` with a one-line pointer to what it produced. | everywhere the outputs landed |

Parked mid-flight → `parked` (say why, in the log). The point of the states is that **anyone can read
a brief's header and know exactly where the work stands** — no need to reconstruct it from chat.

To **start a new project**: copy `projects/_templates/` into `projects/NNNN-slug/`, fill in `brief.md`,
add a row to [projects/README.md](projects/README.md). See that file for the numbering convention.

---

## Logging — three tiers, deliberately non-overlapping

So we always know *what has been done and how successfully*, without one log becoming a dumping ground:

| Tier | File | Scope | When you write it | Answers |
|---|---|---|---|---|
| **Strategy** | `decisions/roadmap-decisions.md` | the whole fork | rarely — only on a load-bearing decision | "Why are we targeting Pipeline A?" |
| **Implementation** | `projects/NNNN/log.md` | one work item | per work chunk, as you go | "What was built/tried/decided in *this* project, and did it work?" |
| **Session** | `sessions/SESSIONS.md` | one working session, across projects | **at the end of every session** | "What did today touch, and how did it go?" |

Rule of thumb: a **decision that changes the plan** → decisions log; **progress on a task** → that
project's log; **a chronological "what happened today" for continuity across agents** → the session
journal. When in doubt, the project log is the default home; the session journal just links to it.

---

## Map: where does a thing go?

| I have… | It goes in… |
|---|---|
| a new fact about how cSurvey behaves internally | `reference/` (the relevant doc; add a `path:line` cite) |
| a script I'll run on every survey | `production/tools/` + a line in `production/README.md` |
| a step-by-step operating procedure | `production/` (an SOP) or `production/methods/` (a reusable method) |
| a new problem to solve | a new `projects/NNNN-slug/` (start from `_templates/`) |
| a one-off experiment script or its output | inside its project's `runs/<dated>/` or `findings/` |
| a strategic decision + its rationale | `decisions/roadmap-decisions.md` |
| an idea for later | `backlog/` |
| "what I did this session" | append to `sessions/SESSIONS.md` |
