"""Draw resolved values onto the blank sastavnica.

Pure geometry — no SB, no config, no delivery: a blank PDF plus
``{field key: text}`` in, PDF bytes out. That keeps the typesetting rules
testable against the authored template without a workbook anywhere near.

The rules come from measuring the drafter's own choices (see
``addresses.py``): every value is **centred** in its cell, starts at the size
the drafter set that cell at — 10, 9 or 8 pt, per cell — sits on a baseline a
constant lift above the cell's bottom rule, and is **shrunk until it fits**,
which is exactly what the drafter does by hand. Every cell is one line: template
v2 (2026-10-03) gave the team its own full-width row and put the profil/tlocrt
order into the Mjerilo label, which retired the two cells v1 had to wrap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.sastavnica.addresses import (
    FONT_STEP,
    MIN_FONT_SIZE,
    V2,
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
    """(font size, drawn width, overflowed) for one value in one cell.

    Starts at the cell's **authored** size — what the drafter set that cell at —
    and shrinks from there; never grows past it.
    """
    left, right = cell.text_span()
    available = right - left
    size = cell.size
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

    cells = cells if cells is not None else V2
    unknown = sorted(set(values) - set(cells))
    if unknown:
        raise RenderError(f"Unknown sastavnica field(s): {', '.join(unknown)}")
    if not blank_path.exists():
        raise RenderError(
            f"Blank template not found: {blank_path} – run "
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
        left, right = cell.text_span()
        page.insert_text(
            ((left + right) / 2 - width / 2, cell.baseline),
            text,
            fontname="sastavnica",
            fontsize=size,
            color=VALUE_COLOR,
        )
        placed.append(PlacedValue(key, text, size, width, overflowed))

    if metadata:
        doc.set_metadata({**(doc.metadata or {}), **metadata})
    doc.subset_fonts()          # embed only the glyphs actually used
    use_postscript_font_name(doc, font_path)
    plain_hyphens_and_spaces(doc)
    return doc.tobytes(garbage=4, deflate=True), placed


# In micross.ttf and arial.ttf the hyphen glyph serves both U+002D and U+00AD,
# the space glyph both U+0020 and U+00A0, and MuPDF's ToUnicode picks the
# higher code point. A soft hyphen is a *discretionary* hyphen: Illustrator
# hides it, so "051-716" opened as "051716" and "-14 m" as "14 m" (user,
# 2026-09-20, on the first SB 1256 nacrt); the semicolon likewise came out as
# U+037E, the Greek question mark. Rewrite the CMaps back to the plain
# characters; the glyphs drawn are unchanged, only what the text *means* is.
#
# Only the Unicode *destination* of a two-token ``bfchar`` line may change —
# never a source glyph ID. Matching ``<00AD>`` anywhere also rewrote the line
# ``<00ad> <00c3>`` (glyph 0xAD is Ã in micross) to ``<002D> <00c3>``, and glyph
# 0x2D is the J: every J read as Ã, and every = as æ (user, 2026-09-24).
_TOUNICODE_FIXES = (
    (re.compile(rb"(?im)^(\s*<[0-9a-f]+>\s+)<00AD>(\s*)$"), rb"\g<1><002D>\g<2>"),
    (re.compile(rb"(?im)^(\s*<[0-9a-f]+>\s+)<00A0>(\s*)$"), rb"\g<1><0020>\g<2>"),
    (re.compile(rb"(?im)^(\s*<[0-9a-f]+>\s+)<037E>(\s*)$"), rb"\g<1><003B>\g<2>"),
)


def plain_hyphens_and_spaces(doc) -> int:
    """Patch every ToUnicode CMap in ``doc`` in place; returns streams changed."""
    changed = 0
    for xref in range(1, doc.xref_length()):
        if not doc.xref_is_stream(xref):
            continue
        stream = doc.xref_stream(xref)
        if b"beginbfchar" not in stream and b"beginbfrange" not in stream:
            continue
        patched = stream
        for pattern, replacement in _TOUNICODE_FIXES:
            patched = pattern.sub(replacement, patched)
        if patched != stream:
            doc.update_stream(xref, patched)
            changed += 1
    return changed


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
