"""People — the registry of authors, their aliases, and their izjave.

``registry`` holds the canonical people (data/people/registry.json) and the
alias key map derived from them; ``name_resolver`` produces the comparison
keys a written name goes by; ``statements`` links people to their `Izjava za
katastar` files and feeds the statement gates in ``dossier/gating.py``.
"""

from cave_dossier.people.name_resolver import matches_token, name_keys
from cave_dossier.people.registry import Person, PersonRegistry, RegistryStats
from cave_dossier.people.statements import (
    StatementIndex,
    enrich,
    link_person_statements,
    scan_izjave,
    statements_dir,
)

__all__ = [
    "Person",
    "PersonRegistry",
    "RegistryStats",
    "StatementIndex",
    "enrich",
    "link_person_statements",
    "matches_token",
    "name_keys",
    "scan_izjave",
    "statements_dir",
]
