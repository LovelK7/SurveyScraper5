"""Cell geometry of the sastavnica template — PDF points, origin top-left.

Positional by necessity: the template is an Illustrator export with no form
fields and no structure, so a cell is a rectangle. Every number below was read
out of the authored ``!SUE_sastavnica.pdf`` — the block's own stroked rules for
the boundaries, the example values for the typesetting rules — never assumed.

Hand-maintained, the same convention as ``osz/addresses.py``. Regenerate with::

    python sastavnica-template/tools/inspect_sastavnica.py --mode cells

whenever the drafter revises the ``.ai``, then re-run ``build_blank.py``. A new
template version gets its own map beside this one.

Verified against the committed template 2026-09-19.
"""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

from cave_dossier.core.paths import repo_root

TEMPLATE_VERSION = "v1"

# The blank is a package asset — the renderer fills it on every run, so it
# ships with the code and with the prod bundle.
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
BLANK_TEMPLATE = TEMPLATE_DIR / f"sastavnica_blank_{TEMPLATE_VERSION}.pdf"

# The AUTHORED Illustrator export is a BUILD-TIME input: template-workbench/
# tools/build_blank.py consumes it once to generate the blank above. It is
# never read at runtime and never bundled, so it stays in the workbench and
# is None in a prod install.
_WORKBENCH = "stages/4S-sastavnica/template-workbench/templates"
AUTHORED_TEMPLATE = (
    None if repo_root() is None else repo_root() / _WORKBENCH / "!SUE_sastavnica.pdf"
)


@dataclass(frozen=True)
class Cell:
    """One labelled box. ``label`` is only for messages — the label text is
    printed by the template itself and is never written by this code.

    ``size`` is the size the **drafter** set that cell's value at in the
    authored template, and it is where the renderer starts: shrink-to-fit only
    ever goes down from here. It is per cell because the drafter's own choice
    is per cell — v1.0 sets row 1 at 10 pt, rows 2 to 4 at 9 and row 5 at 8 —
    and starting every cell at 10 instead made the output visibly bigger than
    the template it is meant to match (user, 2026-09-20).
    """

    label: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float = 10.0

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def centre_x(self) -> float:
        return (self.x0 + self.x1) / 2


# Field key -> cell. Keys are the sastavnica's own; where a key names the same
# thing as an OSZ v10 field the spelling is kept identical on purpose.
V1: dict[str, Cell] = {
    "katastarski_broj": Cell("Katastarski broj", 81.35, 49.58, 120.18, 69.66, 10),
    "ime_objekta": Cell("Ime speleološkog objekta", 120.18, 49.58, 291.43, 69.66, 10),
    "broj_plocice": Cell("Broj pločice", 81.35, 69.66, 120.18, 89.74, 9),
    "htrs": Cell("HTRS koordinate", 120.18, 69.66, 248.12, 89.74, 9),
    "nadmorska_visina": Cell("Nadmorska visina", 248.12, 69.66, 291.43, 89.74, 9),
    "lokacija": Cell("Lokacija", 81.35, 89.74, 204.82, 109.82, 9),
    "stvarna_duljina": Cell("Stvarna duljina", 204.82, 89.74, 248.12, 109.82, 9),
    "tlocrtna_duljina": Cell("Tlocrtna duljina", 248.12, 89.74, 291.43, 109.82, 9),
    "crtali": Cell("Crtali", 39.85, 109.82, 120.18, 129.88, 9),
    "mjerili": Cell("Mjerili", 120.18, 109.82, 204.82, 129.88, 9),
    "dubina": Cell("Dubina/vis. razlika", 204.82, 109.82, 248.12, 129.88, 9),
    "mjerilo": Cell("Mjerilo", 248.12, 109.82, 291.43, 129.88, 9),
    "istrazili": Cell("Istražili", 39.85, 129.88, 95.03, 149.94, 8),
    "ekipa": Cell("Ekipa", 95.03, 129.88, 204.82, 149.94, 8),
    "datum": Cell("Datum/razdoblje istraživanja", 204.82, 129.88, 291.43, 149.94, 9),
}

