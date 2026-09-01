"""osz/legacy.py — the ported crospeleo OSZParser core.

Synthetic documents are built in-memory with python-docx (the same
technique crospeleo's own unit tests use); the real archive zapisnici are
exercised live, not from tests.
"""

from __future__ import annotations

import pytest

docx = pytest.importorskip("docx")

from cave_dossier.osz.legacy import (
    LegacyParseError,
    _normalize_coordinate_source,
    _split_entrance_elevation_parts,
    parse_legacy_osz,
    to_v10_fields,
)


def _paragraph_doc(lines, path):
    document = docx.Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))
    return path


def test_paragraph_pass_sticky_labels(tmp_path):
    path = _paragraph_doc([
        "Ime objekta: Jama kod Sela",
        "Sinonimi: Stara jama; Jama iznad sela",
        "Položaj i pristup: Ulaz je uz makadamski put.",
        "Pristupa se pješice 10 minuta od zadnje kuće.",  # continuation line
        "Duljina: 120,5 m",
        "Dubina: 45 m",
        "Razdoblje istraživanja: 2019.; 2021.",
        "Članovi ekipe: Lovel Kukuljan; Maja Primjer",
        "Zapisničar: Lovel Kukuljan",
    ], tmp_path / "legacy.docx")

    content = parse_legacy_osz(path)
    fields, ticks, notes = to_v10_fields(content)
    assert fields["ime_objekta"] == "Jama kod Sela"
    assert fields["sinonimi"] == "Stara jama; Jama iznad sela"
    # The continuation paragraph joined onto the sticky label.
    assert "makadamski put" in fields["polozaj_pristup"]
    assert "10 minuta" in fields["polozaj_pristup"]
    assert fields["duljina"] == "120,5"
    assert fields["dubina"] == "45"
    assert fields["datum_istrazivanja"] == "2019.; 2021."
    assert fields["zapisnicar"] == "Lovel Kukuljan"


def test_table_label_value_and_elevation_split(tmp_path):
    document = docx.Document()
    table = document.add_table(rows=3, cols=4)
    table.cell(0, 0).text = "Kota ulaza [m]:"
    table.cell(0, 1).text = "535"
    table.cell(0, 2).text = "Odr. po:"
    table.cell(0, 3).text = "TK"
    table.cell(1, 0).text = "Stvarna duljina [m]:"
    table.cell(1, 1).text = "15 m"
    table.cell(1, 2).text = "Dubina [m]:"
    table.cell(1, 3).text = "16 m"
    table.cell(2, 0).text = "Špiljski ulaz širina visina:"
    table.cell(2, 1).text = "0.4 / 1"
    path = tmp_path / "table.docx"
    document.save(str(path))

    fields, _, _ = to_v10_fields(parse_legacy_osz(path))
    assert fields["kota_ulaza"] == "535"
    assert fields["izvor_kote"] == "TK"
    assert fields["duljina"] == "15"
    assert fields["dubina"] == "16"
    assert fields["sirina_ulaza"] == "0,4"
    assert fields["visina_duljina_ulaza"] == "1"


def test_bold_selection_becomes_tick(tmp_path):
    document = docx.Document()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Vrsta objekta:"
    paragraph = table.cell(0, 1).paragraphs[0]
    run = paragraph.add_run("Jama")            # selected — bold
    run.bold = True
    paragraph.add_run(" Špilja Kaverna")       # the rest of the option list
    path = tmp_path / "bold.docx"
    document.save(str(path))

    content = parse_legacy_osz(path)
    assert content.bold_selections.get("object_type") == "Jama"
    _, ticks, _ = to_v10_fields(content)
    assert "Jama" in ticks


def test_no_content_sentinels_and_signature_drop(tmp_path):
    path = _paragraph_doc([
        "Povijesni podaci: /",
        "Literatura: nepoznato",
        "Napomene: Kastav, dne 1.1.2020. Zapisnik ispunio: Netko",
    ], tmp_path / "sentinels.docx")
    fields, _, _ = to_v10_fields(parse_legacy_osz(path))
    assert "povijest" not in fields
    assert "literatura" not in fields
    assert "napomene" not in fields  # signature footer dropped


def test_coordinate_source_vocabulary_fishing():
    assert _normalize_coordinate_source(
        "GPS Koordinate GPS – WGS 84 [ ] 1 4") == "GPS"
    assert _normalize_coordinate_source("LiDAR") == "LIDAR"
    assert _normalize_coordinate_source("posve nepoznat izvor") == "posve nepoznat izvor"
    assert _normalize_coordinate_source(None) is None


def test_elevation_split_both_generations():
    assert _split_entrance_elevation_parts("680 Izvor kote ulaza: LiDAR") == ("680", "LiDAR")
    assert _split_entrance_elevation_parts("535 Odr. po: TK") == ("535", "TK")
    assert _split_entrance_elevation_parts("612") == ("612", None)


def test_signature_row_place_and_date(tmp_path):
    """'U | Kastvu | , dne | 15. 06. 2025. | Zapisnik ispunio/la: | X' →
    mjesto_zapisnika + datum_zapisnika (crospeleo drops both; we keep)."""
    document = docx.Document()
    table = document.add_table(rows=1, cols=6)
    for index, text in enumerate(
        ["U", "Kastvu", ", dne", "15. 06. 2025.", "Zapisnik ispunio/la:", "Mile Milić"]
    ):
        table.cell(0, index).text = text
    path = tmp_path / "sig.docx"
    document.save(str(path))

    fields, _, _ = to_v10_fields(parse_legacy_osz(path))
    assert fields["mjesto_zapisnika"] == "Kastvu"
    assert fields["datum_zapisnika"] == "15. 06. 2025."
    assert fields["zapisnicar"] == "Mile Milić"


def test_signature_row_2019_generation_without_u(tmp_path):
    document = docx.Document()
    table = document.add_table(rows=1, cols=4)
    for index, text in enumerate(
        ["Postojna", ", dne", "12.03.2019.", "Zapisničar: Lovel Kukuljan"]
    ):
        table.cell(0, index).text = text
    path = tmp_path / "sig2.docx"
    document.save(str(path))

    fields, _, _ = to_v10_fields(parse_legacy_osz(path))
    assert fields["mjesto_zapisnika"] == "Postojna"
    assert fields["datum_zapisnika"] == "12.03.2019."


def test_signature_inline_single_cell(tmp_path):
    document = docx.Document()
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "U Kastvu, dne 1.2.2020."
    path = tmp_path / "sig3.docx"
    document.save(str(path))
    fields, _, _ = to_v10_fields(parse_legacy_osz(path))
    assert fields["mjesto_zapisnika"] == "Kastvu"
    assert fields["datum_zapisnika"] == "1.2.2020."


def test_non_docx_is_reported(tmp_path):
    bad = tmp_path / "old.doc"
    bad.write_bytes(b"\xd0\xcf\x11\xe0 pretend OLE2")
    with pytest.raises(LegacyParseError):
        parse_legacy_osz(bad)
