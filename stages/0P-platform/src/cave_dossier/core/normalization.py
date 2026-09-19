"""Text normalization helpers (ported verbatim from crospeleo-automation).

`normalize_lookup_key` is the diacritic-insensitive comparison key used
everywhere Croatian text is matched (column headers, cave names, author names):
NFKD-decompose, drop combining marks, keep lowercase alphanumerics only.
"""

from __future__ import annotations

import re
import unicodedata


def cleanup_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
    return cleaned or None


def split_semicolon_values(value: str | None) -> list[str]:
    cleaned = cleanup_whitespace(value)
    if not cleaned:
        return []
    normalized = cleaned.replace("|", ";")
    return [part.strip() for part in normalized.split(";") if part.strip()]


def parse_optional_float(value: str | None) -> float | None:
    cleaned = cleanup_whitespace(value)
    if not cleaned:
        return None
    match = re.search(r"-?\d+(?:[.,]\d+)?", cleaned)
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def normalize_lookup_key(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value)
    without_diacritics = "".join(char for char in ascii_value if not unicodedata.combining(char))
    return "".join(char.lower() for char in without_diacritics if char.isalnum())
