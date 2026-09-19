"""Field-data intake — the folders under `!!!Digitalizacija/!Za digitalizirat`.

Each **leaf** folder there holds one cave's raw material (survey files, photos,
notes). They are named by whoever collected the data, so they carry a cave name,
a surveyor's first name, a local id, or some mix — `Sik Šits_Sara`,
`108_Renata`, `Logor`, `79_89_Jamorinke_Fero`. The plan (user, 2026-08-28) is to
prefix each leaf with its **Redni broj**, making the folder the cave's pre-SUE
working identity.

Two things make this different from the staged-photo scan:

**Numbers here are a suggestion, never evidence.** The user's account (2026-08-29)
is that they are old *Za istražit* numbers, kept in SB's Napomena as
``za istražit, NNN, …`` — and `old_queue_candidates` looks them up on exactly
that. But the numbering collides across campaigns, and checking 20 folder
numbers against the live workbook resolved only 5, every one of them pointing at
a Šverda cave while the folder sat in a Veprinac LIDAR group. So a number is
surfaced for a human to accept, and never turned into a rename by itself; a
folder with nothing but a number stays unresolved, which is the honest answer.

**Nothing is stripped.** The local id is information the user still needs, so a
proposal only ever prepends: `SB_<Redni broj>_<Ime objekta>_<original name>`.
Inserting the cave name is also what keeps a second run idempotent, since the
name is then the signal that matches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import ClassVar

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import SB_PREFIX, CaveCandidate, PathMatch, match_paths
from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.intake import liburnija

#: Files Windows or Drive leave behind; never cave data.
_SYSTEM_FILENAMES = {"desktop.ini", "thumbs.db", ".ds_store"}


class IntakeMatch(PathMatch):
    """A leaf intake folder resolved to a cave."""

    #: Row number in the Liburnija LIDAR sheet, when that is what linked it.
    sheet_number: str | None = None

    #: A folder, so a dot in the name is part of the name ("M.Dol Pećina").
    has_extension: ClassVar[bool] = False

    #: Confirmed to hold data for a cave that is not in SB yet. Set from
    #: `intake.new_entries`; overrides any automatic match, because a new cave
    #: often resembles an existing name (`Božur_Frustuck` is NOT *Božur* 1087).
    is_new_entry: bool = False  # per-instance, set by match_leaves

    #: The cave the matcher HAD resolved before an `intake.new_entries` line
    #: discarded it. SB only grows, so such a line is a point-in-time
    #: observation that goes stale the moment someone enters the row: on
    #: 2026-09-19 nine of them were suppressing exact-name hits on rows
    #: 1440–1456, entered weeks after the list was written, and the run said
    #: "confirmed absent from SB" every time. Keeping the discarded match is
    #: what lets `stale_override` report the contradiction instead of erasing
    #: it. Neither side wins automatically — see the property.
    overridden: CaveCandidate | None = None
    overridden_evidence: str | None = None

    #: More than one cave in one folder (`vrazji prolaz 2kom` is VP1 + VP2).
    #: A leaf is one cave's working identity, so this can never be prefixed;
    #: it is reported with both target names for a human to split by hand.
    split_into: tuple[CaveCandidate, ...] = ()

    @property
    def stale_override(self) -> bool:
        """`intake.new_entries` says "not in SB", but a row now matches.

        Reported, never resolved automatically. Trusting the matcher would
        mis-number a genuinely new cave whose name resembles an existing one
        (the `Božur_Frustuck` case the list exists for); trusting the config
        is what produced the 2026-09-19 failure. Disagreeing evidence proposes
        nothing and goes to a human — the same rule as `confidence="conflict"`.
        """
        return self.is_new_entry and self.overridden is not None

    @property
    def proposed_name(self) -> str | None:
        """``SB_<Redni broj>_<Ime objekta>_<original folder name>``.

        Unlike the photo path, a foreign leading number is never stripped: in
        these folders it is a LIDAR point or an expedition sequence the user
        still needs, not a stale SB id. (The cave's OWN previous prefix does
        come off — that is what upgrades a pre-2026-08-30 ``<broj>_…`` rename
        to the ``SB_``-marked form instead of stacking the number twice.)
        """
        if self.split_into:
            return None
        if self.is_new_entry or self.cave is None or self.cave.serial_number is None:
            return None
        if self.confidence == "conflict" or self.already_correct:
            return None
        return f"{SB_PREFIX}{self.cave.serial_number}_{self.rest(strip_stale=False)}"


@dataclass
class LeafFolder:
    """One intake folder that holds cave data rather than more folders."""

    path: Path
    relative: Path       # relative to the intake root, for display
    file_count: int
    #: Ruled out by `intake.ignore_folders` — not a cave's folder at all.
    #: Still discovered, so the run can say what it skipped.
    ignored: bool = False

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


def find_cave_leaf(root: Path, serial: int) -> Path | None:
    """The cave's existing ``SB_<Redni broj>_…`` folder anywhere under ``root``.

    The leaf is the cave's pre-SUE working identity, so every per-cave step
    (OSZ prefill/fetch, photo processing) resolves it the same way: the
    serial is matched padded or not, since the folders are unpadded while
    the files delivered into them pad to four digits.
    """
    pattern = re.compile(rf"^SB_0*{serial}(_|$)", re.IGNORECASE)
    if not root.is_dir():
        return None
    for candidate in sorted(root.rglob("SB_*")):
        if candidate.is_dir() and pattern.match(candidate.name):
            return candidate
    return None


def is_ignored(relative: Path, ignore_names: list[str] | None) -> bool:
    """A leaf that is not a cave's folder at all.

    `primjeri` in the Veprinac expedition group is sample material, not a cave
    (user, 2026-09-19). Nothing about the folder says so, so left alone it sits
    in the report forever as a cave whose SB row nobody can find — noise in the
    one list that is supposed to be a to-do.

    fnmatch patterns, like `photos.ignore_filenames`. A pattern containing a
    separator is matched against the path relative to the intake root instead
    of the bare name, so one group's `primjeri` can be ruled out without ruling
    out every folder of that name.
    """
    name = relative.name.casefold()
    path = relative.as_posix().casefold()
    for pattern in ignore_names or ():
        folded = pattern.casefold().replace("\\", "/")
        target = path if "/" in folded else name
        if fnmatch(target, folded):
            return True
    return False


def find_leaf_folders(
    root: Path, ignore_names: list[str] | None = None
) -> list[LeafFolder]:
    """Every folder under ``root`` that contains no further folders.

    Depth is not assumed: today the tree is 1–3 levels deep (`Tin/Tingen-BP/Penj`),
    and a leaf can sit at any of them.

    Folders ruled out by ``ignore_names`` are returned FLAGGED, not dropped:
    the caller decides, and the run reports what it skipped.
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
        relative = path.relative_to(root)
        leaves.append(
            LeafFolder(
                path=path,
                relative=relative,
                file_count=len(files),
                ignored=is_ignored(relative, ignore_names),
            )
        )
    return leaves


