"""Prefilled "Položaj i pristup objektu" texts (config/pristupi.yaml).

Quick-fix rule engine (user, 2026-08-30): caves around one trailhead share
the approach road up to the last few turns, so the shared part is prefilled
and the recorder continues it. A rule matches on the RESOLVED (Najbliže
mjesto, Lokalitet) pair — diacritic/case-folded, and Lokalitet matches any
of its comma/semicolon-separated tokens. The geographic successor (cluster
the archive's approach texts by entrance coordinates) is a backlog idea.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from cave_dossier.core.config import FEATURE_ROOT
from cave_dossier.core.normalization import normalize_lookup_key

PRISTUPI_PATH = FEATURE_ROOT / "config" / "pristupi.yaml"

_TOKEN_SPLIT_RE = re.compile(r"[,;/]+")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PristupRule:
    najblize_mjesto: str
    lokalitet: str
    text: str


def load_rules(path: Path | None = None) -> list[PristupRule]:
    """Rules from the YAML; [] (never raises) when absent or malformed."""
    path = path or PRISTUPI_PATH
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as exc:
        logger.warning("pristupi.yaml unreadable: %s", exc)
        return []
    rules: list[PristupRule] = []
    for entry in raw:
        match = (entry or {}).get("match") or {}
        text = (entry or {}).get("text")
        najblize = match.get("najblize_mjesto")
        lokalitet = match.get("lokalitet")
        if najblize and lokalitet and text:
            rules.append(PristupRule(
                najblize_mjesto=str(najblize),
                lokalitet=str(lokalitet),
                text=str(text).strip(),
            ))
    return rules


def find_pristup(
    najblize_mjesto: str | None,
    lokalitet: str | None,
    path: Path | None = None,
) -> str | None:
    """The first rule's text whose pair matches, or None."""
    if not najblize_mjesto or not lokalitet:
        return None
    najblize_key = normalize_lookup_key(najblize_mjesto)
    lokalitet_keys = {
        normalize_lookup_key(token)
        for token in _TOKEN_SPLIT_RE.split(lokalitet)
        if token.strip()
    }
    for rule in load_rules(path):
        if (normalize_lookup_key(rule.najblize_mjesto) == najblize_key
                and normalize_lookup_key(rule.lokalitet) in lokalitet_keys):
            return rule.text
    return None
