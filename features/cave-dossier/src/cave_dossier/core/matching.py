"""Match free-form filenames and folder names back to SB rows.

Shared by part 2.1d (staged entrance photos) and the field-data intake scan:
both face the same problem — a human-named path (`Sik Šits_Sara`,
`051-550_Goli breg 4.jpg`) that has to be resolved to one cave among ~1300.

Evidence is **weighed, not ranked**: every independent signal is collected, and
two that agree beat any single one. Two that disagree are a finding in their own
right (a mislabelled file, a reused plaque number) and propose nothing.

Signals:

* **plaque number** in the name (`051-550`, `051 418`) — strongest single one
* **cave name or synonym**, longest match wins so "Vela jama na Krku" beats
  "Vela jama"; an exact whole-stem match is accepted at any length, which is
  what resolves `ak 47` → *AK-47*
* **leading number**, checked against the cave's Redni broj (a path already
  renamed — this is what makes renaming idempotent) and against the old
  Za-istražit broj (what the pre-v3.0 names carry). Optional, because in some
  folders a leading number is a local id (LIDAR point, expedition sequence) and
  trusting it would produce confident nonsense.
* **manual mapping**, a configured name fragment → Redni broj, for abbreviations
  no rule can reach (`Jama GB 1` → *Goli breg 1*).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import ClassVar

from cave_dossier.core.config import Settings
from cave_dossier.core.normalization import normalize_lookup_key, split_semicolon_values
from cave_dossier.dossier.sb_mapper import parse_queue_flag
from cave_dossier.sb.loader import SBReader

#: Leading "123_" / "123 " — meaning depends on the folder, see ``use_numbers``.
LEADING_NUMBER_RE = re.compile(r"^(\d{1,4})(?=[_\s.-])")
#: Plaque numbers appear as "051-550" or "051 418". Underscore is a word
#: character, so \b would not fire in "051-550_Goli breg" — use digit lookarounds.
PLAQUE_RE = re.compile(r"(?<!\d)(\d{3})[\s-](\d{3})(?!\d)")
#: Keys shorter than this match too much ("ak", "GB") to hunt for as substrings.
MIN_NAME_KEY_CHARS = 5
#: Characters Windows forbids in a name, plus separators that would make the
#: result ambiguous to re-parse.
_ILLEGAL_FILENAME_CHARS = str.maketrans({c: "-" for c in '\\/:*?"<>|'})


@dataclass(frozen=True)
class CaveCandidate:
    """One SB row, keyed for matching."""

    serial_number: int | None
    object_name: str
    sue_number: str | None
    plaque_number: str | None
    old_queue_number: str | None
    name_key: str
    #: SB's "Fotografija ulaza" cell (DA / NE / empty) — a human-maintained
    #: claim that gets cross-checked against what is actually on Drive.
    entrance_photo_flag: str | None = None
    #: `Sinonimi`, normalised. A path often carries a synonym rather than the
    #: main name — `Goli breg 4` is *Sik Šits* (user, 2026-08-26).
    synonym_keys: tuple[str, ...] = ()

    @property
    def all_keys(self) -> tuple[str, ...]:
        return (self.name_key, *self.synonym_keys)


@dataclass
class PathMatch:
    """One path and the cave it resolves to, with the evidence that got there."""

    path: Path
    cave: CaveCandidate | None
    evidence: str | None = None
    confidence: str = "none"  # high | medium | conflict | none
    conflict_with: CaveCandidate | None = None

    #: Files have an extension to preserve; folders do not. Without this a
    #: folder named "M.Dol Pećina" would have ".Dol Pećina" torn off as if it
    #: were a suffix. Subclasses for directories set it False.
    has_extension: ClassVar[bool] = True

    @property
    def stale_prefix(self) -> str | None:
        """A leading number that is NOT this cave's Redni broj.

        A leading number that is really the first half of a plaque
        (`051-550_Goli breg`) is left alone: stripping it would leave a dangling
        `550_`, and the plaque is worth keeping in the name.
        """
        leading = LEADING_NUMBER_RE.match(self.path.name)
        if not leading or self.cave is None:
            return None
        plaque = PLAQUE_RE.search(self.path.name)
        if plaque and plaque.start() == 0:
            return None
        if self.cave.serial_number is not None and leading.group(1) == str(self.cave.serial_number):
            return None
        return leading.group(1)

    @property
    def already_correct(self) -> bool:
        """The path already starts with this cave's Redni broj."""
        leading = LEADING_NUMBER_RE.match(self.path.name)
        return bool(
            leading
            and self.cave is not None
            and self.cave.serial_number is not None
            and leading.group(1) == str(self.cave.serial_number)
        )

    def rest(self, *, strip_stale: bool = True, insert_name: bool = True) -> str:
        """The name minus a stale number, with the SB cave name put in front.

        Target shape ``<broj>_<Ime objekta>_<sve ostalo>``: the number alone is
        unreadable in a listing, and the tail usually carries the collector or a
        description worth keeping.

        Three cases:

        * the SB name is already in the name (in any word order) → untouched
        * a leading segment is the *same cave under a worse spelling*
          (`Bilova ponikva_Cico` vs SB *Billova ponikva*) → that segment is
          **replaced** by the SB name, per the user's instruction 2026-08-29
        * otherwise → the SB name is prepended and nothing is lost
        """
        rest = self.path.name
        if strip_stale:
            stale = self.stale_prefix
            if stale:
                rest = rest[len(stale) :].lstrip("_ -.")
        if self.cave is None or not insert_name:
            return rest
        name = sanitize_for_filename(self.cave.object_name)
        if not name:
            return rest
        suffix = Path(rest).suffix if self.has_extension else ""
        stem = rest[: -len(suffix)] if suffix else rest
        if normalize_lookup_key(name) in normalize_lookup_key(stem):
            return rest
        # Same words in a different order ("Grotta possibile" vs "Possibile
        # Grotta") — the name is already there, just rearranged.
        if _tokens(name) and _tokens(name) <= _tokens(stem):
            return rest
        return f"{name}_{_drop_variant_segments(stem, name)}{suffix}".rstrip("_")

    @property
    def proposed_name(self) -> str | None:
        """``<Redni broj>_<rest>``, or None when there is nothing to propose."""
        if self.cave is None or self.cave.serial_number is None:
            return None
        if self.confidence == "conflict" or self.already_correct:
            return None
        return f"{self.cave.serial_number}_{self.rest()}"


