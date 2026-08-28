"""Part 2.1d — entrance-photo processing.

Today: matching the free-form staged photos back to SB rows (read-only
proposals). Later: the downsize + rename step itself, which turns a 7 MB field
photo into the ~1 MB archive copy named after the cave's SUE number.
"""

from cave_dossier.photos.matcher import (
    CaveCandidate,
    PhotoMatch,
    RenameOutcome,
    apply_renames,
    build_candidates,
    list_other_files,
    list_photos,
    match_photos,
    staged_photo_dir,
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
