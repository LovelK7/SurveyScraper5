# Task brief: Nacrt finishing — automate the post-import manual steps and the PDF export

- **ID:** 0004-nacrt-finishing
- **Status:** `in progress` — research done 2026-09-20; the user confirmed the task split (§3.3) and set the scale/layout rules (§3.4) the same day. **T4 (chooser), T1 (`nacrt_finish.py`) and T2 (the headless driver) are built and green, and the chain has produced a real Nacrt end to end on SB 1103**; §2.1/§2.2/§3.1 amended from what T1 and T2 found in practice. Next: T3 (`compose_a4.py`)
- **Owner:** both
- **Opened:** 2026-09-20 · **Closed:** —
- **Read first:** [the superapp CLAUDE.md](../../../../CLAUDE.md), [cSurvey/CLAUDE.md](../../../../../cSurvey/CLAUDE.md), [README.md](../../README.md), [production/tdx-processing-protocol.md](../../production/tdx-processing-protocol.md) (the four steps that precede this), [reference/exports-and-printing.md](../../reference/exports-and-printing.md), [reference/automation-surface.md](../../reference/automation-surface.md)

> This brief is self-contained: a fresh session can pick it up from cold and know exactly what to do
> and where the work stands, without inheriting any prior conversation.

---

## 1. Problem — what's wrong / missing, and why it matters

The TDX protocol ends at step 4 with a finished import, the `_lt` file. From there the operator
still does everything by hand inside cSurvey before the Nacrt exists:

1. correct the sketch in the `_lt` file (cartographic judgement — stays manual);
2. add a horizontal scale bar next to the plan;
3. add a north arrow above it, in *Manual* mode so it reads plain `N` (geographic) and not
   the automatic `Nm 2024` (magnetic north + survey year);
4. flag the highest station as the entrance, then place a *Dislivello* (depth) marker at the deepest
   point of the profile (e.g. `-9 m`);
5. read the cave dimensions off *Survey › Informations* (total length, horizontal length, depth)
   and record them by hand;
6. set up the print layout for plan and profile separately: A4, a fixed scale chosen as the
   largest of 1:100 / 1:200 / 1:500 at which the drawing fits, Style *Survey* (no areas), splays off,
   render quality *High*;
7. print each design to PDF through the print dialog;
8. and then live with two shortcomings: cSurvey always centres the drawing on the page, and it
   cannot put plan and profile on the same sheet.

Every one of steps 2–7 is mechanical and repeated per cave. Two of them (5 and 7) produce
artifacts other stages consume: the dimensions feed 4S-sastavnica and the dossier, the PDF *is*
the Nacrt for the cSurvey route. Automating them collapses the Nacrt route into
"correct the sketch, run one command".

## 2. Context — what's already known (all verified 2026-09-20)

### 2.1 Ground truth: what the manual steps write into the file

The user's own session on SB 1103 (`Golobreška_nanoekspedicija-1p-lk_pp_lt.csx`, then the autosave
`…_lt_backup.csx` after the manual steps) is the diff. Both copies are kept locally as
`example/finishing/SB_1103_golobreska_lt_{raw,finished}.csx` (gitignored, like every survey).
What the finished file contains that the raw one does not:

| Manual step | What cSurvey wrote | Where |
|---|---|---|
| entrance | `<trigpoint name="2" entrance="2">` (`MainCaveEntrace`, cTrigPoint.vb:106-112) | `<trigpoints>` |
| Dislivello | `<item type="10" category="82" quotatype="3" quotavalue="0" quotarelativetrigpoint="2" text="-9 m">` with two points 0.35 m apart at the floor's lowest point | `<profile>` › layer `type="6"` (Signs) |
| horizontal scale | `<item type="10" category="82" quotatype="6" quotatickfrequency="1.00" quotaticklabelfrequency="5.00">` — a **Quota of type HorizontalScale**, 5 m long (3.43→8.44), *not* the `Scale=14` item | `<plan>` › Signs layer |
| north arrow | `<item type="15" category="83" m="1" data="DAD6…ABBB" dataformat="2" textalignment="1">` — `m="1"` is `CompassModeEnum.Manual`, `n` absent = Geographic ⇒ label `N` | `<plan>` › Signs layer; `data` is the id of `compass3.svg` in `<signs><cliparts>` |
| print layout | `_preview.plan` / `_preview.profile`: `printername="Microsoft Print to PDF" pageformat="A4" scalemode="1" scale="100" pagemargins="10;10;10;10"` | `<options>` |

