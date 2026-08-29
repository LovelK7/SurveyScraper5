"""Selector registry for the georef.hr DOM — ported verbatim from
crospeleo-automation ``georef/selectors.py`` (see docs/PORTING.md)."""

from __future__ import annotations

from pathlib import Path

from cave_dossier.core.normalization import cleanup_whitespace


def load_selectors(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    selectors: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        # Strip an inline `# comment` from the value, but only when the
        # `#` lives OUTSIDE quoted scope.  CSS selectors legitimately
        # contain `#` (id selectors), so naive stripping would mangle
        # them — track quote state and only break on a `#` that is not
        # inside `"` / `'`.
        cleaned_value = _strip_inline_yaml_comment(value)
        cleaned = cleanup_whitespace(cleaned_value.strip().strip("'").strip('"'))
        if cleaned:
            selectors[key.strip()] = cleaned
    return selectors


def _strip_inline_yaml_comment(value: str) -> str:
    """Return `value` with any trailing `<whitespace># comment` removed.

    Honours quoted scope: a `#` inside matching `'...'` or `"..."` is
    treated as a literal character (so CSS id selectors like `#header`
    inside a quoted value are preserved).  A `#` outside quotes that is
    preceded by whitespace ends the value.
    """
    in_single = False
    in_double = False
    prev_was_space = True  # start-of-string acts like whitespace
    for index, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single
            prev_was_space = False
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            prev_was_space = False
            continue
        if ch == "#" and not in_single and not in_double and prev_was_space:
            return value[:index]
        prev_was_space = ch.isspace()
    return value


class SelectorRegistry:
    def __init__(self, selectors: dict[str, str]) -> None:
        self._selectors = selectors

    def require(self, key: str) -> str:
        selector = self._selectors.get(key)
        if not selector:
            raise ValueError(f"Required Georef selector missing: {key}")
        return selector

    def optional(self, key: str) -> str | None:
        return self._selectors.get(key)
