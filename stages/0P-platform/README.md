# 0P — Platform

**The shared spine.** Not a pipeline step: the code every other stage stands on.

## What lives here

| Module | What it is |
|---|---|
| `core/config.py` | `Settings` — `config.yaml` + `.env` resolved into one frozen object. Also the LIVE/FALLBACK/SANDBOX workbook switch. |
| `core/paths.py` | **The anchor.** `workspace_root()` finds the workspace by walking up for `.cavedossier-workspace`; `repo_root()` is dev-only and returns `None` in prod. |
| `core/normalization.py` | Diacritic folding, whitespace cleanup, optional-float parsing. Imported by 21 modules. |
| `core/matching.py` | The weighted-evidence matcher: a free-form folder or filename → an SB row. |
| `core/people.py`, `core/person_aliases.py` | Split an author cell into people; generate the abbreviation spellings (`L.Kukuljan` ↔ `Lovel Kukuljan`). |
| `core/societies.py` (+ `societies.json`, `crospeleo_organizations.json`) | **Registar udruga** — every caving society, its CroSpeleo name, aliases and short form; resolve a written name, shorten a list to fit. `cavedossier societies`. See [Registar udruga](#registar-udruga--cavedossier-societies). |
| `cli/` | The single `argparse` entry point. Every `cavedossier` subcommand is parsed and dispatched here; the work happens in the stage modules. |
| `gui/` | The local dashboard, `cavedossier gui` — the current cave's workflow (done / next / stale), every stage's commands behind buttons, "open SB", photos, the dossier. A mockup of the future GUI that already runs things. See [The dashboard](#the-dashboard--cavedossier-gui). |

## The dashboard — `cavedossier gui`

```powershell
cavedossier gui                 # starts http://127.0.0.1:8765/ and opens it in the browser
cavedossier gui --port 8800     # another port (the next free one up to +19 is taken)
cavedossier gui --no-browser    # just serve; open the URL yourself
```

One page, in Croatian, with a tab per stage. The tabs follow the **working order
for one cave** rather than the label digits: Baza (1T, 2B) → Objekt (4G, 4I, 4O,
3N, 4S, 4F) → Provjera i predaja (5O, 5D, 6P).

- **Otvori SB** in the top bar opens the live Speleo baza in Excel. The SB card
  lists every `!Speleo_baza_SUE_v*.xlsm` on Drive and warns when a newer one
  exists than `config.yaml` points at.
- **Objekt**: pick the cave you are working on. The picker opens with every
  cave that has an `SB_<broj>_…` folder under `!Za digitalizirat` (📷 = photos
  queued), and typing searches **all of SB** too (name, synonym, SUE number or
  Redni broj, diacritics ignored), so a cave with no folder yet can be picked
  and started with ★ *Novi objekt*. Every command on every tab then uses that
  number. The SB list is read once (`/api/sb-index`, a few seconds) and again
  on **Osvježi**.
- **Pregled → tijek objekta** is the cave's work as a dependency graph
  (`gui/workflow.py`). Every step is **gotovo** (green), **sljedeći** (gold,
  "SADA"), **zastarjelo** (amber: an input changed after the output was made,
  so redo it), or waiting. A button runs the step directly. Two examples:
  the OSZ filled after the Nacrt was composed turns KORAK 3c amber, and a
  survey measured after the OSZ was made turns "OSZ ← duljina i dubina" gold.
  The 3N tab colours its KORAK cards the same way.
- **Pokreni** runs a command. Output streams into the **Ispis** panel at the
  bottom; when a tool asks something (the 3N file menu, the layout menu) you
  answer in the box under the output. Every run is logged to `runs/gui/`.
- **3N › KORAK 3a** draws the layout menu as A4 sheets: the title block, and
  each proposal's plan and profile boxes with the cave's walls in them,
  computed by a dry run of `nacrt_finish.py --layouts-json` on the chosen
  `_postp` file (well under a second, cached until the file changes). Clicking
  a sheet puts its number in `--layout`, and a new file starts from the
  proposal (1), so the run never stops to ask. The dry run's warnings (no
  entrance sign, origin mismatch …) are listed under the sheets.
- Runs that only read go on one click. Anything that writes to Drive, to the
  cave's folder or to georef.hr asks first (orange **Pokreni…**). Ticking
  `--dry-run` / `--local` makes it a plain run again. **Ne pitaj više** in
  that dialog turns the question off for every action and ★ recipe, and it
  stays off after a reload (the browser's localStorage). Pregled then shows
  **Uključi ponovno** to turn it back on. Deleting a photo always asks.
- **OSZ gaps on Pregled.** Each cave view also checks the zapisnik's obligatory
  fields (4O `osz provjera`): the empty ones are listed under **OSZ popunjen
  (Word)**, those the nacrt's sastavnica needs first. One of those missing keeps
  the step open, and **KORAK 3c** warns that it would print a `?` for them.
- **3N › Mapiranje simbola** draws the TopoDroid → cSurvey mapping for the
  current cave (TopoDroid's speleo and "speleo 2" sets by default, every set on
  request; a filter lists what would arrive without a proper cSurvey sign).
  Each TopoDroid tool is shown in its own colours, and next to it
  the cSurvey glyph it becomes, picked from a list. Below that are the
  centerline (colour pickers, widths and styles, with a live preview), sign and
  label sizes, and the import switches. Every part says which KORAK it takes
  effect in. **Spremi** writes only the difference from the shared
  `tdx-mapping.json` into the cave's folder as `tdx-mapping-objekt.json`, so
  KORAK 1 and 2 apply it to that cave alone. **Vrati na zadano** deletes that
  file. When `_prep`/`_postp` are older than the saved override, the page says
  which KORAK to redo. See
  [csurvey-settings.md](../3N-nacrt/production/csurvey-settings.md#per-cave-mapping-the-dashboards-mapiranje-page).
- **4F** shows the cave's photos as a gallery (Pillow thumbnails cached in
  `runs/gui/thumbs`; without Pillow the originals are served). **Obriši**
  sends a photo to the bin. On the Drive that means the Google Drive trash
  (30 days), on a local disk the Windows Recycle Bin. Only photos in the
  current cave's folder can be deleted, and always after a confirmation.
- **Fotografije u redu čekanja.** Nobody browses
  `!!Fotografije ulaza za istražit`, so the page does. Pregled lists every
  cave with photos waiting there, the cave picker marks them 📷, the cave's
  workflow makes "pull them in" its photo step, and 4F shows them in a
  gallery of their own with one **Povuci u mapu objekta** button
  (`photos pull-staged --apply`, after a confirm). Photos are shown whole:
  portrait shots are letterboxed, never cropped.
- **4I** shows the cave's map excerpt and its `!georef_zapisi.csv` row
  (georef.hr point id, HTRS coordinates, date); click to enlarge.
- **Dokumentacija** in the sidebar opens the current stage's README and the
  project docs (prod upute, ARCHITECTURE, STATUS, commands, decisions) in an
  in-page viewer; links between docs stay inside it. Dev only: prod has no
  repo, and the viewer says so.
- **5D Dosje** draws `report` as the two gates: blockers, warnings, and the
  rules still waiting on a source (folded). **5O** shows the cave's people and
  their izjave from the same data; `people check --broj` is the command form.
- A Word/Excel owner file (`~$…`) in the cave's folder is reported as "open
  in Word", since steps that rewrite that file cannot replace it while it is
  open.
- **★ Brze radnje** (sidebar, under Pregled) runs several steps for the
  current cave as **one job with one confirmation**. *Novi objekt u jednom
  potezu*: create the folder → map excerpt → OSZ prefill → pull queued photos
  (only if any) → process photos. *Spoji nakon izmjere*: OSZ prefill → KORAK
  3c. *Provjeri objekt*: SB row, dosje, izjave (read-only). Every step can be
  unticked. Each step skips work that already exists, so a chain can be
  re-run. A failing step stops the chain, unless it is marked ↷ (karta,
  photos: the OSZ works without them).
- **Kopiraj** gives the same command for the terminal. 3N commands use `$T`,
  as in the [3N README](../3N-nacrt/README.md).
- **cSurvey** buttons open a survey in cSurvey, found as: `CSURVEY_DIR` from
  `.env`, then the shared copy on the Drive
  (`!!!Digitalizacija/Software/csurvey64`), then `C:\csurvey64`.

How it is built, for whoever turns it into the real GUI:

| File | Role |
|---|---|
| `gui/catalog.py` | **The table of every action**: stage, Croatian label, argv template (`{broj}`, `{file}`, `{query}`), options, what it writes. The page draws its buttons from this, and the server builds argv only from this. A new button is one `Action` entry. Also the stage list with its nav groups, and the ★ `RECIPES` (fast actions: ordered `RecipeStep`s over catalog actions). |
| `gui/workflow.py` | **The per-cave dependency graph**: each step's output files, input files and status (done / stale / todo / blocked …), and the catalog action that (re)makes it. Reads file names, mtimes, the OSZ's v10 cells and the dimensions JSON; writes nothing. |
| `gui/state.py` | Read-only view of the machine: settings, SB versions, Drive dirs, caves in work, a cave's files classified by name, open-document locks. Fail-soft: a missing Drive is a note on the page. |
| `gui/mapping.py` | The 3N mapping page: the shared mapping, a cave's override, the pictures (`tdx-mapping-catalog.json`). Loads 3N's pure-data `tdx_mapping.py` from the tools folder by path, so the page and KORAK 1/2 merge the same way; validates and writes the override. Runs no tool. |
| `gui/layouts.py` | KORAK 3a's sheet thumbnails: runs `nacrt_finish.py --layouts-json` (a dry run, writes nothing) as a script, so the picture and the run read the same menu; caches per (path, mtime, size). |
| `gui/media.py` | Photo thumbnails and the recoverable delete (shell "allow undo"). |
| `gui/jobs.py` | One subprocess per run, with stdin open for answers, output polled by offset, `taskkill /T` to stop it. `start_sequence` runs a recipe's steps one after another as a single job (stop on exit 2+ unless `keep_going`; 0/1 are the CLI's "done / not ready"). |
| `gui/server.py` | `http.server` on 127.0.0.1 with a JSON API: `/api/state`, `/caves`, `/cave/<broj>` (files + workflow), `/dossier/<broj>`, `/doc?path=` (repo Markdown), `/catalog`, `/run`, `/recipe`, `/job/<id>`, `/open`, `/delete`, `/mapping/<broj>` (GET, POST, POST `…/reset`), `/mapping-catalog`, `/societies` (the registar udruga for the Udruge page), `/layouts?broj=&path=` (KORAK 3a's sheets; only the cave's own `_postp` files), and `/thumb` for images (photos, queued photos, the map excerpt). `/caves` also carries the photo-queue counts. Every call needs the random token the page was served with (`/thumb` takes it as `?t=`, because an `<img>` cannot send a header). Opening is limited to paths under Drive, the workspace and the repo. The port is bound exclusively, so a second dashboard moves to the next port instead of silently sharing one. |
| `gui/static/` | `index.html` (with the SVG icon set), `app.css` (the gold `#EBAF01` palette, light and dark), `app.js`, `mapping.js` (the 3N mapping page). Plain JS, no build step. |

Only standard library in the base install; Pillow (the `photos` extra) makes
the gallery faster, and lxml (the `osz` extra) lets the workflow read the OSZ.
Why it is built this way:
[design decisions §The dashboard](../../docs/design-decisions.md#the-dashboard--cavedossier-gui-2026-09-24).

## Registar udruga — `cavedossier societies`

Society names turn up everywhere — the OSZ's *Istražile udruge*, the Nacrt's
*Istražili*, SB, izjave — in every spelling from `Speleološka udruga
"Estavela", Kastav` to `SUE`. The registry resolves any of them to one society
and knows its short form for tight spaces.

| File | What | Who edits it |
|---|---|---|
| [`crospeleo_organizations.json`](src/cave_dossier/core/crospeleo_organizations.json) | **Ground truth**: every organisation CroSpeleo credits, canonical name + how often. 226 from the March 2026 export. | Nobody — `societies build` regenerates it |
| [`societies.json`](src/cave_dossier/core/societies.json) | Curated overlay, joined on the CroSpeleo canonical: working name (`SO HPD Mosor`), `short` (`SOM`), `aliases` (including wrong spellings OSZs really carry), HPS plaque codes. Seeded from crospeleo-automation's curated registry + the HPS plaque list. | By hand |

A CroSpeleo organisation with no overlay entry still resolves: its working
name is derived from the canonical (`Speleološko društvo "Pauk", Fužine` → `SD
Pauk`). Lookup is exact on a diacritic/case/punctuation-folded key — never
fuzzy.

```powershell
cavedossier societies find "SKOL, SO Sv. Jakov Bitelić"   # each society, its forms, the shorter renderings
cavedossier societies list [--all]                        # curated societies (--all: every CroSpeleo one)
cavedossier societies check                               # conflicts, shared short forms, canonicals CroSpeleo lacks
cavedossier societies build "C:\…\CroSpeleo - objekti.xlsx"  # regenerate the ground truth from a fresh export
```

**On the dashboard: Udruge**, under Osobe in the sidebar: the same registry as
a table — short form, working name and seat, CroSpeleo name, other spellings,
plaque codes — with a search box over every spelling (diacritic- and
punctuation-insensitive: `sv jakov`, `biteli`, `051`, `speleo 8`). The curated
societies show by default; a tick adds the other CroSpeleo organisations.
Read-only.

**Adding or fixing a society** — edit `societies.json`: put the exact
CroSpeleo `canonical` (copy it from `societies list --all`), then `name`,
`short`, `aliases`; run `societies check` and the tests. Used today by 4S's
Istražili cell ([4S README](../4S-sastavnica/README.md)). Why it is built this
way: [design decisions §Registar udruga](../../docs/design-decisions.md#registar-udruga-crospeleo-is-the-ground-truth-2026-10-04).

## Why this stage exists

It is not a design preference — it is what the dependency graph says.
`core.config` is imported by 24 modules and `core.normalization` by 21, and
the CLI dispatches all eleven other stages. Forcing that into any one
substage would make that substage a hidden dependency of every other.

## The three roots, and why they are separate

`core/paths.py` exists because the old `FEATURE_ROOT = parents[3]` conflated
three different things and broke whenever the package moved:

- **workspace** — `config.yaml`, `.env`, `data/`, `runs/`, `sb-sync/`. The repo
  root in dev; `%LOCALAPPDATA%\CaveDossier\v<X>` in prod. One marker file finds
  both.
- **package assets** — the OSZ template, `selectors.yaml`, `pristupi.yaml`.
  These use neither root: each module resolves its own with
  `Path(__file__).parent`, so the asset travels with its code.
- **repo** — dev-only, for reaching `../crospeleo-automation`. `None` in prod,
  so callers must fail soft.

## Where things are

- Code: [`src/cave_dossier/core/`](src/cave_dossier/core/), [`src/cave_dossier/cli/`](src/cave_dossier/cli/), [`src/cave_dossier/gui/`](src/cave_dossier/gui/)
- Cross-cutting records: [`docs/PORTING.md`](docs/PORTING.md) (every file copied from
  `../crospeleo-automation`), [`docs/EXCEL_WORKBOOK_SAFETY.md`](docs/EXCEL_WORKBOOK_SAFETY.md)
  (why reads are openpyxl and writes are Excel COM only)
- Tests: [`tests/test_gui.py`](tests/test_gui.py), [`tests/test_societies.py`](tests/test_societies.py); the repo-root [`conftest.py`](../../conftest.py) and [`tests/fixtures/`](../../tests/fixtures/)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)
