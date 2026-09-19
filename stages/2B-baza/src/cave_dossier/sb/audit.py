"""Whole-workbook audits — data-quality passes over SB, not per-cave dossiers.

Read-only, like everything else in `sb/`. These exist because the dossier gate
can only report on one cave at a time, while some problems are only visible (and
only fixable) as a column-wide sweep in Excel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from cave_dossier.core.config import Settings
from cave_dossier.core.people import is_author_shorthand, is_placeholder, split_authors
from cave_dossier.dossier.model import LifecycleState
from cave_dossier.dossier.sb_mapper import (
    derive_lifecycle,
    is_participation,
    nesredeni_keywords,
    parse_queue_flag,
)
from cave_dossier.sb.loader import CaveRow, SBReader

# "Malez, M. (1960)" / "Božić (1985)" — a year in brackets marks a literature
# source rather than a person who drew the survey.
_CITATION_RE = re.compile(r"\(\s*(?:19|20)\d{2}\s*\)")
#: One parsed name longer than this is almost certainly a phrase, not a person.
_LONG_NAME_CHARS = 40


@dataclass
class AuthorFinding:
    """One `Autori nacrta ili izvor` cell worth a human look."""

    row_number: int
    serial_number: int | None
    sue_number: str | None
    object_name: str | None
    raw: str | None
    parsed: list[str] = field(default_factory=list)
    societies: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    lifecycle: LifecycleState = LifecycleState.UNCLASSIFIED


#: flag -> what it means, printed as the legend of `sb audit-authors`.
AUTHOR_FLAG_HELP: dict[str, str] = {
    "empty": "cell is empty — no author and no source recorded",
    "placeholder": "cell holds a placeholder ('/', '-') that means 'nobody'",
    "citation": "looks like a literature source (year in brackets), not a survey author",
    "single_name": "one bare word — a first name or nickname, not resolvable to a person",
    "long_entry": f"a single parsed name longer than {_LONG_NAME_CHARS} chars — probably a phrase",
    "conjunction": "split on the word 'i'/'te' — verify the two halves are really two people",
    "society": "carries an outside-society bracket, e.g. (SOV)",
}


def audit_authors(reader: SBReader, settings: Settings) -> list[AuthorFinding]:
    """Every author cell the splitter cannot read confidently.

    Deliberately generous: the point is a worklist for one Excel cleanup pass,
    so a false positive costs the user a glance, while a miss costs a wrong
    izjava check later.
    """
    findings: list[AuthorFinding] = []
    for cave in _iter_caves(reader, settings):
        raw = _cell(cave.values, settings.sb_drawing_authors_column)
        names, societies = split_authors(raw)
        note = _cell(cave.values, settings.sb_field_columns.get("note", "Napomena"))
        lifecycle = derive_lifecycle(
            cave.sue_number,
            parse_queue_flag(note).queued,
            bool(nesredeni_keywords(note)),
            is_participation(note),
        )

        flags: list[str] = []
        if raw is None:
            flags.append("empty")
        elif is_placeholder(raw):
            flags.append("placeholder")
        if raw and _CITATION_RE.search(raw):
            flags.append("citation")
        if raw and re.search(r"\b(?:i|te)\b", raw, re.IGNORECASE):
            flags.append("conjunction")
        if societies:
            flags.append("society")
        for name in names:
            if len(name) > _LONG_NAME_CHARS:
                flags.append("long_entry")
                break
        for name in names:
            # "Renata" — one word, no initial, no dot: nothing to match a person on.
            if " " not in name and "." not in name and len(name.split()) == 1:
                flags.append("single_name")
                break

        if flags:
            findings.append(
                AuthorFinding(
                    row_number=cave.row_number,
                    serial_number=_int(_cell(cave.values, settings.sb_field_columns.get("serial_number"))),
                    sue_number=cave.sue_number,
                    object_name=cave.object_name,
                    raw=raw,
                    parsed=names,
                    societies=societies,
                    flags=sorted(set(flags)),
                    lifecycle=lifecycle,
                )
            )
    return findings


@dataclass
class UnclassifiedRow:
    """A named row that appears in none of SB's three Power Query views."""

    row_number: int
    serial_number: int | None
    object_name: str | None
    locality: str | None
    exploration_period: str | None
    note: str | None


def audit_unclassified(reader: SBReader, settings: Settings) -> list[UnclassifiedRow]:
    """Rows with no SUE number and no Napomena flag of any kind.

    Invisible in Istraženi, Nesređeni and Za istražit alike, so nobody is
    looking at them. 47 in v3.0 before *sudjelovanje* was recognised as its own
    state, 19 after — the rest were other societies' caves SUE took part in.
    """
    columns = settings.sb_field_columns
    rows: list[UnclassifiedRow] = []
    for cave in _iter_caves(reader, settings):
        note = _cell(cave.values, columns.get("note", "Napomena"))
        lifecycle = derive_lifecycle(
            cave.sue_number,
            parse_queue_flag(note).queued,
            bool(nesredeni_keywords(note)),
            is_participation(note),
        )
        if lifecycle is not LifecycleState.UNCLASSIFIED:
            continue
        rows.append(
            UnclassifiedRow(
                row_number=cave.row_number,
                serial_number=_int(_cell(cave.values, columns.get("serial_number"))),
                object_name=cave.object_name,
                locality=_cell(cave.values, columns.get("locality")),
                exploration_period=_cell(cave.values, settings.sb_exploration_period_column),
                note=note,
            )
        )
    return rows


def iter_author_names(reader: SBReader, settings: Settings):
    """``(CaveRow, survey-author names)`` for every named row that has any.

    The people-registry sweep (`cavedossier people check`). Skipped on purpose:
    placeholder cells, literature citations, and — per the user's single
    criterion (2026-08-30) — every name NOT in the ``N.Surname`` shorthand,
    because in this cell only that form marks a survey author; everything else
    is a cave finder/source, who needs no izjava and no registry entry.
    """
    for cave in _iter_caves(reader, settings):
        raw = _cell(cave.values, settings.sb_drawing_authors_column)
        if raw is None or is_placeholder(raw) or _CITATION_RE.search(raw):
            continue
        names, _societies = split_authors(raw)
        authors = [name for name in names if is_author_shorthand(name)]
        if authors:
            yield cave, authors


# ── Shared helpers ────────────────────────────────────────────────────


def _iter_caves(reader: SBReader, settings: Settings):
    """Every named row as a ``CaveRow`` — blank spacer rows skipped.

    v3.0's table runs 7 rows past the last cave; those carry no name and no SUE
    and would otherwise pollute every audit.
    """
    frame = reader.load_rows()
    for _index, row in frame.iterrows():
        record = {str(key).strip(): value for key, value in row.to_dict().items()}
        cave = reader._to_cave_row(record)  # noqa: SLF001 — same package, deliberate
        if not cave.object_name:
            continue
        yield cave


def _cell(values: dict[str, Any], column: str | None) -> str | None:
    if not column:
        return None
    value = values.get(column)
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
        text = text[:-2]
    return text


def _int(text: str | None) -> int | None:
    try:
        return int(float(text)) if text else None
    except ValueError:
        return None


__all__ = [
    "AUTHOR_FLAG_HELP",
    "AuthorFinding",
    "UnclassifiedRow",
    "audit_authors",
    "audit_unclassified",
    "iter_author_names",
]
