"""`Izjava za katastar` filenames — who signed, and what the signature covers.

Convention in `!!Izjave za katastar RH` (confirmed by the user 2026-08-26):

    Izjava_<Osoba>[_<Opseg>].<ext>

* **No suffix → universal.** `Izjava_ABahović.pdf` covers every cave.
* **Suffix → scope.** `Izjava_ACiceran_Šverda.pdf` covers only caves in the
  *Šverda* locality; the same author drawing a cave elsewhere needs a new
  izjava. The scope may also name a single cave (`Kaverna-Učka`, `Kotluša`) —
  both are exceptions rather than the rule.
* **A double surname is joined with a hyphen**, not an underscore, so
  `SKapidžić-Antolič` reads as one person rather than a person plus a scope.
  (Until the user finishes renaming, the legacy underscore form is detected
  heuristically — see ``LEGACY_DOUBLE_SURNAMES``.)
* Files whose name starts with `!` are society notes and blank templates
  (`!!Izjava_SUE_član_2021_prazna.pdf`, `!!!Fale_Brane.txt`), never izjave.
  The `!!!` ones are the society's own lists of *missing* izjave.

Scope resolution needs the dossier, because a suffix is only a locality if the
cave says so: ``covers`` compares it against ``Lokalitet``, then the object
name and its synonyms.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.normalization import normalize_lookup_key

_PREFIX = "izjava"
#: Person tokens that legitimately contain an underscore because the surname is
#: double and predates the hyphen convention. Normalised keys.
LEGACY_DOUBLE_SURNAMES: frozenset[str] = frozenset({
    normalize_lookup_key("SKapidžić_Antolič"),
})


@dataclass(frozen=True)
class Izjava:
    """One statement file on Drive."""

    path: Path
    person: str
    scope: str | None = None  # None → universal

    @property
    def person_key(self) -> str:
        return normalize_lookup_key(self.person)

    @property
    def scope_key(self) -> str | None:
        return normalize_lookup_key(self.scope) if self.scope else None

    @property
    def is_universal(self) -> bool:
        return self.scope is None


def is_izjava_file(path: Path) -> bool:
    """True for a real statement — not a template, a note, or the missing-list."""
    name = path.name
    if name.startswith("!"):
        return False
    return path.stem.casefold().startswith(_PREFIX + "_")


def parse_izjava(path: Path) -> Izjava | None:
    """Split ``Izjava_<Osoba>[_<Opseg>]`` into person and scope."""
    if not is_izjava_file(path):
        return None
    remainder = path.stem[len(_PREFIX) + 1 :]
    if not remainder:
        return None

    person, separator, scope = remainder.partition("_")
    if not separator:
        return Izjava(path=path, person=person)

    # A legacy double surname is a person, not a scope.
    if normalize_lookup_key(remainder) in LEGACY_DOUBLE_SURNAMES:
        return Izjava(path=path, person=remainder.replace("_", "-"))

    return Izjava(path=path, person=person, scope=scope or None)


def covers(izjava: Izjava, *, locality: str | None, object_name: str | None,
           synonyms: tuple[str, ...] = ()) -> bool:
    """Does this statement apply to the cave described by these fields?

    A universal izjava always does. A scoped one applies when its scope names
    the cave's locality, the cave itself, or one of its synonyms — otherwise the
    author needs a fresh statement for this cave.
    """
    if izjava.is_universal:
        return True
    scope = izjava.scope_key
    if not scope:
        return True
    targets = {
        normalize_lookup_key(value)
        for value in (locality, object_name, *synonyms)
        if value
    }
    return scope in targets


__all__ = ["LEGACY_DOUBLE_SURNAMES", "Izjava", "covers", "is_izjava_file", "parse_izjava"]
