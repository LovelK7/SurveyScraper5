"""Link people to their `Izjava za katastar` files; feed the statement gates.

Ported and restructured from crospeleo-automation ``services/statement_checker.py``
(docs/PORTING.md). What changed:

* crospeleo matches raw filename stems; here the stems go through
  ``archive/izjave.py`` first, so the **scope** suffix
  (``Izjava_ACiceran_Šverda.pdf`` covers only Šverda caves) survives into the
  linkage and the gate.
* Matching is registry-aware: an izjava token (``LKukuljan``) and an SB
  shorthand (``L.Kukuljan``) and an OSZ full name (``Lovel Kukuljan``) all
  resolve to one registry person, so they link even when no direct
  token-variant match exists.
* The result is per-person (``PersonStatementStatus``), not just per-role file
  buckets — the same 2026-05-27 Konglomeratača lesson (a present photo-author
  izjava must never hide a missing drawing-author one), carried one level
  further.

``link_person_statements`` is pure over the dossier, so gating can fall back to
it for hand-built dossiers that never ran ``enrich``.
"""

from __future__ import annotations

import json
from pathlib import Path

from cave_dossier.archive.izjave import Izjava, covers, parse_izjava
from cave_dossier.core.config import Settings
from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.core.people import is_author_shorthand
from cave_dossier.dossier.model import (
    ArchiveFile,
    CaveDossier,
    FileRole,
    PersonRole,
    PersonStatementStatus,
    Source,
)
from cave_dossier.people.name_resolver import matches_token
from cave_dossier.people.registry import Person, PersonRegistry

#: Same set crospeleo accepts (``known_statement_suffixes``).
KNOWN_STATEMENT_SUFFIXES: tuple[str, ...] = (".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png")

_ROLE_FILE_ROLES: dict[PersonRole, FileRole] = {
    PersonRole.DRAWING_AUTHOR: FileRole.STATEMENT_DRAWING_AUTHOR,
    PersonRole.PHOTO_AUTHOR: FileRole.STATEMENT_PHOTO_AUTHOR,
}


def statements_dir(settings: Settings) -> Path | None:
    """`!!Izjave za katastar RH` on the local Drive mount, or None if unconfigured."""
    relative = settings.archive_dirs.get("statements_dir")
    if not relative or settings.local_drive_root is None:
        return None
    return settings.local_drive_root / relative


