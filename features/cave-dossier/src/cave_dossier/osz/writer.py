"""OSZ DOCX writer: fill the v10 template's cells, controls and image frame.

The fill primitives are lifted from ``osz-template/tools/make_mockup.py``
(the proven writer — see backlog 2026-08-23); that script stays frozen as
the template-QA workbench, THIS module is the maintained copy. Everything
works on ``word/document.xml`` through lxml because Word ``w:sdt`` content
controls are invisible to python-docx.

Hard-won rules preserved verbatim:
- a plain-text control is single-paragraph unless ``multiLine`` is set;
  writing a second ``w:p`` into it makes Word REJECT the file — multi-line
  content is one paragraph with ``<w:br/>`` separators;
- ticking a checkbox must set BOTH ``w14:checked`` and the visible
  ``w:sym`` glyph char, or Word shows an unticked box with a ticked state.

New here: ``embed_png`` — a PNG into a table cell as an inline drawing
(media entry + relationship + content-type default + ``w:drawing`` run).
"""

from __future__ import annotations

import copy
import shutil
import struct
import zipfile
from pathlib import Path

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
_IMAGE_REL_TYPE = f"{_R_NS.rsplit('/relationships', 1)[0]}/relationships/image"

_EMU_PER_TWIP = 635
# Fallback frame width when the cell carries no usable w:tcW: 9 cm.
_DEFAULT_FRAME_WIDTH_EMU = 9 * 360_000


class OszWriteError(RuntimeError):
    """The template does not look like the expected OSZ layout."""


