"""Field-data intake — the folders under `!!!Digitalizacija/!Za digitalizirat`.

Each **leaf** folder there holds one cave's raw material (survey files, photos,
notes). They are named by whoever collected the data, so they carry a cave name,
a surveyor's first name, a local id, or some mix — `Sik Šits_Sara`,
`108_Renata`, `Logor`, `79_89_Jamorinke_Fero`. The plan (user, 2026-08-28) is to
prefix each leaf with its **Redni broj**, making the folder the cave's pre-SUE
working identity.

Two things make this different from the staged-photo scan:

**Leading numbers are not SB numbers here.** `!!Lidarke Veprinac/43_Jasna` and
`Venio/Jasnina jam lidar 43` are the same object under LIDAR point 43; the
Veprinac expedition folders (`108_Renata`, `295_Dino`, `Kraj 309_Sara`) use
their own sequence. Reading those as Redni broj would produce confident
nonsense, so the number signal is switched off — an unmatched folder is the
honest answer, and the user maps it by hand.

**Nothing is stripped.** The local id is information the user still needs, so a
proposal only ever prepends: `<Redni broj>_<Ime objekta>_<original name>`.
Inserting the cave name is also what keeps a second run idempotent, since the
name is then the signal that matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import CaveCandidate, PathMatch, match_paths
from cave_dossier.core.normalization import normalize_lookup_key

#: Files Windows or Drive leave behind; never cave data.
_SYSTEM_FILENAMES = {"desktop.ini", "thumbs.db", ".ds_store"}


class IntakeMatch(PathMatch):
    """A leaf intake folder resolved to a cave."""

    @property
    def proposed_name(self) -> str | None:
        """``<Redni broj>_<Ime objekta>_<original folder name>``.

        Unlike the photo path, a leading number is never stripped: in these
        folders it is a LIDAR point or an expedition sequence the user still
        needs, not a stale SB id.
        """
        if self.cave is None or self.cave.serial_number is None:
            return None
        if self.confidence == "conflict" or self.already_correct:
            return None
        return f"{self.cave.serial_number}_{self.rest(strip_stale=False)}"


@dataclass
class LeafFolder:
    """One intake folder that holds cave data rather than more folders."""

    path: Path
    relative: Path       # relative to the intake root, for display
    file_count: int

    @property
    def group(self) -> str:
        """The container it sits in (`!!Mune`), or "" for a top-level leaf."""
        parent = self.relative.parent
        return "" if str(parent) == "." else str(parent)


def intake_root(settings: Settings) -> Path | None:
    """The field-data intake dir, resolved against LOCAL_DRIVE_ROOT."""
    relative = settings.archive_dirs.get("intake_dir")
    if not relative or settings.local_drive_root is None:
        return None
    return settings.local_drive_root / relative


def find_leaf_folders(root: Path) -> list[LeafFolder]:
    """Every folder under ``root`` that contains no further folders.

    Depth is not assumed: today the tree is 1–3 levels deep (`Tin/Tingen-BP/Penj`),
    and a leaf can sit at any of them.
    """
    if not root.is_dir():
        return []
    leaves: list[LeafFolder] = []
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_dir():
            continue
        if any(child.is_dir() for child in path.iterdir()):
            continue
        files = [
            child
            for child in path.iterdir()
            if child.is_file() and child.name.lower() not in _SYSTEM_FILENAMES
        ]
        leaves.append(
            LeafFolder(path=path, relative=path.relative_to(root), file_count=len(files))
        )
    return leaves


def match_leaves(
    leaves: list[LeafFolder],
    candidates: list[CaveCandidate],
    manual: dict[str, int] | None = None,
) -> list[IntakeMatch]:
    """Resolve leaf folders to SB rows. Leading numbers are NOT used — see above."""
    return match_paths(
        [leaf.path for leaf in leaves],
        candidates,
        manual,
        use_numbers=False,
        match_class=IntakeMatch,
    )


def suggest(name: str, candidates: list[CaveCandidate], limit: int = 3) -> list[tuple[CaveCandidate, float]]:
    """Closest SB rows to a folder name, for the ones nothing resolved.

    Deliberately separate from matching: these are prompts for a human, never
    evidence. A low top score is itself informative — it usually means the cave
    was never entered into SB, which is the most common reason a folder here
    cannot be mapped.
    """
    from difflib import SequenceMatcher

    key = normalize_lookup_key(name)
    if not key:
        return []
    scored: list[tuple[CaveCandidate, float]] = []
    for cave in candidates:
        best = max(
            (SequenceMatcher(None, key, candidate_key).ratio() for candidate_key in cave.all_keys),
            default=0.0,
        )
        scored.append((cave, best))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


__all__ = [
    "IntakeMatch",
    "LeafFolder",
    "find_leaf_folders",
    "intake_root",
    "match_leaves",
    "suggest",
]