def match_leaves(
    leaves: list[LeafFolder],
    candidates: list[CaveCandidate],
    manual: dict[str, int] | None = None,
    new_entries: list[str] | None = None,
    sheet_rows: dict[str, object] | None = None,
    split_folders: dict[str, list[int]] | None = None,
) -> list[IntakeMatch]:
    """Resolve leaf folders to SB rows. Leading numbers are NOT used — see above."""
    matches: list[IntakeMatch] = match_paths(  # type: ignore[assignment]
        [leaf.path for leaf in leaves],
        candidates,
        manual,
        use_numbers=False,
        match_class=IntakeMatch,
    )
    # The Liburnija sheet resolves what the names cannot: a folder named after
    # a sheet row number reaches SB through that row's plaque number.
    if sheet_rows:
        for match in matches:
            if match.cave is not None:
                continue
            for token in sheet_number_tokens(match.path.name):
                resolved = liburnija.resolve(token, sheet_rows, candidates)  # type: ignore[arg-type]
                if resolved and resolved[1] is not None:
                    row, cave = resolved
                    match.cave = cave
                    match.confidence = "high"
                    match.evidence = (
                        f"Liburnija list br. {row.number} -> pločica {row.plaque}"
                    )
                    match.sheet_number = row.number
                    break

    fragments = [fragment.casefold() for fragment in (new_entries or [])]
    for match in matches:
        if any(fragment in match.path.name.casefold() for fragment in fragments):
            match.is_new_entry = True
            # The match is set aside, not destroyed: a `new_entries` line that
            # now contradicts a live SB row is a finding, not a silent veto.
            match.overridden = match.cave
            match.overridden_evidence = match.evidence
            match.cave = None
            match.evidence = "potvrđeno: nema retka u SB"
            match.confidence = "new"

    by_serial = {c.serial_number: c for c in candidates if c.serial_number is not None}
    for fragment, serials in (split_folders or {}).items():
        for match in matches:
            if fragment.casefold() not in match.path.name.casefold():
                continue
            resolved = tuple(c for c in (by_serial.get(s) for s in serials) if c is not None)
            if not resolved:
                continue
            match.split_into = resolved
            match.cave = None
            match.is_new_entry = False
            match.confidence = "split"
            match.evidence = "više objekata u jednoj mapi"
    return matches


def sheet_number_tokens(name: str) -> list[str]:
    """Digit runs in a folder name that could be a Liburnija sheet row number.

    A number only counts when it stands on its own — at the start, after a
    separator, or after a lone LIDAR marker letter (`lisina L366`). Two digits
    minimum. Without this, `Mune_Nat4_Natalija` would offer up the "4" inside
    "Nat4" and match sheet row 4, which is *Integral* in an entirely different
    place — a false positive found on the first live run.
    """
    tokens: list[str] = []
    for hit in re.finditer(r"\d{2,4}(?!\d)", name):
        start = hit.start()
        before = name[start - 1] if start else ""
        if start == 0 or before in " _-.(/" or before in "Ll":
            tokens.append(hit.group())
    return tokens


def old_queue_candidates(
    name: str, candidates: list[CaveCandidate]
) -> list[tuple[str, CaveCandidate]]:
    """Caves whose old Za-istražit broj appears as a number in this folder name.

    Reported as a **suggestion only**, never as evidence. The numbering is scoped
    per campaign and collides across them: `43_Jasna` sits in a Veprinac LIDAR
    group, while old broj 43 is *Jama na 25000 2* in Šverda. Verified against the
    live workbook 2026-08-29 — of 20 folder numbers checked, 5 resolved and all 5
    pointed at the wrong locality. A human decides.
    """
    by_old = {c.old_queue_number: c for c in candidates if c.old_queue_number}
    hits: list[tuple[str, CaveCandidate]] = []
    seen: set[int] = set()
    for token in re.findall(r"\d{1,4}", name):
        cave = by_old.get(token.lstrip("0") or token)
        if cave and id(cave) not in seen:
            seen.add(id(cave))
            hits.append((token, cave))
    return hits


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
    "is_ignored",
    "match_leaves",
    "old_queue_candidates",
    "sheet_number_tokens",
    "suggest",
]
