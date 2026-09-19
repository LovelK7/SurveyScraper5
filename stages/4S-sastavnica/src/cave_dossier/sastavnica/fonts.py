"""Which font the sastavnica's values are typeset in.

The template's own font is a **subset** of Myriad Pro carrying only the glyphs
its example text used, so it cannot set new text — the first letter the example
lacks would come out blank. The renderer brings its own face instead, resolved
in three tiers:

1. ``config.yaml`` ``sastavnica.font_path`` — an explicit choice always wins.
2. **Myriad Pro**, if the machine has it. Everyone on this branch runs
   Illustrator, which installs ``MyriadPro-Regular.otf`` under its own Support
   Files; using it makes the values typographically identical to the labels the
   template prints.
3. A system fallback (Calibri / Segoe UI / Arial) — close enough to read as one
   design, and reported on every run so nobody mistakes it for the real thing.

Myriad Pro is licensed with Illustrator: it is *found*, never bundled. Vendoring
an OFL substitute (Source Sans 3) for machines without Illustrator is a backlog
item, not a blocker — those machines are not drafting in Illustrator either.

Croatian coverage is verified, not assumed: a face that cannot draw č ć ž š đ
is rejected even if it is the configured one.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path

CROATIAN_GLYPHS = "čćžšđČĆŽŠĐ"

# Illustrator's bundled-font dir, across install years and CC/CS naming.
MYRIAD_PATTERNS = (
    r"C:\Program Files\Adobe\Adobe Illustrator *\Support Files\Required\Fonts\MyriadPro-Regular.otf",
    r"C:\Program Files\Common Files\Adobe\Fonts\MyriadPro-Regular.otf",
    r"C:\Windows\Fonts\MyriadPro-Regular.otf",
    r"C:\Windows\Fonts\MyriadPro-Regular.ttf",
)

SYSTEM_FALLBACKS = (
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
)


class FontUnavailable(RuntimeError):
    """No usable face anywhere; message is CLI-ready."""


@dataclass(frozen=True)
class ResolvedFont:
    path: Path
    tier: str           # "config" | "myriad" | "fallback"
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

    for pattern in MYRIAD_PATTERNS:
        for found in sorted(glob.glob(pattern), reverse=True):   # newest install first
            path = Path(found)
            if _covers_croatian(path):
                return ResolvedFont(path, "myriad")
            tried.append(path.name)

    for candidate in SYSTEM_FALLBACKS:
        path = Path(candidate)
        if path.exists() and _covers_croatian(path):
            return ResolvedFont(
                path, "fallback",
                note=(f"Myriad Pro nije nađen — vrijednosti su složene u {path.stem}. "
                      "Izgled se malo razlikuje od naslova na predlošku; instaliraj "
                      "Illustrator ili postavi sastavnica.font_path."),
            )
        tried.append(path.name)

    raise FontUnavailable(
        "No usable font found (tried: " + ", ".join(tried or ["nothing"]) + "). "
        "Set sastavnica.font_path in config.yaml to a TTF/OTF with Croatian coverage."
    )


def _covers_croatian(path: Path) -> bool:
    try:
        import pymupdf

        font = pymupdf.Font(fontfile=str(path))
    except Exception:       # noqa: BLE001 — an unreadable face is simply not a candidate
        return False
    return all(font.has_glyph(ord(char)) for char in CROATIAN_GLYPHS)
