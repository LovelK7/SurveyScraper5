"""`sat sync` — compare a satellite against SB and produce the review lists.

Nothing is ever written by machine. A run ends in four reviewable lists, and a
person carries them out (user, 2026-08-29):

1. **Za SB** — confirmed caves the satellite has and SB does not, each rendered
   as a full SB row in the workbook's own column order, ready to paste below the
   last row of `Svi objekti`.
2. **Dopune SB** — cells to add to *existing* SB rows. Today that is the
   `LiDAR Kristal N` synonym, which turns a fuzzy match into a permanent key.
3. **Za tablicu** — cells the satellite has wrong, one line each, corrected by
   hand in the browser. SB is ground truth for everything in this list.
4. **Za odluku** — conflicts and ambiguities. No rule may settle these.

The direction of each list is fixed by ownership (hub doc §6): the field owns
"is it a cave", SB owns everything from the moment a candidate crosses into it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.satellites import liburnija
from cave_dossier.satellites.liburnija import SheetRow
from cave_dossier.satellites.model import (
    CandidateState,
    Decision,
    Difference,
    LinkStatus,
    NewRow,
    SBEdit,
    SyncResult,
)
from cave_dossier.satellites.resolver import Resolution, SBRecord

#: Fallback column order, used only when the workbook's own header is not to
#: hand (tests). A real run passes SB's header so the block pastes straight in.
NEW_ROW_COLUMNS = (
    "Redni broj",
    "Katastarski broj SUE",
    "CroSpeleo unos",
    "Katastarski broj RH",
    "Broj pločice",
    "Ime objekta",
    "Sinonimi",
    "X HTRS",
    "Y HTRS",
    "Z",
    "Lokalitet",
    "Najbliže mjesto",
    "Duljina",
    "Dubina",
    "Godina ili period istraživanja",
    "Autori nacrta ili izvor",
    "Napomena",
    "Fotografija ulaza",
    "Zagađenost",
    "Ledenica",
    "Link Nacrt",
    "Link Zapisnik",
    "Dopunski zapisnik?",
    "Godina zadnjeg istraživanja",
)

#: Windows Excel reads a UTF-8 file as the local codepage unless it finds a BOM,
#: which turns every č/š/ž into mojibake. `utf-8-sig` writes that BOM.
FILE_ENCODING = "utf-8-sig"


def _same_name(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return normalize_lookup_key(left) == normalize_lookup_key(right)


def _sb_says_photo(record: SBRecord) -> bool:
    """`Fotografija ulaza` is an explicit DA/NE claim, not a link."""
    return (record.photo_flag or "").strip().upper().startswith("DA")


def _sb_has_document(record: SBRecord, link: str | None) -> bool:
    """Does SB say this cave has a nacrt / zapisnik at all?

    `Link Nacrt` and `Link Zapisnik` record only whether a **digital** copy is
    linked, so an empty cell is no evidence of absence — every *Istraženi*
    object has both, analog or digital (user, 2026-08-29). The katastarski broj
    SUE is therefore the stronger signal, and the link is the fallback for caves
    that do not have one yet.
    """
    return bool(record.sue_number) or bool(link)


def sheet_differences(resolution: Resolution) -> tuple[list[Difference], list[Decision]]:
    """What one linked row disagrees with SB about, split by who is right.

    SB wins on name, plaque, exploration status and the deliverable flags. The
    one case that flows the other way is the sheet claiming an entrance photo SB
    has no record of — the field telling us something, so it goes to the decide
    list instead of being overwritten.
    """
    row, record = resolution.row, resolution.record
    if record is None:
        return [], []

    differences: list[Difference] = []
    decisions: list[Decision] = []

    def propose(column: str, current: str, proposed: str, reason: str) -> None:
        differences.append(
            Difference(
                row_id=row.row_id,
                column=column,
                current=current,
                proposed=proposed,
                reason=reason,
            )
        )

    # Name — SB is ground truth; `Naziv_novi` is filled in afterwards, so where
    # they differ the sheet is the one that is wrong (user, 2026-08-29). A
    # `LiDAR Kristal N` placeholder is never written back: it would claim the
    # cave has been named when it has not.
    if not record.has_placeholder_name and not (
        _same_name(record.name, row.name_new) or _same_name(record.name, row.name_old)
    ):
        propose(
            liburnija.COL_NAME_NEW,
            row.name_new or "—",
            record.name,
            f"SB {record.serial_number} je mjerodavan za ime",
        )

    if record.plaque and not row.plaque:
        propose(
            liburnija.COL_PLAQUE,
            "—",
            record.plaque,
            f"SB {record.serial_number} ima pločicu",
        )

    if record.is_explored != row.explored:
        why = (
            f"SUE {record.sue_number}"
            if record.sue_number
            else (record.note or "nije u redu za istražit")
        )
        propose(
            liburnija.COL_EXPLORED,
            "1" if row.explored else "0",
            "1" if record.is_explored else "0",
            f"SB {record.serial_number}: {why}",
        )

    # Nacrt / Zapisnik are only ever proposed in the TRUE direction. SB's empty
    # link cell means "no digital copy on file", never "no such document", so
    # the sheet claiming one is not a disagreement worth raising.
    for column, in_sheet, link, label in (
        (liburnija.COL_NACRT, row.has_nacrt, record.nacrt_link, "nacrt"),
        (liburnija.COL_ZAPISNIK, row.has_zapisnik, record.zapisnik_link, "zapisnik"),
    ):
        if in_sheet or not _sb_has_document(record, link):
            continue
        reason = (
            f"SB {record.serial_number} ima katastarski broj SUE "
            f"{record.sue_number} — dakle i {label}"
            if record.sue_number
            else f"SB {record.serial_number} ima digitalni {label}"
        )
        propose(column, "FALSE", "TRUE", reason)

    # Fotografija ulaza is a DA/NE claim in SB, so it disagrees in both
    # directions and the sheet's own TRUE is worth acting on.
    if _sb_says_photo(record) and not row.has_photo:
        propose(
            liburnija.COL_PHOTO,
            "FALSE",
            "TRUE",
            f"SB {record.serial_number} ima Fotografija ulaza",
        )
    elif row.has_photo and not _sb_says_photo(record):
        decisions.append(
            Decision(
                row_id=row.row_id,
                issue="tablica tvrdi Foto ulaza, SB ne kaže DA",
                detail=f"SB {record.serial_number} · {record.name}"
                       f" — provjeriti i po potrebi ispraviti SB",
            )
        )

    return differences, decisions


def synonym_edit(resolution: Resolution) -> SBEdit | None:
    """Propose the `LiDAR Kristal N` synonym on a linked SB row that lacks it.

    This is the convention that makes the sheet's number a legitimate key (hub
    doc §5): once SB carries it, the row resolves on a hard key forever instead
    of on coordinates or a name. Only ever an *addition* — the existing
    `Sinonimi` text is preserved.
    """
    row, record = resolution.row, resolution.record
    if record is None or not row.kristal_name or not row.kristal_number:
        return None
    if row.kristal_number in record.kristal_numbers:
        return None
    current = "; ".join(record.synonyms)
    return SBEdit(
        serial_number=record.serial_number,
        column="Sinonimi",
        current=current or "—",
        proposed=f"{current}; {row.kristal_name}" if current else row.kristal_name,
        reason=f"tablica red {row.row_id} → {record.name}; sinonim čini vezu trajnom",
        row_id=row.row_id,
    )


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
    """Turn resolved rows into the review lists."""
    result = SyncResult()
    counts = {status.value: 0 for status in LinkStatus}

    for resolution in resolutions:
        counts[resolution.status.value] += 1

        if resolution.status is LinkStatus.LINKED:
            differences, decisions = sheet_differences(resolution)
            result.to_sheet.extend(differences)
            result.to_decide.extend(decisions)
            edit = synonym_edit(resolution)
            if edit is not None:
                result.to_sb_edits.append(edit)
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


# ── rendering ──────────────────────────────────────────────────────


def _joined(lines: list[str]) -> str:
    """One text block, newline-terminated."""
    return chr(10).join(lines) + chr(10)


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

    ``columns`` must be **the workbook's own header, in its own order** — a
    subset or a reordering cannot be pasted into `Svi objekti` at all. Columns
    a new row has no value for are emitted empty, which is what keeps the block
    aligned with the table.

    Tab-separated because that is the format Excel and Google Sheets split into
    cells on paste; comma-separated text would land in a single cell.
    """
    by_key = {normalize_lookup_key(column): column for column in columns}
    lines = [chr(9).join(columns)]
    for row in rows:
        # Match our value keys to the workbook's spelling, not the other way.
        values = {
            by_key.get(normalize_lookup_key(name), name): value
            for name, value in row.values.items()
        }
        lines.append(
            chr(9).join(_tsv_cell(values.get(column, "")) for column in columns)
        )
    return _joined(lines)


