"""Part 2.1d — the staged entrance photos in `!!Fotografije ulaza za istražit`.

That folder is a staging queue for caves with no SUE number yet, and its names
are free-form: a cave name, sometimes a plaque number, sometimes an old queue
number, sometimes just ``ak 47.jpg``. The plan (user, 2026-08-26) is to keep the
free naming but prefix each file with its **Redni broj**, turning the folder
into one collection point that a later step renames to ``<SUE>_…`` and moves up.

The matching itself lives in `core/matching.py` — shared with the field-data
intake scan. This module adds what is specific to photos: which extensions
count, and the promotion check for photos left behind after their cave was
explored.
"""

from __future__ import annotations

from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import (
    CaveCandidate,
    PathMatch,
    RenameOutcome,
    apply_renames,
    build_candidates,
    match_paths,
)

#: ``.jfif`` is a plain JPEG under an older extension — Windows and some phone
#: exports still write it, and four staged entrance photos use it.
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".jfif", ".png", ".heic", ".tif", ".tiff", ".webp"}
#: Windows writes these into synced folders; never a cave artefact.
_SYSTEM_FILENAMES = {"desktop.ini", "thumbs.db", ".ds_store"}


class PhotoMatch(PathMatch):
    """A staged photo, plus the question of whether it should still be there."""

    @property
    def needs_promotion(self) -> bool:
        """The cave earned a SUE number while its photos stayed in the queue.

        The standing leak the user described (2026-08-28): promoting a queued
        cave's photos into `!!Fotografije ulaza` under the SUE number is manual,
        and it is routinely forgotten once newer photos arrive — so stale copies
        linger for caves that are long since explored. Surfacing them is the
        whole point; promoting or deleting is the user's call, never this tool's.
        """
        return self.cave is not None and bool(self.cave.sue_number)

    @property
    def promoted_name(self) -> str | None:
        """What the file would be called in the main archive: ``<padded SUE>_<rest>``."""
        if not self.needs_promotion or self.cave is None or not self.cave.sue_number:
            return None
        return f"{self.cave.sue_number.zfill(3)}_{self.rest()}"

    @property
    def proposed_name(self) -> str | None:
        """As the base class, except a photo awaiting promotion proposes nothing.

        Stamping the pre-SUE id on an explored cave's photo would only bury the
        fact that it belongs in the main archive instead.
        """
        if self.needs_promotion:
            return None
        return super().proposed_name


def match_photos(
    paths: list[Path],
    candidates: list[CaveCandidate],
    manual: dict[str, int] | None = None,
) -> list[PhotoMatch]:
    """Resolve staged photos to SB rows. Leading numbers are meaningful here."""
    return match_paths(paths, candidates, manual, use_numbers=True, match_class=PhotoMatch)


def staged_photo_dir(settings: Settings) -> Path | None:
    """The staging folder, resolved against LOCAL_DRIVE_ROOT."""
    relative = settings.archive_dirs.get("queued_photos_dir")
    if not relative or settings.local_drive_root is None:
        return None
    return settings.local_drive_root / relative


def list_photos(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES),
        key=lambda p: p.name.lower(),
    )


def list_other_files(directory: Path) -> list[Path]:
    """Everything in the folder that is not an entrance photo, system files aside.

    Video mostly. Surfaced rather than skipped: a folder inventory that silently
    drops files is how the ``.jfif`` photos went unnoticed in the first place.
    """
    if not directory.is_dir():
        return []
    return sorted(
        (
            p
            for p in directory.iterdir()
            if p.is_file()
            and p.suffix.lower() not in _IMAGE_SUFFIXES
            and p.name.lower() not in _SYSTEM_FILENAMES
        ),
        key=lambda p: p.name.lower(),
    )


__all__ = [
    "CaveCandidate",
    "PhotoMatch",
    "RenameOutcome",
    "apply_renames",
    "build_candidates",
    "list_other_files",
    "list_photos",
    "match_photos",
    "staged_photo_dir",
]
