---
name: theme-round
description: One tuning round of the 3N symbol themes (project 0007) — the user's feedback on the printed mockup and/or a re-exported Illustrator drawing → theme.json edits → one command that re-splits, applies boja + crno-bijelo, prints with cSurvey and makes comparison sheets → show the user the crops. Use whenever the user comments on how a sign, line or area looks ("more gaps", "denser", "should sit on the line", "make it blue", "dashed"), says they changed/re-exported the drawing (drawing_catalogue.svg), or asks for another round/print of the themes. Not for building theme features (code) — that is /feature-dev.
---

# /theme-round [feedback]

Iterating on the artwork takes many short rounds. Each round must be **minutes, not an
agent run**: do it directly in this session, no subagents. Everything slow is cached by
`theme_round.py` (≈15 s per round).

Paths are relative to `stages/3N-nacrt/` unless they start with `.claude/`.

| What | Where |
|---|---|
| Runner | `production/tools/theme_round.py` |
| Feedback → field table | `production/tools/theme_tuning_cheatsheet.md` (**read it every round**; the limits section too) |
| Themes | `production/themes/boja/theme.json` (edit this), `crno-bijelo/theme.json` (only B/W-specific overrides) |
| Schema | `production/themes/README.md` |
| The user's drawing | `projects/0007-symbol-themes/drawing_catalogue.svg` (Illustrator export) |
| Rounds | `projects/0007-symbol-themes/runs/<date>-<label>/` |
| Project record | `projects/0007-symbol-themes/brief.md`, `log.md` |

## 1 · Sort the feedback (no tools yet)

Split the user's message into items and classify each one:

- **Value**: a `theme.json` change (spacing, density, scale, alignment, dash, colour, pattern). Look the
  phrase up in the cheatsheet.
- **Artwork**: the user re-exported, or the fix needs a redraw (shape wrong, a tile too big, a stroke-only
  piece). → `--split`, or tell the user exactly what to redraw.
- **B/W only**: goes in `crno-bijelo/theme.json` as an override. Everything else goes in `boja`, which
  crno-bijelo inherits.
- **Limit**: the cheatsheet's "Limits" says no field fixes it (meander on curves, first unit starts late,
  overlaps print white…). Say so in one line and offer the nearest alternative. Don't burn rounds on it.
- **Ambiguous**: if two readings give different results (e.g. "gap" = between symbols, or between line
  and symbol), pick the likelier one, **say which reading you took** in the reply, and do it. Asking first
  costs a round trip; a wrong guess costs one 15 s round.

## 2 · Artwork check (only if the drawing changed)

```
python production/tools/theme_round.py <label> --split --no-print
```

Read the split summary. **Stop and tell the user** on these, before printing anything:

- unnamed groups (`<Group>`, `_x3C_Group…`): name the piece and its layer. This usually happens after
  *Outline Stroke*, which wraps the result in a new unnamed group;
- duplicate names;
- a stroke-only piece in a sign (it is invisible with the pen off) → outline the strokes;
- new keys with no `theme.json` entry → add an entry (colour from the summary, defaults otherwise).

Artwork rules to repeat to the user when they redraw (from the cheatsheet):

- one named group per piece, on layer `Znakovi` / `Linije` / `Površine`; notes go on a `_` layer;
- fills only (*Outline Stroke*);
- no invisible padding shapes;
- line units are one repeating piece without the baseline;
- area tiles are small sparse clusters;
- arrows drawn pointing up;
- one colour (plus white) per piece.

## 3 · Edit and run

1. Edit `theme.json` with the smallest change per item. Add a `_note` on the entry that says what the user
   asked for, e.g. `"_note": "more gaps (user, r9)"`. Never touch pieces the user didn't mention.
2. `python production/tools/themes.py check`, which must say OK.
3. Run the round, focusing on what changed:
   ```
   python production/tools/theme_round.py <rN-short-label> [--split] --focus <key>,<key>[,...] [--seeds 2]
   ```
   - Label rounds `r9`, `r10`… (continue from the last folder in `runs/`), plus a 1–2 word hint.
   - Use `--seeds 2` when area density changed, so the evenness is judged on more than one random layout.
   - Use `--fresh-mockup` only if the cache seems stale. It rebuilds automatically when keys or generators change.

## 4 · Look before you show

**Read** the focus crops `theme-mockup_detalj_*.png` and `pregled.png` yourself, at full resolution.
The overview sheets downscale and hide thin lines; a missing base line was a false alarm once for that
reason. For each item, decide whether it visibly holds.

- **Holds:** go to 5.
- **Doesn't hold:** adjust and re-run **at most twice** without asking. If it still fails, report what
  you tried and the trade-off.

## 5 · Reply to the user (short)

- One line per feedback item: what changed (`field old → new`), and ✅ visible / ⚠ trade-off.
- The crop path(s) to open, linked: the `pregled.png` first, then focus crops.
- Anything that needs their hand: a redraw, a naming fix, or a choice between two looks.
- No restating the whole history and no next-step essays.

## 6 · Record (every round, 1 minute)

- Fill the "Feedback → change" table in the round's `RUNLOG.md`. The runner writes everything else.
- Append one line to `projects/0007-symbol-themes/log.md` under the latest dated entry, or start a dated
  entry for the first round of the day.
- Decisions that change a rule go to the brief §3.8, or the decision record if they're cross-cutting.
  Examples: "arrows are drawn up", "labels stay labels".

## 7 · End of an iteration session

```
python -m pytest stages/3N-nacrt -q
python .claude/skills/csurvey-defaults/check_defaults.py
python tools/pipeline_doctor.py
```

`tests/test_themes.py` asserts some starter-theme values. If a tuning change trips it, update the
assertion to the new value; don't revert the user's change. Then `/wrap-up`.

Themes reach operators only through the csx kit (T5) and `/publish`. A tuning round never publishes.

## Don'ts

- Don't spawn agents for a round. Everything here is a 15 s command.
- Don't edit the SVGs under `themes/boja/` by hand. They come from `--split`. Exception: a hand-built unit
  like `lines/ceiling-step@T.svg` (documented in the themes README) survives splits because split never
  deletes files.
- Don't edit `../cSurvey` or `C:\csurvey64`. The runner uses its own DTD-free copy for imports.
- Don't change mappings (`tdx-mapping.json`) here. That is `/csurvey-defaults`.
