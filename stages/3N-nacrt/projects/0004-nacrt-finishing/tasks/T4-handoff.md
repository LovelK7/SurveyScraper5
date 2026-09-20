# T4 — handoff back to the orchestrating session

**Status: T4 is done and green, and the working tree is uncommitted by design.**
Written 2026-09-20 by the T4 session for whoever drives project 0004 next.
Prompt that produced it: [T4-choose-layout.md](T4-choose-layout.md). Brief: [../brief.md](../brief.md).
Log entries: the two `2026-09-20` blocks at the end of [../log.md](../log.md).

This file exists so the next session does not have to re-read the module to write the T1, T3 and
T5 prompts. Everything T1/T3 need to cite about the chooser is below, verbatim.

> **Amended by the research session, 2026-09-20 (later), after the user's review of this handoff:**
> (a) "one step" means **one rung of `SCALES`**, not a factor of 2 — `MAX_SCALE_RATIO` is gone,
> `MAX_STEP = 1` replaces it; (b) **1:400 is on the ladder**, `SCALES = (100, 200, 250, 300, 400, 500)`,
> written as cSurvey's custom entry `scalemode="99"` + `scale="400"` (`SCALEMODE[400] == 99`);
> (c) **alternatives are Pareto-pruned per arrangement** (`_dominated`) so the menu carries no
> pointless downscales. §2/§3/§6 below are otherwise still accurate; where they say "factor of 2"
> read "one rung". Worked examples that changed: 6 × 8 / 50 × 30 ⇒ `1:300/1:250`; SB 1103's menu
> is now the proposal plus one side-by-side alternative.

## Contents

