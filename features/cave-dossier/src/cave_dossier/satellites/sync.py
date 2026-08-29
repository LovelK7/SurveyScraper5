"""`sat sync` — compare a satellite against SB and produce three lists.

Nothing is ever written by machine. A run ends in exactly three reviewable
lists, and a person carries them out (user, 2026-08-29):

1. **Za SB** — confirmed caves the satellite has and SB does not, each rendered
   as a complete SB row in SB's own column order, ready to paste below the last
   row of `Svi objekti`.
2. **Za tablicu** — cells the satellite has wrong, one line each, corrected by
   hand in the browser. SB is ground truth for everything in this list.
3. **Za odluku** — conflicts, ambiguities, and the cases where the *satellite*
   knows something SB does not. No rule may settle these.

The direction of each list is fixed by ownership (hub doc §6): the field owns
"is it a cave", SB owns everything from the moment a candidate crosses into it.
"""

from __future__ import annotations

from dataclasses import dataclass

from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.satellites import liburnija
from cave_dossier.satellites.liburnija import SheetRow
from cave_dossier.satellites.model import (
    CandidateState,
    Decision,
    Difference,
    LinkStatus,
    NewRow,
    SyncResult,
)
from cave_dossier.satellites.resolver import Resolution, SBRecord

#: SB columns a new row from Liburnija can honestly fill, in SB's own order.
#: Deliberately short: a value nobody has is left empty rather than invented.
NEW_ROW_COLUMNS = (
    "Redni broj",
    "Broj pločice",
    "Ime objekta",
    "Sinonimi",
    "X HTRS",
    "Y HTRS",
    "Z",
    "Autori nacrta ili izvor",
    "Napomena",
)


@dataclass(frozen=True)
class _FlagField:
    """One of the three deliverable flags the sheet keeps by hand."""

    column: str          # the sheet's column
    label: str           # what SB calls it, for the reason line
    sheet_value: str     # attribute on SheetRow
    sb_value: str        # attribute on SBRecord


_FLAGS = (
    _FlagField("Nacrt", "Link Nacrt", "has_nacrt", "nacrt_link"),
    _FlagField("Zapisnik", "Link Zapisnik", "has_zapisnik", "zapisnik_link"),
    _FlagField("Foto ulaza", "Fotografija ulaza", "has_photo", "photo_flag"),
)


