"""The *Liburnija_pot_speleo_2024* sheet — a third source, read for one job.

A Google Sheet (`grozicdino@gmail.com`, 396 numbered rows) listing LIDAR-derived
cave candidates on Liburnija: coordinates, whether someone checked the point,
whether it turned out to be a cave, and — for the ones that did — a name and a
**plaque number**.

Its `name` column is a plain row number, and that number is what the Veprinac
intake folders are named after: `!!!Ekspedicija Veprinac_2025/108_Renata` is
sheet row 108. The row's `Br.pl` then resolves into SB, which is how a folder
called `108_Renata` becomes *LiDAR Kristal 108* (Redni broj 1248).

**This is a read-only bridge, not an integration.** Wiring the sheet in as a
proper source — people do enter data there — is a later architecture decision
(user, 2026-08-29); for now it exists to give the folders correct prefixes. The
sheet is cached as CSV under `example/` (gitignored, it is society data);
refresh it with the Drive MCP export when the numbers stop resolving.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import CaveCandidate
from cave_dossier.core.normalization import normalize_lookup_key


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
    from cave_dossier.core.config import FEATURE_ROOT

    relative = settings.intake_sheet_csv
    if not relative:
        return None
    path = Path(relative)
    return path if path.is_absolute() else FEATURE_ROOT / path


def load_rows(path: Path) -> dict[str, LiburnijaRow]:
    """Row number → row, for the rows that carry a numeric `name`."""
    if not path.is_file():
        return {}
    rows: dict[str, LiburnijaRow] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            number = (record.get("name") or "").strip()
            if not number.isdigit():
                continue
            plaque = (record.get("Br.pl") or "").strip()
            rows[number] = LiburnijaRow(
                number=number,
                plaque=plaque if plaque and plaque != "/" else None,
                name=(record.get("Naziv_novi") or record.get("Naziv_stari") or "").strip() or None,
                is_cave=(record.get("speleo_obj (1/0)") or "").strip() == "1",
                explored=(record.get("istrazeno (1/0)") or "").strip() == "1",
                comment=(record.get("Komentar") or "").strip() or None,
            )
    return rows


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
