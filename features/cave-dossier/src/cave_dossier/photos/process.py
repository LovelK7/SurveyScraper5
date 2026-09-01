"""Part 2.1d — per-cave entrance-photo processing.

`photos match-queued` was a one-off sweep that gave the unidentified staged
photos a `SB_<Redni broj>_` prefix; it is not run any more. This module is the
standing step: for ONE cave, take the raw photos out of its intake leaf and
produce archive-ready copies —

    SB_<Redni broj>_<Ime objekta>_<Autor>_<n>.jpg

downsized to screen size. The author comes from the cave's filled OSZ cell
**Autor fotografije ulaza**, converted to the archive's filename spelling
("Lovel Kukuljan" → `LKukuljan`, matching `MDevcic` / `TMarkanjević` /
`SClashin` in `!!Fotografije ulaza`); the component is simply left out when the
OSZ has no author, rather than guessed from anywhere else.

Two deliberate limits (user, 2026-09-01):

- **Copies, never in-place edits.** The optimal output resolution is not
  settled yet, so every run writes new files and leaves the originals
  untouched — a second run with different targets is free.
- **This is not the filing step.** The copies stay in the intake leaf next to
  their originals. Moving them into `!!Fotografije ulaza` and re-numbering
  `SB_<Redni broj>` → `<Katastarski broj>` happens when the cave earns its SUE
  number, and is still a separate, later step.

Needs Pillow (the ``[karta]`` extra). Without it the planning half still works
— the dry run prints the full rename plan and only the writing fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import SB_PREFIX, sanitize_for_filename
from cave_dossier.core.people import split_person_names
from cave_dossier.intake.scanner import find_cave_leaf, intake_root
from cave_dossier.photos.matcher import list_photos

#: Fallbacks for `photos.target_long_edge_px` / `photos.target_max_bytes`
#: (config.yaml). "Screen size" is the FastStone preset the manual workflow
#: used, which lands a 7 MB field photo around 1 MB.
DEFAULT_LONG_EDGE_PX = 1920
DEFAULT_MAX_BYTES = 1_500_000

#: JPEG qualities tried in order until the file fits `max_bytes`. The floor is
#: deliberately not lower: an entrance photo that still misses the budget at 70
#: is better delivered slightly oversized than visibly mushy.
_QUALITY_LADDER = (92, 88, 84, 80, 75, 70)

#: Every processed copy is a JPEG regardless of what the camera wrote — the
#: archive is uniformly .jpg, and these are photographs.
OUTPUT_SUFFIX = ".jpg"

#: Formats Pillow opens without an extra plugin. `.heic` needs `pillow-heif`,
#: which is not a dependency — such a file is reported, never silently dropped.
_UNSUPPORTED_SUFFIXES = {".heic", ".heif"}


@dataclass(frozen=True)
class PhotoPlan:
    """One source photo and the archive-ready copy it should produce."""

    source: Path
    target: Path
    unsupported: bool = False

    @property
    def target_exists(self) -> bool:
        return self.target.exists()


@dataclass(frozen=True)
class ProcessedPhoto:
    """What actually happened to one planned copy."""

    plan: PhotoPlan
    #: ``written`` | ``exists`` | ``unsupported`` | ``error``
    status: str
    detail: str | None = None
    source_bytes: int | None = None
    target_bytes: int | None = None
    source_px: tuple[int, int] | None = None
    target_px: tuple[int, int] | None = None


@dataclass(frozen=True)
class PhotoJob:
    """Everything resolved for one cave before any file is touched."""

    serial: int
    folder: Path | None
    plans: tuple[PhotoPlan, ...] = ()
    author: str | None = None            # filename token, e.g. "LKukuljan"
    author_source: str | None = None     # the OSZ text it came from
    osz_path: Path | None = None
    notes: tuple[str, ...] = ()


# ── the author, out of the OSZ ───────────────────────────────────────
def author_filename_token(name: str) -> str:
    """"Lovel Kukuljan" → ``LKukuljan`` — the archive's filename spelling.

    Initial(s) plus surname with no dot and no space, which is what the
    existing `!!Fotografije ulaza` names use. A name that is not a plain
    multi-token "First Last" (already a token, or an initial·dot form) is
    passed through with its separators removed rather than reshaped — an
    honest passthrough beats a mangled guess.
    """
    cleaned = sanitize_for_filename(name).replace(".", " ").replace("_", " ")
    parts = [part for part in cleaned.split() if part]
    if not parts:
        return ""
    *given, last = parts
    return "".join(part[0] for part in given) + last


def entrance_photo_author(osz_path: Path) -> tuple[str | None, str | None]:
    """``(filename token, raw OSZ text)`` from **Autor fotografije ulaza**.

    Several people in the cell join with ``-`` (`LKukuljan-DReš`); an empty or
    unreadable cell gives ``(None, None)``, which drops the component from the
    filename instead of inventing one.
    """
    from cave_dossier.osz.reader import read_osz

    raw = (read_osz(osz_path).get("autor_fotografije_ulaza") or "").strip()
    names = split_person_names(raw)
    tokens = [token for token in (author_filename_token(n) for n in names) if token]
    if not tokens:
        return None, raw or None
    return "-".join(tokens), raw


# ── planning ─────────────────────────────────────────────────────────
def _already_processed_re(serial: int) -> re.Pattern[str]:
    """Names this command itself produced — never a source for the next run."""
    return re.compile(rf"^{re.escape(SB_PREFIX)}0*{serial}(_|$)", re.IGNORECASE)


def source_photos(folder: Path, serial: int) -> list[Path]:
    """The cave's RAW photos in its intake leaf.

    Copies live beside their originals, so a second run has to tell them
    apart: anything already carrying this cave's ``SB_<broj>`` prefix is
    output, not input. Subfolders are not descended into — the leaf is the
    cave's working folder, and a subfolder there is somebody's own grouping.
    """
    pattern = _already_processed_re(serial)
    return [path for path in list_photos(folder) if not pattern.match(path.name)]


def target_name(serial: int, cave_name: str | None, author: str | None, index: int) -> str:
    """``SB_<broj>_<Ime objekta>[_<Autor>]_<n>.jpg``.

    The index is always present: caves routinely have several entrance photos,
    and a bare name would collide on the second one.
    """
    parts = [f"{SB_PREFIX}{serial}", sanitize_for_filename(cave_name), author or "", str(index)]
    stem = "_".join(part for part in parts if part)
    return stem + OUTPUT_SUFFIX


def plan_photos(
    folder: Path,
    serial: int,
    cave_name: str | None,
    author: str | None,
) -> list[PhotoPlan]:
    """One plan per raw photo, numbered in the folder's own name order."""
    plans: list[PhotoPlan] = []
    for index, source in enumerate(source_photos(folder, serial), 1):
        plans.append(
            PhotoPlan(
                source=source,
                target=folder / target_name(serial, cave_name, author, index),
                unsupported=source.suffix.lower() in _UNSUPPORTED_SUFFIXES,
            )
        )
    return plans


