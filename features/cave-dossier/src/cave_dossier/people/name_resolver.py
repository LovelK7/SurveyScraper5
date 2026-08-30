"""Person-name comparison keys across SB, the OSZ and izjava filenames.

Ported from crospeleo-automation ``services/name_resolver.py`` (docs/PORTING.md).
The class wrapper was dropped (it carried no state); the substance is verbatim.

This is the *matcher's* view of a name, complementary to
``core/person_aliases.variants_for``:

* ``variants_for`` generates spellings **of** a canonical two-token
  "First Last" name — the registry uses it to derive aliases.
* ``name_keys`` here produces comparison keys **for a name as written
  anywhere** — full, SB shorthand, 3+ tokens, hyphenated double surname —
  and is what links an izjava's person token to an author entry.

The diacritic fold has its own override map because NFKD does not decompose
``đ``/``Đ`` (unlike ``č ć š ž``, which lose their combining mark on the filter
below). Names use diacritics consistently across SB, OSZ and filenames
(operator-confirmed in crospeleo, 2026-05-27), so the fold is a safety net for
single-side stripping, not a convention change.
"""

from __future__ import annotations

import unicodedata

_DIACRITIC_OVERRIDES = {"đ": "d", "Đ": "d"}


def _fold_diacritics(value: str) -> str:
    overridden = "".join(_DIACRITIC_OVERRIDES.get(char, char) for char in value)
    decomposed = unicodedata.normalize("NFKD", overridden)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize(value: str) -> str:
    """Lowercase alphanumeric key with Croatian diacritics folded (incl. đ)."""
    folded = _fold_diacritics(value)
    return "".join(char.lower() for char in folded if char.isalnum())


def _cleanup(value: str) -> str:
    """Filename separators become spaces so tokens split like written names."""
    return value.replace("_", " ").replace("-", " ").replace(".", " ").strip()


def name_keys(raw_name: str | None) -> set[str]:
    """Every comparison key a name as written can go by.

    For ``"Lovel Kukuljan"``: the compact form (``lovelkukuljan``), the surname
    alone (``kukuljan``), initials+surname (``lkukuljan``) and the last two
    tokens joined. Unlike ``variants_for`` this handles 3+ token names —
    initials come from every token but the last — which is what matches
    legacy surname-first citation forms.

    Keys are derived over TWO tokenizations (a departure from the crospeleo
    original, which only splits): the hyphen as a separator AND the hyphen as
    a name joiner. The izjava filename convention makes the hyphen load-bearing
    — ``Izjava_SKapidžić-Antolič`` is initial + ONE double surname — so
    ``"Sanja Kapidžić-Antolič"`` must derive ``skapidzicantolic``, which only
    the joined tokenization produces.
    """
    if not raw_name:
        return set()

    cleaned = _cleanup(raw_name)
    hyphens_kept = raw_name.replace("_", " ").replace(".", " ").strip()
    keys: set[str] = set()
    for candidate in {cleaned, hyphens_kept}:
        if candidate:
            keys.update(_keys_for(candidate))
    return keys


def _keys_for(cleaned: str) -> set[str]:
    parts = [part for part in cleaned.split() if part]
    keys = {normalize(cleaned)}

    if parts:
        keys.add(normalize(parts[-1]))  # surname alone

        initials = "".join(part[0] for part in parts[:-1] if part)
        if initials:
            keys.add(normalize(f"{initials}{parts[-1]}"))
            keys.add(normalize(f"{initials} {parts[-1]}"))

        if len(parts) >= 2:
            keys.add(normalize("".join(parts[-2:])))

    return {key for key in keys if key}


def matches_token(raw_name: str | None, person_token: str) -> bool:
    """Does an izjava's person token (``ABahović``) name this person?

    The token comes out of ``archive.izjave.parse_izjava`` — scope already
    stripped — so unlike the crospeleo original there is no ``Izjava`` prefix
    left to peel here.
    """
    target = normalize(_cleanup(person_token))
    if not target:
        return False
    return target in name_keys(raw_name)


__all__ = ["matches_token", "name_keys", "normalize"]
