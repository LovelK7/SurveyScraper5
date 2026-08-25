"""SBReader unit tests against the synthetic mini workbook.

The fixture (tests/fixtures/mini_sb.xlsx, regenerable via make_mini_sb.py)
replicates the live workbook's traps: metadata row above the header, header
spellings differing in case/whitespace from config, Croatian diacritics.
The ``settings`` / ``reader`` fixtures live in conftest.py.
"""

from __future__ import annotations

from cave_dossier.sb.loader import SBReader


def test_header_row_detected_below_metadata(reader: SBReader) -> None:
    header_row, columns = reader.describe_columns()
    assert header_row == 2  # metadata in Excel row 1, real header in row 2
    # Case/spacing variants canonicalized back to the configured names:
    assert "Ime objekta" in columns
    assert "X HTRS" in columns


def test_load_rows_excel_row_numbers(reader: SBReader) -> None:
    frame = reader.load_rows()
    assert len(frame) == 5
    assert frame["__excel_row_number"].tolist() == [3, 4, 5, 6, 7]


def test_find_by_name_diacritic_insensitive(reader: SBReader) -> None:
    matches = reader.find_caves("spilja testovka")  # no diacritics, lowercase
    assert len(matches) == 1
    cave = matches[0]
    assert cave.object_name == "Špilja Testovka"
    assert cave.sue_number == "001"
    assert cave.row_number == 3


def test_find_by_sue_number(reader: SBReader) -> None:
    matches = reader.find_caves("003")
    assert len(matches) == 1
    assert matches[0].object_name == "Ponor pod Kukom"
    assert matches[0].row_number == 5


def test_find_by_name_substring_fallback(reader: SBReader) -> None:
    matches = reader.find_caves("ponor")
    names = {cave.object_name for cave in matches}
    # substring fallback catches both ponor rows
    assert names == {"Ponor pod Kukom", "Đulin ponor mali"}


def test_find_no_match(reader: SBReader) -> None:
    assert reader.find_caves("nepostojeća jama") == []


def test_stats(reader: SBReader) -> None:
    stats = reader.stats()
    assert stats["data_rows"] == 5
    assert stats["header_row"] == 2
    assert "Svi objekti" in stats["sheet_names"]
    assert "Bilješke" in stats["sheet_names"]
    column, count = stats["fill_counts"]["object name"]
    assert column == "Ime objekta"
    assert count == 5
    _, coords_count = stats["fill_counts"]["X HTRS"]
    assert coords_count == 4  # one cave has no coordinates