- [1. What landed](#1-what-landed)
- [2. The API T1 and T3 will import](#2-the-api-t1-and-t3-will-import)
- [3. What the user changed after seeing it drawn](#3-what-the-user-changed-after-seeing-it-drawn)
- [4. Amendments already made to the brief](#4-amendments-already-made-to-the-brief)
- [5. What the orchestrator has to do](#5-what-the-orchestrator-has-to-do)
- [6. Paste-in facts for the T1 / T3 / T5 prompts](#6-paste-in-facts-for-the-t1--t3--t5-prompts)
- [7. Open, and deliberately not decided here](#7-open-and-deliberately-not-decided-here)

## 1. What landed

| File | State | What |
|---|---|---|
| `stages/3N-nacrt/production/tools/nacrt_layout.py` | **new** | the chooser + a preview CLI |
| `stages/3N-nacrt/tests/test_nacrt_layout.py` | **new** | 37 test cases (17 named + a 20-case invariant sweep) |
| `stages/3N-nacrt/production/tools/README.md` | modified | new *Nacrt finishing (KORAK 3)* section with the tool table |
| `stages/3N-nacrt/projects/0004-nacrt-finishing/brief.md` | modified | §3.1 row 6 and §3.4 amended — see [§4](#4-amendments-already-made-to-the-brief) |
| `stages/3N-nacrt/projects/0004-nacrt-finishing/log.md` | modified | two entries: the build, then the user review |

Verification, both re-runnable from the repo root:

```powershell
python -m pytest stages/3N-nacrt/tests -q     # 57 passed (35 of them from this task)
python tools/pipeline_doctor.py               # 0 fail - 3 warn (all pre-existing, historical links)
```

**Nothing is committed.** The T4 prompt said to leave the tree for review, and the auto-commit hook
will sweep it into a `chore(auto):` checkpoint on the next throttle tick — so the first thing the
orchestrator should decide is whether to commit it deliberately with a real message.

Visual review page (the user reviewed the proposals here and answered on it):
<https://claude.ai/code/artifact/d41299c3-e175-4393-83f4-59652cadf819> — nine cases drawn to scale
on the A4 sastavnica page, each with its ranked alternatives, and the four decisions at the foot.
It is a private artifact, not a repo file; the numbers in it are regenerated from
`choose_layout()`, so it goes stale if the rules move again.

## 2. The API T1 and T3 will import

`nacrt_layout.py` is stdlib-only and imports nothing from the repo, like every tool in that folder.
T1's `nacrt_finish.py` will sit in the same directory, so a plain `import nacrt_layout` works; a
caller from anywhere else does what the tests do — `sys.path.insert(0, <tools dir>)`.

```python
SCALES     = (100, 200, 250, 300, 500)
SCALEMODE  = {100: 1, 200: 2, 250: 3, 300: 4, 500: 5}   # _preview.* combo index
MAX_SCALE_RATIO = 2.0      # the two designs' denominators, at most one step apart
TALL_ASPECT     = 1.3      # height/width above which a design is "tall and narrow"
DRASTIC_RATIO   = 1.6      # profile.larger > 1.6 * plan.larger -> promote the plan

A4_PORTRAIT_MM  = (210.0, 297.0)
TITLE_BLOCK_MM  = Placement(x=14.06, y=17.49, width=88.75, height=35.4)
#   derived from the 4S cell table (outermost cells 39.85, 49.58 -> 291.43, 149.94 pt).
#   Usable band = 190 x 224.1 mm, from y 62.9 down to y 287.

BBox(width, height)                    # metres; .larger, .aspect
Placement(x, y, width, height)         # millimetres, origin top-left; .right, .bottom, .overlaps()
Layout(plan_scale, profile_scale, arrangement, profile, plan, mjerilo, note)
    .scalemodes -> (profile_scalemode, plan_scalemode)     # what _preview.* wants
    .key        -> (profile_scale, plan_scale, arrangement)

mjerilo(profile_scale, plan_scale) -> str   # "1:100" | "profil/tlocrt: 1:200/1:100"

choose_layout(plan, profile, *, page=A4_PORTRAIT_MM, title_block=TITLE_BLOCK_MM,
              margin_mm=10.0, gap_mm=10.0, max_alternatives=3)
    -> (Layout | None, [Layout], reason_str)
```

Contract notes that matter downstream:

- **Argument order is `(plan, profile)`** — alphabetical, not importance order. The profile is the
  primary *design*; the plan is the first *parameter*. Easy to swap by accident.
- `best is None` **only** when nothing fits at 1:500. Then the alternatives list is empty and
  `reason` is one Croatian line naming the 1:500 sizes in mm. The caller writes `scalemode="0"`
  (cSurvey fit-to-page) and warns that the printed scale is no longer true.
- Every `Placement` is millimetres from the page's top-left, rounded to 0.1 mm, and always inside
  the margins and below the title block. PyMuPDF's page origin for a portrait A4 is the same
  corner, so T3 converts with `pt = mm * 72 / 25.4` and nothing else.
- `note` is one line of Croatian for the operator menu; `mjerilo` is the string 4S prints in the
  Mjerilo cell.
- Alternatives are distinct by `.key` and never equal the best. `max_alternatives` caps the list.
- `choose_layout` raises `ValueError` on a non-positive bbox — that is a caller bug (an empty
  design), not an operator condition.

CLI, for a human sanity check without writing any file:

```powershell
python stages/3N-nacrt/production/tools/nacrt_layout.py <plan_w> <plan_h> <profile_w> <profile_h>
#   metres; prints the proposal plus alternatives as a numbered menu. Exit 0 fits, 1 no fit, 2 usage.
```

## 3. What the user changed after seeing it drawn

The first build followed brief §3.4 literally. The user reviewed nine proposals drawn on the real
A4 page and settled four things; all four are implemented, tested, and folded into the brief.

1. **The strip beside the sastavnica is out.** Pushing a narrow pair into the 87 mm band right of
   the title block bought a scale step and left half the sheet empty — rejected on sight. The free
   area is now only the full-width band below the block, so every drawing starts at `y 62.9`.
2. **1:250 is on the ladder** (`scalemode 3`). A 40 m profile misses 1:200 by 10 mm; 1:250 gives it
   160 mm instead of dropping to 1:300. 1:250 carries a profile up to 47.5 m, so 1:300 now only
   appears past that.
3. **At most one step between the two scales**, implemented as `MAX_SCALE_RATIO = 2.0` rather than
   adjacency in `SCALES`. A factor of 2 *is* one step of the ladder as it stood when the user
   decided it (1:200 with 1:100, the blessed common case) and keeps that meaning now that 1:250
   sits between the rungs, where counting index positions would not. `1:300/1:100` proposals are
   gone; a long profile pulls its plan up to `1:300/1:200`.
4. **Top-packed and centred stays.** Both drawings centre on the page axis, the profile's top edge
   is the top of the band, and the leftover page collects at the bottom.

Worked examples after the change — useful as T1/T3 fixtures:

| plan (m) | profile (m) | result |
|---|---|---|
| 4 × 9 | 5 × 10 | `1:100`, vertical — SB 1103, profile 50 × 100 at (80.0, 62.9), plan 40 × 90 at (85.0, 172.9) |
| 6 × 8 | 36 × 12 | `profil/tlocrt: 1:200/1:100`, vertical — the common case |
| 6 × 8 | 40 × 12 | `profil/tlocrt: 1:250/1:200`, vertical |
| 6 × 8 | 50 × 30 | `profil/tlocrt: 1:300/1:200`, vertical |
| 2 × 12 | 3 × 25 | `profil/tlocrt: 1:200/1:100`, **side_by_side** |
| 50 × 40 | 200 × 120 | `None` — "ni pri 1:500 ne stane na A4: profil 400x240 mm …" |

## 4. Amendments already made to the brief

Do not re-derive these; they are in `brief.md` with the date.

- **§3.1 row 6:** `scalemode ∈ {1,2,3,4,5}` (1:100 / 1:200 / **1:250** / 1:300 / 1:500).
- **§3.4 bullet 1:** the five-rung ladder, plus the factor-of-2 cap between the two designs.
- **§3.4 bullet 2:** the drawings live only in the band below the title block; centred and packed
  to the top.

§3.3 (the task list) is **not** amended — T1/T2/T3/T5 are unchanged in scope.

## 5. What the orchestrator has to do

1. **Review and commit the tree** (or reject it) — `git status` lists the five paths in [§1](#1-what-landed).
   One commit, message in the repo's style, e.g. `3N/0004: T4 — per-design scale + A4 arrangement chooser`.
2. **Write the T1 prompt** using [§6](#6-paste-in-facts-for-the-t1--t3--t5-prompts). T1 is the next
   task in the agreed order (T4 → T1 → T2 → T3 → T5) and is the one that consumes T4.
3. **Decide the bbox question before T1 starts** — see [§7](#7-open-and-deliberately-not-decided-here).
   T1 cannot call `choose_layout` without knowing where the two bboxes come from, and no session
   has yet established that the design bbox is readable from the XML alone. It is the single
   dependency that can stall T1 mid-task.
4. **Keep the review page in mind, not in the repo.** If the rules move again, regenerate it rather
   than editing it; if it goes stale and nobody needs it, drop the link from the log.

## 6. Paste-in facts for the T1 / T3 / T5 prompts

**T1 (`nacrt_finish.py`)** — add to the prompt:

> `production/tools/nacrt_layout.py` already exists (T4) and sits in the same folder, so
> `import nacrt_layout` works. Call
> `best, alternatives, reason = nacrt_layout.choose_layout(plan_bbox, profile_bbox)` — note the
> argument order — and write `best.scalemodes[0]` into `_preview.profile@scalemode` and
> `best.scalemodes[1]` into `_preview.plan@scalemode`, with `scale` set to the matching
> denominator. When `best is None`, write `scalemode="0"` (cSurvey fit-to-page) and print `reason`
> as a warning. Emit the chosen `best.mjerilo`, both scales and both `Placement`s into the
> dimensions/sidecar JSON so T3 can compose without recomputing. Offer the alternatives as a
> numbered console menu (Enter = accept the proposal) in the same style as
> `sb_select.choose_file`; `layout.note` is the menu line. Do not re-implement any layout rule —
> §3.4 lives in that module now.

**T3 (`compose_a4.py`)** — add to the prompt:

> Placements come from T4 via T1's JSON: millimetres, origin at the A4 top-left, already clear of
> the sastavnica title block and the 10 mm margins. Convert with `pt = mm * 72 / 25.4` and place
> the cropped ink bbox of each printed PDF at that rectangle **without scaling** — the page was
> printed at that exact denominator, so any scaling breaks the acceptance check (a 5 m bar measures
> 50 mm at 1:100). Render the Mjerilo cell from `best.mjerilo`, which is either `1:100` or
> `profil/tlocrt: 1:250/1:200`; the two-value form is what needs the custom 4S cell layout.

**T5 (operator kit)** — one line that is easy to miss:

> `prod/build_csx_kit.py` has an explicit `TOOLS = [...]` list of files copied into
> `csurvey_alati/`. Add `nacrt_layout.py` to it alongside `nacrt_finish.py`, or the KORAK 3
> launcher will `ImportError` on an operator machine while working fine in the repo.

## 7. Open, and deliberately not decided here

- **Where do the two bboxes come from?** T4 takes them as metres and does not care, which was the
  point — but nobody has yet proved they can be read from the `_lt` file without cSurvey.
  `inspect_survey.py` already reports a per-design **geometry digest (bounding box)**, so the most
  likely answer is "reuse that", in the design's own world units. The alternative is the
  speleometrics (`pl`, `pvr+nvr`) from T2's recalc, which are whole metres and describe the cave,
  not the *drawing* — the sketch usually spills past the centerline. **Recommendation:** have T1
  read the design bbox the way `inspect_survey.py` does, and have T1's `--dry-run` print both that
  and the `<sm>` numbers so the user can see the difference on SB 1103 before anything relies on it.
- **Every case but SB 1103 is synthetic.** The rules have only met one real cave. Expect the
  thresholds (`TALL_ASPECT` 1.3, `DRASTIC_RATIO` 1.6) to want tuning once T1 feeds real bboxes in;
  they are single constants at the top of the module for exactly that reason.
- **The factor-of-2 reading of "one step"** ([§3](#3-what-the-user-changed-after-seeing-it-drawn),
  item 3) was the T4 session's call, stated to the user and not contradicted. If the user meant the
  stricter reading — a 1:300 profile forcing the plan to 1:250 — it is a one-line change plus two
  test updates.
- **`example/finishing/SB_1103_golobreska_lt_{raw,finished}.csx`** is still the only real fixture
  pair, still gitignored, still the oracle for T1.