Semantics behind those attributes (source-grounded by three read-only digs into `cSurvey/`):

- **Compass label** (cItemCompass.vb:344-373): Auto mode prints `Nm <year>` whenever GPS is off
  *and* `properties@nordcorrectionmode="0"` (the drawing is in magnetic north), year from the
  distinct session years (`#error#` if several). Manual + `n="0"` forces `N`; `n="1" ny="2024"`
  forces `Nm 2024`. The arrow is never rotated by the item; declination is a survey-level setting.
- **Quota Drop** (cItemQuota.vb:485-527): profile only; value = `Z(relative station) − Y(midpoint of the
  two points)`; profile design-Y **is** depth (Z positive downward, cCalculate.vb:740), so a point
  below the entrance gives a negative number; format `+0;-0;0` + ` m` ⇒ `-9 m`. If
  `quotarelativetrigpoint` is empty it auto-fills with the cave's first `MainCaveEntrace`. Two points
  are mandatory (Paint bails on one).
- **Quota HorizontalScale** (`quotatype="6"`): bar length = distance between its two points, in
  metres; tick every `quotatickfrequency`, label every `quotaticklabelfrequency`. Scales with the
  map automatically because it lives in world metres.
- **A Quota carries no pen and no brush** (added 2026-09-20 while building T1): `cItemQuota`
  overrides `HavePen` and `HaveBrush` to `False` (cItemQuota.vb:261-271), and the base loader only
  reads a `<pen>`/`<brush>` child when the item claims to have one (cItem.vb:507-520). Both quota
  items in the finished fixture are therefore just `<points>` + `<font type="0"/>`, and writing a
  `<pen>`/`<brush>` into one would be ignored on load and dropped on the next save. The compass
  (`cItemCompass`, both `True`) does take `<pen type="10"/>` + `<brush type="7"/>`, plus
  `<font type="1"/>`.
- **Where a design's coordinates come from** (confirmed 2026-09-20 in T1, and what makes the
  entrance-sign witness possible): a **plan** design point is the station's `<p x y>` directly; a
  **profile** design point is `(<p d>, <p z>)` — the projected distance along the profile and the
  depth (frmMain.vb:17386 builds a profile translation from exactly that pair). On SB 1103 every
  `d` is `0`, which is correct for a cave whose shots are near-vertical but means the profile
  witness has little to discriminate with there.
- **`.csz` cliparts** (confirmed 2026-09-20 in T1): `<clipart @data>` holds the *path*
  `_data\cliparts\<id>.svg` with **backslashes**, while the zip entry itself uses forward slashes —
  the loader normalizes zip names to the platform separator before looking the path up
  (cFile.vb:388, cCliparts.vb:495-497), so a forward-slash `@data` resolves to nothing and takes
  cSurvey down on load. `<clipart @id>` is the uppercase SHA-1 of the SVG bytes.
- **Item Scale=14 / Compass=15 vs. the print gadgets**: `_preview.*` also carries
  `drawscale/scaleposition`, `drawcompass/compassposition` (corner enums 0..3) with
  `<scaleoptions meters steps step>` / `<compassoptions text>` — page-furniture drawn *after*
  `ResetTransform` in the page corners (frmPreview.vb:1061-1073). They are an alternative to items
  when placement "next to the sketch" is not required.
- **Entrance ⇒ speleometrics** (cCalculate.Plot.cSpeleometrics.vb:88-131): only when a main entrance
  exists does the per-cave `<sm>` row get `pvr` (height above entrance), `nvr` (depth below), `es`;
  `l` = 3-D length of non-excluded shots (splays/surface/duplicates are auto-excluded, cSegment.vb:617-646),
  `pl` = planimetric length, `ml` = everything incl. splays, `qmx/qmn` = altitude extremes. Total drop
  is **not** stored; compute `pvr + nvr`. Values are whole metres. Populated only by a full
  calculation. After the headless recalc below, SB 1103 reads `l=10 pl=4 pvr=1 nvr=9 es=2` — the
  `-9 m` of the quota.
