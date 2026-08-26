"""Part 2.1d — match the free-form staged entrance photos back to SB rows.

`!!Fotografije ulaza/!!Fotografije ulaza za istražit` is a staging queue for
caves that have no SUE number yet, and its 59 filenames are free-form: a cave
name, sometimes a plaque number, sometimes an old queue number, sometimes just
``ak 47.jpg``. The user's plan (2026-08-26) is to keep the free naming but
prefix each file with its **Redni broj**, turning the folder into a single
collection point that a later step can rename to ``<SUE>_…`` and move up.

Doing that by hand means reading 59 names against 1294 rows, so this module
proposes the mapping. It is **read-only**: it never renames or moves anything,
it prints proposals for the user to accept.

Matching, strongest evidence first:

1. **plaque number** in the filename (``051-550``, ``051 418``) — unambiguous
2. **cave name** appearing in the filename, longest match wins, so
   "Vela jama na Krku" beats "Vela jama"
3. **old Za-istražit broj** (``478_…``, ``479 (1)``) against the number parsed
   out of the Napomena queue flag — a hint, hence lowest confidence
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.dossier.sb_mapper import parse_queue_flag
from cave_dossier.sb.loader import SBReader

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp"}
#: Leading "123_" / "123 " — verified against the cave's Redni broj below, because
#: most staged files already start with the *old Za-istražit broj*, which the v3.0
#: renumbering made stale.
_LEADING_NUMBER_RE = re.compile(r"^(\d{1,4})(?=[_\s.-])")
#: Plaque numbers appear as "051-550" or "051 418". Underscore is a word
#: character, so \b would not fire in "051-550_Goli breg" — use digit lookarounds.
_PLAQUE_RE = re.compile(r"(?<!\d)(\d{3})[\s-](\d{3})(?!\d)")
#: Names shorter than this match too much ("ak", "GB") to trust as a hit.
_MIN_NAME_KEY_CHARS = 5


@dataclass(frozen=True)
class CaveCandidate:
    serial_number: int | None
    object_name: str
    sue_number: str | None
    plaque_number: str | None
    old_queue_number: str | None
    name_key: str


@dataclass
class PhotoMatch:
    path: Path
    cave: CaveCandidate | None
    evidence: str | None = None
    confidence: str = "none"  # high | medium | conflict | none
    conflict_with: CaveCandidate | None = None

    @property
    def stale_prefix(self) -> str | None:
        """A leading number that is NOT this cave's Redni broj — the old queue broj.

        A leading number that is really the first half of a plaque
        (``051-550_Goli breg``) is left alone: stripping it would leave a
        dangling ``550_``, and the plaque is worth keeping in the name.
        """
        leading = _LEADING_NUMBER_RE.match(self.path.name)
        if not leading or self.cave is None:
            return None
        plaque = _PLAQUE_RE.search(self.path.name)
        if plaque and plaque.start() == 0:
            return None
        if self.cave.serial_number is not None and leading.group(1) == str(self.cave.serial_number):
            return None
        return leading.group(1)

    @property
    def already_correct(self) -> bool:
        leading = _LEADING_NUMBER_RE.match(self.path.name)
        return bool(
            leading
            and self.cave is not None
            and self.cave.serial_number is not None
            and leading.group(1) == str(self.cave.serial_number)
        )

    @property
    def proposed_name(self) -> str | None:
        """``<Redni broj>_<rest>`` — replacing a stale old-queue-broj prefix if present.

        None when there is nothing to propose: no match, no Redni broj on the
        row, the name is already right, or the evidence conflicts.
        """
        if self.cave is None or self.cave.serial_number is None:
            return None
        if self.confidence == "conflict" or self.already_correct:
            return None
        rest = self.path.name
        stale = self.stale_prefix
        if stale:
            rest = rest[len(stale) :].lstrip("_ -.")
        return f"{self.cave.serial_number}_{rest}"


def build_candidates(reader: SBReader, settings: Settings) -> list[CaveCandidate]:
    """Every named SB row, keyed for matching."""
    columns = settings.sb_field_columns
    frame = reader.load_rows()
    candidates: list[CaveCandidate] = []
    for _index, row in frame.iterrows():
        record = {str(key).strip(): value for key, value in row.to_dict().items()}
        cave = reader._to_cave_row(record)  # noqa: SLF001 — same package, deliberate
        if not cave.object_name:
            continue
        note = _text(record.get(columns.get("note", "Napomena")))
        candidates.append(
            CaveCandidate(
                serial_number=_int(_text(record.get(columns.get("serial_number")))),
                object_name=cave.object_name,
                sue_number=cave.sue_number,
                plaque_number=_text(record.get(settings.sb_plaque_column)),
                old_queue_number=parse_queue_flag(note).old_number,
                name_key=normalize_lookup_key(cave.object_name),
            )
        )
    return candidates


def match_photos(paths: list[Path], candidates: list[CaveCandidate]) -> list[PhotoMatch]:
    """Propose a cave for each staged photo. Order of evidence is documented above."""
    by_plaque = {
        normalize_lookup_key(c.plaque_number): c for c in candidates if c.plaque_number
    }
    by_old_number = {
        c.old_queue_number: c for c in candidates if c.old_queue_number
    }
    # Longest name first so a specific name wins over a prefix of itself.
    by_name = sorted(
        (c for c in candidates if len(c.name_key) >= _MIN_NAME_KEY_CHARS),
        key=lambda c: len(c.name_key),
        reverse=True,
    )

    matches: list[PhotoMatch] = []
    for path in paths:
        stem = path.stem
        key = normalize_lookup_key(stem)

        # Gather every independent piece of evidence, then weigh them: two that
        # agree is the strongest signal available, and two that disagree is a
        # data-quality finding in its own right (a mislabelled photo, or a
        # reused plaque number).
        evidence: list[tuple[str, CaveCandidate]] = []

        plaque = _PLAQUE_RE.search(stem)
        if plaque:
            candidate = by_plaque.get(normalize_lookup_key(f"{plaque.group(1)}-{plaque.group(2)}"))
            if candidate:
                evidence.append((f"pločica {plaque.group(0)}", candidate))

        named = next((c for c in by_name if c.name_key in key), None)
        if named:
            evidence.append((f"ime '{named.object_name}'", named))

        leading = _LEADING_NUMBER_RE.match(stem)
        if leading:
            candidate = by_old_number.get(leading.group(1))
            if candidate:
                evidence.append((f"stari broj {leading.group(1)}", candidate))

        if not evidence:
            matches.append(PhotoMatch(path, None))
            continue

        caves = {id(item[1]): item[1] for item in evidence}
        if len(caves) > 1:
            first, second = evidence[0], evidence[1]
            matches.append(
                PhotoMatch(
                    path,
                    first[1],
                    f"{first[0]} vs {second[0]} ({second[1].object_name})",
                    "conflict",
                    conflict_with=second[1],
                )
            )
            continue

        cave = evidence[0][1]
        reasons = " + ".join(item[0] for item in evidence)
        confidence = "high" if len(evidence) > 1 or evidence[0][0].startswith("pločica") else "medium"
        matches.append(PhotoMatch(path, cave, reasons, confidence))
    return matches


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


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none"}:
        return None
    if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
        text = text[:-2]
    return text


def _int(text: str | None) -> int | None:
    try:
        return int(float(text)) if text else None
    except ValueError:
        return None


__all__ = [
    "CaveCandidate",
    "PhotoMatch",
    "build_candidates",
    "list_photos",
    "match_photos",
    "staged_photo_dir",
]
