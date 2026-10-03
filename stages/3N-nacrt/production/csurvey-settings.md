# cSurvey settings the 3N kit predefines

Whoever opens a survey in cSurvey while working on 3N should see the same
settings: a red centerline, pen smoothing off, and so on. cSurvey keeps
its settings in **two different places**. Each place gets its own way of
being set, and its own file in this folder where the values live.

**Contents:** [The two kinds](#the-two-kinds) ·
[App settings: why priming once is enough](#app-settings-why-priming-once-is-enough) ·
[What is predefined now](#what-is-predefined-now) ·
[Per-cave mapping: the dashboard's Mapiranje page](#per-cave-mapping-the-dashboards-mapiranje-page) ·
[Adding a setting](#adding-a-setting) ·
[Pitfalls](#pitfalls)

## The two kinds

| | **File settings** | **App settings** |
|---|---|---|
| Stored in | the survey itself, `.csx`/`.csz` → `<properties><designproperties>` | Windows registry, `HKCU\Software\Cepelabs\cSurvey` |
| Belong to | that survey, on any computer | one Windows user on one computer |
| Typically | Properties dialog: centerline colours and widths, text scales, line type; sign and label sizes on items | ribbon and options: pen smoothing on/off and its factor, rulers, grid, quality |
| Values live in | [`tools/tdx-mapping.json`](tools/tdx-mapping.json), section `postimport` | [`tools/csurvey-app-settings.json`](tools/csurvey-app-settings.json) |
| Applied by | **KORAK 2** (`fix_imported_linetypes.py`), into every `_lt` file | **KORAK 0** (`csurvey_0_postavi_csurvey.bat` → `csurvey_app_settings.py apply`), once per computer |
| Checked by | — (it is in the file) | KORAK 2 prints a warning when this computer isn't primed (`… check`) |

When cSurvey offers a choice, the file wins: a design property in the survey
overrides the matching app setting (for example `LineType`,
`cSurvey/cSurveyPC/frmMain2.vb:2777`). Prefer a file setting wherever one
exists. It reaches everyone without priming.

## App settings: why priming once is enough

cSurvey handles the registry like this (`cEnvironmentSettings`,
`cSurvey/cSurveyPC/cEditTools.vb:154-201`):

1. **When its window starts**, it reads the key **once** (`frmMain2.vb:2678`).
2. **While it runs**, it uses its own copy in memory and never looks at the registry again.
3. **When it closes**, it writes that copy back, overwriting whatever is there
   (`frmMain2.vb:2903`).

So:

- **If cSurvey is closed when the settings are written**, it starts with them.
  When it closes, it saves the same values back, so they stay. ✅
- **If cSurvey is open when they are written**, the window ignores them. When
  it closes, it writes its old values back and the new ones are lost. ❌
  That's why KORAK 0 refuses to run while `cSurveyPC.exe` is running.

That gives one rule for operators: **before your first 3N survey on a
computer, close cSurvey and double-click `csurvey_0_postavi_csurvey.bat`.**
After that, forget about it. Run it again only if:

- you are on a new computer or a different Windows user;
- someone changed one of these settings by hand in cSurvey;
- the profile gained a new setting. KORAK 2's warning tells you when.

Re-running is always safe: it just writes the same values again.

Opening a survey by double-clicking it does not apply app settings, because
they are not in the file. Priming is what puts them on the computer. The
headless print in KORAK 3 (`csurvey_headless.ps1`) only **reads** the
registry and never writes it back, so it doesn't undo priming.

## What is predefined now

The JSON files are the source of truth. `python
tools/csurvey_app_settings.py show` lists the app profile next to what this
computer has right now.

**App settings** (`csurvey-app-settings.json`):

| Registry value | Value | In cSurvey |
|---|---|---|
| `pens.smooting` | `"0"` (off) | Pen ribbon → Smoothing toggle. Off keeps freehand strokes exactly as drawn. With it off, the Smoothing factor (`pens.smooth`) is greyed out and never used, so the profile doesn't set it (`frmMain2.vb:18970`). cSurvey stores the toggle as the text `"0"`/`"1"`. |

The smoothing factor itself (`pens.smooth`), and the separate factor for the
manual reduce-points action (`tools.smooth`), are left at whatever each
computer has. The first plan was to pin both to 0.01. The user then chose to
switch the toggle off instead, because the toggle had been switched on
unintentionally.

**File settings** (`tdx-mapping.json` → `postimport`):

| Key | What it sets |
|---|---|
| `centerline` | Properties → Centerline: **red** stations, shots and station numbers (`PlotPenColor`/`PlotPointColor`/`PlotTextColor` = -65536, `PlotCenterlineForceColor` = 1), pen widths, triangle stations, splay, LRUD, translation-line and surface-profile pens, `PlotTextScaleFactor` (station/shot-number text, 1.0, cSurvey's default) and `PlotNoteTextScaleFactor` (notes, **1.0**; cSurvey's default is 0.5, raised 2026-10-03). To make shot numbers smaller, lower `PlotTextScaleFactor`. |
| `designproperties` | Any other survey-wide property, each with its type (empty so far) |
| `sign_sizes` | Item sizes per sign: entrance default, air draught, stalactite, stalagmite medium |
| `label_sizes` | Item sizes per label text: `"!"` large |
| `spline_linetypes`, `nonstandard_water` | Import fixes (splines so decorations render; the water brush) |

## Per-cave mapping: the dashboard's Mapiranje page

The mapping in `tdx-mapping.json` (symbols, lines and areas for KORAK 1;
`postimport` for KORAK 2) is the **shared default**. One cave can differ
without touching it: the cave's `SB_<broj>_…` folder may hold
`tdx-mapping-objekt.json`, which contains only what differs from the default,
in the same schema. `tools/tdx_mapping.py` merges the two:

- an entry under `points`/`lines`/`areas` replaces the default's entry for that
  TopoDroid name, and `null` removes it, giving the natural import behaviour;
- dicts under `postimport` (`centerline`, `sign_sizes`, `label_sizes`,
  `designproperties`) merge key by key; other values replace.

KORAK 1 and KORAK 2 look for the file from each survey's folder up to the
`SB_` folder, per file, so in a batch one cave's override never reaches
another's. They print `mapping: + prilagodba objekta …` when they use one.
This works the same from the dashboard and from the `.bat` kit, because the
file lives on the Drive beside the survey.

The way to edit it is the dashboard: **3N › Mapiranje simbola**
(`cavedossier gui`). It shows every TopoDroid tool in its own colours next to
the cSurvey glyph it becomes, the centerline with a live preview, and the
sizes. Changes stay in the page until **Spremi**, which writes only the
difference. **Vrati na zadano** deletes the file. The page also says what to
redo:

| Changed | Takes effect in | Redo |
|---|---|---|
| Symbols, lines, areas, `generic` | KORAK 1, before import | KORAK 1, the import into cSurvey, then KORAK 2 |
| Centerline, sizes, import switches (`postimport`) | KORAK 2 | KORAK 2 on the file saved from cSurvey |

The pictures come from `tools/tdx-mapping-catalog.json`, generated by
`make_signs_catalog.py` from the cSurvey gallery and TopoDroid's symbol files.
Regenerate it after a cSurvey or TopoDroid upgrade. It ships with the kit.

## Adding a setting

**1. Find out which kind it is.** Change the setting in cSurvey and see where
the change lands:

- **Registry.** Run `reg query "HKCU\Software\Cepelabs\cSurvey"` before and
  after. Close cSurvey first, because it only writes on exit. A value that
  changed means an app setting.
- **File.** Save the survey and look in the `.csx` under
  `<properties><designproperties>` for an `<item name=… type=…>`. A value
  there means a file setting.
- Alternatively, find the control in the cSurvey source. An app setting is read
  with `My.Application.Settings.GetSetting("…")`; a file setting with
  `DesignProperties.GetValue("…")`.

**2. Add one entry.**

- **App setting:** add it to `settings` in `csurvey-app-settings.json`:
  ```json
  "design.rulers": { "value": 1, "ui": "View > Rulers", "why": "...", "source": "cSurvey/cSurveyPC/frmMain2.vb:2595" }
  ```
  A JSON **string** is written as `REG_SZ`, and decimals use a dot, as cSurvey
  stores them. A JSON **integer** is written as `REG_DWORD`. Match the type
  the key already has in the registry.
- **File setting:** if the key is one of the Centerline keys
  (`CENTERLINE_TYPES` in `fix_imported_linetypes.py`), add it to
  `postimport.centerline`. Otherwise, add it to `postimport.designproperties`
  with the type cSurvey writes for it:
  ```json
  "SomeProperty": { "type": "single", "value": 0.5 }
  ```
  Types: `single`, `double`, `decimal`, `integer`, `long`, `int32`, `color`
  (a signed ARGB integer, red = -65536), `boolean`, `string`. **Fonts** are
  nested elements, not values, so they need code.

A setting for **one cave only** needs no JSON editing: use the Mapiranje page,
or put the same entry into that cave's `tdx-mapping-objekt.json`.

**3. Ship it.** Publish the kit (`/publish`). File settings reach every `_lt`
made from then on. For app settings, KORAK 2 warns each computer that isn't
primed with the new value yet, until KORAK 0 is run there again.

## Pitfalls

- **The mapping workbench export drops `postimport`.**
  `tdx-mapping-workbench.html` builds its download from scratch with only
  `points`, `lines`, `areas` and `generic`. After exporting a new mapping from
  it, copy the `postimport` block back from the old file, or the red
  centerline and every other file setting are gone.
- **A new file setting only reaches surveys that pass KORAK 2 after the
  change.** `_lt` files made earlier keep what they had; set those by hand in
  Properties.
- **cSurvey clamps the smoothing factors** (`pens.smooth`, `tools.smooth`)
  to at least 0.01 (`frmMain2.vb:2679`). A lower profile value is shown as
  0.01.
