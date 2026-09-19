"""Read a FILLED OSZ v10 document's addressable cells (the reading half,
behind `cavedossier osz backfill`).

Counterpart of ``writer.py``: same lxml-on-``word/document.xml`` approach
(Word ``w:sdt`` content controls are invisible to python-docx), same
``addresses.V10`` coordinate map. Reads only the identity/location/metadata
cells the SB backfill needs — the checkbox groups and narrative controls are
CroSpeleo material for a later stage.

Reading rules (from the template audits, see backlog 2026-08-23/25):
- a control still showing its grey placeholder (``w:showingPlcHdr``) reads
  as EMPTY, not as the placeholder text;
- runs are joined before use — Word splits them unpredictably; ``w:br``
  inside a control becomes ``"; "`` (multi-line values stay one cell);
- a plain cell's text is everything outside any nested control.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from cave_dossier.osz.addresses import V10
from cave_dossier.osz.writer import W, W14, _checkbox_label

_PLACEHOLDER_MARKERS = ("«", "»", "⟨", "⟩")


class OszReadError(RuntimeError):
    """The file is not a readable OSZ v10 document; message is CLI-ready."""


def read_osz(path: Path) -> dict[str, str | None]:
    """{field key -> cell text or None} for every address in ``V10``.

    Line breaks inside a value join as ``"; "`` — the fetcher/backfill
    convention. The migration path uses ``read_osz_content`` instead,
    which keeps real newlines and also reads the checkbox states.
    """
    return _read_values(path, br_sep="; ")


@dataclass(frozen=True)
class OszContent:
    """Everything a filled v10 document carries that can migrate forward."""

    fields: dict[str, str | None]
    ticked: tuple[str, ...] = field(default=())


def read_osz_content(path: Path) -> OszContent:
    """The full migratable content: every ``V10`` value with real newlines
    preserved (so a re-fill reproduces the line structure) plus the labels
    of every TICKED checkbox."""
    values = _read_values(path, br_sep="\n")
    root = _document_root(path)
    ticked: list[str] = []
    for sdt in root.iter(W + "sdt"):
        pr = sdt.find(W + "sdtPr")
        if pr is None or pr.find(W14 + "checkbox") is None:
            continue
        checked = pr.find(W14 + "checkbox/" + W14 + "checked")
        if checked is not None and checked.get(W14 + "val") in ("1", "true"):
            label = _checkbox_label(sdt)
            if label:
                ticked.append(label)
    return OszContent(fields=values, ticked=tuple(ticked))


def _document_root(path: Path):
    try:
        with zipfile.ZipFile(path) as zin:
            return etree.fromstring(zin.read("word/document.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, etree.XMLSyntaxError) as exc:
        raise OszReadError(f"{path}: not a readable DOCX ({exc})") from exc


def _read_values(path: Path, br_sep: str) -> dict[str, str | None]:
    root = _document_root(path)
    body = root.find(W + "body")
    if body is None:
        raise OszReadError(f"{path}: no document body")
    tables = body.findall(W + "tbl")

    values: dict[str, str | None] = {}
    for key, addr in V10.items():
        try:
            tr = tables[addr.table].findall(W + "tr")[addr.row]
            node = [n for n in tr if n.tag in (W + "tc", W + "sdt")][addr.cell]
        except IndexError as exc:
            raise OszReadError(
                f"{path.name}: table[{addr.table}].row[{addr.row}].cell[{addr.cell}] "
                f"({key}) does not exist — is this a v10 document?"
            ) from exc
        if addr.kind == "sdt_inline":
            text = _inline_sdt_text(node, br_sep)
        elif node.tag == W + "sdt":
            text = _sdt_text(node, br_sep)
        else:
            text = _plain_cell_text(node, br_sep)
        values[key] = text or None
    return values


def _inline_sdt_text(tc, br_sep: str) -> str:
    """The text control nested inside a plain cell (narrative sections
    whose heading shares the cell)."""
    if tc.tag == W + "sdt":  # tolerate a template that made it cell-level
        return _sdt_text(tc, br_sep)
    for sdt in tc.iter(W + "sdt"):
        pr = sdt.find(W + "sdtPr")
        if pr is not None and pr.find(W + "text") is not None:
            return _sdt_text(sdt, br_sep)
    return ""


def _sdt_text(sdt, br_sep: str = "; ") -> str:
    pr = sdt.find(W + "sdtPr")
    if pr is not None and pr.find(W + "showingPlcHdr") is not None:
        return ""  # untouched control — the grey placeholder is not a value
    content = sdt.find(W + "sdtContent")
    if content is None:
        return ""
    text = _runs_text(content, br_sep)
    # The Google-Docs variant loses control state: an untouched field comes
    # back as literal ⟨placeholder⟩ text — treat those as empty too.
    stripped = text.strip()
    if stripped and stripped[0] in _PLACEHOLDER_MARKERS and stripped[-1] in _PLACEHOLDER_MARKERS:
        return ""
    return text


def _plain_cell_text(tc, br_sep: str = "; ") -> str:
    """Text of the cell OUTSIDE any nested control (a nested control's value
    is read via its own address, never double-counted here)."""
    parts: list[str] = []
    for p in tc.findall(W + "p"):
        for node in p.iter():
            if _inside_sdt(node, stop=p):
                continue
            if node.tag == W + "t":
                parts.append(node.text or "")
            elif node.tag == W + "br":
                parts.append(br_sep)
    return _collapse("".join(parts), br_sep)


def _runs_text(holder, br_sep: str = "; ") -> str:
    parts: list[str] = []
    for node in holder.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "br":
            parts.append(br_sep)
    return _collapse("".join(parts), br_sep)


def _inside_sdt(node, stop) -> bool:
    parent = node.getparent()
    while parent is not None and parent is not stop:
        if parent.tag == W + "sdt":
            return True
        parent = parent.getparent()
    return False


def _collapse(text: str, br_sep: str = "; ") -> str:
    """Collapse run whitespace but keep the break separator intact (a "\\n"
    separator must survive so the migration re-fill keeps the lines)."""
    text = text.replace("\xa0", " ")
    if "\n" in br_sep:
        lines = [" ".join(line.split()).strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line).strip()
    return " ".join(text.split()).strip()
