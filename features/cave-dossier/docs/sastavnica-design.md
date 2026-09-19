# Sastavnica prefill — `cavedossier sastavnica <Redni broj>` (design note)

The **sastavnica** is the title block that sits on a finished Nacrt: the society
logo plus fifteen labelled cells naming the cave, its numbers, its dimensions
and the people who surveyed it. It is an Illustrator asset (`!SUE_sastavnica.ai`
on the Drive) and today a drafter types all fifteen values into it by hand,
copying from SB and from the filled OSZ.

This note designs the step that stops that: **a PDF prefill** — same input and
same shape as `osz prefill`, a Redni broj in, a prefilled document delivered
into the cave's intake leaf. It is part [**2.1e**](../../../ARCHITECTURE.md#part-21e)
and bridge [**B13**](../../../ARCHITECTURE.md#b13), and it serves the
[Illustrator route](../../../ARCHITECTURE.md#two-routes-to-the-nacrt--csurvey-and-illustrator)
to the Nacrt (route B), which the society's own digitization instructions
already describe.

Status: **design only, not built.** Written 2026-09-19 from the user's spec plus
a measured spike against the authored template — every geometry number below was
read out of `!SUE_sastavnica.pdf`, not assumed, and the spike reproduced the
authored layout to 0.01 pt before the design was written down.

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
- [Open questions for the user](#open-questions-for-the-user)

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
| Committed copy | [`sastavnica-template/templates/!SUE_sastavnica.pdf`](../sastavnica-template/templates/) |
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
[`osz/addresses.py`](../src/cave_dossier/osz/addresses.py): one map per template
version, regenerated by the builder tool whenever the `.ai` changes.

## Field map — where each of the fifteen values comes from

Three sources, in precedence order per field: **SB** (the master), the cave's
**filled OSZ** in its intake leaf (read with the existing `osz/reader.read_osz`,
which returns every `V10` key), and the **geo finders**. Nothing here writes
anywhere; like `osz prefill`, any value the finders produce that SB lacks goes
out as a `dopune-sb.csv` review row for a person to paste.

| Cell | Source (in order) | Notes |
|---|---|---|
| Katastarski broj | SB `Katastarski broj SUE` | blank until the cave earns one — see [open question 2](#open-questions-for-the-user) |
| Ime speleološkog objekta | SB `Ime objekta` | |
| Broj pločice | SB `Broj pločice` | |
| HTRS koordinate | SB `X HTRS` + `Y HTRS` | `"<X> <Y>"`, integer metres — the authored form |
| Nadmorska visina | SB `Z` → `geo.elevation` kota | `"<n> m"`; SB wins, a mismatch is a note |
| Lokacija | `geo.locality` finding / SB `Lokalitet` · `Najbliže mjesto` | composition is [open question 1](#open-questions-for-the-user) |
| Stvarna duljina | OSZ `duljina` → SB `Duljina` | `"<n> m"` |
| Tlocrtna duljina | OSZ `horizontalna_duljina` | not in SB — blank when no OSZ |
| Dubina/vis. razlika | OSZ `dubina` / `visinska_razlika` → SB `Dubina` | `"-<n> m"` for jame |
| Mjerilo | — | the drafter's own choice, made while drawing; always blank |
| Crtali | OSZ `crtali` → SB `Autori nacrta ili izvor` | the SB cell holds the *source* for queued caves, so the OSZ wins |
| Mjerili | OSZ `mjerili` (+ `mjerili_2`) | not in SB |
| Istražili | OSZ `istrazile_udruge` (+ `_2`) | society default — [open question 6](#open-questions-for-the-user) |
| Ekipa | OSZ `clanovi_ekipe` (+ `_2`, `_3`) | joined with `, ` |
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
- **Re-runs are idempotent**: overwrite the delivered file unless its content
  would be unchanged. An existing file the **drafter has already edited** must
  not be silently overwritten — see [open question 7](#open-questions-for-the-user).

## Module layout

`sastavnica/` inside `cave_dossier`, **not a new feature**: it reads SB through
`SBReader`, the leaf through `intake.scanner`, the OSZ through `osz.reader` and
the coordinates through `geo/`. A separate feature could not import any of that
(features integrate via artifacts, never imports), so a sibling module beside
`osz/` and `georef/` is the only placement consistent with the architecture. The
*pipeline branch* is what is new; the code is one more module.

```
src/cave_dossier/sastavnica/
  addresses.py   # the cell table above, one map per template version
  render.py      # blank PDF + {key: value} -> filled PDF (centring, fit, font)
  fonts.py       # the three-tier font resolution
  prefill.py     # orchestrator: SB + OSZ + geo -> fields -> render -> deliver
sastavnica-template/
  templates/!SUE_sastavnica.pdf          # authored, copied from the Drive
  templates/sastavnica_blank_v1.pdf      # generated by the builder
  tools/build_blank.py                   # the stripper
  tools/inspect_sastavnica.py            # dump cells/colours/fonts of any version
```

## Fail-soft behaviour

The same contract as every other delivery in this feature — the run copy is
always the fallback, and no single missing input kills the run:

- No OSZ in the leaf → the five OSZ-only cells stay blank, with a note.
- Geo finders offline or failing → SB values only, with a note.
- No coordinates in SB → no HTRS, no kota, no lokacija; the rest still renders.
- Drive unreachable, or the file open in Acrobat → run copy kept, note explains.
- No usable font anywhere → hard error (nothing sensible can be drawn).

## Testing

Per the house protocol — synthetic fixtures first, then the real thing:

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
   editable vector text.

## Prod

Nothing new is required: the blank template and the fallback font ride in the
bundle exactly as the OSZ template does, the command takes only a Redni broj,
and output lands in a Drive dir that tolerates hand management. Once it
stabilizes it gets a launcher from `tools/build_prod.py` like the other two.
Worth noting that this branch's operators are the *Illustrator* users —
arguably the group that benefits most from a double-click launcher.

## Open questions for the user

1. **Lokacija composition.** The authored example reads
   `Obruč, Jelenje, Gorski kotar` — a massif, an općina and a region. The geo
   finder produces *lokalitet*, *najbliže mjesto*, *grad/općina* and *županija*,
   and SB carries `Lokalitet` + `Najbliže mjesto`. Which three, in which order?
   (Proposed default: `Lokalitet, Grad/općina, <wider region>` — but nothing in
   SB or the finders currently yields "Gorski kotar".)
2. **Katastarski broj.** `osz prefill` deliberately never fills it (the archivist
   assigns it last). But the sastavnica is drawn at the end, when the number
   often exists. Fill it from SB when present — or leave it blank always?
3. **Mjerilo.** Assumed always blank (the drafter picks the scale while drawing).
   Confirm, or name a default.
4. **Stvarna vs tlocrtna duljina.** SB has one `Duljina`. Is it the *stvarna*
   one (assumed), and should the tlocrtna cell stay blank until an OSZ exists?
5. **Output page.** Keep the A4 page exactly as authored (assumed — it then
   places into Illustrator identically), or crop to the block's 88.7 × 35.4 mm?
6. **Istražili.** Default to `SU Estavela` when no OSZ says otherwise?
7. **Overwrite policy.** If the drafter has already edited the delivered
   `SB_<broj>_sastavnica.pdf`, should a re-run back it up (`…_stari_<datum>`, as
   `osz prefill` does), refuse, or overwrite?
8. **Command name.** `cavedossier sastavnica <broj>` — or under a `pdf` group
   ("PDF prefill", as you phrased it), leaving room for other PDF outputs?
