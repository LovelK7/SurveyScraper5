"""Intake's view of the Liburnija sheet: number → row → plaque → SB.

The sheet itself — all 18 columns, the candidate lifecycle, the two-way sync —
lives in `cave_dossier.satellites.liburnija`. This module is the narrow slice
**intake** needs: the Veprinac folders are named after sheet row numbers
(`!!!Ekspedicija Veprinac_2025/108_Renata` is sheet row 108), and the row's
plaque number is what turns `108_Renata` into *LiDAR Kristal 108* (Redni broj
1248).

Kept as its own surface because the two callers want different things: intake
resolves a folder name and stops, while the hub compares every row against SB.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import CaveCandidate
from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.satellites import liburnija as sheet


@dataclass(frozen=True)
class LiburnijaRow:
    """One LIDAR candidate. Only the fields this bridge needs."""

    number: str
    plaque: str | None
    name: str | None          # Naziv_novi, else Naziv_stari
    is_cave: bool             # speleo_obj (1/0)
    explored: bool            # istrazeno (1/0)
    comment: str | None


def sheet_path(settings: Settings) -> Path | None:
    """Cached CSV export, resolved against the feature root."""
    return sheet.sheet_path(settings)


def load_rows(path: Path) -> dict[str, LiburnijaRow]:
    """Row number → row, for the rows that carry a numeric `name`."""
    return {
        row.row_id: LiburnijaRow(
            number=row.row_id,
            plaque=row.plaque,
            name=row.field_name,
            is_cave=row.is_cave,
            explored=row.explored,
            comment=row.comment,
        )
        for row in sheet.load(path)
        if row.row_id.isdigit()
    }


def resolve(
    number: str, rows: dict[str, LiburnijaRow], candidates: list[CaveCandidate]
) -> tuple[LiburnijaRow, CaveCandidate | None] | None:
    """Follow number → sheet row → plaque → SB row.

    Returns ``None`` when the number is not a sheet row at all, and
    ``(row, None)`` when it is but SB has no cave with that plaque — the second
    case is the one that produces "add this to SB".

    The plaque is what makes this safe to run on every folder rather than only
    the Veprinac ones: numbers from other numbering schemes either miss the
    sheet or land on a row with no plaque, and neither yields a match.
    """
    row = rows.get(number)
    if row is None:
        return None
    if not row.plaque:
        return row, None
    key = normalize_lookup_key(row.plaque)
    match = next(
        (cave for cave in candidates if cave.plaque_number and normalize_lookup_key(cave.plaque_number) == key),
        None,
    )
    return row, match


__all__ = ["LiburnijaRow", "load_rows", "resolve", "sheet_path"]