# The block itself, for the record: 251.58 x 100.36 pt ~ 88.7 x 35.4 mm at the
# top-left of an A4 page. The page is delivered exactly as authored (user,
# 2026-09-19) so it places into Illustrator at 100 % with no adjustment.
BLOCK = (39.85, 49.58, 291.43, 149.94)

# ── typesetting, measured off the authored values ────────────────────
# Baseline sits a constant distance above the cell's bottom rule. In v1.0 the
# authored baselines cluster at 4.11-4.59 below it (median 4.34); the four in
# row 2 and `datum` sit at 3.2, hand nudges the drafter made in Illustrator.
# One uniform rule reads better than fifteen copied numbers. Re-measured
# 2026-09-20 for v1.0 — it was 4.6 under the Myriad template, which put every
# value a quarter-point high.
BASELINE_LIFT = 4.3
# Side padding inside a cell before shrinking starts. 2 pt is what the drafter's
# own 8 pt choice for the Ekipa cell implies.
SIDE_PADDING = 2.0
# A cell that may carry TWO lines (only Mjerilo does, and only on the cSurvey
# route, where plan and profile can be printed at different scales — see
# render.MULTILINE). The lines are set as a block centred in the cell, their
# size capped so the block fits between the rules with this much clearance at
# each end. Derived from the face's own ascent and descent rather than from
# fixed baseline fractions, because those only hold for one font: the first
# try, a third and two thirds of the cell height, put the two lines 0.9 pt into
# each other once the template moved from Myriad Pro to Microsoft Sans Serif.
MULTILINE_PADDING = 0.6
# A one-line value that would have to be set below this takes a second line
# instead, where its cell allows one. The drafter's own Ekipa is 8 pt, and
# their v1.0 example wraps that cell rather than going under it.
WRAP_BELOW_SIZE = 8.0
# The ceiling across every cell; each cell's own starting size is Cell.size.
MAX_FONT_SIZE = 10.0
MIN_FONT_SIZE = 6.0
FONT_STEP = 0.25
# The authored value colour (#030505), as an RGB triple for PyMuPDF.
VALUE_COLOR = (0.012, 0.020, 0.020)

# Cells that are never data-driven (user, 2026-09-19):
#   Katastarski broj — the archivist assigns it at the very end and edits the
#   PDF by hand, so the prefill keeps the template's own 0000 placeholder.
#   Carrying the number across SB/Nacrt/OSZ at once is a later step.
#   Mjerilo — the drafter picks the scale while drawing; "1:" is left as a
#   visible stub rather than an empty box.
CONSTANTS: dict[str, str] = {
    "katastarski_broj": "0000",
    "mjerilo": "1:",
}

# ── stubs: no cell is ever delivered empty ───────────────────────────
# A finished sastavnica is edited in Illustrator, and an EMPTY cell there is not
# an empty text box — it is *no* text box, so filling it in means drawing one
# first, at the right size, in the right place. A stub costs one click instead
# (user, 2026-09-20). Two of them:
STUB_UNKNOWN = "?"            # nobody recorded it, and somebody could
STUB_NOT_APPLICABLE = "/"     # there is nothing to record
# Per-field override; everything not listed gets STUB_UNKNOWN. Which cells are
# "not applicable" rather than merely unknown is the society's call, not a thing
# the tool can derive — these two are the user's (2026-09-20): a cave with no
# plaque has no plaque number, and a cave surveyed solo has no team.
STUBS: dict[str, str] = {
    "broj_plocice": STUB_NOT_APPLICABLE,
    "ekipa": STUB_NOT_APPLICABLE,
}


def stub_for(key: str) -> str:
    return STUBS.get(key, STUB_UNKNOWN)
