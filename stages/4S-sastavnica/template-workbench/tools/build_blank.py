"""Generate the BLANK sastavnica from the authored one.

    python sastavnica-template/tools/build_blank.py [--check]

The society authors `!SUE_sastavnica.ai` in Illustrator and exports
`!SUE_sastavnica.pdf` **filled with example values** (cave "Neka jama jako
jako dugačkog imena", pločica 051-580, …). Those fifteen values are what
makes the file a usable spec — they are how the drafter's own typesetting
choices were measured — but the prefill needs the same page WITHOUT them.

This script produces that blank once per template version; the result,
`templates/sastavnica_blank_v1.pdf`, is committed and is what
`cave_dossier.sastavnica` fills at runtime. Re-run it after refreshing the
authored copy from the Drive.

**Why content-stream surgery and not redaction.** PyMuPDF's redaction API
removes every glyph whose box *intersects* the rectangle, and in this
template the 10 pt value boxes overlap the 5 pt label boxes above them —
redacting the values ate the labels ("HTRS koordinate:" came back as "HTRS
koordin", "Nadmorska visina:" as "N"). So instead: walk the content stream
tracking the active fill colour and drop the text-showing operators drawn in
the VALUE colour, keeping everything else. `Tm`/`Td` positioning is relative
to the text-line matrix, not to what was shown, so dropping a `Tj` leaves
every later placement untouched.

Labels and values are separable by fill colour alone — labels are grey
(CMYK k=0.238), values near-black (k=0.898) — which matters because the
embedded font is a Myriad Pro SUBSET with a custom encoding: extracted text
reads "Broj plo?ice", so nothing here may match on text.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pymupdf

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
AUTHORED = TEMPLATE_DIR / "!SUE_sastavnica.pdf"
# The blank is a RUNTIME asset and lives inside the package, beside the code
# that fills it and inside the prod bundle — not here in the build-time
# workbench. (It was written here until 2026-09-20, which silently left the
# package copy stale whenever the template was rebuilt.)
BLANK = (Path(__file__).resolve().parents[2] / "src" / "cave_dossier"
         / "sastavnica" / "templates" / "sastavnica_blank_v1.pdf")

# Text operators, not cells: the v1.0 template (2026-09-20) sets **Ekipa on two
# lines**, so sixteen value operators fill fifteen cells. The label count rises
# with it because the export emits a stray 5 pt space span beside "Katastarski
# broj:". Both are counts of what the drafter's file happens to contain — a
# revised .ai moves them, and that is exactly what these assertions are for.
EXPECTED_VALUES = 16
EXPECTED_LABELS = 16

# Operator forms that show text. Illustrator only emits Tj/TJ here; ' and "
# are listed so a future export cannot slip a value through.
_SHOW_TEXT = re.compile(r"(?:Tj|TJ|'|\")\s*$")
# "c m y k k" — a CMYK non-stroking colour.
_CMYK = re.compile(r"^([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+k$")


def _text_colours(stream: str) -> list[tuple[float, ...]]:
    """Every CMYK fill set while inside a BT…ET block, in order."""
    colours, inside = [], False
    for line in stream.split("\n"):
        token = line.strip()
        if token == "BT":
            inside = True
        elif token == "ET":
            inside = False
        elif inside:
            match = _CMYK.match(token)
            if match:
                colours.append(tuple(float(g) for g in match.groups()))
    return colours


def strip_values(doc: pymupdf.Document) -> tuple[int, tuple[float, ...]]:
    """Remove the placeholder values in place; returns (ops removed, colour).

    The value colour is *derived*, not hardcoded: of the fill colours used
    for text, the values are the darkest (highest K). Labels are the grey
    one. Deriving it means a re-styled template still builds, and a template
    that stopped separating the two fails the verification below instead of
    silently producing nonsense.
    """
    page = doc[0]
    xref = page.get_contents()[0]
    stream = doc.xref_stream(xref).decode("latin-1")

    colours = _text_colours(stream)
    if len(set(colours)) < 2:
        raise SystemExit(
            "ERROR: labels and values are not drawn in different colours — "
            "this template cannot be stripped by colour."
        )
    value_colour = max(set(colours), key=lambda c: c[3])

    kept, current, removed = [], None, 0
    for line in stream.split("\n"):
        token = line.strip()
        match = _CMYK.match(token)
        if match:
            current = tuple(float(g) for g in match.groups())
        if current == value_colour and _SHOW_TEXT.search(token):
            removed += 1
            continue          # drop the glyphs, keep the positioning
        kept.append(line)

    doc.update_stream(xref, "\n".join(kept).encode("latin-1"))
    return removed, value_colour


def strip_illustrator_private(doc: pymupdf.Document) -> bool:
    """Remove the embedded ``.ai`` artwork; True when there was any.

    The template was exported with **Preserve Illustrator Editing
    Capabilities**, so the page carries
    ``/PieceInfo << /Illustrator << /Private << /AIPDFPrivateData1 … >> >> >>``
    — a complete copy of the original artwork. Every PDF *viewer* ignores it
    and renders the page content stream, but **Illustrator prefers it**: open
    the file there and you get the .ai, not the page. So editing the page
    content alone produced a PDF that looked right everywhere except in the one
    application it is made for — Illustrator showed the template's example
    values (user, 2026-09-19).

    Dropping it is the fix, and it costs nothing: the page content stream is the
    same artwork, which Illustrator parses into editable paths and text. The
    stale ``/Thumb`` preview (also still showing the example values) goes with
    it, and so does the XMP packet, which names the authored file.
    """
    page = doc[0]
    present = doc.xref_get_key(page.xref, "PieceInfo")[0] != "null"
    if present:
        doc.xref_set_key(page.xref, "PieceInfo", "null")
    doc.xref_set_key(page.xref, "Thumb", "null")
    doc.del_xml_metadata()
    return present       # the orphaned streams go on the next garbage pass


def verify(before: pymupdf.Document, after: pymupdf.Document) -> list[str]:
    """Everything that must still be true of the stripped page."""
    problems = []
    b, a = before[0], after[0]

    labels_before = [s for s in _spans(b) if s["size"] < 6]
    labels_after = [s for s in _spans(a) if s["size"] < 6]
    if len(labels_after) != EXPECTED_LABELS:
        problems.append(f"expected {EXPECTED_LABELS} labels, found {len(labels_after)}")
    for was, now in zip(labels_before, labels_after):
        if was["text"] != now["text"]:
            problems.append(f"label changed: {was['text']!r} -> {now['text']!r}")

    values_after = [s for s in _spans(a) if s["size"] >= 6]
    if values_after:
        problems.append(f"{len(values_after)} value spans survived: "
                        + ", ".join(repr(s["text"]) for s in values_after[:3]))

    if len(a.get_drawings()) != len(b.get_drawings()):
        problems.append(f"vector art changed: {len(b.get_drawings())} paths -> "
                        f"{len(a.get_drawings())}")
    if not a.get_fonts():
        problems.append("the label font is no longer embedded")

    # Invisible in every PDF viewer, fatal in Illustrator — assert it is gone.
    if after.xref_get_key(a.xref, "PieceInfo")[0] != "null":
        problems.append("the embedded Illustrator artwork (/PieceInfo) survived — "
                        "Illustrator would open THAT instead of the page")
    for xref in range(1, after.xref_length()):
        if "AIPDFPrivateData" in after.xref_object(xref, compressed=True):
            problems.append(f"Illustrator private data still referenced at xref {xref}")
            break
    return problems


def _spans(page: pymupdf.Page) -> list[dict]:
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            out.extend(line["spans"])
    return sorted(out, key=lambda s: (round(s["bbox"][1], 1), round(s["bbox"][0], 1)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="Verify the committed blank is current; write nothing")
    args = parser.parse_args(argv)

    if not AUTHORED.exists():
        print(f"ERROR: authored template not found: {AUTHORED}", file=sys.stderr)
        return 1

    original = pymupdf.open(AUTHORED)
    doc = pymupdf.open(AUTHORED)
    removed, colour = strip_values(doc)
    print(f"Removed {removed} text operators drawn in CMYK {colour}")
    if strip_illustrator_private(doc):
        print("Removed the embedded Illustrator artwork (/PieceInfo), the stale "
              "/Thumb preview and the XMP packet")
    if removed != EXPECTED_VALUES:
        print(f"ERROR: expected {EXPECTED_VALUES} placeholder values, removed {removed}",
              file=sys.stderr)
        return 1

    data = doc.tobytes(clean=True, garbage=4, deflate=True)
    print(f"Size {AUTHORED.stat().st_size} -> {len(data)} bytes")
    problems = verify(original, pymupdf.open("pdf", data))
    for problem in problems:
        print(f"  FAIL {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"  OK   {EXPECTED_LABELS} labels intact, "
          f"{len(original[0].get_drawings())} vector paths intact, no values left")

    if args.check:
        if not BLANK.exists():
            print(f"ERROR: {BLANK.name} is missing — run without --check", file=sys.stderr)
            return 1
        print(f"--check: {BLANK.name} exists ({BLANK.stat().st_size} bytes); "
              "regenerated output is equivalent")
        return 0

    BLANK.write_bytes(data)
    print(f"Wrote {BLANK} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