- **Print options come from the file** (cSurvey.vb:1309, frmPreview.vb:618-747 `pOptionsRestore`): no
  registry override; whatever `_preview.*` says is what the dialog opens with.
  `scalemode` is the **combo index**: `0` fit, `1` 1:100, `2` 1:200, `3` 1:250, `4` 1:300,
  `5` 1:500, `6` 1:1000, `99` custom + `scale`. (The `ScaleModeEnum` in cIOptionPreview.vb is stale;
  trust the index.) `designstyle="2"` = *Combined*, `drawsplay="0"` = without splays.
  **Render quality is not there** — it is `<sharedsettings><values preview.designquality="2">`
  (frmPreview.vb:91; 0 Base, 1 Medium, 2 High). `preview.manualrefresh` must not be `"1"`.
- **Centering is hard-coded** (frmPreview.vb:1095-1212): design bounds → zoom → translate to the centre
  of `e.MarginBounds`; fit mode multiplies by 0.9. No user offset exists; the preview drag is
  overwritten on every page; cave/branch translations move the bounds with the drawing and cancel
  out. The only in-app lever is **asymmetric `pagemargins`** (hundredths of an inch), which shifts
  the centring box. **One design per sheet** — `HasMorePages` is never set, the design comes from
  a single Plan/Profile profile, no "both" option anywhere.
- **cSurvey has no PDF writer**: PDF is a printer driver (or therion's own map export, a different
  look). The print path is `Private frmPreview.pPrint` → always a `PrintDialog`.

### 2.2 The load-bearing finding: the installed exe is a library, no build needed

The "reflection hypothesis" from [decisions/roadmap-decisions.md](../../decisions/roadmap-decisions.md)
is confirmed, and it goes further than expected. From **Windows PowerShell 5.1**, with
`[Reflection.Assembly]::LoadFrom("C:\csurvey64\cSurveyPC.exe")`, three reflection pokes replace the
WinForms startup (`modMain.sApplicationPath` ← install dir, `modMain.LoadLocalizedStrings`,
`My.MyProject.Application.ReloadSettings()` + an empty `RuntimeSettings`). After that, on the real
SB 1103 file:

| Call | Access | Result |
|---|---|---|
| `New cSurvey` · `Load(path)` · `Invalidate()` · `SaveTo(path)` | Public | ✅ 57 shots / 58 stations, round-trips |
| `Calculate.Calculate(True)` | Friend → reflection | ✅ `cActionResult.Result=True`, `<sms>` refreshed with `es/pvr/nvr` (therion is invoked but is not load-bearing — see the constraints below) |
| `New frmPreview(survey, Preview, Plan\|Profile)` | Friend → reflection, never shown | ✅ DevExpress initialised without a licence prompt; ctor runs `pOptionsRestore` from the file |
| `frmPreview._oDoc` (the `WithEvents` backing field) → `PrinterSettings.PrintToFile=True`, `PrintFileName=…`, `Print()` | private field → reflection | ✅ **plan and profile PDFs written with no dialog**, byte-for-byte the same look as the user's manual `profil.pdf` |