def _column(value: str, width: int) -> str:
    """Pad to ``width``, but never let a long value swallow the next column."""
    return value.ljust(width) if len(value) < width else value + "  "


def _table(
    header: tuple[str, ...], widths: tuple[int, ...], rows: list[tuple]
) -> list[str]:
    lines = ["".join(_column(h, w) for h, w in zip(header[:-1], widths)) + header[-1]]
    for row in rows:
        lines.append(
            "".join(_column(str(v), w) for v, w in zip(row[:-1], widths)) + str(row[-1])
        )
    return lines


def render_sb_edits(edits: list[SBEdit]) -> str:
    """List 2: cells to add to rows SB already has."""
    return _joined(
        [
            "DOPUNE SB — dodati u postojeće retke `Svi objekti`.",
            "Samo dopuna: postojeći sadržaj ćelije ostaje.",
            "",
            *_table(
                ("Redni broj", "stupac", "sada", "dodati", "razlog"),
                (12, 12, 26, 30),
                [
                    (e.serial_number, e.column, e.current, e.proposed, e.reason)
                    for e in edits
                ],
            ),
        ]
    )


def render_sheet_list(differences: list[Difference]) -> str:
    """List 3 as a worksheet: one line per cell, to tick off in the browser."""
    return _joined(
        [
            "ZA TABLICU — ćelije koje SB zna bolje.",
            "Ispraviti rukom u Liburnija tablici; SB je mjerodavan.",
            "",
            *_table(
                ("red", "stupac", "sada", "treba", "razlog"),
                (10, 18, 22, 22),
                [
                    (d.row_id, d.column, d.current, d.proposed, d.reason)
                    for d in differences
                ],
            ),
        ]
    )


