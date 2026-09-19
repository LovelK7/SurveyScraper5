"""Diacritic-folded fuzzy toponym matching.

Ported verbatim from crospeleo-automation ``locality/toponym_matcher.py``
(see docs/PORTING.md) — including the hard-won distinction between
"rapidfuzz absent" and "rapidfuzz rejected the candidate" documented on
``fuzzy_best_match``.
"""

from __future__ import annotations

import difflib
import re
import unicodedata


def normalize_for_matching(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace — keeps spaces."""
    nfkd = unicodedata.normalize("NFKD", text)
    without_diacritics = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    lowercased = without_diacritics.lower()
    return re.sub(r"\s+", " ", lowercased).strip()


def fuzzy_best_match(
    query: str,
    candidates: list[str],
    score_cutoff: float = 60.0,
) -> tuple[str, float] | None:
    """
    Return (best_candidate, score_0_to_100) or None if no candidate clears score_cutoff.

    Uses rapidfuzz.fuzz.token_sort_ratio when rapidfuzz is installed,
    falls back to difflib.SequenceMatcher (scaled to 0–100) only when
    rapidfuzz is unavailable.  Both paths normalise via
    ``normalize_for_matching`` before comparison.

    The two scorers are *not* equivalent — token_sort_ratio operates on
    sorted tokens, difflib's SequenceMatcher.ratio() is character-based.
    For e.g. ``"Nina Grozić"`` vs ``"Dino Grozić"`` token_sort_ratio
    returns 55 (below the usual 80 cutoff) while the character-based
    ratio returns 82 (above).  Earlier (in crospeleo-automation) the
    difflib path doubled as a second-chance fallback when rapidfuzz
    reported "no match", which silently re-accepted candidates rapidfuzz
    had correctly rejected — causing the registry to map ``"Nina Grozić"``
    onto ``"Dino Grozić"`` in object 527 (Bunker iznad Trinajstići 1,
    2026-05-24).  The fix distinguishes ``ImportError`` (rapidfuzz absent
    → use difflib) from ``score < cutoff`` (rapidfuzz present, candidate
    truly rejected → return None).
    """
    if not query or not candidates:
        return None

    query_norm = normalize_for_matching(query)
    candidates_norm = [normalize_for_matching(c) for c in candidates]

    try:
        result = _rapidfuzz_match(query_norm, candidates_norm, score_cutoff)
    except ImportError:
        result = _difflib_match(query_norm, candidates_norm, score_cutoff)

    if result is None:
        return None

    idx, score = result
    return candidates[idx], score


def _rapidfuzz_match(
    query_norm: str,
    candidates_norm: list[str],
    score_cutoff: float,
) -> tuple[int, float] | None:
    """Best match via rapidfuzz token_sort_ratio; raises ImportError if absent."""
    from rapidfuzz import fuzz, process  # type: ignore[import-untyped]

    result = process.extractOne(
        query_norm,
        candidates_norm,
        scorer=fuzz.token_sort_ratio,
        score_cutoff=score_cutoff,
    )
    if result is None:
        return None
    _match, score, idx = result
    return idx, float(score)


def _difflib_match(
    query_norm: str,
    candidates_norm: list[str],
    score_cutoff: float,
) -> tuple[int, float] | None:
    best_idx: int | None = None
    best_score = -1.0

    for idx, candidate in enumerate(candidates_norm):
        ratio = difflib.SequenceMatcher(None, query_norm, candidate).ratio()
        score = ratio * 100.0
        if score > best_score:
            best_score = score
            best_idx = idx

    if best_idx is None or best_score < score_cutoff:
        return None
    return best_idx, best_score