def sanitize_for_filename(name: str | None) -> str:
    """A cave name safe to paste into a path (`Jama u Vrtači` stays as is)."""
    if not name:
        return ""
    cleaned = name.translate(_ILLEGAL_FILENAME_CHARS).strip()
    return " ".join(cleaned.split())


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
        synonyms = split_semicolon_values(_text(record.get(columns.get("synonyms"))))
        candidates.append(
            CaveCandidate(
                serial_number=_int(_text(record.get(columns.get("serial_number")))),
                object_name=cave.object_name,
                sue_number=cave.sue_number,
                plaque_number=_text(record.get(settings.sb_plaque_column)),
                old_queue_number=parse_queue_flag(note).old_number,
                name_key=normalize_lookup_key(cave.object_name),
                entrance_photo_flag=_text(record.get(columns.get("entrance_photo_flag"))),
                synonym_keys=tuple(
                    key for key in (normalize_lookup_key(s) for s in synonyms) if key
                ),
            )
        )
    return candidates


def match_paths(
    paths: list[Path],
    candidates: list[CaveCandidate],
    manual: dict[str, int] | None = None,
    *,
    use_numbers: bool = True,
    match_class: type[PathMatch] = PathMatch,
) -> list[PathMatch]:
    """Resolve each path to a cave. See the module docstring for the evidence.

    ``use_numbers=False`` disables the leading-number signal — set it for
    folders whose names start with a local id (LIDAR point, expedition
    sequence) that has nothing to do with SB numbering.
    """
    by_plaque = {
        normalize_lookup_key(c.plaque_number): c for c in candidates if c.plaque_number
    }
    by_old_number = {c.old_queue_number: c for c in candidates if c.old_queue_number}
    by_serial = {c.serial_number: c for c in candidates if c.serial_number is not None}
    keyed: list[tuple[str, CaveCandidate]] = [
        (key, cave) for cave in candidates for key in cave.all_keys if key
    ]
    keyed.sort(key=lambda item: len(item[0]), reverse=True)

    matches: list[PathMatch] = []
    for path in paths:
        stem = path.stem if path.suffix else path.name
        key = normalize_lookup_key(stem)

        manual_hit = _manual_match(path.name, manual or {}, by_serial)
        if manual_hit:
            matches.append(match_class(path, manual_hit, "ručno mapiranje", "high"))
            continue

        evidence: list[tuple[str, CaveCandidate]] = []

        plaque = PLAQUE_RE.search(stem)
        if plaque:
            candidate = by_plaque.get(normalize_lookup_key(f"{plaque.group(1)}-{plaque.group(2)}"))
            if candidate:
                evidence.append((f"pločica {plaque.group(0)}", candidate))

        named_key, named, how = _match_by_name(stem, key, keyed)
        if named is not None:
            label = "ime" if named_key == named.name_key else "sinonim"
            evidence.append((f"{label} '{named.object_name}'{how}", named))

        if use_numbers:
            leading = LEADING_NUMBER_RE.match(stem)
            if leading:
                # A path already renamed to `<Redni broj>_…` must keep matching,
                # or re-running after an apply would report it as unmatched.
                current = by_serial.get(int(leading.group(1)))
                if current:
                    evidence.append((f"Redni broj {leading.group(1)}", current))
                candidate = by_old_number.get(leading.group(1))
                if candidate:
                    evidence.append((f"stari broj {leading.group(1)}", candidate))

        if not evidence:
            matches.append(match_class(path, None))
            continue

        caves = {id(item[1]): item[1] for item in evidence}
        if len(caves) > 1:
            first, second = evidence[0], evidence[1]
            matches.append(
                match_class(
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
        confidence = (
            "high" if len(evidence) > 1 or evidence[0][0].startswith("pločica") else "medium"
        )
        matches.append(match_class(path, cave, reasons, confidence))
    return matches


@dataclass
class RenameOutcome:
    """What actually happened to one path when ``apply_renames`` ran."""

    source: Path
    target: Path | None
    status: str  # renamed | skipped_exists | failed
    detail: str | None = None


def apply_renames(matches: list[PathMatch]) -> list[RenameOutcome]:
    """Perform the proposed renames in place.

    Only paths with a proposal are touched, so conflicts, unmatched paths and
    already-correct names are skipped by construction. An existing target is
    never overwritten — the pair is reported for a human to resolve.
    """
    outcomes: list[RenameOutcome] = []
    for match in matches:
        proposal = match.proposed_name
        if not proposal:
            continue
        target = match.path.with_name(proposal)
        if target.exists():
            outcomes.append(
                RenameOutcome(match.path, target, "skipped_exists", "target already exists")
            )
            continue
        try:
            match.path.rename(target)
        except OSError as exc:  # Drive sync can hold a lock
            outcomes.append(RenameOutcome(match.path, target, "failed", str(exc)))
            continue
        outcomes.append(RenameOutcome(match.path, target, "renamed"))
    return outcomes


def _drop_variant_segments(stem: str, sb_name: str) -> str:
    """Remove leading segments that are the SB name under a worse spelling.

    `Bilova ponikva_Cico` + *Billova ponikva* → `Cico`, so the proposal reads
    `976_Billova ponikva_Cico` rather than carrying both spellings. Only leading
    segments are considered, and only while they resemble the SB name: the tail
    (the collector, a local id, a qualifier) is never touched.
    """
    segments = stem.split("_")
    name_key = normalize_lookup_key(sb_name)
    if not name_key:
        return stem
    kept = list(segments)
    while kept:
        key = normalize_lookup_key(kept[0])
        if not key:
            kept.pop(0)
            continue
        resembles = (
            key in name_key
            or name_key in key
            or SequenceMatcher(None, key, name_key).ratio() >= 0.6
        )
        if not resembles:
            break
        kept.pop(0)
    return "_".join(kept)


def _tokens(text: str) -> set[str]:
    """Word tokens of a name, normalised, one-letter noise dropped."""
    parts = re.split(r"[\s_\-.,()+&/]+", text)
    keys = {normalize_lookup_key(part) for part in parts}
    return {key for key in keys if len(key) > 1}


def _match_by_name(
    stem: str, key: str, keyed: list[tuple[str, CaveCandidate]]
) -> tuple[str | None, CaveCandidate | None, str]:
    """Resolve a path name to a cave by its name or a synonym.

    Four passes, strongest first. The last two exist because folder names in the
    intake tree are abbreviations of the SB name as often as extensions of it:

    1. **exact** — the whole stem is the name (`ak 47` → *AK-47*)
    2. **contains** — the SB name sits inside the stem (`Rubijina jama_ivana`)
    3. **contained** — the stem is part of the SB name (`Ciciklama` →
       *Jama Ciciklama*), accepted only when exactly one cave matches, since a
       short fragment like "jama" would otherwise hit hundreds
    4. **word set** — every SB name word appears in the stem in any order
       (`Grotta possibile` → *Possibile Grotta*), needing a 2+ word SB name and
       again a unique hit
    """
    exact = next(((k, c) for k, c in keyed if k == key), None)
    if exact:
        return exact[0], exact[1], ""

    contains = next(
        ((k, c) for k, c in keyed if len(k) >= MIN_NAME_KEY_CHARS and k in key), None
    )
    if contains:
        return contains[0], contains[1], ""

    if len(key) >= MIN_NAME_KEY_CHARS:
        contained = [(k, c) for k, c in keyed if key in k]
        unique = {id(c) for _, c in contained}
        if len(unique) == 1:
            return contained[0][0], contained[0][1], " (skraćeno)"
        if len(unique) > 1:
            return None, None, ""

    stem_tokens = _tokens(stem)
    if stem_tokens:
        word_hits = [
            (k, c)
            for k, c in keyed
            if len(k) >= MIN_NAME_KEY_CHARS
            and len(_tokens(c.object_name if k == c.name_key else k)) >= 2
            and _tokens(c.object_name if k == c.name_key else k) <= stem_tokens
        ]
        unique = {id(c) for _, c in word_hits}
        if len(unique) == 1:
            return word_hits[0][0], word_hits[0][1], " (drugi redoslijed riječi)"

    return None, None, ""


def _manual_match(
    name: str, manual: dict[str, int], by_serial: dict[int, CaveCandidate]
) -> CaveCandidate | None:
    """First configured fragment that occurs in the name, case-insensitively."""
    lowered = name.casefold()
    for fragment, serial in manual.items():
        if fragment.casefold() in lowered:
            return by_serial.get(serial)
    return None


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
    "PathMatch",
    "RenameOutcome",
    "apply_renames",
    "build_candidates",
    "match_paths",
    "sanitize_for_filename",
]
