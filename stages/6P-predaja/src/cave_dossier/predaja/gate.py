"""The SUE gate — what the society needs before a cave gets its katastarski broj.

6P owns this gate (user, 2026-10-22); 5D judges only CroSpeleo. It is the old
5D "gate 1" minus the izjava requirement, which is a CroSpeleo rule and never
held a delivery back. The rest of the SUE gate is checked in ``plan.py`` from
the leaf itself: the OSZ's obligatory fields (``osz provjera``, those marked
SUE), the Nacrt and a processed entrance photo.

The checks here read the cave's SB row (through 5D's ``CaveDossier`` mapping)
and, for Dubina, the zapisnik — delivery fills an empty SB Dubina from it, so
either is enough. Protokol §5.1 decides how strict coordinates and pločica are:
mandatory for caves first explored in 2015 or later, warnings for older ones
(a cave explored in 1960 never had a pločica); a kaverna needs no pločica.
"""

from __future__ import annotations

import re

from cave_dossier.core.people import is_placeholder

#: Protokol §5.1 — from this exploration year on, coordinates + pločica are mandatory.
REQUIRED_FROM_YEAR = 2015
_YEAR = re.compile(r"(?:19|20)\d{2}")

#: SB cells the society needs (label, CaveDossier attribute).
SB_FIELDS: tuple[tuple[str, str], ...] = (
    ("Ime objekta", "object_name"),
    ("Lokalitet", "locality"),
    ("Najbliže mjesto", "nearest_place"),
    ("Razdoblje istraživanja", "exploration_period"),
    ("Autori nacrta ili izvor", "drawing_authors"),
)


def start_year(dossier) -> int | None:
    """Earliest year in the exploration period (the conservative §5.1 reading)."""
    for candidate in (dossier.exploration_period, dossier.last_exploration_year):
        years = _YEAR.findall(candidate or "")
        if years:
            return min(int(year) for year in years)
    return None


def sue_issues(dossier, osz_fields: dict | None = None,
               osz_ticked=()) -> list[tuple[str, str]]:
    """``[(severity, text)]`` — ``"blocker"`` or ``"warning"``, Croatian text."""
    out: list[tuple[str, str]] = []
    for label, attribute in SB_FIELDS:
        value = getattr(dossier, attribute, None)
        empty = not value if isinstance(value, list) else is_placeholder(value)
        if empty:
            out.append(("blocker", f"SB: prazno '{label}'."))

    osz_depth = (osz_fields or {}).get("dubina")
    if dossier.effective_depth_m() is None and is_placeholder(osz_depth):
        out.append(("blocker", "Dubina: nema je ni u SB-u ni u OSZ-u (3N KORAK 4 je upisuje u OSZ)."))

    year = start_year(dossier)
    modern = year is not None and year >= REQUIRED_FROM_YEAR
    severity = "blocker" if modern else "warning"
    why = (f"istraživanje {year} ≥ {REQUIRED_FROM_YEAR}" if modern
           else f"istraživanje {year or 'nepoznate godine'} – prije {REQUIRED_FROM_YEAR} nije obvezno")
    if dossier.exploration_period and not _YEAR.search(dossier.exploration_period):
        out.append(("warning", f"SB: 'Razdoblje istraživanja' = {dossier.exploration_period!r} nema "
                               "godinu – §5.1 se računa kao nepoznata godina."))
    if dossier.georeference is None or not dossier.georeference.has_position:
        out.append((severity, f"SB: nema koordinata ulaza ({why})."))
    cavern = "kavern" in " ".join([dossier.object_type or "", *map(str, osz_ticked)]).casefold()
    if not cavern and is_placeholder(dossier.plaque_number):
        out.append((severity, f"SB: nema broja pločice ({why})."))
    return out