def scan_izjave(directory: Path) -> list[Izjava]:
    """Every real statement in the dir — templates, notes and folders skipped."""
    izjave: list[Izjava] = []
    for path in sorted(directory.glob("*"), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in KNOWN_STATEMENT_SUFFIXES:
            continue
        izjava = parse_izjava(path)
        if izjava is not None:
            izjave.append(izjava)
    return izjave


class StatementIndex:
    """The person ↔ izjava linkage over one scan of the statements dir."""

    def __init__(self, izjave: list[Izjava], registry: PersonRegistry | None = None) -> None:
        self.izjave = izjave
        self.registry = registry
        #: izjava → the registry person its token resolves to (None = orphan).
        self.owners: dict[Path, Person | None] = {
            izjava.path: (registry.resolve(izjava.person) if registry else None)
            for izjava in izjave
        }

    def statements_for(self, name: str | None) -> list[Izjava]:
        """Every izjava linked to this person, whatever its scope.

        Registry identity first (SB shorthand ↔ full name ↔ token all land on
        one person), then a direct token-variant match so an author missing
        from the registry still finds their conventionally named file.
        """
        if not name:
            return []
        person = self.registry.resolve(name) if self.registry else None
        candidates = {name}
        if person:
            candidates.add(person.name)
            candidates.update(person.aliases)
        linked: list[Izjava] = []
        for izjava in self.izjave:
            owner = self.owners.get(izjava.path)
            if person is not None and owner is person:
                linked.append(izjava)
            elif any(matches_token(candidate, izjava.person) for candidate in candidates):
                linked.append(izjava)
        return linked

    def orphan_izjave(self) -> list[Izjava]:
        """Statements whose person token resolves to nobody in the registry."""
        if not self.registry:
            return []
        return [izjava for izjava in self.izjave if self.owners.get(izjava.path) is None]

    def missing_statement_people(self) -> list[Person]:
        """Registry people with NO izjava on file — the registry-wide warning."""
        if not self.registry:
            return []
        owned = {person.name for person in self.owners.values() if person is not None}
        return [person for person in self.registry.people if person.name not in owned]


def link_person_statements(
    dossier: CaveDossier,
    izjave: list[Izjava] | None = None,
    registry: PersonRegistry | None = None,
) -> list[PersonStatementStatus]:
    """One ``PersonStatementStatus`` per (person, role) named in the dossier.

    With ``izjave=None`` the statements are re-parsed from
    ``dossier.statement_files`` — the pure fallback gating uses.
    """
    if izjave is None:
        izjave = [
            parsed
            for archive_file in dossier.statement_files
            if (parsed := parse_izjava(archive_file.path)) is not None
        ]
    index = StatementIndex(izjave, registry)

    # SB's author cell mixes survey authors with cave FINDERS (user,
    # 2026-08-30): only the `N.Surname` shorthand marks an author, so only
    # those names carry the izjava requirement. Finders are exempt entirely —
    # no entry, no gate-1 blocker, no gate-2 warning. The other buckets come
    # from the OSZ, where names are full and everyone listed took part.
    drawing_authors = [
        name for name in dossier.drawing_authors if is_author_shorthand(name)
    ]

    buckets: tuple[tuple[PersonRole, list[str]], ...] = (
        (PersonRole.DRAWING_AUTHOR, drawing_authors),
        (PersonRole.PHOTO_AUTHOR, dossier.photo_author_candidates),
        (PersonRole.RECORDER, [dossier.recorder] if dossier.recorder else []),
        (PersonRole.TEAM_MEMBER, dossier.team_members),
    )

    entries: list[PersonStatementStatus] = []
    for role, names in buckets:
        seen: set[str] = set()
        for name in names:
            cleaned = (name or "").strip()
            key = normalize_lookup_key(cleaned)
            if not cleaned or not key or key in seen:
                continue
            seen.add(key)
            person = registry.resolve(cleaned) if registry else None
            linked = index.statements_for(cleaned)
            covering = [
                izjava
                for izjava in linked
                if covers(
                    izjava,
                    locality=dossier.locality,
                    object_name=dossier.object_name,
                    synonyms=tuple(dossier.synonyms),
                )
            ]
            entries.append(
                PersonStatementStatus(
                    name=cleaned,
                    role=role,
                    canonical=person.name if person else None,
                    in_registry=(person is not None) if registry else None,
                    statements=[izjava.path for izjava in linked],
                    covering=[izjava.path for izjava in covering],
                )
            )
    return entries


def enrich(
    dossier: CaveDossier, settings: Settings, registry: PersonRegistry | None = None
) -> bool:
    """Scan the shared izjave dir and fill the dossier's statement linkage.

    Returns False — and leaves ``Source.STATEMENTS`` ungathered, so the
    statement gates honestly report "not checked yet" — when the dir is
    unconfigured or unreachable (Drive not mounted).
    """
    directory = statements_dir(settings)
    if directory is None or not directory.exists():
        return False

    izjave = scan_izjave(directory)
    dossier.person_statements = link_person_statements(dossier, izjave=izjave, registry=registry)

    by_role: dict[FileRole, dict[Path, ArchiveFile]] = {}
    all_files: dict[Path, ArchiveFile] = {}
    for entry in dossier.person_statements:
        file_role = _ROLE_FILE_ROLES.get(entry.role, FileRole.STATEMENT)
        for path in entry.statements:
            archive_file = ArchiveFile(path=path, role=file_role)
            by_role.setdefault(file_role, {})[path] = archive_file
            all_files.setdefault(path, archive_file)

    dossier.drawing_author_statement_files = sorted(
        by_role.get(FileRole.STATEMENT_DRAWING_AUTHOR, {}).values(),
        key=lambda item: item.path.name.lower(),
    )
    dossier.photo_author_statement_files = sorted(
        by_role.get(FileRole.STATEMENT_PHOTO_AUTHOR, {}).values(),
        key=lambda item: item.path.name.lower(),
    )
    dossier.statement_files = sorted(all_files.values(), key=lambda item: item.path.name.lower())
    dossier.mark_gathered(Source.STATEMENTS)
    return True


def write_index_json(index: StatementIndex, path: Path, *, source_dir: Path) -> None:
    """A derived JSON snapshot of the person ↔ izjava linkage.

    Landing under gitignored ``runs/people/`` — the registry stays the curated
    record, this is just the linkage made inspectable (and diffable) per run.
    """
    people = []
    for person in index.registry.people if index.registry else []:
        izjave = [
            {"file": izjava.path.name, "scope": izjava.scope}
            for izjava in index.izjave
            if index.owners.get(izjava.path) is person
        ]
        people.append(
            {
                "name": person.name,
                "society": person.society,
                "izjave": izjave,
                "has_statement": bool(izjave),
            }
        )
    payload = {
        "_note": (
            "Derived person <-> izjava linkage. Regenerate with `cavedossier "
            "people check`; the curated record is data/people/registry.json."
        ),
        "statements_dir": str(source_dir),
        "people": people,
        "orphan_izjave": [izjava.path.name for izjava in index.orphan_izjave()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "KNOWN_STATEMENT_SUFFIXES",
    "StatementIndex",
    "enrich",
    "link_person_statements",
    "scan_izjave",
    "statements_dir",
    "write_index_json",
]
