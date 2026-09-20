"""Draw resolved values onto the blank sastavnica.

Pure geometry — no SB, no config, no delivery: a blank PDF plus
``{field key: text}`` in, PDF bytes out. That keeps the typesetting rules
testable against the authored template without a workbook anywhere near.

The rules come from measuring the drafter's own choices (see
``addresses.py``): every value is **centred** in its cell, sits on a baseline a
constant lift above the cell's bottom rule, and is **shrunk until it fits** —
which is exactly what the drafter does by hand, and why the authored example
carries values at 10, 9 and 8 pt. Nothing ever wraps: a cell is one line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.sastavnica.addresses import (
    BASELINE_LIFT,
    FONT_STEP,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    MULTILINE_BASELINES,
    SIDE_PADDING,
    V1,
    VALUE_COLOR,
    Cell,
)


@dataclass(frozen=True)
class PlacedValue:
    """One value as it was actually set — what the sidecar records."""

    key: str
    text: str
    font_size: float
    width: float
    overflowed: bool      # still too wide at MIN_FONT_SIZE


class RenderError(RuntimeError):
    """The blank template could not be filled; message is CLI-ready."""


def fit_size(font, text: str, cell: Cell,
             max_size: float = MAX_FONT_SIZE) -> tuple[float, float, bool]:
    """(font size, drawn width, overflowed) for one value in one cell."""
    available = cell.width - 2 * SIDE_PADDING
    size = max_size
    while size > MIN_FONT_SIZE and font.text_length(text, size) > available:
        size -= FONT_STEP
    width = font.text_length(text, size)
    return size, width, width > available


# The one cell that may carry two lines. On the cSurvey route plan and profile
# can be printed at different scales, and T4 then renders Mjerilo as
# "profil/tlocrt: 1:200/1:100" — which does not fit the 43 pt cell on one line
# at any readable size. Everything else in this template is one line by rule
# (see docs/sastavnica-design.md, "Typesetting rules"), and the single-value
# form of Mjerilo is untouched.
MULTILINE = {"mjerilo"}

_TWO_VALUE = re.compile(r"^\s*([^/:]+?)\s*/\s*([^/:]+?)\s*:\s*(\S+)\s*/\s*(\S+)\s*$")


def split_lines(key: str, text: str) -> list[str]:
    """`profil/tlocrt: 1:200/1:100` -> `["profil 1:200", "tlocrt 1:100"]`.

    Anything that is not that shape — `1:100`, the Illustrator route's `1:`
    stub, a hand-typed value — comes back as a single line, so no existing
    output changes.
    """
    if key not in MULTILINE:
        return [text]
    match = _TWO_VALUE.match(text)
    if match is None:
        return [text]
    left, right, first, second = match.groups()
    return [f"{left} {first}", f"{right} {second}"]


def _baselines(cell: Cell, count: int) -> list[float]:
    """Where the baselines of `count` lines sit inside one cell."""
    if count == 1:
        return [cell.y1 - BASELINE_LIFT]
    height = cell.y1 - cell.y0
    return [cell.y0 + fraction * height for fraction in MULTILINE_BASELINES[:count]]


def _line_cap(cell: Cell, count: int) -> float:
    """Largest font size that keeps `count` lines from colliding in one cell.

    The baseline gap is the hard limit: a size above it would put one line's
    descenders through the next line's ascenders.
    """
    if count == 1:
        return MAX_FONT_SIZE
    baselines = _baselines(cell, count)
    return min(MAX_FONT_SIZE, baselines[1] - baselines[0])


def render(blank_path: Path, values: dict[str, str], font_path: Path,
           cells: dict[str, Cell] | None = None,
           metadata: dict[str, str] | None = None) -> tuple[bytes, list[PlacedValue]]:
    """Fill the blank with ``values``; returns (PDF bytes, what was placed).

    Keys absent from ``values`` — or mapping to an empty string — are left
    blank, ready for the drafter to type into in Illustrator. An unknown key
    is an error, not a silent no-op: it means the address map and the caller
    disagree about the template.

    ``metadata`` is written onto the document; the caller uses it to stamp its
    own output so a later run can recognise it (see ``prefill.STAMP``).
    """
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RenderError(
            "PyMuPDF is required for the sastavnica: pip install -e .[sastavnica]"
        ) from exc

    cells = cells if cells is not None else V1
    unknown = sorted(set(values) - set(cells))
    if unknown:
        raise RenderError(f"Unknown sastavnica field(s): {', '.join(unknown)}")
    if not blank_path.exists():
        raise RenderError(
            f"Blank template not found: {blank_path} — run "
            "sastavnica-template/tools/build_blank.py"
        )

    font = pymupdf.Font(fontfile=str(font_path))
    doc = pymupdf.open(blank_path)
    page = doc[0]
    page.insert_font(fontname="sastavnica", fontfile=str(font_path))

    placed: list[PlacedValue] = []
    for key, cell in cells.items():
        text = (values.get(key) or "").strip()
        if not text:
            continue
        lines = split_lines(key, text)
        baselines = _baselines(cell, len(lines))
        cap = _line_cap(cell, len(lines))
        sizes, widths, overflows = [], [], []
        for line, baseline in zip(lines, baselines):
            size, width, overflowed = fit_size(font, line, cell, max_size=cap)
            page.insert_text(
                (cell.centre_x - width / 2, baseline),
                line,
                fontname="sastavnica",
                fontsize=size,
                color=VALUE_COLOR,
            )
            sizes.append(size)
            widths.append(width)
            overflows.append(overflowed)
        # One record per CELL, not per line: the sidecar answers "is this cell
        # cramped?", so the tightest line is the one worth reporting.
        placed.append(PlacedValue(key, text, min(sizes), max(widths),
                                  any(overflows)))

    if metadata:
        doc.set_metadata({**(doc.metadata or {}), **metadata})
    doc.subset_fonts()          # embed only the glyphs actually used
    return doc.tobytes(garbage=4, deflate=True), placed
