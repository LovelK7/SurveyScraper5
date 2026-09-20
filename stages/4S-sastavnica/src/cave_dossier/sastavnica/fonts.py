"""Which font the sastavnica's values are typeset in.

The template's own font is a **subset** carrying only the glyphs its example
text used, so it cannot set new text — the first letter the example lacks would
come out blank. The renderer brings its own face instead, resolved in tiers:

1. ``config.yaml`` ``sastavnica.font_path`` — an explicit choice always wins.
2. **Microsoft Sans Serif**, the face the v1.0 template itself is set in.
3. A system fallback (Arial / Segoe UI / Calibri), reported on every run.

**Why not Myriad Pro** (user, 2026-09-20). Until v1.0 the template was set in
Myriad Pro, so the renderer used it too — found in the local Illustrator
install, never bundled, because it is licensed with Illustrator. It looked
right in every PDF viewer and was **broken in the one application the document
is made for**: opened in Illustrator the prefilled values came up as
``Myriad#20Pro#20Regular*``, red-underlined as a missing font. PyMuPDF embeds an
inserted face as a Type0/Identity-H CID subset whose BaseFont carries the font's
*display* name, spaces and all — which matches no installed PostScript name, so
Illustrator cannot resolve it and the text is not editable. The society
re-authored the template in **Microsoft Sans Serif**, which ships with Windows,
and the renderer follows it: the same face in the labels and the values, and one
Illustrator resolves on any machine.

Croatian coverage is verified, not assumed: a face that cannot draw č ć ž š đ
is rejected even if it is the configured one.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path

CROATIAN_GLYPHS = "čćžšđČĆŽŠĐ"

# The template's own face, v1.0 onward. Part of Windows since forever, so it is
# on every machine that opens a sastavnica — found, like Myriad Pro was, never
# bundled, but this one needs no Illustrator licence behind it.
TEMPLATE_FONT_PATTERNS = (
    r"C:\Windows\Fonts\micross.ttf",
    r"C:\Windows\Fonts\MicrosoftSansSerif.ttf",
)

SYSTEM_FALLBACKS = (
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
)


class FontUnavailable(RuntimeError):
    """No usable face anywhere; message is CLI-ready."""


@dataclass(frozen=True)
class ResolvedFont:
    path: Path
    tier: str           # "config" | "template" | "fallback"
    note: str | None = None


def resolve(configured: str | None = None) -> ResolvedFont:
    """The face to typeset values in. Raises ``FontUnavailable`` if none."""
    tried: list[str] = []

    if configured:
        path = Path(configured)
        if not path.exists():
            raise FontUnavailable(
                f"sastavnica.font_path points at a file that does not exist: {path}"
            )
        if not _covers_croatian(path):
            raise FontUnavailable(
                f"sastavnica.font_path ({path.name}) cannot draw Croatian diacritics "
                "(č ć ž š đ) — pick another face."
            )
        return ResolvedFont(path, "config")

    for pattern in TEMPLATE_FONT_PATTERNS:
        for found in sorted(glob.glob(pattern)):
            path = Path(found)
            if _covers_croatian(path):
                return ResolvedFont(path, "template")
            tried.append(path.name)

    for candidate in SYSTEM_FALLBACKS:
        path = Path(candidate)
        if path.exists() and _covers_croatian(path):
            return ResolvedFont(
                path, "fallback",
                note=(f"Microsoft Sans Serif nije nađen — vrijednosti su složene u "
                      f"{path.stem}. Izgled se malo razlikuje od naslova na "
                      "predlošku; postavi sastavnica.font_path ako smeta."),
            )
        tried.append(path.name)

    raise FontUnavailable(
        "No usable font found (tried: " + ", ".join(tried or ["nothing"]) + "). "
        "Set sastavnica.font_path in config.yaml to a TTF/OTF with Croatian coverage."
    )


def postscript_name(path: Path) -> str | None:
    """The face's PostScript name (``MicrosoftSansSerif``), out of its own file.

    Not the display name PyMuPDF's ``Font.name`` gives (``Microsoft Sans Serif
    Regular``) — that one, written into a PDF's ``/BaseFont``, matches nothing
    installed and is what made Illustrator mark our text as a missing font. Read
    from the sfnt ``name`` table, nameID 6, which both TTF and OTF carry.
    """
    import struct

    try:
        data = path.read_bytes()
        (num_tables,) = struct.unpack(">H", data[4:6])
        table = None
        for i in range(num_tables):
            tag, _sum, offset, length = struct.unpack(
                ">4sIII", data[12 + 16 * i:28 + 16 * i])
            if tag == b"name":
                table = (offset, length)
                break
        if table is None:
            return None
        offset, _length = table
        count, string_offset = struct.unpack(">HH", data[offset + 2:offset + 6])
        best = None
        for i in range(count):
            platform, encoding, _lang, name_id, size, at = struct.unpack(
                ">HHHHHH", data[offset + 6 + 12 * i:offset + 18 + 12 * i])
            if name_id != 6:
                continue
            raw = data[offset + string_offset + at:offset + string_offset + at + size]
            text = (raw.decode("utf-16-be", "ignore") if platform == 3
                    else raw.decode("latin-1", "ignore"))
            text = text.strip()
            if text and (best is None or platform == 3):
                best = text
        return best
    except Exception:       # noqa: BLE001 — a name we cannot read is simply absent
        return None


def _covers_croatian(path: Path) -> bool:
    try:
        import pymupdf

        font = pymupdf.Font(fontfile=str(path))
    except Exception:       # noqa: BLE001 — an unreadable face is simply not a candidate
        return False
    return all(font.has_glyph(ord(char)) for char in CROATIAN_GLYPHS)