def render_decision_list(decisions: list[Decision]) -> str:
    """List 4 as a worksheet. Nothing here may be actioned by a rule."""
    lines = ["ZA ODLUKU — ništa se ne mijenja automatski.", ""]
    for item in decisions:
        lines.append(f"red {item.row_id}: {item.issue}")
        if item.detail:
            lines.append(f"    {item.detail}")
    return _joined(lines)


#: Where a run lands when `--out` is given no path. One dated folder per run,
#: grouped by satellite; gitignored (see sb-sync/README.md).
SYNC_ROOT_NAME = "sb-sync"


def default_out_dir(satellite: str, today: date) -> Path:
    """`sb-sync/<satellite>/<YYYY-MM-DD>/`, resolved against the feature root."""
    from cave_dossier.core.config import FEATURE_ROOT

    return FEATURE_ROOT / SYNC_ROOT_NAME / satellite / today.isoformat()


def write_lists(
    result: SyncResult,
    directory: Path,
    columns: tuple[str, ...] = NEW_ROW_COLUMNS,
) -> dict[str, Path]:
    """Write the review lists into ``directory``, returning what was written.

    List 1 is TSV because it is meant to be pasted into `Svi objekti`; the rest
    are plain text because they are worked through by hand, one line at a time.
    All of them carry a BOM — see ``FILE_ENCODING``. Nothing here writes to SB
    or to the sheet.
    """
    directory.mkdir(parents=True, exist_ok=True)
    written = {
        "za-sb": directory / "1-za-sb.tsv",
        "dopune-sb": directory / "2-dopune-sb.txt",
        "za-tablicu": directory / "3-za-tablicu.txt",
        "za-odluku": directory / "4-za-odluku.txt",
    }
    written["za-sb"].write_text(to_tsv(result.to_sb, columns), encoding=FILE_ENCODING)
    written["dopune-sb"].write_text(
        render_sb_edits(result.to_sb_edits), encoding=FILE_ENCODING
    )
    written["za-tablicu"].write_text(
        render_sheet_list(result.to_sheet), encoding=FILE_ENCODING
    )
    written["za-odluku"].write_text(
        render_decision_list(result.to_decide), encoding=FILE_ENCODING
    )
    return written


__all__ = [
    "FILE_ENCODING",
    "NEW_ROW_COLUMNS",
    "SYNC_ROOT_NAME",
    "build",
    "default_out_dir",
    "new_sb_row",
    "render_decision_list",
    "render_sb_edits",
    "render_sheet_list",
    "sheet_differences",
    "synonym_edit",
    "to_tsv",
    "write_lists",
]
