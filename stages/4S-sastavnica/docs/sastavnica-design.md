# Sastavnica prefill — `cavedossier sastavnica <Redni broj>` (design note)

The **sastavnica** is the title block that sits on a finished Nacrt: the society
logo plus fifteen labelled cells naming the cave, its numbers, its dimensions
and the people who surveyed it. It is an Illustrator asset (`!SUE_sastavnica.ai`
on the Drive) and today a drafter types all fifteen values into it by hand,
copying from SB and from the filled OSZ.

This note is the step that stopped that: **a PDF prefill** — same input and
same shape as `osz prefill`, a Redni broj in, a prefilled document delivered
into the cave's intake leaf. It is part [**2.1e**](../../../ARCHITECTURE.md#part-21e)
and bridge [**B13**](../../../ARCHITECTURE.md#b13), and it serves the
[Illustrator route](../../../ARCHITECTURE.md#two-routes-to-the-nacrt--csurvey-and-illustrator)
to the Nacrt (route B), which the society's own digitization instructions
already describe.

Status: **built and validated live, 2026-09-19** (`cavedossier sastavnica`,
module `sastavnica/`, 31 tests). Designed and built the same day: every geometry
number below was read out of `!SUE_sastavnica.pdf`, not assumed, and the design
was only written down once a spike had reproduced the authored layout to 0.01 pt.
Validated end to end on SB 1220 (a cave already being drafted in Illustrator —
its leaf holds the DXF exports) and SB 811.

**2026-09-20:** the package grew a second command, `cavedossier nacrt`, which
composes 3N's printed plan and profile onto this same block to finish the
**cSurvey** route's Nacrt — see
[4S README](../README.md#cavedossier-nacrt--the-csurvey-routes-finished-sheet)
and project [0004-nacrt-finishing](../../3N-nacrt/projects/0004-nacrt-finishing/brief.md)
(T3). It touches this design in three places, each marked below: a fourth field
source for four cells, the supersession of decision 3 on that route, and the one
cell allowed two lines.

## Contents

- [The command](#the-command)
- [The template, measured](#the-template-measured)
- [Cell geometry](#cell-geometry)
- [Field map — where each of the fifteen values comes from](#field-map--where-each-of-the-fifteen-values-comes-from)
- [Typesetting rules](#typesetting-rules)
- [The font question](#the-font-question)
- [The blank-template builder](#the-blank-template-builder)
- [Delivery](#delivery)
- [Module layout](#module-layout)
- [Fail-soft behaviour](#fail-soft-behaviour)
- [Testing](#testing)
- [Prod](#prod)
- [Settled (user, 2026-09-19)](#settled-user-2026-09-19)
- [Decided while building (2026-09-19)](#decided-while-building-2026-09-19)
- [Still open](#still-open)

## The command

```powershell
cavedossier sastavnica 1320              # SB (+ the leaf's filled OSZ) -> prefilled PDF
cavedossier sastavnica 1320 --offline    # no network; SB + OSZ only, no geo finders
cavedossier sastavnica 1320 --local      # keep the run copy, skip Drive delivery
```

Top level, like `karta` — the sastavnica is not an OSZ sub-step. The **Redni
broj is the only required input**, per the standing portability rule. Exit codes
stay the house convention: **1** delivered, **0** nothing to do, **99** error.

## The template, measured

| Fact | Value |
|---|---|
| Authored in | Adobe Illustrator 24.0 → `!SUE_sastavnica.ai` (Drive), exported as PDF 1.5 |
| Committed copy | [`template-workbench/templates/!SUE_sastavnica.pdf`](../template-workbench/templates) — **v1.0, 2026-09-20**, re-authored in Microsoft Sans Serif (see [The font question](#the-font-question)); same page, same 59 vector paths, same cell rules to the hundredth of a point, so the geometry below is unchanged |
| Pages | 1, A4 portrait (595.28 × 841.89 pt), no rotation |
| Form fields | **none** — not an AcroForm; there is nothing to "fill" in the PDF sense |
| Images | **none** — the mammoth logo is 59 vector paths, so output stays fully vector |
| Fonts | one embedded subset — `ZJSHCV+MicrosoftSansSerif` in v1.0 (`ECYHUF+MyriadPro-Regular` before it), custom encoding either way |
| The block | (39.85, 49.58) → (291.43, 149.94) = **251.58 × 100.36 pt ≈ 88.7 × 35.4 mm**, top-left of the page |
| Rows | five bands of ~20.08 pt; bottoms at y = 69.66 · 89.74 · 109.82 · 129.88 · 149.94 |
| Logo cell | (39.85, 49.58) → (81.35, 109.82) — spans the first three rows |

**The one fact the whole design rests on:** labels and placeholder values are
distinguishable by **fill colour alone**, in the content stream itself —

| | CMYK operator in the stream | RGB | Size |
|---|---|---|---|
| Labels | `0.625 0.527 0.52 0.238 k` | `#5e6161` | 5 pt, always |
| Values | `0.746 0.676 0.668 0.898 k` | `#030505` | 8–10 pt, hand-chosen per cell |

So the fifteen placeholders can be found and removed mechanically, with no text
matching — which matters, because the subset font's custom encoding makes the
Croatian diacritics unreadable to text extraction (`Broj plo?ice`,
`Istra?ili`). Nothing in this design ever matches on extracted text.

## Cell geometry

Read from the template's own rules (its stroke operators), not guessed. PDF
points, origin top-left, as PyMuPDF reports them.

| Key | Label | x0 | y0 | x1 | y1 | Authored size |
|---|---|---|---|---|---|---|
| `katastarski_broj` | Katastarski broj | 81.35 | 49.58 | 120.18 | 69.66 | 10 |
| `ime_objekta` | Ime speleološkog objekta | 120.18 | 49.58 | 291.43 | 69.66 | 10 |
| `broj_plocice` | Broj pločice | 81.35 | 69.66 | 120.18 | 89.74 | 9 |
| `htrs` | HTRS koordinate | 120.18 | 69.66 | 248.12 | 89.74 | 9 |
| `nadmorska_visina` | Nadmorska visina | 248.12 | 69.66 | 291.43 | 89.74 | 9 |
| `lokacija` | Lokacija | 81.35 | 89.74 | 204.82 | 109.82 | 9 |
| `stvarna_duljina` | Stvarna duljina | 204.82 | 89.74 | 248.12 | 109.82 | 9 |
| `tlocrtna_duljina` | Tlocrtna duljina | 248.12 | 89.74 | 291.43 | 109.82 | 9 |
| `crtali` | Crtali | 39.85 | 109.82 | 120.18 | 129.88 | 9 |
| `mjerili` | Mjerili | 120.18 | 109.82 | 204.82 | 129.88 | 9 |
| `dubina` | Dubina/vis. razlika | 204.82 | 109.82 | 248.12 | 129.88 | 9 |
| `mjerilo` | Mjerilo | 248.12 | 109.82 | 291.43 | 129.88 | 9 |
| `istrazili` | Istražili | 39.85 | 129.88 | 95.03 | 149.94 | 8 |
| `ekipa` | Ekipa | 95.03 | 129.88 | 204.82 | 149.94 | 8 |
| `datum` | Datum/razdoblje istraživanja | 204.82 | 129.88 | 291.43 | 149.94 | 9 |

The authored sizes vary because they are the drafter's own choice per row —
10 pt in row 1, 9 in rows 2 to 4, 8 in row 5 (re-measured for v1.0, 2026-09-20;
most were 10 under the Myriad template) — and because the drafter **shrinks a
value by hand until it fits** when a long one needs it. Both halves are
reproduced: `Cell.size` is where the fitter starts, and it only ever goes down
from there. Starting every cell at 10 pt instead made the output visibly bigger
than the template it copies. This table becomes `sastavnica/addresses.py`, the direct counterpart of
[`osz/addresses.py`](../../4O-osz/src/cave_dossier/osz/addresses.py): one map per template
version, regenerated by the builder tool whenever the `.ai` changes.

## Field map — where each of the fifteen values comes from

Three sources, in precedence order per field: **SB** (the master), the cave's
**filled OSZ** in its intake leaf (read with the existing `osz/reader.read_osz`,
which returns every `V10` key), and the **geo finders**. On the cSurvey route
`cavedossier nacrt` adds a **fourth, ahead of them all for four cells only**:
the `<name>_dimenzije.json` KORAK 3 leaves in the same leaf, which carries the
lengths and depth measured off the very survey being composed and the scale it
was printed at. Source label `nacrt`; `run_prefill(use_dimensions=True)` is the
only way in, so `cavedossier sastavnica` is unaffected. Nothing here writes
anywhere; like `osz prefill`, any value the finders produce that SB lacks goes
out as a `dopune-sb.csv` review row for a person to paste.

| Cell | Source (in order) | Notes |
|---|---|---|
| Katastarski broj | — | **never filled**: the template's `0000` stays, the archivist stamps the real number in by hand ([decision 2](#settled-user-2026-09-19)) |
| Ime speleološkog objekta | SB `Ime objekta` | |
| Broj pločice | SB `Broj pločice` | |
| HTRS koordinate | SB `X HTRS` + `Y HTRS` | `"<X> <Y>"`, integer metres — the authored form |
| Nadmorska visina | SB `Z` → `geo.elevation` kota | `"<n> m"`, **whole metres**; SB wins, a mismatch is a note |
| Lokacija | `geo.locality` finding / SB `Lokalitet` · `Najbliže mjesto` | `Lokalitet, Najbliže mjesto` — those two only ([decision 1](#settled-user-2026-09-19)) |
| Stvarna duljina | *(`nacrt`: `l`)* → OSZ `duljina` → SB `Duljina` | `"<n> m"`; a **0** means "not surveyed yet" and stays blank |
| Tlocrtna duljina | *(`nacrt`: `pl`)* → OSZ `horizontalna_duljina` | not in SB — blank when no OSZ |
| Dubina/vis. razlika | *(`nacrt`: `nvr`/`pvr`)* → OSZ `dubina` / `visinska_razlika` → SB `Dubina` | `"-<n> m"` for jame; `nacrt` renders `"-9/+1 m"` when the cave also goes up **and** both numbers still fit above 7 pt |
| Mjerilo | *(`nacrt`: the printed scale)* | the drafter's own choice on the Illustrator route, where the stub `1:` stays ([decision 3](#settled-user-2026-09-19)); on the cSurvey route it is known, and may take two lines |
| Crtali | OSZ `crtali` → SB `Autori nacrta ili izvor` | the SB cell holds the *source* for queued caves, so the OSZ wins; **abbreviated** |
| Mjerili | OSZ `mjerili` (+ `mjerili_2`) | not in SB; **abbreviated** |
| Istražili | OSZ `istrazile_udruge` (+ `_2`) → `sastavnica.society` | one society written out; **two or more abbreviated** — `SU Estavela, SO Velebit` → `SUE, SOV` — because the cell is 55 pt wide and that is the form a caver writes anyway (user, 2026-09-20). `core.people.society_shorthand`; a name outside the four caving-org patterns is never abbreviated |
| Ekipa | OSZ `clanovi_ekipe` (+ `_2`, `_3`) | joined with `, `; **abbreviated** |
| Datum/razdoblje istraživanja | OSZ `datum_istrazivanja` → SB `Godina ili period istraživanja` | |

Five of the fifteen cells cannot be filled from SB at all — they are survey
facts. That is the honest ceiling of this step, and it is why reading the leaf's
filled OSZ is part of the design rather than an extra: run before the OSZ is
filled, the tool prefills nine cells; run after it, fourteen.

## Typesetting rules

Derived by measuring the authored values, then confirmed by reproducing them:

- **Centred** horizontally in the cell. Verified on 13 of 15 authored values
  (cell centre = value bbox centre to <0.5 pt); `istrazili` and `htrs` are
  hand-nudged by ~2 pt and are not a different rule.
- **Baseline = row bottom − 4.3 pt** (re-measured for v1.0, 2026-09-20; it was
  4.6 under the Myriad template, which set every value a quarter-point high).
  The authored baselines cluster at −4.11 … −4.59; row 2 and `datum` sit at
  −3.2, hand nudges the drafter made in Illustrator. One uniform rule reads
  better than fifteen copied numbers.
- **Shrink to fit**: start at the **cell's own authored size** (`Cell.size`),
  step down by 0.25 pt while `Font.text_length(text, size) > cell_width −
  2 × 2 pt`, floor at ~6 pt. The 2 pt side padding is what the drafter's own
  8 pt choice for *Ekipa* implies.
- **Colour** `#030505`, the authored value colour.
- **One line, with two named exceptions** (2026-09-20). `render.MULTILINE` is
  the set of cells allowed a second line, and it holds `mjerilo` and `ekipa`;
  every other cell is one line, and a value too long even at the floor size is
  set at the floor size and named in a printed warning.
  - **Mjerilo** wraps only in the two-value form the cSurvey route produces
    when plan and profile print at different scales — `profil/tlocrt:
    1:200/1:100` does not fit 43 pt on one line at any readable size, so it is
    set as `profil 1:200` over `tlocrt 1:100`. A single-value Mjerilo,
    including the `1:` stub, renders exactly as before.
  - **Ekipa** wraps when one line would have to go below `WRAP_BELOW_SIZE`
    (8 pt, the drafter's own size for that cell): Microsoft Sans Serif puts a
    three-person team at 6.75 pt on one line and does not fit a four-person one
    at all, which is why the v1.0 example itself sets that cell over two. The
    break goes at a comma, the comma stays on the first line, and the two
    halves are chosen by **measured** width so one long name pulls the break.
  - Both lines of a wrapped cell take **one size** — the tighter line's. The
    block is centred in the cell and its size capped so it fits between the
    rules, derived from the face's own ascent and descent
    (`addresses.MULTILINE_PADDING`) rather than from fixed baseline fractions:
    the first try, a third and two thirds of the cell height, put the two lines
    0.9 pt into each other once the template moved to Microsoft Sans Serif.
- **The value is formatted the drafter's way before it is measured** — names
  abbreviated, kota rounded, depth signed, a zero dropped. That is what keeps a
  three-person Ekipa at 9.5 pt instead of 6.25; see
  [Decided while building](#decided-while-building-2026-09-19).

**No cell is delivered empty** (user, 2026-09-20). An empty cell in Illustrator
is not an empty text box — it is *no* text box, so filling it in means drawing
one first, at the right size in the right place. Every cell the sources could
not fill therefore carries a stub: `?` where somebody could still record the
value (`addresses.STUB_UNKNOWN`), `/` where there is nothing to record
(`STUB_NOT_APPLICABLE`). The stubs are `source="stub"` in the sidecar and are
not counted as filled fields on the run. `addresses.STUBS` maps the cells that
read `/` instead of `?` — **Broj pločice** (a cave may carry no plaque) and
**Ekipa** (a cave may have been surveyed solo), the user's two, 2026-09-20.

## The font question

The template's own font is a **subset** carrying only the glyphs its example
text used. Typesetting new values with it would fail on the first letter the
example lacks, so the generator brings its own font, resolved in tiers:

1. A configurable override in `config.yaml` (`sastavnica.font_path`).
2. **Microsoft Sans Serif** (`C:\Windows\Fonts\micross.ttf`) — the face the
   v1.0 template is authored in, and part of Windows, so it is on every machine
   that will ever open a sastavnica.
3. A system fallback (Arial / Segoe UI / Calibri), named in a run note.

### Why it is no longer Myriad Pro (user, 2026-09-20)

Until v1.0 the template was set in Myriad Pro, so the renderer used it too —
found in the local Illustrator install, never bundled, because it is licensed
with Illustrator. It looked right in every PDF viewer and was **broken in the
one application the document is made for.** Opened in Illustrator, the
prefilled values came up as `Myriad#20Pro#20Regular*`, red-underlined as a
missing font and therefore not editable.

Two separate causes, and both are fixed:

- **The name.** PyMuPDF embeds an inserted face as a Type0/Identity-H CID
  subset whose `/BaseFont` carries the font's *display* name, spaces and all
  (`/Microsoft#20Sans#20Serif#20Regular`), while the descendant CIDFont carries
  the PostScript name. Nothing installed answers to the display name, so no
  reader can resolve it. `render.use_postscript_font_name` rewrites it from the
  face's own `name` table (nameID 6, `fonts.postscript_name`) after subsetting,
  keeping the `ABCDEF+` tag — which PDF 32000-1 §9.7.6.1 asks for anyway: a
  Type 0 font's BaseFont shall be its descendant's.
- **The face.** Myriad Pro is on a machine only because Illustrator put it
  there. Microsoft Sans Serif ships with Windows, so the labels and the values
  now resolve to the same installed family on any machine.

Two consequences worth knowing. Microsoft Sans Serif is **wider** than Myriad,
so the drafter's own sizes came down with it (most 10 pt values are 9 pt in
v1.0) and the Ekipa cell no longer holds a three-person team on one line —
which is why v1.0 sets that cell over two. And PyMuPDF's generated `ToUnicode`
maps this face's space glyph to U+00A0, because space and no-break space share
it: the drawn page is identical, only extracted text differs, so comparisons
normalise it.

### Soft hyphens (found 2026-09-20, on the first SB 1256 nacrt)

Opened in Illustrator, `051-716` read `051716` and `-14 m` read `14 m`. The glyphs were there;
the *meaning* was wrong: in `micross.ttf` (and `arial.ttf`) one glyph serves both U+002D and
U+00AD, one both U+0020 and U+00A0, and MuPDF's generated ToUnicode CMap picks the higher code
point — so the PDF said *soft hyphen*, which Illustrator treats as a discretionary hyphen and
hides. Subsetting is not the cause (reproduced without it). `render.plain_hyphens_and_spaces`
rewrites every ToUnicode CMap back to U+002D / U+0020 after rendering, and `compose_nacrt` runs
it again on the composed page because the sastavnica's fonts travel into it. Regression test:
`test_hyphens_and_spaces_are_plain_characters_not_soft_ones`.

## The blank-template builder

A one-time step per template version, not a runtime one:
`sastavnica-template/tools/build_blank.py` reads the authored PDF, removes the
fifteen placeholder values, and writes
`sastavnica-template/templates/sastavnica_blank_v1.pdf` — the committed artifact
the prefill actually fills. Re-run it when the drafter revises the `.ai`.

**The algorithm: content-stream surgery, not redaction.** Walk the page's
content stream tracking the active fill colour; drop every `Tj`/`TJ` operator
issued under the value colour, keep everything else — including the `Tm`/`Td`
positioning, which is relative to the text-line matrix and so stays valid.
Measured result: 15 text operators removed, all 15 labels intact, all 59 logo
and rule paths intact.

PyMuPDF's redaction API was tried first and **does not work here**: redaction
removes any glyph whose box intersects the rectangle, and the 10 pt value boxes
overlap the 5 pt label boxes above them, so `HTRS koordinate:` came back as
`HTRS koordin` and `Nadmorska visina:` as `N`. Recorded so nobody
re-discovers it.

**It also strips the embedded `.ai`.** The authored PDF was exported with
*Preserve Illustrator Editing Capabilities*, so the page carried
`/PieceInfo → /Illustrator → /Private → /AIPDFPrivateData*` — a complete copy of
the original artwork, 80 % of the file. Every PDF **viewer** ignores it and
renders the page content; **Illustrator prefers it**. So the first delivered
sastavnica looked right in Acrobat and opened in Illustrator showing the
template's example values — the one defect that no PDF viewer can reveal (user,
2026-09-19). The builder now drops `/PieceInfo`, the stale `/Thumb` preview
(which also still pictured the example values) and the XMP packet naming the
authored file; the blank went from 226 KB to 45 KB. Illustrator then parses the
page content into editable paths and text, which is what it should have been
doing all along. `verify()` asserts the payload is gone, and
`tests/test_sastavnica.py` asserts it on both the blank and a rendered output.

The alternative — asking the drafter to save a values-deleted `.ai` by hand — is
strictly simpler and stays available; the builder exists so the repo can derive
the blank from whatever the drafter authors, without a second file to keep in
sync.

## Delivery

Identical in shape to `osz prefill`, because the drafter looks in the same place:

- **Name**: `SB_<zero-padded Redni broj>_sastavnica.pdf` (`osz prefill` writes
  `SB_<padded>_OSZ.docx`).
- **Destination**: the cave's intake leaf under
  `!!!Digitalizacija/!Za digitalizirat/`, found with the shared
  `intake.scanner.find_cave_leaf` and created with
  `osz.prefill.intake_folder_name` when the cave has none — the same folder that
  already holds its OSZ, photos and survey files, and the folder the drafter
  opens to start digitizing.
- **Run artifacts**: `runs/sastavnica/<padded>/` — the PDF copy, a
  `sastavnica.json` sidecar (every field with its value, source and chosen
  size), and `dopune-sb.csv` when the finders proposed anything.
- **Re-runs replace their own output, and only their own.** The delivered PDF
  carries a metadata stamp (`prefill.STAMP`); a file under that name WITHOUT the
  stamp is refused with a warning rather than overwritten, `--force` being the
  way past. An Illustrator re-save replaces the producer, so a sastavnica the
  drafter has already worked on is protected by the same rule
  ([decision 7](#settled-user-2026-09-19)).

## Module layout

`sastavnica/` inside `cave_dossier`, **not a new feature**: it reads SB through
`SBReader`, the leaf through `intake.scanner`, the OSZ through `osz.reader` and
the coordinates through `geo/`. A separate feature could not import any of that
(features integrate via artifacts, never imports), so a sibling module beside
`osz/` and `georef/` is the only placement consistent with the architecture. The
*pipeline branch* is what is new; the code is one more module.

```
src/cave_dossier/sastavnica/
  addresses.py   # the cell table above + the typesetting constants
  render.py      # blank PDF + {key: value} -> filled PDF (centring, fit, font)
  fonts.py       # the three-tier font resolution
  prefill.py     # orchestrator: SB + OSZ + geo -> fields -> render -> deliver
  compose.py     # (2026-09-20) pure geometry: ink bbox, placement, refusals
  nacrt.py       # orchestrator for `cavedossier nacrt` — prefill + compose + deliver
  models.py      # the sastavnica.json and nacrt.json sidecars
sastavnica-template/
  templates/!SUE_sastavnica.pdf          # authored, copied verbatim from the Drive
  templates/sastavnica_blank_v1.pdf      # generated by the builder, committed
  tools/build_blank.py                   # the stripper (+ --check)
  tools/inspect_sastavnica.py            # dump cells/colours/fonts of any version
```

Only `config.yaml` carries anything tunable — `sastavnica.font_path` and
`sastavnica.society`. The geometry stays in code because it is a property of the
template, not of a machine or a society.

## Fail-soft behaviour

The same contract as every other delivery in this feature — the run copy is
always the fallback, and no single missing input kills the run:

- No OSZ in the leaf → the five OSZ-only cells stay blank, with a note.
- Geo finders offline or failing → SB values only, with a note.
- No coordinates in SB → no HTRS, no kota, no lokacija; the rest still renders.
- Drive unreachable, or the file open in Acrobat → run copy kept, note explains.
- No usable font anywhere → hard error (nothing sensible can be drawn).

## Testing

Per the house protocol — synthetic fixtures first, then the real thing. All of
this is `tests/test_sastavnica.py` (31 tests):

1. **Geometry regression**: fill the blank with the authored example values and
   assert the rendered text bboxes match the authored PDF's to <1 pt. This is
   the test that catches a template change nobody told the code about.
2. **Fit**: a deliberately over-long cave name lands at the floor size and still
   fits the cell; a short one stays at 10 pt.
3. **Diacritics**: č ć ž š đ Č Ć Ž Š Đ render as glyphs, not notdef boxes.
4. **Field map**: against `tests/fixtures/mini_sb.xlsx` plus a synthetic filled
   v10 OSZ, each of the fifteen cells resolves from the expected source.
5. **Live**: run on a real cave that has both an SB row and a filled OSZ, open
   the result in Illustrator, confirm it places at 100 % and the text is
   editable vector text. Done on SB 1220 and SB 811 (2026-09-19); 1220's
   sastavnica is delivered in its intake leaf beside its DXF exports.

## Prod

**Shipped as prod v1.4 on 2026-09-19, the same day** —
`cavedossier_sastavnica_v1.4.bat` sits beside the `osz prefill` and
`photos process` launchers in `!!!Digitalizacija/SurveyScraper5/`. Nothing new
was required of the prod machinery: an entry in `build_prod.py`'s
`PROD_COMMANDS`, a branch in the bootstrap's `switch ($Command)`, the blank PDF
added to `BUNDLE_FILES`, and `sastavnica` (PyMuPDF) added to the pip extras.

The **font is the one thing that does not ride along** — Myriad Pro is licensed
with Illustrator, so it is found on the machine. That is sound precisely here:
this launcher's audience is the people who already run Illustrator, which makes
it arguably the best-fitting of the three.

Validated the way the others were: a clean install from the published folder
(`%LOCALAPPDATA%\CaveDossier1.4` — Python check, bundle, venv, pip,
Chromium, geo copy) followed by a real delivery of SB 1220's sastavnica, with
the run resolving `MyriadPro-Regular.otf [myriad]` from the prod install.

## Settled (user, 2026-09-19)

The eight questions this note opened with, answered, and what each one became:

| # | Question | Decision | Where it lives |
|---|---|---|---|
| 1 | Lokacija composition | **Lokalitet + Najbliže mjesto, nothing else** — the cell is narrow | `_resolve_lokacija` |
| 2 | Katastarski broj | **Never filled; keep the template's `0000`.** The number is assigned at the very end and the archivist edits the PDF by hand. Carrying it across every product at once (SB, Nacrt, OSZ) is a later step of its own | `addresses.CONSTANTS` |
| 3 | Mjerilo | **Blank, but keep `1:`** as a visible stub. **Superseded 2026-09-20 for the cSurvey route only** (project 0004, T3): `cavedossier nacrt` knows the scale the designs were printed at and writes it — `1:100`, or two lines when the two designs differ. The Illustrator route never reads that file and keeps the stub | `addresses.CONSTANTS`; `compose.DIMENSION_FIELDS` |
| 4 | Stvarna vs tlocrtna duljina | SB's `Duljina` is the **stvarna** one; tlocrtna stays blank until a zapisnik carries it | `_resolve_fields` |
| 5 | Output page | **Keep the A4 page exactly as authored** — it places into Illustrator at 100 % | the renderer never touches the page box |
| 6 | Istražili | The OSZ almost always names it; **`SU Estavela` when it does not** | `config.yaml` `sastavnica.society` |
| 7 | Overwrite policy | Collisions are near-impossible (a drafter names their own file differently), so on one: **refuse and warn** | `_deliver` + the metadata stamp |
| 8 | Command name | **`cavedossier sastavnica <broj>`** | `cli.py` |

Decision 7 needed one mechanism the question did not: a re-run must not refuse
its OWN previous output. The delivered PDF is therefore stamped in its metadata
(`prefill.STAMP`), and only an **unstamped** file is refused. That lands exactly
right — an Illustrator re-save replaces the producer, so a sastavnica the
drafter has already worked on is protected, while an ordinary re-run replaces
itself silently. `--force` is the way past.

## Decided while building (2026-09-19)

Four rules the authored example implied but the questions never reached. All
four came out of running the tool on real caves (SB 811, 1220):

- **Names take the drafter's abbreviated form** — `Dario Maršanić` →
  `D. Maršanić`. Not cosmetic: the full names of a three-person team shrank the
  Ekipa cell to 6.25 pt, where the drafter's own form sits at 9.5 pt. Reuses
  `core.person_aliases.to_sb_shorthand`; an outside-society bracket survives
  (`A. Lipovac (SOV)`), and a name that is not "First Last" passes through.
- **Kota is rounded to whole metres** — SB carries the grid's decimals
  (`1285,92`), and the authored example shows a bare `1033 m`.
- **A zero dimension reads as "not surveyed yet"** and leaves the cell blank.
  SB writes `0` for both; `0 m` printed on a nacrt is worse than an empty box.
- **A length is formatted only when the cell is nothing but a number.**
  Deliberately stricter than `parse_optional_float`: a recorder's `oko 20` is a
  hedge, and flattening it to `20 m` would turn an estimate into a measurement.

One pre-existing bug surfaced on the way and was fixed: `core.people`'s
separator regex treated the conjunction "i" as word-bounded rather than
space-bounded, so **every author whose first name starts with I lost their
initial** — `I. Dujmović` split into `. Dujmović`. That fed the izjava gates,
not just this tool. Regression test in `tests/test_people.py`.

## Still open

- **Najbliže mjesto vs the drafter's intuition.** The sastavnica inherits the
  OSZ's geo-admin-wins rule (user, 2026-09-01), so SB 811's Lokacija reads
  *Kobiljak, Grižane-Belgrad* where SB says *Potkobiljak*. Consistency between
  the two documents is the reason to keep it; say if a printed nacrt should
  prefer SB's wording instead.
- **A vendored OFL fallback font** (Source Sans 3) for a machine without
  Illustrator. Not a blocker — such a machine is not drafting in Illustrator
  either — so it stays a backlog item rather than a bundled binary.