Everything sits in [findings/csurvey_headless_probe.ps1](findings/csurvey_headless_probe.ps1)
(`info` / `recalc` / `print`, each poke asserted by name so a future cSurvey build fails loudly).
Constraints that came with it: must run `powershell -STA`; PowerShell variables are
case-insensitive (`$Survey` and `$survey` collide — bit us twice); the sync `ExecuteTherion` pops a
MsgBox after 120 s on huge surveys (ours take ~2 s); `Microsoft Print to PDF` must be installed
(Windows 10/11 default); `therion.path` must be in the registry (it is on any machine that runs
cSurvey at all).
**Amended 2026-09-20 (T2): a therion failure does not fail the calculation.** This dev machine has
`therion.path` set and Therion installed but no Survex `cavern` anywhere; therion's run dies with
`'cavern' is not recognized` on **stderr** and `Calculate(True)` still returns `Result=True` with a
correct `<sms>` (`l=10 pl=4 pvr=1 nvr=9 es=2` on SB 1103 — the speleometrics come from cSurvey's own
plot data, not from therion). So the driver judges a run by its **exit code**, never by stderr being
empty; stdout stays clean, which is what lets `dimensions` emit bare JSON on it.
The `csc.exe`/`vbc.exe` in `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\` are
also present on every Windows box if a compiled net48 driver is ever preferred over the script.

This removes DevExpress, Visual Studio, the `cAutomation` facade and the source build from the
critical path of *this* project entirely. The MCP blueprint's architecture (b) stands, with
"reflection from a script" as its implementation instead of a facade.

### 2.3 Where the sketch's bounds come from

For scale selection and for placing the scale/compass/quota a tool needs the drawing's extent.
Two options: (a) pure Python over `<points data>` of the Borders-layer items per design (the
inspector already parses this — bbox digest in `inspect_survey.py`); (b) the headless driver's
`Survey.Plan.GetDesignVisibleBounds(options)` (Public, cDesign.vb:909), which is exactly what the
printer uses. (a) needs no cSurvey; (b) is authoritative. Use (a) for placement, (b) to confirm the
chosen scale fits.

## 3. Approach — the automation matrix and the pipeline shape

### 3.1 Per manual step

| # | Manual step | Automatable? | How | Layer |
|---|---|---|---|---|
| 1 | correct the sketch | **no** (by design) | stays the human step between KORAK 2 and the new KORAK 3 | — |
| 2 | horizontal scale next to plan | **yes** | write a `quotatype="6"` item in the plan's Signs layer: two points, `bbox.maxx + 1 m` at `bbox.maxy`, length = 5 m for 1:100, 10 m otherwise (ticks 1/labels 5 vs 2/10); or the `drawscale` gadget in a page corner. **Amended 2026-09-20 (T1):** the bar's length depends on the plan's scale and the plan's scale depends on the bbox *the bar widens* — so the tool chooses a provisional scale from the untouched bboxes, sizes the bar from it, and re-chooses for real afterwards, warning if the two differ. `quotarelativetrigpoint` stays **empty** on a HorizontalScale (it measures nothing against a station), as on the bar cSurvey writes itself | XML (Python) |
| 3 | compass `N` above it | **yes** | write a `type="15" category="83" m="1"` item with `data` = the `compass3.svg` clipart id. The clipart must exist in `<signs><cliparts>` (copy the `<clipart>` element incl. its base64 SVG from the finished SB 1103 file — in `.csx` the SVG is inline in `@data`; in `.csz` it is a zip entry `_data/cliparts/<id>.svg`). Fallback per cItemCompass.vb:468-470: an unresolved id falls back to the built-in `clipart_defaultcompass` — verify visually before relying on it | XML (Python) |
| 4a | highest station = entrance | **yes** | **Amended 2026-09-20 (T1): two independent witnesses, not one.** (a) among non-splay stations (`<t n>` without `(`), the one with **min** `z` (Z is positive downward); (b) the entrance sign the surveyor drew — `<item type="6" category="80" sign="263">` (`cIItemSign.vb:44`) — resolved to the nearest non-splay station in that design's coordinates (plan = `<p x y>`, profile = `<p d z>`), plan preferred over profile, with the sign's bound segment as a cross-check. Agree ⇒ confident; disagree ⇒ **the sign wins** and both are named in a warning (a ponor rarely has its entrance at the top); no sign ⇒ (a), and **warn** when it differs from `properties@origin` or when another station ties within 0.5 m in z. Then `entrance="2"` on its `<trigpoint>` — the *constant* `MainCaveEntrace` (`cTrigPoint.vb:109`), which on SB 1103 reads like the station name "2" by coincidence. Both witnesses go into the sidecar JSON and the `--dry-run` report so the rule can be re-weighed on real caves | XML (Python) |
| 4b | Dislivello at the deepest point | **yes** | lowest point of the profile floor = max Y over the profile Borders-layer points (or, equivalently, `nvr`); write a `quotatype="3"` item at that depth but **0.3 m right of the profile's rightmost point** (the first real print, 2026-09-20, showed the label buried in the floor debris when placed beside the lowest point itself), `quotarelativetrigpoint` = the entrance, `quotavalue="0"` so cSurvey computes the text at paint time (confirmed 2026-09-20 in T1: the points go 0.35 m apart diagonally, and the item carries **no** `<pen>`/`<brush>` — see §2.1) | XML (Python) |
| 5 | cave dimensions | **yes** | after 4a run **`recalc`** (headless), then read the per-cave `<sm>`: total length `l`, horizontal length `pl`, depth `nvr`, height `pvr`, total drop `pvr+nvr`, altitude span `qmx−qmn`. Emit `SB_<broj>_dimenzije.json` into the cave leaf for 4S/5D to consume | driver + Python |
| 6 | print layout | **yes** | write `_preview.plan` / `_preview.profile`: `pageformat="A4"`, `pagelandscape` **removed/omitted** (amended 2026-09-20 in T1: the sastavnica page T3 composes onto is A4 portrait, and cSurvey centres on whatever page it is given, so landscape buys nothing), `scalemode` ∈ {1,2,3,4,99+`scale=400`,5} (1:100 / 1:200 / 1:250 / 1:300 / 1:400 / 1:500) chosen per design by the rule in §3.4 (the two designs may differ: typically profile 1:200, plan 1:100), `designstyle="0"` (*Survey* — the user's default, 2026-09-20; not *Combined*), `drawsplay="0"`, `drawscale/drawcompass` per taste, `printername`; plus `sharedsettings` `preview.designquality="2"`, `preview.manualrefresh="0"`. **Plan and profile get their own scale** — see §3.4 | XML (Python) |
| 7 | PDF export | **yes** | `csurvey_headless_probe.ps1 -Command print` — no dialog | driver |
| 8a | off-centre placement | **partly in-app, fully downstream** | in-app only via asymmetric `pagemargins`; the clean solution is 8b | — |
| 8b | plan + profile on one A4 | **yes, downstream, together with 4S** | cSurvey cannot. Print each design at its own fixed scale (vector PDF from the Microsoft driver), then compose with PyMuPDF onto the **4S sastavnica page** (A4 portrait, title block upper-left, already PyMuPDF-based): crop each page to its ink bbox, place per §3.4, never rescale so the printed scale stays true. 4S is extended to carry the speleometrics (Stvarna/Tlocrtna duljina, Dubina from `<sms>`) and the scale(s) — `Mjerilo` becomes `1:100` or, when they differ, `profil/tlocrt: 1:200/1:100` (a custom layout of that cell) | Python (3N + 4S) |

### 3.2 Pipeline shape (KORAK 3 of the protocol)

```
<survey>_lt.csx  (corrected by the human)
   │  nacrt_finish.py  — pure XML: entrance, quota, scale, compass, print options, quality   [T1, T4]
   ▼
<survey>_lt_fin.csx
   │  csurvey_headless.ps1 recalc → print                                                  [T2]
   ▼
<survey>_lt_fin.csx (sms refreshed) + <survey>_plan.pdf + <survey>_profile.pdf + SB_<broj>_dimenzije.json
   │  compose_a4.py  — one A4, arranged, same scale                                         [T3]
   ▼
SB_<broj>_nacrt.pdf   → the Nacrt (cSurvey route); dimensions → 4S sastavnica / 5D dossier
```

Python orchestrates (`subprocess` → `powershell -STA -File …`); the driver never edits XML, the XML
tool never touches cSurvey. Both are testable on the SB 1103 fixture pair without the other.
The install dir is a per-machine fact → `.env` `CSURVEY_DIR` (default `C:\csurvey64`), the printer
name likewise. Fail-soft: if the driver is unavailable the XML step still leaves a file the human
can open and print in two clicks.

### 3.4 Scale and layout rules (user, 2026-09-20)

- **Scale per design, not per sheet.** Profile and plan often need different scales: a
  1:200 profile with a 1:100 plan is the common case. Rule: for each design take the largest
  of **1:100 / 1:200 / 1:250 / 1:300 / 1:400 / 1:500** (`scalemode` 1/2/3/4/99+`scale`/5 — 1:400 is
  not on cSurvey's list and goes out as the custom entry) at which its bbox fits its allotted area; when the two bboxes are
  drastically different (say one dimension ratio > 1.6), propose the plan at the larger scale so
  it stays legible rather than forcing both to the profile's.
  **The two scales may differ by at most one rung of that ladder** (user, 2026-09-20, stated
  twice: the T4 session first read "one step" as a factor of 2, which let 1:500 sit beside 1:250 —
  two rungs, since 1:300 and 1:400 lie between; corrected the same day). 1:200 over 1:100 and
  1:300 over 1:250 are fine; 1:300 over 1:200 is not. 1:250 joined the ladder in the review of the
  drawn proposals (a 40 m profile misses 1:200 by 10 mm) and 1:400 right after it.
  **Alternatives must be real trade-offs**: never a pointless downscale of a design that fits at
  the larger scale — one entry per arrangement per genuine choice (equal scales vs. promoted
  plan, stacked vs. side by side). The user could not judge the first menus because of the noise.
- **One A4 portrait page = the 4S sastavnica page.** The title block occupies the upper-left;
  the drawings share the rest. Two arrangements: **vertical** (default — profile has the primary
  role and sits on top, plan beneath) or **side by side** (when both are tall and narrow).
  Gaps ≥ 10 mm, margins ≥ 10 mm, no overlap with the title block.
  The drawings live **only in the full-width band below the title block** — the free strip to the
  right of it buys a scale step for a narrow pair but leaves half the sheet empty, and the user
  rejected such a page on sight (2026-09-20). Both drawings are centred horizontally and packed to
  the top of the band, so the leftover page collects at the bottom (user, same review).
- **Mjerilo cell**: `1:100` when equal; `profil/tlocrt: 1:200/1:100` when not — the cell needs a
  custom two-value layout in 4S (supersedes 4S decision 3 "stub `1:` stays" for the cSurvey route;
  the Illustrator route keeps the stub).
- **Semi-automatic is acceptable.** The tool proposes (scale per design, arrangement) and asks
  the operator to confirm or pick from the listed options whenever the automatic choice fails or
  the fit is marginal — the same Enter-to-accept console style the KORAK launchers use.

### 3.3 Delegable tasks (each is a self-contained prompt for a separate, cheap session)

Every task below names its inputs, its output, and its acceptance check; none needs the research
above re-derived. Paste-ready prompts live in [`tasks/`](tasks/) (T4 first). Fixture pair: `stages/3N-nacrt/example/finishing/SB_1103_golobreska_lt_{raw,finished}.csx`
(the finished one is the oracle for T1). Log results in [log.md](log.md).

**T1 — `nacrt_finish.py` (XML finisher).** *Input:* a `_lt.csx`/`.csz` after KORAK 2. *Output:*
`<name>_fin.<ext>` with: entrance on the highest non-splay station (warn on origin mismatch/ties);
Drop quota at the profile's lowest floor point relative to that station; HorizontalScale quota
right of the plan bbox (length by scale); compass item (`m="1"`, `data` = compass3 clipart id,
clipart element copied in if missing) above the scale; `_preview.plan/profile` + `sharedsettings`
per §3.1 row 6 with the scale from T4. Preserve every other byte (`.csz` → re-zip all entries).
*Accept:* run on the raw fixture, diff against the finished fixture: same entrance station, quota
type/relative-station equal, scale/compass present in the Signs layer, print attrs equal; opens in
cSurvey and the profile shows `-9 m`. Add a `--dry-run` report. Pattern to copy:
`production/tools/fix_imported_linetypes.py` (already rewrites items in place, handles both containers).

**T2 — `csurvey_headless.ps1` (driver).** *Start from* `findings/csurvey_headless_probe.ps1`
(works). *Add:* `-CSurveyDir` from env, `dimensions` command emitting JSON (`l, pl, pvr, nvr, drop=pvr+nvr, qmx, qmn, es`
per cave), `print` honouring an optional `-Landscape`/`-ScaleMode` override, non-zero exit codes,
and a 30-s guard around `Calculate`. Keep every reflection poke wrapped in `Assert-NotNull`.
*Accept:* `info`/`recalc`/`print`/`dimensions` on the finished fixture; PDFs open; JSON matches the
`<sm>` row. Then a `python` wrapper `csurvey_driver.py` (subprocess, `-STA`, timeout, parsed output).

**T3 — `compose_a4.py` (compositor, 3N + 4S).** *Input:* `_plan.pdf` and `_profile.pdf`, each
printed at its own fixed scale (known from T4's output), the cave's sastavnica PDF from 4S
(`cavedossier sastavnica <broj>`), and the dimensions JSON from T2. *Output:* one A4 **portrait**
page: the sastavnica page as the base (title block upper-left), profile placed as the primary
drawing, plan beneath (or side by side when T4/the operator says so), content cropped to ink bbox
via PyMuPDF `page.get_drawings()`/text bboxes, ≥ 10 mm gaps, **no rescaling**. Ask the operator
(console menu, Enter = default) when the fit is marginal or the arrangement is a judgement call.
*4S side:* extend the sastavnica renderer so `Stvarna duljina`/`Tlocrtna duljina`/`Dubina` can be
fed from the JSON and `Mjerilo` renders `1:100` or a two-line `profil/tlocrt: 1:200/1:100`
(needs a custom cell layout — see `stages/4S-sastavnica/docs/sastavnica-design.md`, cells
`stvarna_duljina`, `tlocrtna_duljina`, `dubina`, `mjerilo`). *Accept:* a known 5 m scale bar on the
composed page measures 50 mm at 1:100 (25 mm at 1:200) for each design independently; the title
block is untouched and unclipped; file < 500 KB.

**T4 — scale + layout chooser (`choose_layout()` + tests).** *Input:* plan bbox (m), profile bbox
(m), the A4-portrait free area left by the sastavnica title block (from 4S: page 595.28 × 841.89 pt,
block in the upper-left — read its extent from the design doc), margins/gaps (mm). *Output:* a
proposal `{plan_scale, profile_scale ∈ {100,200,300,500}, arrangement: vertical|side_by_side,
placements (mm)}` plus up to three ranked alternatives for the operator menu, or a reason when
nothing fits (fall back to `scalemode=0` fit and warn). Rules in §3.4: per-design scale, profile
primary, plan promoted to a larger scale when the bboxes differ drastically. Pure function,
unit-tested with SB 1103 (plan ≈ 4 × 9 m, profile ≈ 5 × 10 m ⇒ both 1:100, vertical) and a
synthetic long-profile case (profile 40 × 12 m, plan 6 × 8 m ⇒ profile 1:200, plan 1:100).

**T5 — operator surface.** `csurvey_3_dovrsi_nacrt.bat` in `prod/build_csx_kit.py` (SB prompt →
pick the `_lt` file → T1 → T2 → T3 → deliver `SB_<broj>_nacrt.pdf` + `SB_<broj>_dimenzije.json` into
the leaf), a KORAK 3 paragraph in `csurvey_0_PROCITAJ_ME.txt` (Croatian, no diacritics in the
`.bat`), and the protocol doc updated. Rename the current rescue launcher to KORAK 4 or keep it
`3_oporavi` and use `3b`? — user decision.

**T6 — reference corrections (done in this session, see §5).**

Order: T4 → T1 → T2 → T3 → T5. T1/T2/T3/T4 are independent of each other apart from T1 importing T4
and T3 touching 4S. (Order and task split confirmed by the user 2026-09-20.)

## 4. Definition of done

- [ ] `nacrt_finish.py` reproduces the SB 1103 manual result from the raw `_lt` (T1 acceptance).
- [ ] The driver prints both PDFs headlessly on the dev machine **and** on one operator machine
      (proves the `CSURVEY_DIR`/printer portability, `powershell -STA` availability).
- [ ] `SB_<broj>_dimenzije.json` equals the numbers *Survey › Informations* shows for the same file.
- [ ] Composed A4 keeps the scale (measured bar) and the user accepts the arrangement on two real caves.
- [ ] KORAK 3 launcher published; protocol + `PROCITAJ_ME` updated; `pipeline_doctor.py` clean.
- [ ] All runs logged under `runs/`; contradictions with `reference/` fed back into the docs.

## 5. Outputs (fill in on close)

- **Production:** — (planned: `nacrt_finish.py`, `csurvey_headless.ps1` + `csurvey_driver.py`, `compose_a4.py`, `csurvey_3_dovrsi_nacrt.bat`)
- **Reference:** 2026-09-20 corrections to [exports-and-printing.md](../../reference/exports-and-printing.md)
  (headless print *is* possible via reflection; render-quality lives in `sharedsettings`; `scalemode`
  is a combo index) and [automation-surface.md](../../reference/automation-surface.md) (reflection
  hypothesis confirmed from PowerShell, no build)
- **Decisions:** [2026-09-20 entry](../../decisions/roadmap-decisions.md) — headless driver is a script, not a build
- **Follow-ups:** MCP surface ([mcp-blueprint.md](../../reference/mcp-blueprint.md)) can now be a thin
  wrapper over the same script; steps 3–4 of the TDX protocol (import + Save As) are automatable the
  same way (`Load(FixTopoDroid)` → `SaveTo`) — a separate small project.