class OszDocument:
    """One template opened for filling; ``save()`` writes the filled copy."""

    def __init__(self, template_path: Path) -> None:
        self.template_path = template_path
        with zipfile.ZipFile(template_path) as zin:
            self._doc_root = etree.fromstring(zin.read("word/document.xml"))
            self._rels_root = etree.fromstring(zin.read("word/_rels/document.xml.rels"))
            self._types_root = etree.fromstring(zin.read("[Content_Types].xml"))
        body = self._doc_root.find(W + "body")
        if body is None:
            raise OszWriteError(f"{template_path.name}: no w:body")
        self._tables = body.findall(W + "tbl")
        self._media: dict[str, bytes] = {}  # zip path -> bytes

    # ── plain cells ──────────────────────────────────────────────────
    def fill_plain(self, tbl_i: int, row_i: int, cell_i: int, text: str) -> None:
        """Write text into a plain (non-control) table cell, in the cell's
        OWN style.

        The v10 template keeps each empty value cell's intended run style
        (Arial 20 pt bold for IME OBJEKTA, 18 pt for Katastarski broj, …)
        on the paragraph mark (``w:pPr/w:rPr``) — copying a sibling cell's
        style, as the old workbench script did, flattened everything to the
        document default (user report 2026-08-30). Nothing is stripped:
        bold on the mark is bold by design here.
        """
        tc = self._row_nodes(tbl_i, row_i)[cell_i]
        p = tc.find(W + "p")
        if p is None:
            p = etree.SubElement(tc, W + "p")
        rpr = _paragraph_mark_rpr(p)
        if rpr is None:
            rpr = _first_run_rpr(tc, strip=())
        for r in p.findall(W + "r"):
            p.remove(r)
        p.append(_make_run(text, rpr))

    # ── content controls ─────────────────────────────────────────────
    def fill_sdt_cell(self, tbl_i: int, row_i: int, cell_i: int,
                      paragraphs: list[str]) -> None:
        node = self._row_nodes(tbl_i, row_i)[cell_i]
        if node.tag != W + "sdt":
            raise OszWriteError(
                f"table[{tbl_i}].row[{row_i}].cell[{cell_i}] is not a cell-level control"
            )
        _fill_sdt(node, paragraphs)

    def fill_sdt_inline(self, tbl_i: int, row_i: int, cell_i: int,
                        paragraphs: list[str]) -> None:
        tc = self._row_nodes(tbl_i, row_i)[cell_i]
        for sdt in tc.iter(W + "sdt"):
            pr = sdt.find(W + "sdtPr")
            if pr is not None and pr.find(W + "text") is not None:
                _fill_sdt(sdt, paragraphs)
                return
        raise OszWriteError(
            f"no text control in table[{tbl_i}].row[{row_i}].cell[{cell_i}]"
        )

    # ── checkboxes ───────────────────────────────────────────────────
    def tick(self, labels: set[str]) -> set[str]:
        """Tick every checkbox whose trailing label is in labels; returns
        the labels that were NOT found (caller decides how loud to be).

        Matching is exact first, then diacritic/case-folded — legacy
        zapisnici capitalize option words ("Jama") that v10 lowercases.
        """
        from cave_dossier.core.normalization import normalize_lookup_key

        requested_norm = {normalize_lookup_key(label): label for label in labels}
        hit: set[str] = set()
        for sdt in self._doc_root.iter(W + "sdt"):
            pr = sdt.find(W + "sdtPr")
            if pr is None or pr.find(W14 + "checkbox") is None:
                continue
            label = _checkbox_label(sdt)
            if label in labels:
                requested = label
            else:
                requested = requested_norm.get(normalize_lookup_key(label))
                if requested is None:
                    continue
            label = requested
            chk = pr.find(W14 + "checkbox")
            checked = chk.find(W14 + "checked")
            if checked is None:
                checked = etree.SubElement(chk, W14 + "checked")
            checked.set(W14 + "val", "1")
            state = chk.find(W14 + "checkedState")
            char = state.get(W14 + "val") if state is not None else "0052"
            font = state.get(W14 + "font") if state is not None else "Wingdings 2"
            for sym in sdt.findall(".//" + W + "sym"):
                sym.set(W + "char", "F0" + char[-2:])
                sym.set(W + "font", font)
            hit.add(label)
        return set(labels) - hit

    # ── image embedding ──────────────────────────────────────────────
    def embed_png(self, tbl_i: int, row_i: int, cell_i: int,
                  png_bytes: bytes, media_name: str) -> None:
        """Embed a PNG as an inline drawing in a plain table cell, sized to
        the cell width (aspect ratio from the PNG header)."""
        tc = self._row_nodes(tbl_i, row_i)[cell_i]
        if tc.tag != W + "tc":
            raise OszWriteError(
                f"table[{tbl_i}].row[{row_i}].cell[{cell_i}] is not a plain cell"
            )
        width_px, height_px = _png_dimensions(png_bytes)
        cx = self._cell_width_emu(tc)
        cy = int(cx * height_px / width_px)

        zip_path = f"word/media/{media_name}"
        self._media[zip_path] = png_bytes
        rid = self._add_image_relationship(f"media/{media_name}")
        self._ensure_png_content_type()

        p = tc.find(W + "p")
        if p is None:
            p = etree.SubElement(tc, W + "p")
        for r in p.findall(W + "r"):
            p.remove(r)
        p.append(_drawing_run(rid, cx, cy, media_name, self._next_docpr_id()))

    def _cell_width_emu(self, tc) -> int:
        tcpr = tc.find(W + "tcPr")
        tcw = tcpr.find(W + "tcW") if tcpr is not None else None
        if tcw is not None and tcw.get(W + "type") == "dxa":
            try:
                twips = int(tcw.get(W + "w") or 0)
            except ValueError:
                twips = 0
            if twips > 0:
                # Leave the default cell margins (2×108 twips) breathing room.
                return max((twips - 216) * _EMU_PER_TWIP, 360_000)
        return _DEFAULT_FRAME_WIDTH_EMU

    def _next_docpr_id(self) -> int:
        """A drawing id no existing wp:docPr uses (they must be unique)."""
        highest = 0
        for docpr in self._doc_root.iter(f"{{{_WP_NS}}}docPr"):
            try:
                highest = max(highest, int(docpr.get("id") or 0))
            except ValueError:
                continue
        return highest + 1

    def _add_image_relationship(self, target: str) -> str:
        existing = [
            rel.get("Id") or ""
            for rel in self._rels_root.findall(f"{{{_REL_NS}}}Relationship")
        ]
        n = 1
        while f"rId{n}" in existing:
            n += 1
        rid = f"rId{n}"
        rel = etree.SubElement(self._rels_root, f"{{{_REL_NS}}}Relationship")
        rel.set("Id", rid)
        rel.set("Type", _IMAGE_REL_TYPE)
        rel.set("Target", target)
        return rid

    def _ensure_png_content_type(self) -> None:
        for default in self._types_root.findall(f"{{{_CT_NS}}}Default"):
            if (default.get("Extension") or "").lower() == "png":
                return
        default = etree.SubElement(self._types_root, f"{{{_CT_NS}}}Default")
        default.set("Extension", "png")
        default.set("ContentType", "image/png")

    # ── save ─────────────────────────────────────────────────────────
    def save(self, target: Path) -> None:
        """The template zip with the mutated parts swapped in (same
        round-trip as make_mockup.py — every untouched entry is copied
        byte-for-byte)."""
        replacements = {
            "word/document.xml": _serialize(self._doc_root),
            "word/_rels/document.xml.rels": _serialize(self._rels_root),
            "[Content_Types].xml": _serialize(self._types_root),
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.template_path) as zin, \
                zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = replacements.get(item.filename, None)
                zout.writestr(item, data if data is not None else zin.read(item.filename))
            for zip_path, data in self._media.items():
                zout.writestr(zip_path, data)

    # ── internals ────────────────────────────────────────────────────
    def _row_nodes(self, tbl_i: int, row_i: int) -> list:
        try:
            tbl = self._tables[tbl_i]
            tr = tbl.findall(W + "tr")[row_i]
        except IndexError as exc:
            raise OszWriteError(f"table[{tbl_i}].row[{row_i}] does not exist") from exc
        return [n for n in tr if n.tag in (W + "tc", W + "sdt")]


