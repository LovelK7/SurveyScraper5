"""Person-name helpers.

``split_person_names`` is ported from crospeleo-automation's
``services/person_resolver.py`` (``flatten_team_members``) — see
docs/PORTING.md.  SB and the OSZ both let recorders write author lists
freely: ``"D.Reš, I.Glavaš"``, ``"Lovel i Mate"``, ``"A.Kapidžić/L.Kukuljan"``.
Splitting them into individual people is what makes per-author izjava gating
possible at all.
"""

from __future__ import annotations

import re

# Separators authors mix freely: comma, semicolon, slash, ampersand, plus,
# and the Croatian / English conjunctions "i" / "te" / "and" as whole words.
# Word-boundary anchors keep the letter "i" inside a name (``Ivić``) from
# being treated as a separator.
_PERSON_SEPARATOR_RE = re.compile(
    r"\s*(?:[,;/&+]|\b(?:i|te|and)\b)\s*",
    re.IGNORECASE,
)

# Cells whose whole content is one of these mean "nobody / nothing" in SB —
# 1245 "Autori nacrta" cells in v3.0 include bare "/" entries.
_PLACEHOLDER_TOKENS = {"/", "-", "--", "?", "n/a", "na", "nema", "x"}

# A fragment that is nothing but initials (optionally followed by a year):
# older SB rows write the surname-first form "Malez, M. (1960)", which the
# comma separator would otherwise tear into two bogus "people".  Such a
# fragment is glued back onto the name before it.
_INITIALS_ONLY_RE = re.compile(r"^(?:[^\W\d_]\.\s*)+(?:\(\d{4}\))?$", re.UNICODE)


def split_person_names(raw: str | None) -> list[str]:
    """Split one free-text author cell into individual person names."""
    if not raw:
        return []
    names: list[str] = []
    for part in _PERSON_SEPARATOR_RE.split(raw):
        cleaned = part.strip().strip(",").strip()
        if not cleaned or cleaned.casefold() in _PLACEHOLDER_TOKENS:
            continue
        if names and _INITIALS_ONLY_RE.match(cleaned):
            names[-1] = f"{names[-1]} {cleaned}"
            continue
        names.append(cleaned)
    return names


def is_placeholder(value: str | None) -> bool:
    """True for cells that are formally non-empty but mean "nothing"."""
    if value is None:
        return True
    return value.strip().casefold() in _PLACEHOLDER_TOKENS or not value.strip()