def build_job(
    settings: Settings,
    serial: int,
    cave_name: str | None,
    *,
    folder: Path | None = None,
    author_override: str | None = None,
    osz_path: Path | None = None,
) -> PhotoJob:
    """Resolve the cave's leaf, its OSZ author and the copy plan.

    Everything degrades to a note rather than an exception: a missing OSZ or an
    unreadable one costs the author component, not the run.
    """
    notes: list[str] = []
    if folder is None:
        root = intake_root(settings)
        if root is None:
            notes.append(
                "Nije konfiguriran archive.intake_dir / LOCAL_DRIVE_ROOT — "
                "pokaži mapu s --from."
            )
            return PhotoJob(serial=serial, folder=None, notes=tuple(notes))
        if not root.is_dir():
            notes.append(f"Intake mapa nije dostupna: {root}")
            return PhotoJob(serial=serial, folder=None, notes=tuple(notes))
        folder = find_cave_leaf(root, serial)
        if folder is None:
            notes.append(f"Nema SB_{serial}_… mape pod {root}")
            return PhotoJob(serial=serial, folder=None, notes=tuple(notes))

    author: str | None = None
    author_source: str | None = None
    if author_override:
        author = author_filename_token(author_override) or None
        author_source = author_override
    else:
        author, author_source, osz_path = _author_from_osz(settings, serial, osz_path, notes)

    return PhotoJob(
        serial=serial,
        folder=folder,
        plans=tuple(plan_photos(folder, serial, cave_name, author)),
        author=author,
        author_source=author_source,
        osz_path=osz_path,
        notes=tuple(notes),
    )


