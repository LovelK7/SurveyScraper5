"""Person abbreviation variants + the SB shorthand convention.

``variants_for`` is ported from crospeleo-automation
``services/person_alias_generator.py`` (docs/PORTING.md) — the pure
"First Last" abbreviation helper; the global collision-detecting registry
generator was NOT ported (per-row candidate sets here are tiny, like
crospeleo's per-dossier mode).

The SB convention (user, 2026-08-30): the OSZ carries full names
("Lovel Kukuljan"), SB writes initial·dot·surname with no space
("L.Kukuljan") — ``to_sb_shorthand`` produces it, ``same_person`` matches
across the two spellings via the variant keys.
"""

from __future__ import annotations

from cave_dossier.core.normalization import normalize_lookup_key

# Abbreviation templates for "First Last" canonical names.  Indexed by
# ``first``, ``last``, ``f0`` (first initial), ``l0`` (last initial).
# `_CORE_TEMPLATES` are conservative: each fixes BOTH a first-name token
# and a surname token, so collisions are limited to true initial-clashes
# ("LK" = Lovel Kukuljan vs Luka Kovač).
# `_SINGLETON_TEMPLATES` (surname-only / first-name-only) collide easily
# across a large registry but resolve cleanly within one row's author list.
_CORE_TEMPLATES: tuple[str, ...] = (
    "{f0}.{last}",      # L.Kukuljan — the SB convention, kept FIRST
    "{f0}. {last}",
    "{f0} {last}",
    "{first} {l0}.",
    "{f0}.{l0}.",
    "{f0}{l0}",
)
_SINGLETON_TEMPLATES: tuple[str, ...] = (
    "{last}",
    "{first}",
)


def variants_for(canonical: str, *, include_singletons: bool = False) -> list[str]:
    """Abbreviation variants of a "First Last" canonical name.

    Returns ``[]`` for single-token, 3+ token, or too-short names —
    exactly as in crospeleo (the runtime helper handles two-token forms).
    """
    parts = canonical.strip().split()
    if len(parts) != 2:
        return []
    first, last = parts
    if len(first) < 2 or len(last) < 2:
        return []
    f0, l0 = first[0], last[0]
    templates = _CORE_TEMPLATES + (_SINGLETON_TEMPLATES if include_singletons else ())
    return [t.format(first=first, last=last, f0=f0, l0=l0) for t in templates]


def to_sb_shorthand(name: str) -> str:
    """The SB spelling of a person: "Lovel Kukuljan" → "L.Kukuljan".

    A name that is not a plain two-token "First Last" (already shorthand,
    a single token, a double first name) is returned unchanged — better an
    honest passthrough than a mangled guess.
    """
    variants = variants_for(name)
    return variants[0] if variants else name.strip()


def same_person(a: str, b: str) -> bool:
    """True when the two spellings plausibly name the same person.

    Direct key equality first ("L.Kukuljan" vs "L. Kukuljan"), then either
    side's variant keys against the other's key — which is what matches the
    OSZ's "Lovel Kukuljan" to SB's "L.Kukuljan".
    """
    key_a, key_b = normalize_lookup_key(a), normalize_lookup_key(b)
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    variants_a = {normalize_lookup_key(v) for v in variants_for(a)}
    variants_b = {normalize_lookup_key(v) for v in variants_for(b)}
    return key_b in variants_a or key_a in variants_b
