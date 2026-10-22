"""Write the katastarski broj into the two documents that carry it.

Until delivery both documents hold a placeholder by decision (4S, 4O): the
Nacrt's title block prints ``0000`` in its *Katastarski broj* cell and the
OSZ's first cell is left empty, because the archivist assigns the number last.
Delivery is that moment, so it fills both — the user's stated intent since
2026-09-19 ("carry the katastarski broj across all products in one step").

**The Nacrt** is edited, not rebuilt. The archivist approved *this* PDF; a
recompose could pick up an OSZ edited after the review. The ``0000`` span is
found in the page's text, removed by a redaction tight to its middle (so the
cell's label and rules above and below it survive), and the number is set in
its place: same centre, same baseline, same size, the sastavnica's own face.
That works for both routes — the cSurvey route's composed page and an
Illustrator drawing with the sastavnica placed anywhere at any scale.

An Illustrator-saved PDF also carries the editable artwork (``/PieceInfo``),
and Illustrator opens THAT in preference to the page — it would still show
``0000`` (the trap 4S's ``build_blank.py`` found, 2026-09-19). The stamped copy
drops it; the caller keeps the unstamped original as the editable master.

**The OSZ** gets the number in its v10 cell through the same writer KORAK 4
uses. Both are written as 3-digit numbers (``007``), the archive's own form:
``!!Nacrti/007.pdf``, and the cells of the delivered 886…889 read ``886``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: The sastavnica's placeholder (4S ``addresses.CONSTANTS``).
PLACEHOLDER = "0000"
LABEL = "katastarski"


def number_text(sue: int) -> str:
    """``7`` -> ``007``: the archive's spelling, in file names and in cells."""
    return f"{sue:03d}"


class StampError(RuntimeError):
    """The number could not be written; message is CLI-ready (Croatian)."""


@dataclass(frozen=True)
class PdfCheck:
    """Where the number goes in a nacrt PDF.

    ``status``: ``placeholder`` (one ``0000`` found — stampable), ``already``
    (the number itself is already there), ``missing`` (neither), ``ambiguous``
    (several ``0000`` and no label to choose by), ``error`` (unreadable).
    """

    status: str
    note: str = ""
    illustrator: bool = False     # carries the editable /PieceInfo artwork
    rect: tuple[float, float, float, float] | None = None
    origin: tuple[float, float] | None = None
    size: float | None = None
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @property
    def ok(self) -> bool:
        return self.status in ("placeholder", "already")


def _pymupdf():
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StampError("Za upis u nacrt treba PyMuPDF: pip install -e .[sastavnica]") from exc
    return pymupdf


def _spans(page) -> list[dict]:
    out = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                out.append(span)
    return out


def _rgb(value) -> tuple[float, float, float]:
    if isinstance(value, int):
        return ((value >> 16 & 255) / 255, (value >> 8 & 255) / 255, (value & 255) / 255)
    return (0.0, 0.0, 0.0)


def check_pdf(path: Path, sue: int | None = None) -> PdfCheck:
    """Find the cell the number goes into, without changing anything."""
    pymupdf = _pymupdf()
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001 — a note in the plan, never a crash
        return PdfCheck("error", f"{path.name} se ne može otvoriti ({type(exc).__name__}).")
    with doc:
        page = doc[0]
        illustrator = doc.xref_get_key(page.xref, "PieceInfo")[0] != "null"
        spans = _spans(page)
        labels = [s for s in spans if s["text"].strip().lower().startswith(LABEL)]
        holders = [s for s in spans if s["text"].strip() == PLACEHOLDER]
        if sue is not None and not holders:
            done = [s for s in spans if s["text"].strip() in (number_text(sue), str(sue))]
            if done and labels:
                return PdfCheck("already", "Broj je već upisan u nacrt.", illustrator)
        if not holders:
            return PdfCheck("missing", f"U {path.name} nema '{PLACEHOLDER}' u polju "
                            "Katastarski broj – nacrt nije složen iz sastavnice, ili je broj već "
                            "upisan ručno.", illustrator)
        if len(holders) > 1:
            if not labels:
                return PdfCheck("ambiguous", f"{len(holders)}× '{PLACEHOLDER}' i nijedna oznaka "
                                "'Katastarski broj' – ne znam koji je pravi.", illustrator)
            lx, ly = labels[0]["bbox"][0], labels[0]["bbox"][1]
            holders.sort(key=lambda s: (s["bbox"][0] - lx) ** 2 + (s["bbox"][1] - ly) ** 2)
        span = holders[0]
        return PdfCheck("placeholder", "", illustrator, tuple(span["bbox"]),
                        tuple(span["origin"]), float(span["size"]), _rgb(span.get("color")))


