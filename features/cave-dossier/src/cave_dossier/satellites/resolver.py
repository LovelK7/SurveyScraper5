"""Resolve a satellite row to its SB row — ranked keys, never a local id.

Every satellite numbers its own rows, and those numbers leak into folder and
file names where they look exactly like identifiers. Measured 2026-08-29: of 20
field numbers checked against the old *Za istražit* index, 5 resolved and all 5
pointed at the wrong cave. So a local id is never a key here. The keys, in the
order they are tried:

1. **Broj pločice** — the strongest. 68 of Liburnija's 410 rows.
2. **``LiDAR Kristal N`` in SB** (`Ime objekta` or `Sinonimi`) — 56 rows, and
   **zero disagreements** with the plaque key. It adds no coverage today because
   it is a strict subset; its value is forward, once new rows are created
   carrying the convention. Unlike a folder number, this one is a legitimate key:
   the number lives *inside SB*, put there deliberately, rather than being
   guessed from a name.
3. **Coordinate proximity**, off by default and deliberately timid — see
   ``AUTO_LINK_M``.
4. **Name**, corroboration only; never enough on its own.

Two guards keep the whole thing honest:

* **Eligibility** — only rows that are confirmed caves may link at all. A row
  someone checked and rejected is not a cave, so any link from it is a false
  positive by construction. This alone removed 10 of 17 coordinate proposals.
* **Corroboration, not override** — when two keys reach different SB rows the
  result is a ``CONFLICT`` for a human, never a silent pick.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import pandas as pd

from cave_dossier.core.config import Settings
from cave_dossier.core.normalization import normalize_lookup_key, split_semicolon_values
from cave_dossier.satellites.liburnija import SheetRow
from cave_dossier.satellites.model import LinkStatus
from cave_dossier.sb.loader import SBReader

#: `LiDAR Kristal 108`, `lidar kristal 43` — the synonym convention (§5 of the
#: hub doc). Anchored on the words, so a bare number never reaches it.
KRISTAL_RE = re.compile(r"lidar\s*kristal\s*(\d{1,4})", re.IGNORECASE)

#: Coordinate bands, calibrated on the 68 plaque-linked pairs (median 0.9 m,
#: p90 2.6 m, max 12.3 m) against the sheet's own point spacing (54 points sit
#: within 15 m of another point). Auto-linking beyond 5 m starts inventing
#: neighbours; past 15 m there is no evidence any true pair lives there.
AUTO_LINK_M = 5.0
REVIEW_LINK_M = 15.0
#: An auto-link also requires no runner-up this close — dense terrain, so
#: "nearest" is not the same as "unambiguous".
AMBIGUITY_M = 15.0


@dataclass(frozen=True)
class SBRecord:
    """One SB row, with the fields the hub compares against a satellite."""

    serial_number: int | None
    name: str
    synonyms: tuple[str, ...]
    plaque: str | None
    sue_number: str | None
    x: float | None
    y: float | None
    note: str | None
    nacrt_link: str | None
    zapisnik_link: str | None
    photo_flag: str | None
    kristal_numbers: tuple[str, ...]

    @property
    def has_placeholder_name(self) -> bool:
        """True when `Ime objekta` is still `LiDAR Kristal N` — not a real name.

        Such a name must never be written back to the sheet as *the cave's
        name*: it says the opposite, that nobody has named it yet.
        """
        return bool(KRISTAL_RE.fullmatch(self.name.strip()))

    @property
    def is_explored(self) -> bool:
        """SB's answer to "has this been explored".

        A SUE number settles it. Failing that, two things in Napomena say no —
        the v3.0 queue flag (`za istražit, …`) and the Nesređeni keyword
        **neistraženo**, which SB's own Power Query treats as outstanding work.
        Reading only the queue flag made the tool propose *istraženo = 1* for
        SB 914 while quoting a note that begins "neistraženo": a contradiction
        on the very line someone is meant to act on.

        Anything else (`fali nacrt`, `ponoviti`) means visited and surveyed but
        not yet filed — explored, as far as the field sheet is concerned.
        """
        if self.sue_number:
            return True
        from cave_dossier.dossier.sb_mapper import parse_queue_flag

        if parse_queue_flag(self.note).queued:
            return False
        return "neistraz" not in normalize_lookup_key(self.note or "")


@dataclass(frozen=True)
class Resolution:
    """One satellite row and what became of it."""

    row: SheetRow
    record: SBRecord | None
    status: LinkStatus
    key: str | None = None
    evidence: str | None = None
    distance_m: float | None = None
    rival: SBRecord | None = None

    @property
    def is_linked(self) -> bool:
        return self.record is not None and self.status is LinkStatus.LINKED


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def _int(value: object) -> int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _float(value: object) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else float(number)


def next_serial_number(reader: SBReader, settings: Settings) -> int:
    """One past the highest `Redni broj` in the workbook.

    Deliberately spans *every* row, not just the named ones: SB carries a blank
    pre-numbered row (1313 in the 2026-08-29 copy), and numbering new caves from
    the highest **named** row would hand out a number that already exists.
    """
    frame = reader.load_rows()
    by_key = {normalize_lookup_key(str(name)): name for name in frame.columns}
    column = by_key.get(
        normalize_lookup_key(settings.sb_field_columns.get("serial_number", "Redni broj"))
    ) or by_key.get(normalize_lookup_key("Redni broj"))
    if column is None:
        return 1
    serials = pd.to_numeric(frame[column], errors="coerce").dropna()
    return int(serials.max()) + 1 if len(serials) else 1


def build_sb_index(reader: SBReader, settings: Settings) -> list[SBRecord]:
    """Every named SB row, with the columns the satellite comparison needs."""
    columns = settings.sb_field_columns
    frame = reader.load_rows()

    # The workbook's own header spellings vary in unicode normalisation, so
    # resolve every configured name through the same diacritic-insensitive key
    # the rest of the tool uses rather than indexing on an exact string.
    by_key = {normalize_lookup_key(str(name)): name for name in frame.columns}

    def column(configured: str | None, fallback: str | None = None) -> object | None:
        for candidate in (configured, fallback):
            if candidate:
                resolved = by_key.get(normalize_lookup_key(candidate))
                if resolved is not None:
                    return resolved
        return None

    col_name = column(settings.sb_object_name_column, "Ime objekta")
    col_serial = column(columns.get("serial_number"), "Redni broj")
    col_synonyms = column(columns.get("synonyms"), "Sinonimi")
    col_plaque = column(settings.sb_plaque_column, "Broj pločice")
    col_sue = column(settings.sb_archive_reference_column, "Katastarski broj SUE")
    col_x = column(settings.sb_x_htrs_column, "X HTRS")
    col_y = column(settings.sb_y_htrs_column, "Y HTRS")
    col_note = column(columns.get("note"), "Napomena")
    col_nacrt = column(columns.get("nacrt_link"), "Link Nacrt")
    col_zapisnik = column(columns.get("zapisnik_link"), "Link Zapisnik")
    col_photo = column(columns.get("entrance_photo_flag"), "Fotografija ulaza")

    records: list[SBRecord] = []
    for _index, row in frame.iterrows():
        name = _text(row.get(col_name)) if col_name is not None else None
        if not name:
            continue
        synonyms = tuple(
            value
            for value in split_semicolon_values(
                _text(row.get(col_synonyms)) if col_synonyms is not None else None
            )
            if value
        )
        kristal = tuple(
            match.group(1).lstrip("0") or "0"
            for field in (name, *synonyms)
            for match in KRISTAL_RE.finditer(field)
        )
        records.append(
            SBRecord(
                serial_number=_int(row.get(col_serial)) if col_serial is not None else None,
                name=name,
                synonyms=synonyms,
                plaque=_text(row.get(col_plaque)) if col_plaque is not None else None,
                sue_number=_text(row.get(col_sue)) if col_sue is not None else None,
                x=_float(row.get(col_x)) if col_x is not None else None,
                y=_float(row.get(col_y)) if col_y is not None else None,
                note=_text(row.get(col_note)) if col_note is not None else None,
                nacrt_link=_text(row.get(col_nacrt)) if col_nacrt is not None else None,
                zapisnik_link=_text(row.get(col_zapisnik)) if col_zapisnik is not None else None,
                photo_flag=_text(row.get(col_photo)) if col_photo is not None else None,
                kristal_numbers=kristal,
            )
        )
    return records


def _same_name(name: str | None, record: SBRecord) -> bool:
    """Does the satellite's name match this SB row's name or any synonym?"""
    if not name:
        return False
    key = normalize_lookup_key(name)
    return bool(key) and key in {
        normalize_lookup_key(label) for label in (record.name, *record.synonyms)
    }


def _nearest(row: SheetRow, records: list[SBRecord]) -> list[tuple[float, SBRecord]]:
    """SB rows within the review radius, closest first."""
    if not row.has_coordinates:
        return []
    near: list[tuple[float, SBRecord]] = []
    for record in records:
        if record.x is None or record.y is None:
            continue
        # Cheap box test first: this runs 410 × 1313 times.
        if abs(row.x - record.x) > REVIEW_LINK_M or abs(row.y - record.y) > REVIEW_LINK_M:
            continue
        distance = math.hypot(row.x - record.x, row.y - record.y)
        if distance <= REVIEW_LINK_M:
            near.append((distance, record))
    near.sort(key=lambda item: item[0])
    return near


def resolve_rows(
    rows: list[SheetRow],
    records: list[SBRecord],
    *,
    use_coordinates: bool = False,
    manual: dict[str, int] | None = None,
    out_of_scope: set[str] | None = None,
    confirmed_new: set[str] | None = None,
) -> list[Resolution]:
    """Resolve every satellite row. Order of the result mirrors the input.

    ``confirmed_new`` names rows a human has already ruled to be new caves
    despite sitting close to an existing SB row — without it the same proximity
    is re-raised on every run.
    """
    manual = manual or {}
    out_of_scope = out_of_scope or set()
    confirmed_new = {normalize_lookup_key(value) for value in (confirmed_new or set())}

    by_plaque: dict[str, SBRecord] = {}
    by_kristal: dict[str, SBRecord] = {}
    by_serial: dict[int, SBRecord] = {}
    by_name: dict[str, SBRecord] = {}
    for record in records:
        if record.plaque:
            by_plaque.setdefault(normalize_lookup_key(record.plaque), record)
        for number in record.kristal_numbers:
            by_kristal.setdefault(number, record)
        if record.serial_number is not None:
            by_serial.setdefault(record.serial_number, record)
        for label in (record.name, *record.synonyms):
            key = normalize_lookup_key(label)
            if key:
                by_name.setdefault(key, record)

    resolutions: list[Resolution] = []
    for row in rows:
        # 1. States that are not caves never link — the guard that keeps a
        #    rejected point 20 m from a real cave from becoming a "match".
        if not row.state.is_cave:
            status = (
                LinkStatus.NOT_A_CAVE
                if row.checked
                else LinkStatus.UNCHECKED
            )
            resolutions.append(Resolution(row=row, record=None, status=status))
            continue

        # 2. Manual override, for the handful no rule reaches.
        override = manual.get(row.row_id)
        if override is not None and override in by_serial:
            resolutions.append(
                Resolution(
                    row=row,
                    record=by_serial[override],
                    status=LinkStatus.LINKED,
                    key="manual",
                    evidence=f"ručno → Redni broj {override}",
                )
            )
            continue

        by_plaque_hit = by_plaque.get(normalize_lookup_key(row.plaque)) if row.plaque else None
        by_kristal_hit = by_kristal.get(row.kristal_number) if row.kristal_number else None

        # 3. Two keys that disagree are a finding, not a choice to make.
        if (
            by_plaque_hit is not None
            and by_kristal_hit is not None
            and by_plaque_hit.serial_number != by_kristal_hit.serial_number
        ):
            resolutions.append(
                Resolution(
                    row=row,
                    record=None,
                    status=LinkStatus.CONFLICT,
                    evidence=(
                        f"pločica {row.plaque} → {by_plaque_hit.serial_number}, "
                        f"sinonim LiDAR Kristal {row.kristal_number} → "
                        f"{by_kristal_hit.serial_number}"
                    ),
                )
            )
            continue

        if by_plaque_hit is not None:
            corroborated = by_kristal_hit is not None
            resolutions.append(
                Resolution(
                    row=row,
                    record=by_plaque_hit,
                    status=LinkStatus.LINKED,
                    key="plaque",
                    evidence=f"pločica {row.plaque}"
                    + (" + sinonim" if corroborated else ""),
                )
            )
            continue

        if by_kristal_hit is not None:
            resolutions.append(
                Resolution(
                    row=row,
                    record=by_kristal_hit,
                    status=LinkStatus.LINKED,
                    key="kristal",
                    evidence=f"sinonim LiDAR Kristal {row.kristal_number}",
                )
            )
            continue

        # 4. Coordinates last, timid, and only when asked for.
        confirmed = normalize_lookup_key(row.row_id) in confirmed_new
        if use_coordinates and not confirmed:
            near = _nearest(row, records)
            if near:
                distance, record = near[0]
                rival = near[1][1] if len(near) > 1 else None
                rival_distance = near[1][0] if len(near) > 1 else None
                # Two independent signals that agree beat either alone: an exact
                # name match inside the review radius is the same cave, even
                # past the auto band. Sheet 285 *Jama u Puharima* is SB 733 at
                # 5.1 m — one tenth of a metre outside AUTO_LINK_M, and plainly
                # the same cave (user, 2026-08-29).
                if _same_name(row.field_name, record):
                    resolutions.append(
                        Resolution(
                            row=row,
                            record=record,
                            status=LinkStatus.LINKED,
                            key="name+coordinate",
                            evidence=f"isto ime i {distance:.1f} m",
                            distance_m=distance,
                        )
                    )
                    continue
                if distance <= AUTO_LINK_M and rival is None:
                    resolutions.append(
                        Resolution(
                            row=row,
                            record=record,
                            status=LinkStatus.LINKED,
                            key="coordinate",
                            evidence=f"{distance:.1f} m, nema drugog unutar "
                                     f"{AMBIGUITY_M:.0f} m",
                            distance_m=distance,
                        )
                    )
                    continue
                detail = f"{record.name} (Redni broj {record.serial_number}) na {distance:.1f} m"
                if rival is not None:
                    detail += (
                        f"; ali i {rival.name} (Redni broj {rival.serial_number})"
                        f" na {rival_distance:.1f} m"
                    )
                resolutions.append(
                    Resolution(
                        row=row,
                        record=None,
                        status=LinkStatus.CONFLICT,
                        key="coordinate",
                        evidence=detail,
                        distance_m=distance,
                        rival=rival,
                    )
                )
                continue

        # 5. Nothing reaches it. Only now does scope matter: a cave another
        #    society explored separately does not enter SB (user, 2026-08-29).
        #    Deliberately checked LAST — scope decides whether a row may be
        #    ADDED, never whether an existing SB row may be linked. Akupunktura
        #    (`Karsterra, SUE`) is already SB 823 and must stay linked.
        if not row.is_own_society or row.row_id in out_of_scope:
            resolutions.append(
                Resolution(
                    row=row,
                    record=None,
                    status=LinkStatus.OUT_OF_SCOPE,
                    evidence=(
                        f"istražili {row.explored_by}"
                        if row.explored_by and not row.is_own_society
                        else "ručno isključeno"
                    ),
                )
            )
            continue

        # 6. Last guard before proposing a new row: does SB already carry this
        #    name? A name is too weak to LINK on — spellings drift and caves get
        #    reused names — but an exact match is far too strong to ignore when
        #    the alternative is pasting a duplicate. Sheet 285 *Jama u Puharima*
        #    is SB 733 under the same name, 5 m away; adding it would have
        #    duplicated a cave. So the name stops the add and asks.
        twin = (
            by_name.get(normalize_lookup_key(row.field_name))
            if row.field_name and not confirmed
            else None
        )
        if twin is not None:
            resolutions.append(
                Resolution(
                    row=row,
                    record=None,
                    status=LinkStatus.CONFLICT,
                    key="name",
                    evidence=f"SB već ima ime \"{twin.name}\" (Redni broj "
                             f"{twin.serial_number}) — isti objekt ili imenjak?",
                )
            )
            continue

        # 7. A confirmed cave of ours that nothing reaches: it belongs in SB.
        resolutions.append(Resolution(row=row, record=None, status=LinkStatus.CANDIDATE))

    return resolutions


__all__ = [
    "AMBIGUITY_M",
    "AUTO_LINK_M",
    "KRISTAL_RE",
    "REVIEW_LINK_M",
    "Resolution",
    "SBRecord",
    "build_sb_index",
    "next_serial_number",
    "resolve_rows",
]