def _same_name(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return normalize_lookup_key(left) == normalize_lookup_key(right)


def _sb_has_photo(record: SBRecord) -> bool:
    """`Fotografija ulaza` is a DA/NE claim, not a link."""
    flag = (record.photo_flag or "").strip().upper()
    return flag.startswith("DA")


def _sb_flag_present(record: SBRecord, flag: _FlagField) -> bool:
    if flag.sb_value == "photo_flag":
        return _sb_has_photo(record)
    return bool(getattr(record, flag.sb_value))


def sheet_differences(resolution: Resolution) -> tuple[list[Difference], list[Decision]]:
    """What one linked row disagrees with SB about, split by who is right.

    SB wins on name, plaque, exploration status and the deliverable flags. The
    one case that flows the other way is the sheet claiming a deliverable SB has
    no record of — that is the field telling us something, so it goes to the
    decide list instead of being overwritten.
    """
    row, record = resolution.row, resolution.record
    if record is None:
        return [], []

    differences: list[Difference] = []
    decisions: list[Decision] = []

    # Name — SB is ground truth; `Naziv_novi` is filled in afterwards, so where
    # they differ the sheet is the one that is wrong (user, 2026-08-29). A
    # `LiDAR Kristal N` placeholder is never written back: it would claim the
    # cave has been named when it has not.
    if not record.has_placeholder_name and not (
        _same_name(record.name, row.name_new) or _same_name(record.name, row.name_old)
    ):
        differences.append(
            Difference(
                row_id=row.row_id,
                column=liburnija.COL_NAME_NEW,
                current=row.name_new or "—",
                proposed=record.name,
                reason=f"SB {record.serial_number} je mjerodavan za ime",
            )
        )

    if record.plaque and not row.plaque:
        differences.append(
            Difference(
                row_id=row.row_id,
                column=liburnija.COL_PLAQUE,
                current="—",
                proposed=record.plaque,
                reason=f"SB {record.serial_number} ima pločicu",
            )
        )

    if record.is_explored != row.explored:
        why = (
            f"SUE {record.sue_number}"
            if record.sue_number
            else (record.note or "nije u redu za istražit")
        )
        differences.append(
            Difference(
                row_id=row.row_id,
                column=liburnija.COL_EXPLORED,
                current="1" if row.explored else "0",
                proposed="1" if record.is_explored else "0",
                reason=f"SB {record.serial_number}: {why}",
            )
        )

    for flag in _FLAGS:
        in_sheet = bool(getattr(row, flag.sheet_value))
        in_sb = _sb_flag_present(record, flag)
        if in_sheet == in_sb:
            continue
        if in_sb:
            differences.append(
                Difference(
                    row_id=row.row_id,
                    column=flag.column,
                    current="FALSE",
                    proposed="TRUE",
                    reason=f"SB {record.serial_number} ima {flag.label}",
                )
            )
        else:
            decisions.append(
                Decision(
                    row_id=row.row_id,
                    issue=f"tablica tvrdi {flag.column}, SB nema {flag.label}",
                    detail=f"SB {record.serial_number} · {record.name}"
                           f" — provjeriti postoji li i unijeti u SB",
                )
            )

    return differences, decisions


def new_sb_row(row: SheetRow, serial_number: int) -> NewRow:
    """Render a confirmed cave as an SB row.

    Naming follows the convention that makes the sheet's number a legitimate
    key (hub doc §5): a cave with no name of its own **is** `LiDAR Kristal N`;
    a named one keeps its name and carries `LiDAR Kristal N` as a synonym.
    """
    field_name = row.field_name
    kristal = row.kristal_name
    warning: str | None = None

    if field_name and kristal:
        name, synonym = field_name, kristal
    elif field_name:
        # A field find (`nije na Lidaru`) — no number, so the convention cannot
        # reach it and the crosswalk is the only link back.
        name, synonym = field_name, None
        warning = "nema LiDAR broj (nalaz s terena) — veza postoji samo ovdje"
    elif kristal:
        name, synonym = kristal, None
    else:
        name, synonym = row.row_id, None
        warning = "nema ni ime ni LiDAR broj — imenovati ručno prije unosa"

    if row.state is CandidateState.EXPLORED:
        note = row.comment or ""
        warning = "istražen, a nije u SB — provjeriti status prije unosa"
    else:
        # The v3.0 queue flag, so SB's own Power Query files it under
        # "Za istražit" without anyone touching the view.
        note = "za istražit" + (f", {row.comment}" if row.comment else "")

    values = {
        "Redni broj": str(serial_number),
        "Broj pločice": row.plaque or "",
        "Ime objekta": name,
        "Sinonimi": synonym or "",
        "X HTRS": f"{row.x:.0f}" if row.x is not None else "",
        "Y HTRS": f"{row.y:.0f}" if row.y is not None else "",
        "Z": f"{row.z:.0f}" if row.z is not None else "",
        # For a queued cave this column holds the finder/source, not a survey
        # author — which is exactly what `provjerio` is.
        "Autori nacrta ili izvor": row.checked_by or "",
        "Napomena": note,
    }
    return NewRow(row_id=row.row_id, values=values, warning=warning)


def build(resolutions: list[Resolution], *, next_serial: int) -> SyncResult:
    """Turn resolved rows into the three lists."""
    result = SyncResult()
    counts = {status.value: 0 for status in LinkStatus}

    for resolution in resolutions:
        counts[resolution.status.value] += 1

        if resolution.status is LinkStatus.LINKED:
            differences, decisions = sheet_differences(resolution)
            result.to_sheet.extend(differences)
            result.to_decide.extend(decisions)
        elif resolution.status is LinkStatus.CANDIDATE:
            result.to_sb.append(new_sb_row(resolution.row, next_serial))
            next_serial += 1
        elif resolution.status is LinkStatus.CONFLICT:
            result.to_decide.append(
                Decision(
                    row_id=resolution.row.row_id,
                    issue="ne razrješava se jednoznačno",
                    detail=resolution.evidence or "",
                )
            )

    counts["total"] = len(resolutions)
    result.counts = counts
    return result


def _tsv_cell(value: str) -> str:
    """Flatten a cell so the pasted block stays rectangular.

    Comments come from a spreadsheet, so they can carry tabs and line breaks —
    either would silently shift every following column on paste. A value that
    *starts* with a quote is re-parsed by Excel's clipboard reader as a quoted
    field, so the quote is spaced away from the front.
    """
    flat = " ".join(value.split())
    return " " + flat if flat.startswith('"') else flat


def to_tsv(rows: list[NewRow], columns: tuple[str, ...] = NEW_ROW_COLUMNS) -> str:
    """The paste-able block: a header line plus one line per new SB row.

    Tab-separated because that is the format Excel and Google Sheets split into
    cells on paste — comma-separated text would land in a single cell.
    """
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append(
            "\t".join(_tsv_cell(row.values.get(column, "")) for column in columns)
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "NEW_ROW_COLUMNS",
    "build",
    "new_sb_row",
    "sheet_differences",
    "to_tsv",
]