# ── module-level primitives (from make_mockup.py; see fill_plain) ────
def _paragraph_mark_rpr(p):
    """The paragraph mark's run properties — where the template stores an
    empty value cell's intended style."""
    ppr = p.find(W + "pPr")
    mark_rpr = ppr.find(W + "rPr") if ppr is not None else None
    return copy.deepcopy(mark_rpr) if mark_rpr is not None else None


def _first_run_rpr(tc, strip: tuple[str, ...] = ("b", "bCs", "i", "rStyle")):
    r = tc.find(".//" + W + "r")
    if r is None:
        return None
    rpr = r.find(W + "rPr")
    if rpr is None:
        return None
    rpr = copy.deepcopy(rpr)
    for bad in strip:
        for el in rpr.findall(W + bad):
            rpr.remove(el)
    return rpr


def _make_run(text: str, rpr):
    r = etree.SubElement(etree.Element(W + "tmp"), W + "r")
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    t = etree.SubElement(r, W + "t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return r


def _clear_placeholder(sdt) -> None:
    pr = sdt.find(W + "sdtPr")
    if pr is not None:
        for el in pr.findall(W + "showingPlcHdr"):
            pr.remove(el)
        # A plain-text control is single-paragraph unless multiLine is set;
        # writing a second w:p into it otherwise makes Word reject the file.
        txt = pr.find(W + "text")
        if txt is not None:
            txt.set(W + "multiLine", "1")
    # drop the grey PlaceholderText character style
    for rstyle in sdt.findall(".//" + W + "rStyle"):
        if rstyle.get(W + "val") == "PlaceholderText":
            rstyle.getparent().remove(rstyle)


def _fill_sdt(sdt, paragraphs: list[str], rpr=None) -> None:
    """Fill a plain-text content control with one or more paragraphs."""
    _clear_placeholder(sdt)
    content = sdt.find(W + "sdtContent")
    inner_tc = content.find(W + "tc")
    holder = inner_tc if inner_tc is not None else content
    ps = holder.findall(W + "p")
    if ps:
        template_p = ps[0]
        # Take the paragraph mark's rPr (Arial 10 pt) rather than the grey
        # placeholder run's, so filled text renders as normal body text.
        base_rpr = rpr
        if base_rpr is None:
            ppr = template_p.find(W + "pPr")
            mark_rpr = ppr.find(W + "rPr") if ppr is not None else None
            if mark_rpr is not None:
                base_rpr = copy.deepcopy(mark_rpr)
                for bad in ("rStyle", "color", "b", "bCs", "i"):
                    for el in base_rpr.findall(W + bad):
                        base_rpr.remove(el)
        if base_rpr is None:
            base_rpr = _first_run_rpr(inner_tc if inner_tc is not None else template_p)
        for extra in ps[1:]:
            holder.remove(extra)
        for r in template_p.findall(W + "r"):
            template_p.remove(r)
        # One paragraph with <w:br/> separators: a plain-text control may
        # not contain a second w:p — Word rejects the file outright.
        run = _make_run(paragraphs[0], base_rpr)
        for line in paragraphs[1:]:
            etree.SubElement(run, W + "br")
            t = etree.SubElement(run, W + "t")
            t.text = line
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        template_p.append(run)
    else:  # inline run-level control
        rs = content.findall(W + "r")
        # Style from the control's own rPr (what Word applies when the
        # operator types), NOT from the grey placeholder run.
        sdt_pr = sdt.find(W + "sdtPr")
        base_rpr = sdt_pr.find(W + "rPr") if sdt_pr is not None else None
        if base_rpr is None and rs:
            base_rpr = rs[0].find(W + "rPr")
        if base_rpr is not None:
            base_rpr = copy.deepcopy(base_rpr)
            for bad in ("rStyle", "color"):
                for el in base_rpr.findall(W + bad):
                    base_rpr.remove(el)
        for r in rs[1:]:
            content.remove(r)
        if rs:
            content.remove(rs[0])
        content.append(_make_run(" ".join(paragraphs), base_rpr))


def _checkbox_label(sdt) -> str:
    """Text that follows a checkbox control inside its paragraph."""
    p = sdt.getparent()
    while p is not None and p.tag != W + "p":
        p = p.getparent()
    if p is None:
        return ""
    collected, seen = [], False
    for node in p:
        if node is sdt:
            seen = True
            continue
        if not seen:
            continue
        if node.tag == W + "sdt":
            break
        if node.tag == W + "r":
            collected.append("".join(t.text or "" for t in node.findall(W + "t")))
    return " ".join("".join(collected).split()).strip()


# ── drawing construction ─────────────────────────────────────────────
def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """(width, height) straight from the IHDR chunk — no Pillow needed."""
    if len(png_bytes) < 24 or png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise OszWriteError("not a PNG file")
    width, height = struct.unpack(">II", png_bytes[16:24])
    if not width or not height:
        raise OszWriteError("PNG reports zero dimensions")
    return width, height


def _drawing_run(rid: str, cx: int, cy: int, name: str, docpr_id: int):
    xml = f"""<w:r xmlns:w="{W[1:-1]}">
  <w:drawing>
    <wp:inline distT="0" distB="0" distL="0" distR="0" xmlns:wp="{_WP_NS}">
      <wp:extent cx="{cx}" cy="{cy}"/>
      <wp:effectExtent l="0" t="0" r="0" b="0"/>
      <wp:docPr id="{docpr_id}" name="{name}"/>
      <wp:cNvGraphicFramePr>
        <a:graphicFrameLocks noChangeAspect="1" xmlns:a="{_A_NS}"/>
      </wp:cNvGraphicFramePr>
      <a:graphic xmlns:a="{_A_NS}">
        <a:graphicData uri="{_PIC_NS}">
          <pic:pic xmlns:pic="{_PIC_NS}">
            <pic:nvPicPr>
              <pic:cNvPr id="{docpr_id}" name="{name}"/>
              <pic:cNvPicPr/>
            </pic:nvPicPr>
            <pic:blipFill>
              <a:blip r:embed="{rid}" xmlns:r="{_R_NS}"/>
              <a:stretch><a:fillRect/></a:stretch>
            </pic:blipFill>
            <pic:spPr>
              <a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
              <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
            </pic:spPr>
          </pic:pic>
        </a:graphicData>
      </a:graphic>
    </wp:inline>
  </w:drawing>
</w:r>"""
    return etree.fromstring(xml.encode("utf-8"))


def _serialize(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
