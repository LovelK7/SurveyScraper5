"""osz/writer.py against the real committed v10 template.

The template is tracked, so these tests exercise the actual document the
prefill will fill — addresses from osz/addresses.py, the single-w:p
invariant (Word rejects a second w:p in a plain-text control), checkbox
state + glyph, and PNG embedding (rels / content types / media / extent).
"""

from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path

import pytest

lxml_etree = pytest.importorskip("lxml.etree")

from cave_dossier.osz.addresses import KARTA_FRAME, V10
from cave_dossier.osz.writer import W, W14, OszDocument

TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "osz-template" / "templates" / "Zapisnik_OSZ_v10.docx"
)


def make_png(width: int, height: int) -> bytes:
    def chunk(typ: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x20\x40\x60" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _document_root(path: Path):
    with zipfile.ZipFile(path) as zin:
        return lxml_etree.fromstring(zin.read("word/document.xml"))


def _cell_text(root, tbl_i: int, row_i: int, cell_i: int) -> str:
    body = root.find(W + "body")
    tbl = body.findall(W + "tbl")[tbl_i]
    tr = tbl.findall(W + "tr")[row_i]
    nodes = [n for n in tr if n.tag in (W + "tc", W + "sdt")]
    return "".join(t.text or "" for t in nodes[cell_i].iter(W + "t"))


@pytest.fixture()
def template_exists():
    if not TEMPLATE.exists():
        pytest.skip(f"template not present: {TEMPLATE}")


def test_fill_all_v10_addresses(tmp_path, template_exists):
    doc = OszDocument(TEMPLATE)
    values = {key: f"VAL-{key}" for key in V10}
    for key, addr in V10.items():
        if addr.kind == "sdt_cell":
            doc.fill_sdt_cell(addr.table, addr.row, addr.cell, [values[key]])
        else:
            doc.fill_plain(addr.table, addr.row, addr.cell, values[key],
                           style_from=addr.style_from)
    out = tmp_path / "filled.docx"
    doc.save(out)

    root = _document_root(out)
    for key, addr in V10.items():
        assert values[key] in _cell_text(root, addr.table, addr.row, addr.cell), key


def test_multiline_sdt_stays_single_paragraph(tmp_path, template_exists):
    doc = OszDocument(TEMPLATE)
    addr = V10["x_htrs"]
    doc.fill_sdt_cell(addr.table, addr.row, addr.cell, ["prvi", "drugi", "treći"])
    out = tmp_path / "multi.docx"
    doc.save(out)

    root = _document_root(out)
    body = root.find(W + "body")
    tbl = body.findall(W + "tbl")[addr.table]
    tr = tbl.findall(W + "tr")[addr.row]
    sdt = [n for n in tr if n.tag in (W + "tc", W + "sdt")][addr.cell]
    content = sdt.find(W + "sdtContent")
    holder = content.find(W + "tc")
    holder = holder if holder is not None else content
    assert len(holder.findall(W + "p")) == 1  # a second w:p corrupts the file
    assert len(holder.findall(".//" + W + "br")) == 2


def test_tick_checkbox_sets_state_and_glyph(tmp_path, template_exists):
    doc = OszDocument(TEMPLATE)
    missing = doc.tick({"špilja"})
    assert missing == set()
    out = tmp_path / "ticked.docx"
    doc.save(out)

    root = _document_root(out)
    ticked = []
    for sdt in root.iter(W + "sdt"):
        pr = sdt.find(W + "sdtPr")
        if pr is None or pr.find(W14 + "checkbox") is None:
            continue
        checked = pr.find(W14 + "checkbox/" + W14 + "checked")
        if checked is not None and checked.get(W14 + "val") == "1":
            ticked.append(sdt)
    assert len(ticked) == 1
    sym = ticked[0].find(".//" + W + "sym")
    assert sym is not None and sym.get(W + "char", "").startswith("F0")


def test_tick_reports_unknown_label(template_exists):
    doc = OszDocument(TEMPLATE)
    assert doc.tick({"ne postoji takva kućica"}) == {"ne postoji takva kućica"}


def test_embed_png(tmp_path, template_exists):
    doc = OszDocument(TEMPLATE)
    png = make_png(40, 40)
    doc.embed_png(KARTA_FRAME.table, KARTA_FRAME.row, KARTA_FRAME.cell,
                  png, "SB_0001.png")
    out = tmp_path / "with_image.docx"
    doc.save(out)

    with zipfile.ZipFile(out) as zin:
        assert zin.read("word/media/SB_0001.png") == png
        rels = lxml_etree.fromstring(zin.read("word/_rels/document.xml.rels"))
        types = lxml_etree.fromstring(zin.read("[Content_Types].xml"))
        root = lxml_etree.fromstring(zin.read("word/document.xml"))

    rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    image_rels = [r for r in rels.findall(rel_ns + "Relationship")
                  if r.get("Target") == "media/SB_0001.png"]
    assert len(image_rels) == 1

    ct_ns = "{http://schemas.openxmlformats.org/package/2006/content-types}"
    assert any((d.get("Extension") or "").lower() == "png"
               for d in types.findall(ct_ns + "Default"))

    # The template ships with its own drawing (logo), so locate OURS via the
    # relationship id, then check the inline extent that wraps it.
    a_ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    r_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    wp_ns = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
    ours = [b for b in root.iter(a_ns + "blip")
            if b.get(r_ns + "embed") == image_rels[0].get("Id")]
    assert len(ours) == 1
    inline = ours[0]
    while inline is not None and inline.tag != wp_ns + "inline":
        inline = inline.getparent()
    assert inline is not None
    extent = inline.find(wp_ns + "extent")
    cx, cy = int(extent.get("cx")), int(extent.get("cy"))
    assert cx == cy  # square PNG keeps its aspect
    assert cx > 0

    # Our docPr id must not collide with the template's own drawing ids.
    ids = [d.get("id") for d in root.iter(wp_ns + "docPr")]
    assert len(ids) == len(set(ids))


def test_png_dimension_guard():
    from cave_dossier.osz.writer import OszWriteError, _png_dimensions

    assert _png_dimensions(make_png(1017, 1017)) == (1017, 1017)
    with pytest.raises(OszWriteError):
        _png_dimensions(b"not a png at all")
