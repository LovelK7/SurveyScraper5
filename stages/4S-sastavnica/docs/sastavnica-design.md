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
| Committed copy | [`sastavnica-template/templates/!SUE_sastavnica.pdf`](../template-workbench/templates) |
| Pages | 1, A4 portrait (595.28 × 841.89 pt), no rotation |
| Form fields | **none** — not an AcroForm; there is nothing to "fill" in the PDF sense |
| Images | **none** — the mammoth logo is 59 vector paths, so output stays fully vector |
| Fonts | one embedded subset, `ECYHUF+MyriadPro-Regular` (Type1/CFF, custom encoding) |
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
| `broj_plocice` | Broj pločice | 81.35 | 69.66 | 120.18 | 89.74 | 10 |
| `htrs` | HTRS koordinate | 120.18 | 69.66 | 248.12 | 89.74 | 10 |
| `nadmorska_visina` | Nadmorska visina | 248.12 | 69.66 | 291.43 | 89.74 | 10 |
| `lokacija` | Lokacija | 81.35 | 89.74 | 204.82 | 109.82 | 9 |
| `stvarna_duljina` | Stvarna duljina | 204.82 | 89.74 | 248.12 | 109.82 | 10 |
| `tlocrtna_duljina` | Tlocrtna duljina | 248.12 | 89.74 | 291.43 | 109.82 | 10 |
| `crtali` | Crtali | 39.85 | 109.82 | 120.18 | 129.88 | 9 |
| `mjerili` | Mjerili | 120.18 | 109.82 | 204.82 | 129.88 | 9 |
| `dubina` | Dubina/vis. razlika | 204.82 | 109.82 | 248.12 | 129.88 | 10 |
| `mjerilo` | Mjerilo | 248.12 | 109.82 | 291.43 | 129.88 | 10 |
| `istrazili` | Istražili | 39.85 | 129.88 | 95.03 | 149.94 | 8 |
| `ekipa` | Ekipa | 95.03 | 129.88 | 204.82 | 149.94 | 8 |
| `datum` | Datum/razdoblje istraživanja | 204.82 | 129.88 | 291.43 | 149.94 | 9 |

The authored sizes vary because the drafter **shrank each value by hand until it
fit** — that is the behaviour the generator has to reproduce automatically
(below). This table becomes `sastavnica/addresses.py`, the direct counterpart of
[`osz/addresses.py`](../../4O-osz/src/cave_dossier/osz/addresses.py): one map per template
version, regenerated by the builder tool whenever the `.ai` changes.

## Field map — where each of the fifteen values comes from

Three sources, in precedence order per field: **SB** (the master), the cave's
**filled OSZ** in its intake leaf (read with the existing `osz/reader.read_osz`,
which returns every `V10` key), and the **geo finders**. Nothing here writes
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
| Stvarna duljina | OSZ `duljina` → SB `Duljina` | `"<n> m"`; a **0** means "not surveyed yet" and stays blank |
| Tlocrtna duljina | OSZ `horizontalna_duljina` | not in SB — blank when no OSZ |
| Dubina/vis. razlika | OSZ `dubina` / `visinska_razlika` → SB `Dubina` | `"-<n> m"` for jame |
| Mjerilo | — | the drafter's own choice, made while drawing; the stub `1:` stays ([decision 3](#settled-user-2026-09-19)) |
| Crtali | OSZ `crtali` → SB `Autori nacrta ili izvor` | the SB cell holds the *source* for queued caves, so the OSZ wins; **abbreviated** |
| Mjerili | OSZ `mjerili` (+ `mjerili_2`) | not in SB; **abbreviated** |
| Istražili | OSZ `istrazile_udruge` (+ `_2`) → `sastavnica.society` | a society, so never abbreviated |
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
- **Baseline = row bottom − 4.6 pt.** The authored baselines cluster at
  −4.54 · −4.56 · −4.63 · −4.64 · −4.70 across the five rows; the outliers are
  hand nudges. One uniform rule reads better than five copied numbers.
- **Shrink to fit**: start at 10 pt, step down by 0.25 pt while
  `Font.text_length(text, size) > cell_width − 2 × 2 pt`, floor at ~6 pt. The
  2 pt side padding is what the drafter's own 8 pt choice for *Ekipa* implies.
- **Colour** `#030505`, the authored value colour.
- **Never wrap.** Every cell is one line; a value too long even at the floor
  size is set at the floor size and named in a printed warning.
- **The value is formatted the drafter's way before it is measured** — names
  abbreviated, kota rounded, depth signed, a zero dropped. That is what keeps a
  three-person Ekipa at 9.5 pt instead of 6.25; see
  [Decided while building](#decided-while-building-2026-09-19).

Nothing is inserted for an empty value — the cell simply stays blank, ready for
the drafter to type into in Illustrator.

## The font question

The template's own font is a **subset** of Myriad Pro carrying only the glyphs
its example text used. Typesetting new values with it would fail on the first
letter the example lacks, so the generator brings its own font. Three tiers, in
order:

1. **Myriad Pro**, when the machine has it. Every machine on this branch runs
   Illustrator, which installs
   `…/Adobe Illustrator <year>/Support Files/Required/Fonts/MyriadPro-Regular.otf`
   — present and verified on the dev machine, full Croatian coverage. Using it
   makes the output typographically identical to the authored labels.
2. A **vendored OFL fallback** for any machine without it — Source Sans 3 is the
   closest free match (same designer lineage as Myriad) and is redistributable,
   so it can ride in the prod bundle the way the OSZ template does.
3. A configurable override in `config.yaml`, for a society that uses another face.

Never redistribute Myriad Pro itself — it is licensed with Illustrator, so it is
*found*, never bundled.

**Validation:** with Myriad Pro the computed widths reproduce the authored ones
exactly — `0000` 20.52/20.52 pt, `051-580` 33.85/33.85, `339823 5037995`
68.81/68.81, `L. Kukuljan` at 9 pt 40.68/40.66. The metric model is right.

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
  models.py      # the sastavnica.json sidecar
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
| 3 | Mjerilo | **Blank, but keep `1:`** as a visible stub | `addresses.CONSTANTS` |
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
