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

from dataclasses import dataclass
from pathlib import Path

from cave_dossier.sastavnica.addresses import (
    BASELINE_LIFT,
    FONT_STEP,
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
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


def fit_size(font, text: str, cell: Cell) -> tuple[float, float, bool]:
    """(font size, drawn width, overflowed) for one value in one cell."""
    available = cell.width - 2 * SIDE_PADDING
    size = MAX_FONT_SIZE
    while size > MIN_FONT_SIZE and font.text_length(text, size) > available:
        size -= FONT_STEP
    width = font.text_length(text, size)
    return size, width, width > available


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
        size, width, overflowed = fit_size(font, text, cell)
        page.insert_text(
            (cell.centre_x - width / 2, cell.y1 - BASELINE_LIFT),
            text,
            fontname="sastavnica",
            fontsize=size,
            color=VALUE_COLOR,
        )
        placed.append(PlacedValue(key, text, size, width, overflowed))

    if metadata:
        doc.set_metadata({**(doc.metadata or {}), **metadata})
    doc.subset_fonts()          # embed only the glyphs actually used
    return doc.tobytes(garbage=4, deflate=True), placed