def _author_from_osz(
    settings: Settings,
    serial: int,
    osz_path: Path | None,
    notes: list[str],
) -> tuple[str | None, str | None, Path | None]:
    """The author, or a note saying why there is none. Never raises.

    Losing the author costs one filename component; it must never cost the
    run, so a missing OSZ, a missing ``lxml`` and an unreadable document all
    degrade the same way.
    """
    from cave_dossier.osz import backfill as backfill_mod

    if osz_path is None:
        osz_path = backfill_mod.locate_filled_osz(settings, serial).path
    if osz_path is None:
        notes.append(
            "Nema ispunjenog OSZ-a — 'Autor fotografije ulaza' ostaje prazan "
            "(dodaj ga s --author)."
        )
        return None, None, None
    try:
        author, raw = entrance_photo_author(osz_path)
    except ImportError:
        notes.append("Nedostaje lxml (extra `osz`) — autor se ne može pročitati iz OSZ-a.")
        return None, None, osz_path
    except (OSError, RuntimeError) as exc:  # OszReadError is a RuntimeError
        notes.append(f"OSZ se ne može pročitati ({exc}) — autor ostaje prazan.")
        return None, None, osz_path
    if author is None:
        notes.append(
            f"OSZ nema 'Autor fotografije ulaza' ({osz_path.name}) — "
            "ime datoteke ostaje bez autora."
        )
    return author, raw, osz_path


# ── writing ──────────────────────────────────────────────────────────
def process_photo(
    plan: PhotoPlan,
    *,
    long_edge_px: int,
    max_bytes: int,
    overwrite: bool = False,
) -> ProcessedPhoto:
    """Write one downsized JPEG copy. Never touches the source."""
    source_bytes = plan.source.stat().st_size if plan.source.exists() else None
    if plan.unsupported:
        return ProcessedPhoto(
            plan, "unsupported", f"{plan.source.suffix} treba pillow-heif", source_bytes
        )
    if plan.target.exists() and not overwrite:
        return ProcessedPhoto(plan, "exists", "postoji — preskočeno", source_bytes)

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return ProcessedPhoto(
            plan, "error", "nedostaje Pillow — instaliraj extra `karta`", source_bytes
        )

    try:
        with Image.open(plan.source) as opened:
            image = ImageOps.exif_transpose(opened) or opened
            source_px = image.size
            resized = _fit_long_edge(image, long_edge_px)
            if resized.mode not in ("RGB", "L"):
                resized = resized.convert("RGB")
            target_px = resized.size
            exif = resized.info.get("exif") or image.info.get("exif")
            _save_within_budget(resized, plan.target, max_bytes, exif)
    except OSError as exc:
        return ProcessedPhoto(plan, "error", str(exc), source_bytes)

    return ProcessedPhoto(
        plan,
        "written",
        None,
        source_bytes,
        plan.target.stat().st_size,
        source_px,
        target_px,
    )


def _fit_long_edge(image, long_edge_px: int):
    """Downscale so the long edge is ``long_edge_px``. Never upscales — a photo
    already smaller than the target is copied at its own resolution."""
    from PIL import Image

    width, height = image.size
    if max(width, height) <= long_edge_px:
        return image
    scale = long_edge_px / max(width, height)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(size, Image.LANCZOS)


def _save_within_budget(image, target: Path, max_bytes: int, exif: bytes | None) -> None:
    """Save descending the quality ladder until the file fits the budget.

    The last rung is kept even when it still misses: an oversized honest copy
    is a visible fact the gate already warns about
    (`gating.MAX_ENTRANCE_PHOTO_BYTES`), whereas a mushy one is a silent loss.
    """
    kwargs = {"exif": exif} if exif else {}
    for quality in _QUALITY_LADDER:
        image.save(target, "JPEG", quality=quality, optimize=True,
                   progressive=True, **kwargs)
        if target.stat().st_size <= max_bytes:
            return


def process_job(
    job: PhotoJob,
    *,
    long_edge_px: int,
    max_bytes: int,
    overwrite: bool = False,
) -> list[ProcessedPhoto]:
    return [
        process_photo(plan, long_edge_px=long_edge_px, max_bytes=max_bytes,
                      overwrite=overwrite)
        for plan in job.plans
    ]


def resolve_targets(settings: Settings) -> tuple[int, int]:
    """``(long edge px, max bytes)`` from config.yaml's ``photos:`` block."""
    targets = settings.photo_targets or {}
    return (
        int(targets.get("target_long_edge_px") or DEFAULT_LONG_EDGE_PX),
        int(targets.get("target_max_bytes") or DEFAULT_MAX_BYTES),
    )


__all__ = [
    "DEFAULT_LONG_EDGE_PX",
    "DEFAULT_MAX_BYTES",
    "OUTPUT_SUFFIX",
    "PhotoJob",
    "PhotoPlan",
    "ProcessedPhoto",
    "author_filename_token",
    "build_job",
    "entrance_photo_author",
    "plan_photos",
    "process_job",
    "process_photo",
    "resolve_targets",
    "source_photos",
    "target_name",
]
