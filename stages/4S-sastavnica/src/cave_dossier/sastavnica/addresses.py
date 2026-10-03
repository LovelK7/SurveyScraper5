"""Cell geometry of the sastavnica template — PDF points, origin top-left.

Positional by necessity: the template is an Illustrator export with no form
fields and no structure, so a cell is a rectangle. Every number below was read
out of the authored ``!SUE_sastavnica_v2.pdf`` — the block's own stroked rules for
the boundaries, the example values for the typesetting rules — never assumed.

Hand-maintained, the same convention as ``osz/addresses.py``. Regenerate with::

    python sastavnica-template/tools/inspect_sastavnica.py --mode cells

whenever the drafter revises the ``.ai``, then re-run ``build_blank.py``. A new
template version replaces this map: v1's lives in git history, since nothing
renders onto v1 any more.

Template v2 (2026-10-03) verified against the committed export the same day.
"""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path

from cave_dossier.core.paths import repo_root

TEMPLATE_VERSION = "v2"

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
    None if repo_root() is None else repo_root() / _WORKBENCH / f"!SUE_sastavnica_{TEMPLATE_VERSION}.pdf"
)


@dataclass(frozen=True)
class Cell:
    """One labelled box. ``label`` is only for messages — the label text is
    printed by the template itself and is never written by this code.

    ``size`` is the size the **drafter** set that cell's value at in the
    authored template, and it is where the renderer starts: shrink-to-fit only
    ever goes down from here. It is per cell because the drafter's own choice
    is per cell — v2 sets row 1 at 10 pt, most of the rest at 9, Ekipa and
    Istražili at 8 — and starting every cell at 10 instead made the output
    visibly bigger than the template it is meant to match (user, 2026-09-20).
    """

    label: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float = 10.0
    # Right edge of the template's own printed label, for a cell whose value
    # shares a line with it (v2's Ekipa row is too low to put the value under
    # its label). None: the label sits above the value, which gets the whole
    # cell width.
    label_x1: float | None = None
    # Baseline distance above the bottom rule, when the cell needs its own
    # rather than BASELINE_LIFT.
    lift: float | None = None

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def centre_x(self) -> float:
        return (self.x0 + self.x1) / 2

    def text_span(self) -> tuple[float, float]:
        """(left, right) the value may occupy, padding already taken off;
        it is centred between the two. A label on the value's own line is kept
        clear of (user, 2026-10-03: Ekipa once printed over "Ekipa:")."""
        left = self.x0 + SIDE_PADDING
        if self.label_x1 is not None:
            left = max(left, self.label_x1 + LABEL_GAP)
        return left, self.x1 - SIDE_PADDING

    @property
    def baseline(self) -> float:
        return self.y1 - (BASELINE_LIFT if self.lift is None else self.lift)


# Field key -> cell. Keys are the sastavnica's own; where a key names the same
# thing as an OSZ v10 field the spelling is kept identical on purpose
# (`nacrt_uredio`, new in v2). Two vertical rules sit 0.07 pt apart in the
# drafter's file (198.74 the right edge of Lokacija/Mjerili/Nacrt uredio,
# 198.81 the left edge of the cells beside them); both are kept as measured.
V2: dict[str, Cell] = {
    "katastarski_broj": Cell("Katastarski broj", 81.35, 41.46, 120.18, 61.51, 10),
    "ime_objekta": Cell("Ime speleološkog objekta", 120.18, 41.46, 291.43, 61.51, 10),
    "broj_plocice": Cell("Broj pločice", 81.35, 61.51, 120.18, 81.58, 9),
    "htrs": Cell("HTRS koordinate", 120.18, 61.51, 244.28, 81.58, 9),
    "nadmorska_visina": Cell("Nadmorska visina", 244.28, 61.51, 291.43, 81.58, 9),
    "lokacija": Cell("Lokacija", 81.35, 81.58, 198.74, 101.66, 9),
    "stvarna_duljina": Cell("Stvarna duljina", 198.81, 81.58, 244.28, 101.66, 9),
    "tlocrtna_duljina": Cell("Tlocrtna duljina", 244.28, 81.58, 291.43, 101.66, 9),
    "crtali": Cell("Crtali", 39.85, 101.66, 120.18, 121.72, 9),
    "mjerili": Cell("Mjerili", 120.18, 101.66, 198.74, 121.72, 9),
    "dubina": Cell("Dubina/vis. razlika", 198.81, 101.66, 244.28, 121.72, 9),
    # The drafter's example is 8 pt, but only because "1:500/1:300" does not fit
    # at 9: starting at the row's 9 lets a single "1:200" keep the row's size
    # while shrink-to-fit lands the two-scale form near the drafter's 8 anyway.
    "mjerilo": Cell("Mjerilo (profil/tlocrt)", 244.28, 101.66, 291.43, 121.72, 9),
    # A full-width row 12.6 pt high: the label sits on the value's line, so the
    # value starts right of it ("Ekipa:" ends at 55.82). The drafter's baseline
    # is 3.3 above the rule, which centres 8 pt caps in the row; the uniform
    # 4.3 would sit them a point high.
    "ekipa": Cell("Ekipa", 39.85, 121.72, 291.43, 134.31, 8,
                  label_x1=55.82, lift=3.3),
    "istrazili": Cell("Istražili", 39.85, 134.31, 120.18, 154.40, 8),
    "nacrt_uredio": Cell("Nacrt uredio", 120.18, 134.31, 198.74, 154.40, 9),
    "datum": Cell("Datum/razdoblje istraživanja", 198.81, 134.31, 291.43, 154.40, 9),
}

# The block itself, for the record: 251.58 x 112.94 pt ~ 88.7 x 39.8 mm at the
# top-left of an A4 page. The page is delivered exactly as authored (user,
# 2026-09-19) so it places into Illustrator at 100 % with no adjustment.
BLOCK = (39.85, 41.46, 291.43, 154.40)

# ── typesetting, measured off the authored values ────────────────────
# Baseline sits a constant distance above the cell's bottom rule. In v1.0 the
# authored baselines clustered at 4.11-4.59 below it (median 4.34); v2's spread
# wider (3.1-4.6, Istražili 5.5), hand nudges the drafter made in Illustrator.
# One uniform rule reads better than sixteen copied numbers; the one cell with
# a reason to differ (Ekipa, a shorter row) says so via Cell.lift. It was 4.6
# under the Myriad template, which put every value a quarter-point high.
BASELINE_LIFT = 4.3
# Side padding inside a cell before shrinking starts. 2 pt is what the drafter's
# own 8 pt choice for the v1 Ekipa cell implied.
SIDE_PADDING = 2.0
# Clearance between a printed label and a value set beside it on its line;
# v2's example Ekipa starts 2.1 pt after its label.
LABEL_GAP = 2.0
# The ceiling across every cell; each cell's own starting size is Cell.size.
MAX_FONT_SIZE = 10.0
MIN_FONT_SIZE = 6.0
FONT_STEP = 0.25
# The authored value colour: v2 sets the values in black (v1 was #030505).
VALUE_COLOR = (0.0, 0.0, 0.0)

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