def stamp_pdf(src: Path, dst: Path, sue: int, font_path: Path) -> PdfCheck:
    """Write ``sue`` over the placeholder of ``src`` into ``dst``."""
    pymupdf = _pymupdf()
    check = check_pdf(src, sue)
    if check.status == "already":
        dst.write_bytes(src.read_bytes())
        return check
    if check.status != "placeholder":
        raise StampError(check.note)
    text = number_text(sue)
    doc = pymupdf.open(src)
    with doc:
        page = doc[0]
        x0, y0, x1, y1 = check.rect
        mid = (y0 + y1) / 2
        quarter = (y1 - y0) / 4
        # The middle half of the span only: a redaction removes every glyph
        # whose box it touches, and the label sits right above the value.
        page.add_redact_annot(pymupdf.Rect(x0 + 0.2, mid - quarter, x1 - 0.2, mid + quarter))
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
        font = pymupdf.Font(fontfile=str(font_path))
        width = font.text_length(text, check.size)
        page.insert_font(fontname="predaja", fontfile=str(font_path))
        page.insert_text(((x0 + x1) / 2 - width / 2, check.origin[1]), text,
                         fontname="predaja", fontsize=check.size, color=check.color)
        if check.illustrator:
            # build_blank.strip_illustrator_private: Illustrator would open the
            # embedded artwork, which still says 0000.
            doc.xref_set_key(page.xref, "PieceInfo", "null")
            doc.xref_set_key(page.xref, "Thumb", "null")
            doc.del_xml_metadata()
        doc.subset_fonts()
        from cave_dossier.sastavnica.render import plain_hyphens_and_spaces

        plain_hyphens_and_spaces(doc)
        holders_before = _count(_spans(page), PLACEHOLDER)
        dst.write_bytes(doc.tobytes(garbage=3, deflate=True))
    with pymupdf.open(dst) as done:
        spans = _spans(done[0])
    if _count(spans, PLACEHOLDER) != holders_before or not _count(spans, text):
        raise StampError("Provjera nakon upisa u nacrt nije prošla – ništa nije predano.")
    return check


def _count(spans: list[dict], text: str) -> int:
    return sum(1 for s in spans if s["text"].strip() == text)


def stamp_osz(src: Path, dst: Path, sue: int) -> str | None:
    """Write the number into the OSZ's Katastarski broj cell (``src`` -> ``dst``).

    Returns what the cell held before. A cell already holding this number is
    copied unchanged; a cell holding ANOTHER number is refused — the plan
    reports that as a blocker, so this is the last line of defence.
    """
    from cave_dossier.osz.addresses import V10
    from cave_dossier.osz.reader import read_osz_content
    from cave_dossier.osz.writer import OszDocument

    before = (read_osz_content(src).fields.get("katastarski_broj") or "").strip()
    if before and _as_number(before) != sue:
        raise StampError(f"OSZ već ima katastarski broj '{before}' – ne prepisujem ga s {sue}.")
    if before:
        dst.write_bytes(src.read_bytes())
        return before
    addr = V10["katastarski_broj"]
    doc = OszDocument(src)
    if addr.kind == "sdt_cell":
        doc.fill_sdt_cell(addr.table, addr.row, addr.cell, [number_text(sue)])
    else:
        doc.fill_plain(addr.table, addr.row, addr.cell, number_text(sue))
    doc.save(dst)
    after = (read_osz_content(dst).fields.get("katastarski_broj") or "").strip()
    if _as_number(after) != sue:
        raise StampError(f"Provjera nakon upisa u OSZ nije prošla (ćelija kaže '{after}').")
    return None


def _as_number(text: str) -> int | None:
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None
