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

Needs Pillow (the ``[photos]`` extra, also pulled in by ``[karta]``) to write,
and ``lxml`` (``[osz]``) to read the author. Without either, the planning half
still works — the dry run prints the full plan and only that step degrades.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import SB_PREFIX, sanitize_for_filename
from cave_dossier.core.people import split_person_names
from cave_dossier.intake.scanner import find_cave_leaf, intake_root
from cave_dossier.photos.matcher import list_photos, staged_photo_dir

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

#: Sources that can be copied byte-for-byte when nothing needs doing to them.
_JPEG_SUFFIXES = {".jpg", ".jpeg"}

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
    #: images in the leaf that `photos.ignore_filenames` rules out (STATS.png)
    ignored: tuple[Path, ...] = ()
    #: this cave's photos still sitting in the `…za istražit` staging queue
    staged: tuple[Path, ...] = ()
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


def is_ignored(name: str, ignore_names: list[str] | None) -> bool:
    """An image in the leaf that is not an entrance photo.

    `STATS.png` — the cSurvey survey-statistics screenshot — recurs in leaf
    after leaf (user, 2026-09-01), and nothing about the file itself says it is
    not a photo. The list is config, not code (`photos.ignore_filenames`), and
    entries are fnmatch patterns so `STATS*.png` catches the numbered copies
    Windows makes.
    """
    lowered = name.casefold()
    return any(fnmatch(lowered, pattern.casefold()) for pattern in ignore_names or ())


