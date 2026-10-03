---
name: csurvey-defaults
description: Change the SHARED default cSurvey settings the 3N kit applies for everyone — symbol/line/area mapping (TopoDroid → cSurvey, KORAK 1), centerline colours/widths/text, sign and label sizes, import switches (KORAK 2), and cSurvey app settings in the registry such as pen smoothing (KORAK 0). Use whenever the user says "set X to Y by default", "map <symbol> to …", "make the centerline/station numbers …", "always have … in cSurvey", or names a cSurvey option to predefine. Not for one cave only (that is the dashboard's 3N › Mapiranje page).
---

# /csurvey-defaults [what to change]

The user names a setting and a value; this skill turns that into the right
one-line JSON edit, checks it, documents it and commits it, with no context to
rebuild. Background, if ever needed:
[stages/3N-nacrt/production/csurvey-settings.md](../../../stages/3N-nacrt/production/csurvey-settings.md).

## 0 · Scope (decide first, ask only if unclear)

- **Shared default** = every cave from now on → this skill.
- **One cave only** → don't edit JSON. Tell the user: dashboard › 3N ›
  Mapiranje simbola, or that cave's `SB_<broj>_…/tdx-mapping-objekt.json`.
- **"Make cave N's override the default"** → read that cave's
  `tdx-mapping-objekt.json`, apply its entries here (a `null` there means
  "remove the entry"), then the user may delete the cave file.

## 1 · Which file (the whole decision)

All paths under `stages/3N-nacrt/production/tools/`.

| The user wants… | Kind | Edit | Takes effect |
|---|---|---|---|
| a TopoDroid symbol/line/area to become a cSurvey sign/line/area, a text label, or be left alone | file, KORAK 1 | `tdx-mapping.json` › `points` / `lines` / `areas` | new `_pp` (KORAK 1, re-import, KORAK 2) |
| centerline (polygon) colour, width, style; station symbol/size/colour; station-number or note text scale/colour; splay, LRUD, translation line, surface profile pens | file, KORAK 2 | `tdx-mapping.json` › `postimport.centerline` | next KORAK 2 |
| any other survey-wide Properties value | file, KORAK 2 | `tdx-mapping.json` › `postimport.designproperties` | next KORAK 2 |
| size of a sign (entrance, stalactite…) or of a text label | file, KORAK 2 | `postimport.sign_sizes` / `label_sizes` | next KORAK 2 |
| splines for imported lines, non-standard water brush; line-subtype / `-area` stripping | switch | `postimport.spline_linetypes` / `nonstandard_water`; `generic.*` | KORAK 2 / KORAK 1 |
| a cSurvey ribbon/options toggle (pen smoothing, rulers, grid, quality…) — anything cSurvey keeps per computer | app, KORAK 0 | `csurvey-app-settings.json` › `settings` | each computer re-runs KORAK 0 (KORAK 2 warns) |

Prefer a file setting when cSurvey offers both: it reaches every computer with no priming.

## 2 · Value formats (copy these)

**Mapping entries** (key = TopoDroid `th_name`, `:` not `=`, e.g. `wall:blocks`; the `//` notes are not part of the file):
```jsonc
"bat":          { "label": "šišmiš" }            // points only: becomes a text label
"clay":         { "to": "sand" }                  // → cSurvey target
"water-drip":   { "to": "water-flow", "orientation": 180 }   // points: fixed angle
"chimney":      { "to": "overhang", "reverse": true }        // lines: flip decoration side
"user":         { "leave": true }                 // keep, silence the warning
```
To remove a default mapping, delete the key (natural import behaviour returns).

**Targets.** Lines: `wall, wall:presumed, presumed, border, overhang, pit, chimney, slope, floor-meander, ceiling-meander, rock-border, water-flow, section`.
Areas: `water, sand, clay, debris, blocks, pebbles`.
Points: cSurvey sign names, lower case, hyphens optional — list them, and look up a TopoDroid symbol, with:
```powershell
python -c "import json;c=json.load(open('stages/3N-nacrt/production/tools/tdx-mapping-catalog.json',encoding='utf-8'));print(', '.join(t['to'] for t in c['targets']['point']))"
python -c "import json,sys;c=json.load(open('stages/3N-nacrt/production/tools/tdx-mapping-catalog.json',encoding='utf-8'));[print(r['kind'],r['name'],r['set'],r['natural']) for r in c['tdx'] if sys.argv[1] in r['name']]" bat
```
(`set: extra` is the user's "speleo 2" palette.)

**Centerline keys** (`postimport.centerline`, numbers only):
| Key | Meaning | Value |
|---|---|---|
| `PlotPenColor` / `PlotPointColor` / `PlotTextColor` / `PlotNoteTextColor` / `PlotTranslationLinePenColor` / `SurfaceProfilePenColor` | shots / stations / station numbers / notes / translation line / surface profile colour | signed ARGB int |
| `PlotCenterlineForceColor` | use PlotPenColor instead of segment colours | 0/1 |
| `PlotPenWidth`, `PlotSelectedPenWidth`, `PlotSplayPenWidth`, `PlotSplaySelectedPenWidth`, `PlotLRUDPenWidth`, `PlotLRUDSelectedPenWidth`, `PlotTranslationLinePenWidth`, `SurfaceProfilePenWidth`, `SurfaceProfileSelectedPenWidth` | widths | number |
| `PlotPenStyle`, `PlotSplayPenStyle`, `PlotLRUDPenStyle`, `PlotTranslationLinePenStyle`, `SurfaceProfilePenStyle` | style | 0 solid, 1 dashed, 2 dotted |
| `PlotPointSize`, `PlotSelectedPointSize` | station size | number |
| `PlotPointSymbol` | station symbol | combo index + 1 (7 = triangle) |
| `PlotTextScaleFactor` / `PlotNoteTextScaleFactor` | station-number / note text scale | number (cSurvey defaults 1 / 0.5) |
| `PlotSplayCrossScale`, `PlotCenterlineVector` | splay cross size; vector centerline | number; 0/1 |

The full list with types is `CENTERLINE_TYPES` in `fix_imported_linetypes.py`.
Colour → ARGB: `python -c "print(int('ff'+'FF0000',16)-(1<<32))"` (red → -65536; replace `FF0000` with the RGB hex).

**designproperties:** `"Key": {"type": "single|double|decimal|integer|long|int32|color|boolean|string", "value": …}`, typed as cSurvey writes it. Fonts are nested elements → need code; say so.

**Sizes:** `default, verysmall, small, medium, large, verylarge`. Sign names = `SIGN_VALUES` keys in `fix_imported_linetypes.py` (e.g. `entrance`, `air-draught`, `stalactite`).

**App settings** (`csurvey-app-settings.json`):
```json
"pens.smooting": { "value": "0", "ui": "Pen ribbon > Smoothing (toggle) - off", "why": "...(user decision YYYY-MM-DD)", "source": "cSurvey/cSurveyPC/frmMain2.vb:2680" }
```
Match the registry type cSurvey itself writes: JSON string → REG_SZ (decimals with a dot; cSurvey's toggles are the strings "0"/"1"), JSON integer → REG_DWORD. Check the type on this machine with `reg query "HKCU\Software\Cepelabs\cSurvey" /v <name>`.

## 3 · Unknown setting? Find its key (read-only, `../cSurvey` is never edited)

1. Find the caption in the UI resources, then the control, then where it's loaded:
   `git -C ../cSurvey grep -n -i "<caption words>" -- "cSurveyPC/*.resx"` → control name →
   `git -C ../cSurvey grep -n "<controlName>" -- "cSurveyPC/*.vb"`.
2. `My.Application.Settings.GetSetting("x.y")` → **app setting** (registry key `x.y`; its default is the second argument).
   `DesignProperties.GetValue("Key")` → **file setting** (`designproperties`).
3. When unsure, ask the user to change it in cSurvey and then compare: `reg query` before and after with cSurvey **closed**, or the saved `.csx`'s `<designproperties>`.

Cite the `path:line` in the entry's `source`, or in the commit message for file settings.

## 4 · Do it

1. Edit the JSON. Keep the formatting: 2-space indent, `ensure_ascii=False`. For `tdx-mapping.json`, `json.load` → change → `json.dumps(d, indent=2, ensure_ascii=False) + "\n"` round-trips byte-exactly.
2. `python .claude/skills/csurvey-defaults/check_defaults.py` must print `OK`.
3. `python -m pytest -q stages/3N-nacrt/tests prod/tests` must be green.
4. Docs, same commit:
   - `csurvey-settings.md` › "What is predefined now": update the row for the changed setting (app table or file table).
   - `docs/design-decisions.md`: add one dated line to the latest "3N … settings/mapping" section (what changed, why, the user's words).
   - Croatian text you write (labels, `ui`, notes) uses the en dash `–`, never `—`.
5. Commit on `main`: `3N defaults: <what> → <value>`, ending with the Co-Authored-By line.
6. Tell the user, briefly:
   - **what** changed and **where it takes effect** (the table in §1),
   - that operators get it only after **`/publish`** (the csx kit ships these files),
   - for an app setting: each computer must close cSurvey and re-run KORAK 0 (`csurvey_0_postavi_csurvey.bat`); KORAK 2 will warn until it does. Offer to run `python stages/3N-nacrt/production/tools/csurvey_app_settings.py apply` here (refuses while cSurvey is open),
   - for a symbol mapping: existing `_pp` files keep the old result; only a fresh KORAK 1 + import uses it.

Batch several changes into one commit when the user lists several. Never run `/publish` on your own.
