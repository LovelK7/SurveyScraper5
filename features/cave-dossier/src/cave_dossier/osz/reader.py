"""Read a FILLED OSZ v10 document's addressable cells (the fetcher half).

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
from pathlib import Path

from lxml import etree

from cave_dossier.osz.addresses import V10
from cave_dossier.osz.writer import W

_PLACEHOLDER_MARKERS = ("«", "»", "⟨", "⟩")


class OszReadError(RuntimeError):
    """The file is not a readable OSZ v10 document; message is CLI-ready."""


def read_osz(path: Path) -> dict[str, str | None]:
    """{field key -> cell text or None} for every address in ``V10``."""
    try:
        with zipfile.ZipFile(path) as zin:
            root = etree.fromstring(zin.read("word/document.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, etree.XMLSyntaxError) as exc:
        raise OszReadError(f"{path}: not a readable DOCX ({exc})") from exc
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
        text = _sdt_text(node) if node.tag == W + "sdt" else _plain_cell_text(node)
        values[key] = text or None
    return values


def _sdt_text(sdt) -> str:
    pr = sdt.find(W + "sdtPr")
    if pr is not None and pr.find(W + "showingPlcHdr") is not None:
        return ""  # untouched control — the grey placeholder is not a value
    content = sdt.find(W + "sdtContent")
    if content is None:
        return ""
    text = _runs_text(content)
    # The Google-Docs variant loses control state: an untouched field comes
    # back as literal ⟨placeholder⟩ text — treat those as empty too.
    stripped = text.strip()
    if stripped and stripped[0] in _PLACEHOLDER_MARKERS and stripped[-1] in _PLACEHOLDER_MARKERS:
        return ""
    return text


def _plain_cell_text(tc) -> str:
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
                parts.append("; ")
    return _collapse(("".join(parts)))


def _runs_text(holder) -> str:
    parts: list[str] = []
    for node in holder.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "br":
            parts.append("; ")
    return _collapse("".join(parts))


def _inside_sdt(node, stop) -> bool:
    parent = node.getparent()
    while parent is not None and parent is not stop:
        if parent.tag == W + "sdt":
            return True
        parent = parent.getparent()
    return False


def _collapse(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split()).strip()
