"""Part 2.1d — entrance-photo processing.

``matcher`` is the one-off sweep that gave the free-form staged photos an
``SB_<Redni broj>`` prefix (read-only proposals; not run any more).
``process`` is the standing per-cave step: raw photos out of the cave's intake
leaf into archive-ready ``SB_<broj>_<Ime>_<Autor>_<n>.jpg`` copies, downsized
to screen size. Filing them into `!!Fotografije ulaza` under the katastarski
broj stays a later, separate step.
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
from cave_dossier.photos.process import (
    PhotoJob,
    PhotoPlan,
    ProcessedPhoto,
    author_filename_token,
    build_job,
    entrance_photo_author,
    is_ignored,
    plan_photos,
    process_job,
    process_photo,
    resolve_targets,
    source_photos,
    target_name,
)

__all__ = [
    "CaveCandidate",
    "PhotoJob",
    "PhotoMatch",
    "PhotoPlan",
    "ProcessedPhoto",
    "RenameOutcome",
    "apply_renames",
    "author_filename_token",
    "build_candidates",
    "build_job",
    "entrance_photo_author",
    "is_ignored",
    "list_other_files",
    "list_photos",
    "match_photos",
    "plan_photos",
    "process_job",
    "process_photo",
    "resolve_targets",
    "source_photos",
    "staged_photo_dir",
    "target_name",
]
