"""SB row → ``CaveDossier`` (pipeline part 2.2 feeding 2.1).

The dedicated ``settings.sb_*_column`` names cover the columns ``SBReader``
itself needs (identity + lookup).  Everything else the dossier reads comes from
``sb.field_columns`` in config.yaml — a ``canonical dossier field → column
header`` map, the same idiom crospeleo-automation uses in
``profile.sb.field_columns``.  Adding a column to the dossier is then a
one-line config edit plus one assignment here.

Column lookup is diacritic- and case-insensitive (``normalize_lookup_key``),
so a header retyped as "Najblize mjesto" still resolves.
"""

from __future__ import annotations

from typing import Any

from cave_dossier.core.config import Settings
from cave_dossier.core.normalization import (
    cleanup_whitespace,
    normalize_lookup_key,
    parse_optional_float,
    split_semicolon_values,
)
from cave_dossier.core.people import is_placeholder, split_person_names
from cave_dossier.dossier.model import CaveDossier, Georeference, QueueFlag, Source
from cave_dossier.sb.loader import CaveRow

# Marker that flags a row as "still to be explored" (SB v3.0 restructure,
# decision 2026-08-22).  Matched on the normalized key so "Za istražit",
# "za istrazit," and "ZA ISTRAŽIT" all hit.
_QUEUE_PREFIX_KEY = normalize_lookup_key("za istražit")


class _Cells:
    """Diacritic-insensitive access to one SB row's cells."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._by_key = {normalize_lookup_key(str(key)): value for key, value in values.items()}

    def text(self, column: str | None) -> str | None:
        """Cell as clean text; ``None`` for empty / NaN / placeholder cells."""
        if not column:
            return None
        value = self._by_key.get(normalize_lookup_key(column))
        if value is None:
            return None
        text = cleanup_whitespace(str(value))
        if text is None or text.lower() in {"nan", "nat", "none"}:
            return None
        # pandas reads integral numbers as floats: 2018.0 → "2018".
        if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
            text = text[:-2]
        return text or None

    def number(self, column: str | None) -> float | None:
        return parse_optional_float(self.text(column))


def parse_queue_flag(note: str | None) -> QueueFlag:
    """Parse SB v3.0's **Napomena** queue marker.

    ``za istražit, [<old Broj>,] <note>`` — the old Za-istražit Broj is
    optional (``Ponor Gotovž``: ``za istražit, detalji u literaturi``), so a
    numeric second segment is read as the old number and anything else is
    kept as the note.  Never require the number: it is a traceability hint
    back to the pre-v3.0 sheet, not a key.
    """
    text = cleanup_whitespace(note)
    if not text:
        return QueueFlag()
    head, _, tail = text.partition(",")
    if normalize_lookup_key(head) != _QUEUE_PREFIX_KEY:
        return QueueFlag(raw=text)

    old_number: str | None = None
    rest = tail.strip()
    candidate, separator, remainder = rest.partition(",")
    if candidate.strip().isdigit():
        old_number = candidate.strip()
        rest = remainder.strip() if separator else ""
    return QueueFlag(
        queued=True,
        old_number=old_number,
        note=cleanup_whitespace(rest),
        raw=text,
    )


def build_from_sb(cave_row: CaveRow, settings: Settings) -> CaveDossier:
    """Seed a dossier from one SB row. Marks ``Source.SB`` as gathered."""
    cells = _Cells(cave_row.values)
    columns = settings.sb_field_columns

    def mapped(field: str) -> str | None:
        return cells.text(columns.get(field))

    note = mapped("note")
    georeference = Georeference(
        x_htrs=cells.number(settings.sb_x_htrs_column),
        y_htrs=cells.number(settings.sb_y_htrs_column),
        z_m=cells.number(columns.get("entrance_elevation_m")),
    )

    dossier = CaveDossier(
        sb_row_number=cave_row.row_number if cave_row.row_number > 0 else None,
        object_name=cave_row.object_name,
        sue_number=cave_row.sue_number,
        plaque_number=cells.text(settings.sb_plaque_column),
        marker_value=cells.text(settings.sb_marker_column),
        crospeleo_round=cells.text(settings.sb_filter_column),
        synonyms=split_semicolon_values(mapped("synonyms")),
        sb_record=dict(cave_row.values),
        locality=mapped("locality"),
        nearest_place=mapped("nearest_place"),
        # A row with no coordinates at all keeps ``georeference=None`` rather
        # than an all-empty object, so gating can say "no georeference" without
        # poking at four sub-fields.
        georeference=georeference if _has_any(georeference) else None,
        length_m=cells.number(columns.get("length_m")),
        depth_m=cells.number(columns.get("depth_m")),
        exploration_period=cells.text(settings.sb_exploration_period_column),
        last_exploration_year=mapped("last_exploration_year"),
        drawing_authors=split_person_names(cells.text(settings.sb_drawing_authors_column)),
        note=note,
        queue_flag=parse_queue_flag(note),
        entrance_photo_flag=_flag(mapped("entrance_photo_flag")),
        pollution_flag=_flag(mapped("pollution_flag")),
        ice_cave_flag=_flag(mapped("ice_cave_flag")),
        supplementary_record_flag=_flag(mapped("supplementary_record_flag")),
        nacrt_link=mapped("nacrt_link"),
        zapisnik_link=mapped("zapisnik_link"),
    )
    dossier.mark_gathered(Source.SB)
    return dossier


def _has_any(georeference: Georeference) -> bool:
    return georeference.has_position or georeference.z_m is not None


def _flag(value: str | None) -> str | None:
    """DA/NE bookkeeping cells: keep the text, drop "/"-style placeholders."""
    return None if is_placeholder(value) else value