def source_photos(
    folder: Path, serial: int, ignore_names: list[str] | None = None
) -> tuple[list[Path], list[Path]]:
    """``(raw photos, ignored images)`` in the cave's intake leaf.

    Copies live beside their originals, so a second run has to tell them
    apart: anything already carrying this cave's ``SB_<broj>`` prefix is
    output, not input. Subfolders are not descended into — the leaf is the
    cave's working folder, and a subfolder there is somebody's own grouping.

    The ignored ones come back rather than vanishing: quietly dropping files by
    name is how four `.jfif` entrance photos went uncounted for two years, so
    the caller lists them.
    """
    pattern = _already_processed_re(serial)
    photos, ignored = [], []
    for path in list_photos(folder):
        if pattern.match(path.name):
            continue
        (ignored if is_ignored(path.name, ignore_names) else photos).append(path)
    return photos, ignored


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
    ignore_names: list[str] | None = None,
) -> tuple[list[PhotoPlan], list[Path]]:
    """``(one plan per raw photo, the ignored images)``.

    Photos are numbered in the folder's own name order, ignored files taken out
    first — so a leaf's numbering does not shift when a `STATS.png` appears.
    """
    photos, ignored = source_photos(folder, serial, ignore_names)
    plans = [
        PhotoPlan(
            source=source,
            target=folder / target_name(serial, cave_name, author, index),
            unsupported=source.suffix.lower() in _UNSUPPORTED_SUFFIXES,
        )
        for index, source in enumerate(photos, 1)
    ]
    return plans, ignored


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
            # No leaf is usually the "photos are still queued" case, so the
            # staging scan runs here too — that is the whole point of the hint.
            notes.append(f"Nema SB_{serial}_… mape pod {root}")
            return PhotoJob(serial=serial, folder=None,
                            staged=tuple(staged_for_cave(settings, serial)),
                            notes=tuple(notes))

    author: str | None = None
    author_source: str | None = None
    if author_override:
        author = author_filename_token(author_override) or None
        author_source = author_override
    else:
        author, author_source, osz_path = _author_from_osz(settings, serial, osz_path, notes)

    plans, ignored = plan_photos(
        folder, serial, cave_name, author, settings.photo_ignore_names
    )
    return PhotoJob(
        serial=serial,
        folder=folder,
        plans=tuple(plans),
        author=author,
        author_source=author_source,
        osz_path=osz_path,
        ignored=tuple(ignored),
        staged=tuple(staged_for_cave(settings, serial)),
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
        location = backfill_mod.locate_filled_osz(settings, serial)
        osz_path = location.path
        if osz_path is None:
            # The locator's own notes say WHY (no leaf, several .docx
            # candidates, …). Swallowing them left the user with a flat "no
            # OSZ" for a cave whose zapisnik was sitting right there.
            notes.extend(location.notes)
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


# ── the staging queue → the cave's intake leaf ───────────────────────
@dataclass(frozen=True)
class PullMove:
    """One staged photo and where it lands in the cave's leaf."""

    source: Path
    target: Path


@dataclass(frozen=True)
class PullPlan:
    """Everything `photos pull-staged` resolved before touching a file."""

    serial: int
    folder: Path | None            # the leaf, existing or still to be created
    folder_exists: bool = False
    moves: tuple[PullMove, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PullOutcome:
    move: PullMove
    #: ``moved`` | ``exists`` | ``error``
    status: str
    detail: str | None = None


def staged_for_cave(settings: Settings, serial: int) -> list[Path]:
    """This cave's photos still sitting in `!!Fotografije ulaza za istražit`.

    Matched on the ``SB_<broj>_`` prefix alone: the 2026-08-28 sweep named all
    52 staged files, so the prefix IS the queue's index, and re-running the
    whole name/plaque matcher to learn what a filename already states would be
    a needless SB read. A staged photo that somehow lost its prefix is not
    found here — `photos check-flag` is what still surfaces those.
    """
    directory = staged_photo_dir(settings)
    if directory is None:
        return []
    pattern = _already_processed_re(serial)
    return [path for path in list_photos(directory) if pattern.match(path.name)]


def strip_sb_prefix(name: str, serial: int) -> str:
    """``SB_811_Possibile Grotta_13 ulaz.jpg`` → ``Possibile Grotta_13 ulaz.jpg``.

    The ``SB_<broj>_`` marker exists to identify a file sitting in a SHARED
    folder; inside the cave's own ``SB_<broj>_…`` leaf it is redundant. It also
    has to go: `source_photos` reads that prefix as "already processed", so a
    pulled photo would otherwise be invisible to the very command that is
    supposed to process it next.
    """
    stripped = _already_processed_re(serial).sub("", name).lstrip("_ ")
    return stripped or name


def plan_pull(
    settings: Settings,
    cave,
    serial: int,
) -> PullPlan:
    """Where each queued photo would go, creating nothing.

    The leaf is named exactly as `osz prefill` would name it
    (`prefill.intake_folder_name`) when it does not exist yet — a queued cave
    routinely has no leaf, which is precisely why its photos are still queued.
    """
    from cave_dossier.osz.prefill import intake_folder_name

    notes: list[str] = []
    staged = staged_for_cave(settings, serial)
    root = intake_root(settings)
    if root is None:
        return PullPlan(serial, None, notes=(
            "Nije konfiguriran archive.intake_dir / LOCAL_DRIVE_ROOT.",
        ))
    if not root.is_dir():
        return PullPlan(serial, None, notes=(f"Intake mapa nije dostupna: {root}",))

    folder = find_cave_leaf(root, serial)
    folder_exists = folder is not None
    if folder is None:
        folder = root / intake_folder_name(cave, serial, settings)
        notes.append(f"Intake mapa ne postoji — bit će stvorena: {folder.name}")

    moves = tuple(
        PullMove(source=path, target=folder / strip_sb_prefix(path.name, serial))
        for path in staged
    )
    return PullPlan(serial, folder, folder_exists, moves, tuple(notes))


def apply_pull(plan: PullPlan) -> list[PullOutcome]:
    """Move the queued photos in. Never overwrites; the queue is a staging
    area, so the photos LEAVE it rather than being duplicated (design decision
    C3: it is a queue, not a repository)."""
    outcomes: list[PullOutcome] = []
    if plan.folder is None:
        return outcomes
    plan.folder.mkdir(parents=True, exist_ok=True)
    for move in plan.moves:
        if move.target.exists():
            outcomes.append(PullOutcome(move, "exists", "postoji — preskočeno"))
            continue
        try:
            shutil.move(str(move.source), str(move.target))
        except OSError as exc:
            outcomes.append(PullOutcome(move, "error", str(exc)))
            continue
        outcomes.append(PullOutcome(move, "moved"))
    return outcomes


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
            plan, "error", "nedostaje Pillow — instaliraj extra `photos`", source_bytes
        )

    try:
        with Image.open(plan.source) as opened:
            image = ImageOps.exif_transpose(opened) or opened
            source_px = image.size
            if _nothing_to_do(plan.source, source_px, source_bytes,
                              long_edge_px, max_bytes):
                # Re-encoding a JPEG that is already small enough and already
                # the right size only costs quality — and, on an
                # already-compressed phone photo, actually GROWS the file
                # (0.25 MB → 0.35 MB, observed on SB 1250). Copy it verbatim.
                shutil.copy2(plan.source, plan.target)
                return ProcessedPhoto(plan, "written", "kopirano bez rekompresije",
                                      source_bytes, plan.target.stat().st_size,
                                      source_px, source_px)
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


def _nothing_to_do(
    source: Path,
    source_px: tuple[int, int],
    source_bytes: int | None,
    long_edge_px: int,
    max_bytes: int,
) -> bool:
    """Is this source already exactly what the copy should be?

    A JPEG within the long-edge target and within the size budget needs no
    work: every re-encode is generational loss, and gains nothing.
    """
    return (
        source.suffix.lower() in _JPEG_SUFFIXES
        and max(source_px) <= long_edge_px
        and source_bytes is not None
        and source_bytes <= max_bytes
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
    "PullMove",
    "PullOutcome",
    "PullPlan",
    "apply_pull",
    "author_filename_token",
    "build_job",
    "entrance_photo_author",
    "is_ignored",
    "plan_photos",
    "plan_pull",
    "process_job",
    "process_photo",
    "resolve_targets",
    "source_photos",
    "staged_for_cave",
    "strip_sb_prefix",
    "target_name",
]
