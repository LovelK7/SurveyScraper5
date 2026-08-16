"""Read the SB (Speleo baza) workbook — ported and trimmed from
crospeleo-automation's ``services/sb_loader.py`` (see docs/PORTING.md).

Kept from the original: the raw ``header=None`` read with header-row
auto-detection by scoring (the live workbook has metadata in row 1 and the
real headers in row 2), diacritic-insensitive column canonicalization, the
``__excel_row_number`` synthetic column, and the Drive-offline preflight.

Stripped: the CroSpeleo submission-queue machinery (round filtering, marker
checks, submission ledger, dossier seeding) — this tool reads caves, not a
submission queue.  New: ``find_caves`` (name / SUE / plaque lookup with a
name-substring fallback), ``describe_columns``, ``stats``.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from cave_dossier.core.config import Settings
from cave_dossier.core.normalization import cleanup_whitespace, normalize_lookup_key
from cave_dossier.sb.safe_io import SBWorkbookUnreachable, check_workbook_present

# openpyxl emits this UserWarning whenever it reads an .xlsm workbook that
# contains Excel's `<x14:dataValidation>` extension list.  It only affects
# openpyxl's *in-memory* model — the on-disk file is untouched (we never
# save through openpyxl).  Scope the suppression tightly.
warnings.filterwarnings(
    "ignore",
    message=r"Data Validation extension is not supported.*",
    category=UserWarning,
    module=r"openpyxl\..*",
)

_INTERNAL_COLUMNS = {"__excel_row_number"}


@dataclass(frozen=True)
class CaveRow:
    """One SB row, addressable back into the live workbook by Excel row number."""

    row_number: int  # 1-based Excel row
    object_name: str | None
    sue_number: str | None
    values: dict[str, Any]  # canonicalized column -> cell value (internal cols excluded)


class SBReader:
    """Read-only access to the SB workbook. Never writes (see sb/safe_io.py)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self._frame: pd.DataFrame | None = None
        self._header_row_1based: int | None = None

    # ── Public API ─────────────────────────────────────────────────

    def sheet_names(self) -> list[str]:
        workbook_path = Path(self.settings.sb_workbook_path)
        check_workbook_present(workbook_path)
        workbook = pd.ExcelFile(workbook_path, engine="openpyxl")
        return list(workbook.sheet_names)

    def load_rows(self) -> pd.DataFrame:
        """The configured sheet as a DataFrame: canonicalized columns +
        ``__excel_row_number``. Cached per reader instance."""
        if self._frame is None:
            self._frame = self._read_sheet()
        return self._frame

    def describe_columns(self) -> tuple[int, list[str]]:
        """(header row as 1-based Excel row, column names in sheet order)."""
        frame = self.load_rows()
        columns = [str(c) for c in frame.columns if str(c) not in _INTERNAL_COLUMNS]
        assert self._header_row_1based is not None
        return self._header_row_1based, columns

    def find_caves(self, query: str, *, limit: int = 5) -> list[CaveRow]:
        """Match by object name, SUE number, or plaque number.

        Exact matches (diacritic/case-insensitive via ``normalize_lookup_key``)
        win; when none exist, fall back to name-substring matches so
        ``inspect --cave ponor`` finds "Ponor pod Kukom" without the full name.
        """
        target = normalize_lookup_key(query)
        if not target:
            return []
        frame = self.load_rows()

        exact: list[CaveRow] = []
        partial: list[CaveRow] = []
        for _index, row in frame.iterrows():
            record = {str(key).strip(): value for key, value in row.to_dict().items()}
            name = self._cell_as_text(record, self.settings.sb_object_name_column)
            sue = (
                self._cell_as_text(record, self.settings.sb_archive_reference_column)
                if self.settings.sb_archive_reference_column
                else None
            )
            plaque = (
                self._cell_as_text(record, self.settings.sb_plaque_column)
                if self.settings.sb_plaque_column
                else None
            )
            keys = [normalize_lookup_key(v) for v in (name, sue, plaque) if v]
            cave = None
            if any(k == target for k in keys):
                cave = self._to_cave_row(record)
                exact.append(cave)
            elif name and target in normalize_lookup_key(name):
                partial.append(self._to_cave_row(record))
            if len(exact) >= limit:
                break

        results = exact if exact else partial
        return results[:limit]

    def stats(self) -> dict[str, Any]:
        """Sheet inventory + row/fill counts for the configured sheet."""
        frame = self.load_rows()
        key_columns = {
            "object name": self.settings.sb_object_name_column,
            "SUE number": self.settings.sb_archive_reference_column,
            "plaque": self.settings.sb_plaque_column,
            "exploration period": self.settings.sb_exploration_period_column,
            "X HTRS": self.settings.sb_x_htrs_column,
            "Y HTRS": self.settings.sb_y_htrs_column,
            "drawing authors": self.settings.sb_drawing_authors_column,
            "marker": self.settings.sb_marker_column,
            "filter": self.settings.sb_filter_column,
        }
        fill_counts: dict[str, tuple[str, int] | None] = {}
        for label, column in key_columns.items():
            if not column or column not in frame.columns:
                fill_counts[label] = None
                continue
            non_empty = sum(
                1
                for value in frame[column].tolist()
                if self._cell_as_text({"c": value}, "c") is not None
            )
            fill_counts[label] = (column, non_empty)
        return {
            "sheet_names": self.sheet_names(),
            "target_sheet": self.settings.sb_sheet_name,
            "header_row": self._header_row_1based,
            "data_rows": len(frame),
            "fill_counts": fill_counts,
        }

    # ── Row helpers ────────────────────────────────────────────────

    def _to_cave_row(self, record: dict[str, Any]) -> CaveRow:
        name = self._cell_as_text(record, self.settings.sb_object_name_column)
        sue = (
            self._cell_as_text(record, self.settings.sb_archive_reference_column)
            if self.settings.sb_archive_reference_column
            else None
        )
        values = {
            key: value
            for key, value in record.items()
            if key not in _INTERNAL_COLUMNS
        }
        return CaveRow(
            row_number=self._row_number(record),
            object_name=name,
            sue_number=sue,
            values=values,
        )

    @staticmethod
    def _cell_as_text(record: dict[str, Any], column_name: str) -> str | None:
        value = record.get(column_name)
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        text = str(value).strip()
        if text.endswith(".") and text[:-1].isdigit():
            text = text[:-1]
        return text or None

    @staticmethod
    def _row_number(record: dict[str, Any]) -> int:
        value = record.get("__excel_row_number")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return -1

    # ── Sheet reading (ported) ─────────────────────────────────────

    def _read_sheet(self) -> pd.DataFrame:
        # Pre-flight: surface Drive-offline / unmounted-drive as a typed,
        # CLI-friendly error instead of pandas' raw FileNotFoundError.
        workbook_path = Path(self.settings.sb_workbook_path)
        check_workbook_present(workbook_path)
        try:
            workbook = pd.ExcelFile(workbook_path, engine="openpyxl")
            sheet_name = self._resolve_sheet_name(workbook.sheet_names)
            frame = pd.read_excel(
                workbook_path,
                sheet_name=sheet_name,
                engine="openpyxl",
                header=None,
            )
        except FileNotFoundError as exc:
            # Race: path existed at preflight but vanished mid-read (Drive
            # may have unmounted between the two probes).
            raise SBWorkbookUnreachable(
                f"SB workbook disappeared between preflight and open.\n"
                f"  Path:   {workbook_path}\n"
                f"  Reason: Google Drive likely unmounted mid-read.  "
                f"Wait for the Drive sync indicator to settle, then retry.",
                path=workbook_path,
            ) from exc

        header_row_index = self._detect_header_row(frame)
        self._header_row_1based = header_row_index + 1
        header_values = [self._header_text(value) for value in frame.iloc[header_row_index].tolist()]
        data = frame.iloc[header_row_index + 1 :].copy()
        data.columns = header_values
        data = data.loc[:, [column for column in data.columns if column]]
        # The slice keeps the raw frame's 0-based index (0 ↔ Excel row 1),
        # so +1 converts straight to Excel's 1-based numbering.
        data["__excel_row_number"] = data.index + 1
        data = data.reset_index(drop=True)
        return self._canonicalize_columns(data)

    def _resolve_sheet_name(self, sheet_names: Iterable[str]) -> str:
        expected = normalize_lookup_key(self.settings.sb_sheet_name)
        for sheet_name in sheet_names:
            if normalize_lookup_key(sheet_name) == expected:
                return sheet_name
        return self.settings.sb_sheet_name

    def _detect_header_row(self, frame: pd.DataFrame) -> int:
        # Score every row by how many of the configured column names it
        # contains; the best-scoring row is the header.  The live workbook
        # has metadata in row 1 and the real headers in row 2.
        required_columns = [
            self.settings.sb_object_name_column,
            self.settings.sb_archive_reference_column,
            self.settings.sb_filter_column,
            self.settings.sb_marker_column,
        ]
        required_keys = {
            normalize_lookup_key(column) for column in required_columns if column
        }

        best_index = 0
        best_score = -1
        for index, row in frame.iterrows():
            normalized_cells = {
                normalize_lookup_key(cell)
                for cell in (self._header_text(value) for value in row.tolist())
                if cell
            }
            score = len(required_keys & normalized_cells)
            if score > best_score:
                best_index = int(index)
                best_score = score
            if score == len(required_keys):
                return int(index)
        return best_index

    def _canonicalize_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        expected_names = [
            self.settings.sb_filter_column,
            self.settings.sb_marker_column,
            self.settings.sb_object_name_column,
            self.settings.sb_archive_reference_column,
            self.settings.sb_plaque_column,
            self.settings.sb_drawing_authors_column,
            self.settings.sb_exploration_period_column,
            self.settings.sb_x_htrs_column,
            self.settings.sb_y_htrs_column,
        ]
        alias_map = {
            normalize_lookup_key(name): name
            for name in expected_names
            if name
        }
        rename_map: dict[str, str] = {}
        for column in frame.columns:
            if column in _INTERNAL_COLUMNS:
                continue
            canonical_name = alias_map.get(normalize_lookup_key(str(column)))
            if canonical_name:
                rename_map[str(column)] = canonical_name
        return frame.rename(columns=rename_map)

    @staticmethod
    def _header_text(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        return cleanup_whitespace(str(value))
