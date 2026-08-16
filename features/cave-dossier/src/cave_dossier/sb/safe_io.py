"""Safe I/O for the live ``!Speleo_baza_SUE_v2.4.xlsm`` workbook.

Ported near-verbatim from crospeleo-automation (see docs/PORTING.md).
Architectural lessons distilled from
[docs/EXCEL_WORKBOOK_SAFETY.md](../../../docs/EXCEL_WORKBOOK_SAFETY.md):

- **Reads** use ``openpyxl`` with ``data_only=True, read_only=True``.
  ``read_only`` makes ``wb.save()`` physically impossible, so even a
  stray save-call cannot damage the workbook.  ``data_only`` returns
  cached formula values (the workbook's derived sheets — Istraženi,
  Nesređeni, Literatura — are formula-driven mirrors of *Svi objekti*,
  so this is what we want).
- **Writes** go through ``xlwings`` (Excel COM).  Excel itself performs
  the save, which is the only path that preserves:
  - VBA macros (the workbook is `.xlsm` for a reason).
  - Excel data validations (openpyxl warns "Data Validation extension
    is not supported and will be removed" on every load — a save
    would strip them).
  - The FuzzyLookup add-in's scratch sheet bookkeeping
    (`FuzzyLookup_AddIn_Undo_Sheet`).
  - Conditional formats, named ranges, and any cell-level features
    openpyxl doesn't understand.
- A **timestamped backup** is created beside the workbook *before*
  Excel saves.  Manual rollback path if anything corrupts.
- A **pre-flight lock-file check** (`~$<name>`) refuses to proceed
  when an Excel session has the file open — xlwings would otherwise
  attach to that session and surface visible UI flicker.

xlwings is an **optional dependency** (only required for writes — M6).
Install via ``pip install -e ".[sb-write]"`` from the feature root.
Pure-read code paths work without it.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd

LOGGER = logging.getLogger(__name__)


# ── Pre-flight checks ──────────────────────────────────────────────


class SBWorkbookUnreachable(FileNotFoundError):
    """Raised when the SB workbook can't be opened — typically Drive offline.

    Subclasses ``FileNotFoundError`` so any existing
    ``except FileNotFoundError`` still catches it; the dedicated type
    lets the CLI surface a clean message instead of a stack trace.
    Carries the resolved path on ``.path`` for callers that want to
    render it differently.
    """

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path


# Substring that marks a Google Drive "shortcut to a shared folder" path.
# These resolve via Drive Desktop's virtual file system; when Drive is
# offline or still mounting after wake-from-sleep, the substring lives
# inside the configured path but the on-disk node isn't there yet.
_DRIVE_SHORTCUT_SEGMENT = ".shortcut-targets-by-id"


def _diagnose_unreachable(path: Path) -> str:
    """Return the most specific reason ``path`` is missing right now.

    Distinguishes the three Drive-offline failure modes so the operator
    knows whether the drive letter hasn't mounted at all, the shortcut
    hasn't resolved, or the file just isn't there.
    """
    anchor = Path(path.anchor) if path.anchor else None
    if anchor is not None and str(anchor) and not anchor.exists():
        # Drive letter (or UNC root) is not mounted at all.  Most common
        # cause: Google Drive Desktop hasn't started yet after a sleep /
        # reboot.  The G:\ / H:\ drive will appear once Drive launches.
        return (
            f"Drive root {anchor} is not mounted.  Google Drive Desktop is "
            "most likely offline or still starting after wake-from-sleep — "
            "open Drive from the system tray, wait for the drive letter to "
            "appear, then retry."
        )
    if _DRIVE_SHORTCUT_SEGMENT in str(path).lower():
        # Drive letter is mounted but the shortcut hasn't resolved yet.
        return (
            "Path lives inside Google Drive's `.shortcut-targets-by-id`; "
            "Drive Desktop is running but hasn't finished resolving the "
            "shared-folder shortcut (typical right after sleep, or after "
            "the shared item was re-shared).  Wait until the Drive tray "
            "indicator stops syncing, then retry."
        )
    return (
        "Check that Google Drive Desktop is running and that the file is "
        "marked 'available offline' (Explorer should not show the cloud-"
        "only icon).  If the path is wrong, update SB_WORKBOOK_PATH or "
        "LOCAL_DRIVE_ROOT in `.env`."
    )


def check_workbook_present(path: Path) -> None:
    """Raise ``SBWorkbookUnreachable`` with a precise reason when ``path`` is missing."""
    if path.exists():
        return
    reason = _diagnose_unreachable(path)
    raise SBWorkbookUnreachable(
        f"SB workbook is unreachable.\n"
        f"  Path:   {path}\n"
        f"  Reason: {reason}",
        path=path,
    )


def check_excel_not_open(path: Path) -> None:
    """Raise ``RuntimeError`` if Excel has the workbook open (lock file present)."""
    lock = path.with_name("~$" + path.name)
    if lock.exists():
        raise RuntimeError(
            f"SB workbook is open in Excel ({lock} present).\n"
            "  Close the workbook in Excel and retry."
        )


# ── Backup helper ──────────────────────────────────────────────────


def create_backup(path: Path) -> Path:
    """Copy the workbook to a daily sibling backup.  Returns the backup path.

    Naming: ``<stem>.<YYYYMMDD>.backup<suffix>``.  Lands in the same
    directory as the original so manual rollback is just "rename this
    file" — no path-manipulation needed.

    **Daily rotation:** the date-only stamp means the second and later
    writes on the same day overwrite the morning's backup instead of
    spawning a new file per write.  Trade-off: within-day rollback
    windows are coarse, but the SB folder doesn't accumulate dozens of
    near-identical files.

    Uses ``shutil.copy2`` so timestamps + permissions are preserved.
    """
    date_stamp = datetime.now().strftime("%Y%m%d")
    backup_path = path.with_name(f"{path.stem}.{date_stamp}.backup{path.suffix}")
    refreshed = backup_path.exists()
    shutil.copy2(path, backup_path)
    if refreshed:
        LOGGER.info("Refreshed daily SB backup at %s", backup_path)
    else:
        LOGGER.info("Created daily SB backup at %s", backup_path)
    return backup_path


# ── Read path (openpyxl, doubly-safe) ──────────────────────────────


def read_sheet_dataframe(
    workbook_path: Path,
    sheet_name: str,
    *,
    header_row_1based: int | None = None,
) -> "pd.DataFrame":
    """Read a sheet from the workbook and return a ``pandas`` DataFrame.

    Uses ``data_only=True`` semantics (cached formula values).  We never
    call ``.save()`` on the underlying workbook so the read remains safe.
    Excel's 1-based row numbering is preserved as a ``__excel_row_number``
    column so callers can still address rows in the live workbook.
    """
    import pandas as pd  # lazy: heavy import

    check_workbook_present(workbook_path)

    # Read entire sheet as raw 2-D data (header=None) so we have full
    # control over the header row — the real workbook has metadata in
    # row 1 and the actual headers in row 2.
    raw = pd.read_excel(
        workbook_path,
        sheet_name=sheet_name,
        engine="openpyxl",
        header=None,
    )

    if header_row_1based is None:
        raw["__excel_row_number"] = raw.index + 1
        return raw

    header_idx_0 = header_row_1based - 1
    header_values = [
        str(v).strip() if v is not None else f"col_{i + 1}"
        for i, v in enumerate(raw.iloc[header_idx_0].tolist())
    ]
    data = raw.iloc[header_idx_0 + 1 :].copy()
    data.columns = header_values
    data["__excel_row_number"] = data.index + 1
    return data.reset_index(drop=True)


# ── Write path (xlwings, Excel does the save) — dormant until M6 ───


def write_cell_via_excel_com(
    workbook_path: Path,
    sheet_name: str,
    row_1based: int,
    column_1based: int,
    value: Any,
    *,
    backup: bool = True,
) -> Path | None:
    """Write a single cell via Excel COM.  Returns the backup path (or None).

    Pre-flight: workbook must exist and not be open in Excel.
    Backup: timestamped copy taken BEFORE the Excel save (skipped only
    when ``backup=False``, which the caller should never set in
    production).

    Excel does the save itself — VBA, data validations, conditional
    formats, the FuzzyLookup add-in scratch sheet, and all derived-sheet
    formulas survive.  This is the only safe write path for the live
    .xlsm; openpyxl save would strip data validations on every call
    even with ``keep_vba=True``.
    """
    check_workbook_present(workbook_path)
    check_excel_not_open(workbook_path)

    backup_path = create_backup(workbook_path) if backup else None

    try:
        import xlwings as xw  # lazy import — Windows + Excel only
    except ImportError as exc:
        raise RuntimeError(
            "xlwings is required for safe writes to the SB workbook.\n"
            "  Install via:  pip install -e \".[sb-write]\"\n"
            "  Reads work without xlwings; writes do not."
        ) from exc

    app = xw.App(visible=False, add_book=False)
    wb = None
    try:
        wb = app.books.open(str(workbook_path))
        sheet_names = [s.name for s in wb.sheets]
        if sheet_name not in sheet_names:
            raise KeyError(
                f"Sheet {sheet_name!r} not in workbook.  Have: {sheet_names}"
            )
        ws = wb.sheets[sheet_name]
        ws.range((row_1based, column_1based)).value = value
        wb.save()
        LOGGER.info(
            "Wrote SB %s!R%dC%d = %r (backup: %s)",
            sheet_name,
            row_1based,
            column_1based,
            value,
            backup_path.name if backup_path else "<none>",
        )
    finally:
        if wb is not None:
            try:
                wb.close()
            except Exception:
                pass
        app.quit()

    return backup_path
