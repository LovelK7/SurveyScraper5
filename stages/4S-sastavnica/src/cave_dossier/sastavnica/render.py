"""Draw resolved values onto the blank sastavnica.

Pure geometry — no SB, no config, no delivery: a blank PDF plus
``{field key: text}`` in, PDF bytes out. That keeps the typesetting rules
testable against the authored template without a workbook anywhere near.

The rules come from measuring the drafter's own choices (see
``addresses.py``): every value is **centred** in its cell, starts at the size
the drafter set that cell at — 10, 9 or 8 pt, per cell — sits on a baseline a
constant lift above the cell's bottom rule, and is **shrunk until it fits**,
which is exactly what the drafter does by hand. A cell is one line, except the
two in ``MULTILINE`` that may take a second rather than shrink out of
legibility.
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
    MULTILINE_PADDING,
    WRAP_BELOW_SIZE,
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
             max_size: float | None = None) -> tuple[float, float, bool]:
    """(font size, drawn width, overflowed) for one value in one cell.

    Starts at the cell's **authored** size — what the drafter set that cell at —
    and shrinks from there; never grows past it.
    """
    available = cell.width - 2 * SIDE_PADDING
    size = cell.size if max_size is None else min(max_size, cell.size)
    while size > MIN_FONT_SIZE and font.text_length(text, size) > available:
        size -= FONT_STEP
    width = font.text_length(text, size)
    return size, width, width > available


# The cells that may carry two lines. Everything else in this template is one
# line by rule (docs/sastavnica-design.md, "Typesetting rules"); these two earn
# the exception for different reasons, and both come from the drafter's own
# v1.0 example:
#   mjerilo — on the cSurvey route plan and profile can print at different
#     scales, and T4 then renders "profil/tlocrt: 1:200/1:100", which does not
#     fit the 43 pt cell on one line at any readable size. A single-value
#     Mjerilo is untouched.
#   ekipa  — a three-person team drops to 6.75 pt on one line in Microsoft Sans
#     Serif, where the drafter chose 8; a four-person one does not fit at all.
MULTILINE = {"mjerilo", "ekipa"}

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


def lay_out_lines(font, cell: Cell, key: str, text: str) -> list[str]:
    """The lines to set in one cell — usually just ``[text]``.

    A multi-line cell takes a second line only when it needs one: Mjerilo when
    the value is the two-scale form, Ekipa (and anything else added to
    ``MULTILINE``) when one line would have to be set below ``WRAP_BELOW_SIZE``.
    Whatever fits stays on one line, at one line's size.
    """
    if key not in MULTILINE:
        return [text]
    fixed = split_lines(key, text)
    if len(fixed) > 1:
        return fixed
    size, _width, overflowed = fit_size(font, text, cell)
    if size >= WRAP_BELOW_SIZE and not overflowed:
        return [text]
    return _wrap_at_comma(font, text) or [text]


def _wrap_at_comma(font, text: str) -> list[str] | None:
    """Split a comma-separated list into the two most even halves, or None.

    Names, so the break goes at a comma and the comma stays on the first line —
    the drafter's own form. Evenness is measured, not counted: two short names
    beside one long one should not make a ragged pair.
    """
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) < 2:
        return None
    best = None
    for cut in range(1, len(parts)):
        pair = [", ".join(parts[:cut]) + ",", ", ".join(parts[cut:])]
        widest = max(font.text_length(line, MAX_FONT_SIZE) for line in pair)
        # measured at one size for both halves, so the comparison is fair
        if best is None or widest < best[0]:
            best = (widest, pair)
    return best[1]


def _multiline(font, cell: Cell, count: int,
               size: float | None = None) -> tuple[list[float], float]:
    """(baselines, largest usable size) for `count` lines in one cell.

    One line keeps the template's own rule — a constant lift above the bottom
    rule. Two or more are set as a block centred in the cell, at a size small
    enough that the block fits between the rules: the face's ascent-to-descent
    span is what decides that, not a guess about where the baselines go. Pass
    `size` on a second call to re-centre the block once each line has been fitted.
    """
    if count == 1:
        return [cell.y1 - BASELINE_LIFT], cell.size
    height = cell.y1 - cell.y0
    line_height = font.ascender - font.descender          # in em
    cap = min(cell.size,
              (height - 2 * MULTILINE_PADDING) / (count * line_height))
    used = cap if size is None else min(size, cap)
    top = cell.y0 + (height - count * line_height * used) / 2
    return ([top + font.ascender * used + i * line_height * used
             for i in range(count)], cap)


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
        lines = lay_out_lines(font, cell, key, text)
        _baselines, cap = _multiline(font, cell, len(lines))
        # One size for the whole cell — the tightest line sets it. Two lines of
        # a name list at different sizes read as a mistake, not as typesetting.
        size = min(fit_size(font, line, cell, max_size=cap)[0] for line in lines)
        # Re-centre the block on the size the lines actually landed at, so a
        # pair that had to shrink does not sit high in its cell.
        baselines, _cap = _multiline(font, cell, len(lines), size=size)
        available = cell.width - 2 * SIDE_PADDING
        fitted = [(size, font.text_length(line, size),
                   font.text_length(line, size) > available) for line in lines]
        sizes, widths, overflows = [], [], []
        for line, baseline, (size, width, overflowed) in zip(lines, baselines, fitted):
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
    use_postscript_font_name(doc, font_path)
    return doc.tobytes(garbage=4, deflate=True), placed


def use_postscript_font_name(doc, font_path: Path) -> list[str]:
    """Rewrite the inserted font's ``/BaseFont`` to its PostScript name.

    PyMuPDF writes the face's *display* name there — ``/Microsoft#20Sans#20
    Serif#20Regular``, spaces escaped — which matches no installed font, so
    **Illustrator opens the prefilled values as a missing font**, red-underlined
    and not editable (user, 2026-09-20; the same symptom under the old Myriad
    Pro template). PDF 32000-1 §9.7.6.1 says a Type 0 font's BaseFont shall be
    its descendant CIDFont's, and that one is the PostScript name, so this is a
    correctness fix as much as a compatibility one. The subset tag (``ABCDEF+``)
    is kept.

    Only fonts *we* inserted are touched: the template's own embedded face
    already carries a proper name.
    """
    import re

    proper = _postscript_name(font_path)
    if not proper:
        return []
    renamed = []
    for xref in range(1, doc.xref_length()):
        if doc.xref_get_key(xref, "Subtype")[1] != "/Type0":
            continue
        current = (doc.xref_get_key(xref, "BaseFont")[1] or "").lstrip("/")
        if not current:
            continue
        tag, _plus, bare = current.rpartition("+")
        if bare == proper:
            continue                       # the template's own face, or already fixed
        tag = tag + "+" if tag else ""
        fixed = "/" + tag + proper
        doc.xref_set_key(xref, "BaseFont", fixed)
        renamed.append(current)
        for target in _descendants(doc, xref, re):
            doc.xref_set_key(target, "BaseFont", fixed)
            descriptor = re.search(
                r"(\d+) 0 R", doc.xref_get_key(target, "FontDescriptor")[1] or "")
            if descriptor:
                doc.xref_set_key(int(descriptor.group(1)), "FontName", fixed)
    return renamed


def _descendants(doc, xref: int, re) -> list[int]:
    value = doc.xref_get_key(xref, "DescendantFonts")[1] or ""
    return [int(found) for found in re.findall(r"(\d+) 0 R", value)]


def _postscript_name(font_path: Path) -> str | None:
    from cave_dossier.sastavnica.fonts import postscript_name

    return postscript_name(Path(font_path))
