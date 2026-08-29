"""The Liburnija sheet — full reader (the *LiDAR Kristal* table).

`1-YNyvG5p9pkiqss0au5IEKZfwkXzUUAylCcFDRPCFY8`, owner `grozicdino@`. A live
Google Sheet people type into in the field: LIDAR-derived cave candidates with
coordinates, whether anyone checked the point, whether it turned out to be a
cave, and — for the ones that did — a name, a plaque number, and hand-kept flags
for the three gate-1 deliverables.

Read through a cached CSV export under `example/` (gitignored — society data),
refreshed with the Drive MCP. There is no file on the Drive mount to read: the
sheet is a *native* Google Sheet, so nothing about SB's local-path approach
applies to it.

Two shapes of row live here, and both are real objects:

* **396 LIDAR points** — `name` is the point number, and that number is what SB
  carries back as the synonym ``LiDAR Kristal N``.
* **14 field finds** — `name` is free text and `vjerojatnost` reads
  *"nije na Lidaru"*; someone walked past a cave the LIDAR never saw. These have
  no number, so the synonym convention cannot reach them.

Everything after them in the export is blank filler (240 rows) and is skipped.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import FEATURE_ROOT, Settings
from cave_dossier.satellites.model import CandidateState

SOURCE = "liburnija"

# Header spellings as they stand in the export. Kept as constants because the
# sheet is owned by someone else: when a column is renamed there, exactly one
# line here changes.
COL_ID = "name"
COL_X, COL_Y, COL_Z = "x", "y", "z"
COL_PROBABILITY = "vjerojatnost"
COL_CHECKED = "provjereno (1/0)"
COL_CHECKED_BY = "provjerio"
COL_CHECKED_ON = "datum provjere"
COL_IS_CAVE = "speleo_obj (1/0)"
COL_EXPLORED = "istrazeno (1/0)"
COL_EXPLORED_BY = "Istražili"
COL_NAME_NEW = "Naziv_novi"
COL_NAME_OLD = "Naziv_stari"
COL_PLAQUE = "Br.pl"
COL_COMMENT = "Komentar"
COL_ZAPISNIK, COL_NACRT, COL_PHOTO = "Zapisnik", "Nacrt", "Foto ulaza"

#: The society whose caves belong in SB. Anything else was explored separately
#: by another society and stays out — no *sudjelovanje* case (user, 2026-08-29).
OWN_SOCIETY = "SUE"


@dataclass(frozen=True)
class SheetRow:
    """One row of the sheet. ``row_id`` is provenance, never a join key."""

    row_id: str
    line: int                    # 1-based data line in the export ("red 43")
    x: float | None
    y: float | None
    z: float | None
    probability: str | None
    checked: bool
    checked_by: str | None
    checked_on: str | None
    is_cave: bool
    explored: bool
    explored_by: str | None
    name_new: str | None
    name_old: str | None
    plaque: str | None
    comment: str | None
    has_zapisnik: bool
    has_nacrt: bool
    has_photo: bool

    @property
    def state(self) -> CandidateState:
        if not self.checked:
            return CandidateState.UNCHECKED
        if not self.is_cave:
            return CandidateState.NOT_A_CAVE
        return CandidateState.EXPLORED if self.explored else CandidateState.TO_EXPLORE

    @property
    def kristal_number(self) -> str | None:
        """The LIDAR point number, when this row is one. The field finds are not."""
        return self.row_id if self.row_id.isdigit() else None

    @property
    def kristal_name(self) -> str | None:
        """The name SB knows this point by — as `Ime objekta` or as a synonym."""
        number = self.kristal_number
        return f"LiDAR Kristal {int(number)}" if number else None

    @property
    def field_name(self) -> str | None:
        """The name the field gave it, newest first. Often absent."""
        return self.name_new or self.name_old

    @property
    def is_own_society(self) -> bool:
        """False only when the row names *other* societies and not ours.

        The cell holds a list (`Karsterra, SUE` — a joint trip), so membership
        is what counts, not the first name. An empty cell is not a claim that
        someone else explored it: unexplored rows leave it blank.
        """
        if not self.explored_by:
            return True
        parts = re.split(r"[,;/+&]| i ", self.explored_by)
        return any(part.strip().upper().startswith(OWN_SOCIETY) for part in parts)

    @property
    def has_coordinates(self) -> bool:
        return self.x is not None and self.y is not None


def sheet_path(settings: Settings) -> Path | None:
    """Cached CSV export, resolved against the feature root."""
    relative = settings.intake_sheet_csv
    if not relative:
        return None
    path = Path(relative)
    return path if path.is_absolute() else FEATURE_ROOT / path


def _text(record: dict[str, str], column: str) -> str | None:
    """A cell, or None. ``/`` is how the sheet writes "no value"."""
    value = (record.get(column) or "").strip()
    return value if value and value != "/" else None


def _flag(record: dict[str, str], column: str) -> bool:
    """The sheet uses 1/0 for its own flags and TRUE/FALSE for the deliverables."""
    value = (record.get(column) or "").strip().upper()
    return value in ("1", "TRUE", "DA", "YES")


def _number(record: dict[str, str], column: str) -> float | None:
    value = _text(record, column)
    if value is None:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def load(path: Path) -> list[SheetRow]:
    """Every row that has an id. Blank filler rows are skipped, not counted."""
    if not path.is_file():
        return []
    rows: list[SheetRow] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for line, record in enumerate(csv.DictReader(handle), start=1):
            row_id = (record.get(COL_ID) or "").strip()
            if not row_id:
                continue
            rows.append(
                SheetRow(
                    row_id=row_id,
                    line=line,
                    x=_number(record, COL_X),
                    y=_number(record, COL_Y),
                    z=_number(record, COL_Z),
                    probability=_text(record, COL_PROBABILITY),
                    checked=_flag(record, COL_CHECKED),
                    checked_by=_text(record, COL_CHECKED_BY),
                    checked_on=_text(record, COL_CHECKED_ON),
                    is_cave=_flag(record, COL_IS_CAVE),
                    explored=_flag(record, COL_EXPLORED),
                    explored_by=_text(record, COL_EXPLORED_BY),
                    name_new=_text(record, COL_NAME_NEW),
                    name_old=_text(record, COL_NAME_OLD),
                    plaque=_text(record, COL_PLAQUE),
                    comment=_text(record, COL_COMMENT),
                    has_zapisnik=_flag(record, COL_ZAPISNIK),
                    has_nacrt=_flag(record, COL_NACRT),
                    has_photo=_flag(record, COL_PHOTO),
                )
            )
    return rows


def load_from_settings(settings: Settings) -> tuple[list[SheetRow], Path | None]:
    path = sheet_path(settings)
    return (load(path) if path else []), path


__all__ = [
    "OWN_SOCIETY",
    "SOURCE",
    "SheetRow",
    "load",
    "load_from_settings",
    "sheet_path",
]
