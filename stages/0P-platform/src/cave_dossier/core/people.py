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
#
# A conjunction must be SURROUNDED BY SPACE, not merely word-bounded (fixed
# 2026-09-19). Word boundaries alone matched the initial of every author whose
# first name starts with I — "I. Dujmović" split into "" and ". Dujmović",
# losing the initial, and "I.Dujmović" likewise. That silently mangled every
# Ivan/Ivo/Igor/Iva/Ines in the author cells the izjava gates read.
_PERSON_SEPARATOR_RE = re.compile(
    r"\s*[,;/&+]\s*|\s+(?:i|te|and)\s+",
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


# "A.Lipovac (SOV)" — the bracket is not part of the name. In SB it flags that
# the sketch was drawn by someone from a society other than SUE (user, 2026-08-26).
_SOCIETY_SUFFIX_RE = re.compile(r"\s*\(([^()]{1,40})\)\s*$")


# Croatian caving-organisation type prefixes, long form and short. The
# abbreviation a member writes glues the short prefix straight onto the named
# entity's initial: "Speleološka udruga Estavela" / "SU Estavela" -> "SUE",
# "SO Velebit" -> "SOV", "SO HPD Željezničar" -> "SOŽ". Rule and prefix table
# adapted from crospeleo-automation's
# services/organization_alias_generator.py — see docs/PORTING.md.
_SOCIETY_PREFIXES: tuple[tuple[str, str], ...] = (
    ("speleoloski odsjek", "SO"),
    ("speleolosko drustvo", "SD"),
    ("speleoloski klub", "SK"),
    ("speleoloska udruga", "SU"),
    ("so", "SO"),
    ("sd", "SD"),
    ("sk", "SK"),
    ("su", "SU"),
)
# A section canonical may carry its parent society's acronym between the type
# prefix and the named entity ("SO PDS Velebit"); the abbreviation skips it.
_PARENT_ACRONYMS = frozenset({"hpd", "pds", "pd", "pk"})

_FOLD = str.maketrans("čćžšđČĆŽŠĐ", "cczsdCCZSD")


def society_shorthand(name: str | None) -> str | None:
    """``SU Estavela`` -> ``SUE``; None when the name is not of that shape.

    The Sastavnica's Istražili cell is 55 pt wide and holds one society
    comfortably. Two do not fit written out, and the abbreviation is what a
    caver writes anyway, so a list of societies is set in short form (user,
    2026-09-20). A name that does not follow the four caving-organisation
    patterns comes back as None and is left exactly as written — this never
    invents an abbreviation.
    """
    if not name:
        return None
    # A canonical ends in ", <City>"; the entity is before that.
    head = name.split(",")[0].replace('"', " ").replace("„", " ").replace("”", " ")
    tokens = [token for token in head.split() if token]
    if len(tokens) < 2:
        return None
    folded = [token.translate(_FOLD).casefold().strip(".") for token in tokens]

    for long_form, short in _SOCIETY_PREFIXES:
        words = long_form.split()
        if folded[:len(words)] != words:
            continue
        rest = tokens[len(words):]
        while rest and rest[0].translate(_FOLD).casefold().strip(".") in _PARENT_ACRONYMS:
            rest = rest[1:]
        if not rest or not rest[0][:1].isalpha():
            return None
        return short + rest[0][:1].upper()
    return None


def split_authors(raw: str | None) -> tuple[list[str], dict[str, str]]:
    """Split an author cell into ``(names, {name: society})``.

    The society bracket is stripped off the name so that izjava matching and
    any future person registry see the bare person, while the flag itself
    survives — an outside-society author still needs an izjava, and knowing the
    sketch came from outside SUE is worth showing.
    """
    names: list[str] = []
    societies: dict[str, str] = {}
    for entry in split_person_names(raw):
        match = _SOCIETY_SUFFIX_RE.search(entry)
        if match:
            bracket = match.group(1).strip()
            name = entry[: match.start()].strip()
            # A bracket that swallowed the whole entry is not a society, and
            # neither is a bare year — legacy rows write "Malez, M. (1960)",
            # where the year belongs to the citation, not to a society.
            if name and not bracket.isdigit():
                societies[name] = bracket
                entry = name
        names.append(entry)
    return names, societies


def is_placeholder(value: str | None) -> bool:
    """True for cells that are formally non-empty but mean "nothing"."""
    if value is None:
        return True
    return value.strip().casefold() in _PLACEHOLDER_TOKENS or not value.strip()


# One or more uppercase initials, each with a dot (optional space), then an
# uppercase-starting surname (hyphen/apostrophe joins allowed: Kapidžić-Antolič).
_AUTHOR_SHORTHAND_RE = re.compile(
    r"^(?:[^\W\d_]\.\s?)+[^\W\d_]+(?:[-'][^\W\d_]+)*$",
    re.UNICODE,
)


def is_author_shorthand(name: str | None) -> bool:
    """Is this the ``N.Surname`` form that marks a SURVEY AUTHOR in SB?

    The `Autori nacrta ili izvor` cell mixes two groups (user, 2026-08-30):
    survey authors — who need an izjava — are consistently written
    initial·dot·surname (``L.Kukuljan``, ``S.Kapidžić-Antolič``), while cave
    finders/sources are written every other way (bare first names, full names,
    phrases) and need none. This predicate is the single criterion: only names
    it accepts go through the statement gates and the registry sweep.
    """
    if not name:
        return False
    cleaned = name.strip()
    if not _AUTHOR_SHORTHAND_RE.match(cleaned):
        return False
    # The regex is case-blind by construction; the convention is not.
    surname = cleaned.rsplit(".", 1)[-1].strip()
    return cleaned[0].isupper() and bool(surname) and surname[0].isupper()
