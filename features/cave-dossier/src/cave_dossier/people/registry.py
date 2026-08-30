"""The people registry — canonical authors + curated aliases, one JSON file.

Design ported from crospeleo-automation's registry stack (docs/PORTING.md):
over there a scraped mirror holds one canonical name per person, abbreviation
aliases are **derived at load time** with two-pass collision detection
(``person_alias_generator.generate_person_aliases``), and a small curated file
holds only the overrides the derivation cannot settle — curated wins on key
conflicts. Here the mirror and the curated file collapse into ONE committed
JSON (`data/people/registry.json`): this society's people are curated by hand,
not scraped.

Registry entry shapes (both accepted, crospeleo-tolerant)::

    "Lovel Kukuljan"
    {"name": "Lovel Kukuljan", "aliases": ["..."], "society": "SUE", "note": "..."}

* ``name`` in full "First Last" form unlocks the derived variants
  (``L.Kukuljan``, ``LKukuljan``, ``Lovel K.`` …) via
  ``core/person_aliases.variants_for`` plus the izjava-token keys via
  ``people/name_resolver.name_keys``.
* ``name`` still in izjava-token form (``ABahović`` — full first name not yet
  known) matches the izjava file and SB's ``A.Bahović`` shorthand, just not an
  OSZ's full spelling. Upgrade entries to full names as they are learned.
* Surname-only / first-name-only keys are **never** derived globally — across
  ~120 people they collide too easily (crospeleo's rule; per-row author lists
  are where singletons are safe, and ``core/person_aliases.same_person``
  already covers that).
* A derived key claimed by two people is dropped for both and recorded in
  ``stats.collisions`` — resolution must stay deterministic. A curated alias
  wins over any derived key; two curated claims on the same key drop both.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.core.person_aliases import variants_for
from cave_dossier.people import name_resolver

# "A.Lipovac (SOV)" — the trailing bracket is an affiliation flag, not a name
# part; stripping it and retrying is what let crospeleo match object 542's
# "M.Rakovac (SOV)" cell.
_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


@dataclass(frozen=True)
class Person:
    """One registry entry. ``society=None`` means the society's own member.

    ``deceased=True`` exempts the person from the izjava requirement entirely
    (user, 2026-08-30): no gate blocker, no warning, never listed as missing
    a statement — a statement cannot be obtained.
    """

    name: str
    aliases: tuple[str, ...] = ()
    society: str | None = None
    note: str | None = None
    deceased: bool = False

    @property
    def key(self) -> str:
        return normalize_lookup_key(self.name)


@dataclass(frozen=True)
class RegistryStats:
    """What alias derivation did — printed by ``cavedossier people list``."""

    people_total: int = 0
    keys_derived: int = 0
    keys_curated: int = 0
    collisions: tuple[str, ...] = ()  # normalized keys dropped as ambiguous


@dataclass
class PersonRegistry:
    """Canonical people + the alias key map derived from them."""

    people: list[Person] = field(default_factory=list)
    key_map: dict[str, Person] = field(default_factory=dict)
    stats: RegistryStats = field(default_factory=RegistryStats)
    path: Path | None = None

    # ── Construction ──────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> PersonRegistry:
        """Read the JSON registry; a missing file is an EMPTY registry.

        Empty is a working state, not an error: every resolution then answers
        ``None`` and the gate-2 warnings say who to add.
        """
        if not path.exists():
            registry = cls.from_people([])
            registry.path = path
            return registry
        raw = json.loads(path.read_text(encoding="utf-8"))
        people: list[Person] = []
        for entry in raw.get("people", []):
            if isinstance(entry, str):
                people.append(Person(name=entry))
            elif isinstance(entry, dict) and entry.get("name"):
                people.append(
                    Person(
                        name=str(entry["name"]),
                        aliases=tuple(str(a) for a in entry.get("aliases", []) if a),
                        society=entry.get("society") or None,
                        note=entry.get("note") or None,
                        deceased=bool(entry.get("deceased", False)),
                    )
                )
        registry = cls.from_people(people)
        registry.path = path
        return registry

    @classmethod
    def from_people(cls, people: list[Person]) -> PersonRegistry:
        derived: dict[str, list[Person]] = {}
        for person in people:
            for key in _derived_keys(person.name):
                derived.setdefault(key, []).append(person)

        key_map: dict[str, Person] = {}
        collisions: list[str] = []
        for key, claimants in derived.items():
            if len(claimants) == 1:
                key_map[key] = claimants[0]
            else:
                collisions.append(key)
        keys_derived = len(key_map)

        curated: dict[str, list[Person]] = {}
        for person in people:
            for alias in person.aliases:
                key = normalize_lookup_key(alias)
                if key:
                    curated.setdefault(key, []).append(person)
        keys_curated = 0
        for key, claimants in curated.items():
            if len({claimant.name for claimant in claimants}) == 1:
                key_map[key] = claimants[0]  # curated wins over derived
                keys_curated += 1
            else:
                key_map.pop(key, None)
                collisions.append(key)

        return cls(
            people=list(people),
            key_map=key_map,
            stats=RegistryStats(
                people_total=len(people),
                keys_derived=keys_derived,
                keys_curated=keys_curated,
                collisions=tuple(sorted(set(collisions))),
            ),
        )

    # ── Resolution ────────────────────────────────────────────────────

    def resolve(self, raw: str | None) -> Person | None:
        """The person a written name refers to, or ``None``.

        Deterministic key lookup only — no substring, no fuzzy: crospeleo's own
        guards show how dangerous those are for two-letter forms, and a society
        registry this size does not need them. One defensive retry strips a
        trailing affiliation bracket.
        """
        if not raw:
            return None
        key = normalize_lookup_key(raw)
        if key and key in self.key_map:
            return self.key_map[key]
        stripped = _TRAILING_PAREN_RE.sub("", raw).strip()
        if stripped and stripped != raw:
            key = normalize_lookup_key(stripped)
            if key and key in self.key_map:
                return self.key_map[key]
        return None

    def resolve_name(self, raw: str | None) -> str | None:
        person = self.resolve(raw)
        return person.name if person else None

    def __len__(self) -> int:
        return len(self.people)

    def __bool__(self) -> bool:
        """An empty registry is falsy so callers can treat it as "no registry"."""
        return bool(self.people)


def _derived_keys(name: str) -> set[str]:
    """Every key a canonical name derives — canonical + variants, no singletons."""
    keys = {normalize_lookup_key(name)}
    keys.update(normalize_lookup_key(variant) for variant in variants_for(name))
    parts = [part for part in name.replace(".", " ").split() if part]
    if len(parts) >= 2:
        singletons = {name_resolver.normalize(parts[-1]), name_resolver.normalize(parts[0])}
        keys.update(name_resolver.name_keys(name) - singletons)
    return {key for key in keys if key}


__all__ = ["Person", "PersonRegistry", "RegistryStats"]
