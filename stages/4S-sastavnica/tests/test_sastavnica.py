"""Part 2.1e — the sastavnica renderer and its prefill orchestration.

The renderer is tested against the **authored** template, not against itself:
the drafter's own example values are the only ground truth for the typesetting
rules, so the first test re-sets them and asserts the geometry comes back where
the drafter put it. That is what catches a revised `.ai` whose cells moved.

The prefill tests run over the mini SB fixture with the geo finders and the
OSZ reader stubbed — what they check is the precedence rule (SB for identity,
the zapisnik for survey facts), the two constant cells, and the collision
refusal, not anything about PDFs.
"""

from __future__ import annotations

import dataclasses

import pytest

pytest.importorskip("pymupdf")

import pymupdf

from cave_dossier.geo.models import ElevationFinding, LocalityFinding
from cave_dossier.sastavnica import addresses, fonts, prefill, render as render_mod

# The values the authored template ships with, and the size the drafter chose
# for each. Leading/trailing spaces are the drafter's own nudges and are
# stripped here — the renderer centres properly instead.
# Updated 2026-09-20 for template v1.0, which is authored in **Microsoft Sans
# Serif** rather than Myriad Pro (see fonts.py for why). That face is wider, and
# the drafter's own sizes came down with it — most values that sat at 10 pt now
# sit at 9. `ekipa` is the drafter's FIRST LINE: in v1.0 they set that cell over
# two lines, because a three-person team no longer fits one.
AUTHORED = {
    "katastarski_broj": ("0000", 10),
    "ime_objekta": ("Neka jama jako jako dugačkog imena", 10),
    "broj_plocice": ("051-580", 9),
    "htrs": ("339823 5037995", 9),
    "nadmorska_visina": ("1033 m", 9),
    "lokacija": ("Obruč, Jelenje, Gorski kotar", 9),
    "stvarna_duljina": ("75 m", 9),
    "tlocrtna_duljina": ("15 m", 9),
    "crtali": ("L. Kukuljan", 9),
    "mjerili": ("I. Dujmović", 9),
    "dubina": ("-60 m", 9),
    "mjerilo": ("1:500", 9),
    "istrazili": ("SU Estavela", 8),
    "ekipa": ("T. Tepavac, S. Mikičić,", 8),
    "datum": ("10.12.2023.", 9),
}

# PyMuPDF's generated ToUnicode maps this face's space glyph to U+00A0, because
# space and no-break space share it. The drawn page is identical either way;
# only extracted text differs, so comparisons normalise it.
def _plain(text: str) -> str:
    return text.replace(" ", " ")


@pytest.fixture(scope="module")
def font():
    if not addresses.BLANK_TEMPLATE.exists():
        pytest.skip("blank template not built (sastavnica-template/tools/build_blank.py)")
    try:
        return fonts.resolve(None)
    except fonts.FontUnavailable as exc:
        pytest.skip(str(exc))


def _spans(data: bytes) -> dict[str, dict]:
    """Rendered value spans (the big ones), keyed by the cell they fall in."""
    page = pymupdf.open("pdf", data)[0]
    out = {}
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["size"] < 6:
                    continue          # a template label
                mid_x = (span["bbox"][0] + span["bbox"][2]) / 2
                mid_y = (span["bbox"][1] + span["bbox"][3]) / 2
                for key, cell in addresses.V1.items():
                    if cell.x0 <= mid_x <= cell.x1 and cell.y0 <= mid_y <= cell.y1:
                        out[key] = span
                        break
    return out


# ── the blank template ───────────────────────────────────────────────
def test_blank_template_keeps_labels_and_art(font):
    page = pymupdf.open(addresses.BLANK_TEMPLATE)[0]
    labels = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
              for s in l["spans"]]
    # 16, not 15: the v1.0 export emits a stray 5 pt space span beside
    # "Katastarski broj:" alongside the fifteen real labels.
    assert len(labels) == 16, "the printed labels must survive the strip"
    assert all(s["size"] < 6 for s in labels), "no example value may survive"
    assert len(page.get_drawings()) == 59, "the logo and rules must be untouched"


def test_blank_template_carries_no_embedded_illustrator_artwork(font):
    """Regression (2026-09-19): the one defect no PDF viewer can show you.

    The authored template was exported with *Preserve Illustrator Editing
    Capabilities*, so the page carried the whole `.ai` as private data.
    Illustrator opens THAT in preference to the page content — the delivered
    sastavnica rendered correctly in Acrobat and showed the template's example
    values in the one application it is made for.
    """
    doc = pymupdf.open(addresses.BLANK_TEMPLATE)
    assert doc.xref_get_key(doc[0].xref, "PieceInfo")[0] == "null"
    assert not any("AIPDFPrivateData" in doc.xref_object(x, compressed=True)
                   for x in range(1, doc.xref_length()))


def test_rendered_output_stays_free_of_it(font):
    data, _ = render_mod.render(addresses.BLANK_TEMPLATE, {"ime_objekta": "Jama"},
                                font.path)
    doc = pymupdf.open("pdf", data)
    assert doc.xref_get_key(doc[0].xref, "PieceInfo")[0] == "null"
    # …and the old example values are nowhere in the file, not even as a thumbnail.
    assert "Neka jama" not in doc[0].get_text()
    assert doc.xref_get_key(doc[0].xref, "Thumb")[0] == "null"


# ── geometry, against the drafter's own layout ───────────────────────
def test_render_reproduces_the_authored_layout(font):
    values = {key: text for key, (text, _size) in AUTHORED.items()}
    data, placed = render_mod.render(addresses.BLANK_TEMPLATE, values, font.path)
    assert len(placed) == 15
    spans = _spans(data)
    assert set(spans) == set(addresses.V1)

    for key, span in spans.items():
        cell = addresses.V1[key]
        centre = (span["bbox"][0] + span["bbox"][2]) / 2
        assert abs(centre - cell.centre_x) < 0.6, f"{key} is not centred"
        baseline = span["origin"][1]
        assert abs(baseline - (cell.y1 - addresses.BASELINE_LIFT)) < 0.1, \
            f"{key} sits on the wrong baseline"


def test_fitter_agrees_with_the_drafters_own_sizes(font):
    """Never shrink what the drafter did not, and never exceed their size."""
    face = pytest.importorskip("pymupdf").Font(fontfile=str(font.path))
    for key, (text, authored_size) in AUTHORED.items():
        size, width, overflowed = render_mod.fit_size(face, text, addresses.V1[key])
        assert not overflowed
        assert size >= authored_size - 0.5, f"{key}: shrank past the drafter's {authored_size} pt"
        assert size <= addresses.MAX_FONT_SIZE


def test_long_value_shrinks_but_still_fits(font):
    cell = addresses.V1["ime_objekta"]
    myriad = pymupdf.Font(fontfile=str(font.path))
    long_name = "Špilja u Čardačkoj dragi kod Đurđevca"
    size, width, overflowed = render_mod.fit_size(myriad, long_name, cell)
    assert size < addresses.MAX_FONT_SIZE
    assert width <= cell.width - 2 * addresses.SIDE_PADDING
    assert not overflowed
    short_size, _, _ = render_mod.fit_size(myriad, "Jama", cell)
    assert short_size == addresses.MAX_FONT_SIZE


def test_overflow_is_reported_not_hidden(font):
    cell = addresses.V1["mjerilo"]                 # the narrowest cell
    myriad = pymupdf.Font(fontfile=str(font.path))
    _size, _width, overflowed = render_mod.fit_size(myriad, "x" * 80, cell)
    assert overflowed


def test_croatian_diacritics_survive_the_round_trip(font):
    # ime_objekta, not ekipa: the Ekipa cell wraps a long list of names, and
    # what is under test here is the glyphs, not the line breaking.
    text = "Čćžšđ Dujmović, Mikičić, Milićević"
    data, _ = render_mod.render(addresses.BLANK_TEMPLATE,
                                {"ime_objekta": text}, font.path)
    assert text in _plain(pymupdf.open("pdf", data)[0].get_text())


def test_unknown_field_is_an_error(font):
    with pytest.raises(render_mod.RenderError, match="Unknown"):
        render_mod.render(addresses.BLANK_TEMPLATE, {"nema_takvog": "x"}, font.path)


def test_empty_values_leave_the_cell_blank(font):
    data, placed = render_mod.render(
        addresses.BLANK_TEMPLATE, {"ime_objekta": "Jama", "crtali": ""}, font.path
    )
    assert [p.key for p in placed] == ["ime_objekta"]
    assert set(_spans(data)) == {"ime_objekta"}


# ── prefill orchestration ────────────────────────────────────────────
class _Locality:
    def locate(self, x, y, sb_lokalitet=None, sb_najblize_mjesto=None):
        return LocalityFinding(
            zupanija="Istarska", grad_opcina="Lanišće",
            najblize_mjesto=sb_najblize_mjesto or "Računato Selo",
            najblize_mjesto_source="sb" if sb_najblize_mjesto else "geo-admin",
            lokalitet=sb_lokalitet or "Računati dolac",
            lokalitet_source="sb" if sb_lokalitet else "geo-rgi",
        )


class _Elevation:
    def kota(self, x, y):
        return ElevationFinding(elevation_m=505, source_label="DMV", tile_name="t.tif")


@pytest.fixture()
def run(tmp_path, monkeypatch, font):
    monkeypatch.setattr(prefill, "RUNS_DIR", tmp_path / "runs" / "sastavnica")
    monkeypatch.setattr(prefill.locality_mod, "build_finder",
                        lambda settings, **kw: _Locality())
    monkeypatch.setattr(prefill.elevation_mod, "build_finder",
                        lambda settings, **kw: _Elevation())
    monkeypatch.setattr(prefill, "_read_osz", lambda folder, result: {})
    return tmp_path


def test_prefill_from_sb_alone(settings, run):
    outcome = prefill.run_prefill(settings, 1)
    fields = outcome.result.fields

    assert outcome.result.cave_name == "Špilja Testovka"
    assert fields["ime_objekta"].value == "Špilja Testovka"
    assert fields["broj_plocice"].value == "T-01"
    assert fields["htrs"].value == "450123 5023456"
    # SB wins over the 505 m the grid computed, and 5 m is inside tolerance.
    assert fields["nadmorska_visina"].value == "500 m"
    assert fields["nadmorska_visina"].source == "sb"
    # Lokalitet + Najbliže mjesto, and nothing else (user, 2026-09-19).
    assert fields["lokacija"].value == "Testni kras, Testno Selo"
    # No zapisnik: SB's own dimensions carry the two cells it can.
    assert fields["stvarna_duljina"].value == "40 m"
    assert fields["dubina"].value == "-12 m"          # depth is signed
    # Only a zapisnik knows it — so the cell carries a stub, never nothing
    assert fields["tlocrtna_duljina"].value == addresses.STUB_UNKNOWN
    assert fields["tlocrtna_duljina"].source == "stub"
    assert fields["crtali"].value == "A. Anić"        # SB fallback, abbreviated
    assert fields["istrazili"].value == "SU Estavela"
    assert fields["istrazili"].source == "default"
    assert fields["datum"].value == "2015"
    assert outcome.pdf_path.exists()
    assert outcome.sidecar_path.exists()


def test_constant_cells_are_never_data_driven(settings, run):
    fields = prefill.run_prefill(settings, 1).result.fields
    assert fields["katastarski_broj"].value == "0000"
    assert fields["katastarski_broj"].source == "constant"
    assert fields["mjerilo"].value == "1:"
    # SB row 1 HAS a Katastarski broj SUE — the constant still wins, because
    # the archivist stamps the number into the PDF at the very end.
    assert prefill.run_prefill(settings, 1).result.sue_number == "001"


def test_zapisnik_wins_for_survey_facts(settings, run, monkeypatch):
    monkeypatch.setattr(prefill, "_read_osz", lambda folder, result: {
        "duljina": "44", "horizontalna_duljina": "31", "visinska_razlika": "-13,5",
        "crtali": "L. Kukuljan", "mjerili": "I. Dujmović", "mjerili_2": "M. Marić",
        "clanovi_ekipe": "A. Anić", "clanovi_ekipe_2": "I. Ivić",
        "istrazile_udruge": "SU Spelunka", "datum_istrazivanja": "10.12.2023.",
    })
    fields = prefill.run_prefill(settings, 1).result.fields
    assert fields["stvarna_duljina"].value == "44 m"        # not SB's 40
    assert fields["tlocrtna_duljina"].value == "31 m"
    assert fields["dubina"].value == "-13,5 m"              # already signed, kept
    assert fields["mjerili"].value == "I. Dujmović, M. Marić"   # already short
    assert fields["ekipa"].value == "A. Anić, I. Ivić"
    assert fields["istrazili"].value == "SU Spelunka"
    assert fields["datum"].value == "10.12.2023."
    assert all(fields[k].source == "osz" for k in
               ("stvarna_duljina", "tlocrtna_duljina", "mjerili", "ekipa", "datum"))


def test_row_without_coordinates_still_renders(settings, run):
    outcome = prefill.run_prefill(settings, 4)             # Đulin ponor mali: no X/Y
    fields = outcome.result.fields
    assert all(fields[key].source == "stub" for key in ("htrs", "nadmorska_visina"))
    assert fields["ime_objekta"].value == "Đulin ponor mali"
    assert fields["katastarski_broj"].value == "0000"
    assert any("koordinate" in note for note in outcome.result.notes)
    assert outcome.pdf_path.exists()


def test_unknown_serial_is_a_clean_error(settings, run):
    with pytest.raises(prefill.SastavnicaError, match="9999"):
        prefill.run_prefill(settings, 9999)


# ── the value formatters ─────────────────────────────────────────────
@pytest.mark.parametrize("raw, expected", [
    ("Dario Maršanić, Matija Vrkić", "D. Maršanić, M. Vrkić"),
    ("F.Karabaić", "F. Karabaić"),                  # already short, re-spaced
    ("A.Lipovac (SOV)", "A. Lipovac (SOV)"),        # the outside-society flag survives
    # A legacy citation in the author cell: not a person, so nothing is
    # abbreviated — the trailing initial just joins its surname.
    ("Malez, M. (1960)", "Malez M. (1960)"),
    ("", None),
])
def test_people_take_the_drafters_abbreviated_form(raw, expected):
    assert prefill._people(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("40", "40 m"), ("13,5", "13,5 m"), ("0", None), (None, None), ("oko 20", "oko 20"),
])
def test_length_formatting(raw, expected):
    assert prefill._metres(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("12", "-12 m"), ("-13,5", "-13,5 m"), ("0", None), ("nepoznato", "nepoznato"),
])
def test_depth_is_signed_downward(raw, expected):
    assert prefill._depth(raw) == expected


def test_elevation_is_rounded_to_whole_metres(settings, run, monkeypatch):
    """The DMV grid returns decimals (1285,92); a printed nacrt shows metres."""
    class _Precise:
        def kota(self, x, y):
            return ElevationFinding(elevation_m=1285.92, source_label="DMV",
                                    tile_name="t.tif")

    monkeypatch.setattr(prefill.elevation_mod, "build_finder",
                        lambda settings, **kw: _Precise())
    # Point the Z column at a header the fixture does not have, so the row
    # reads as "SB has no kota" and the computed value is what lands.
    no_z = dataclasses.replace(
        settings,
        sb_field_columns={**settings.sb_field_columns,
                          "entrance_elevation_m": "Nepostojeći stupac"},
    )
    outcome = prefill.run_prefill(no_z, 1)
    assert outcome.result.fields["nadmorska_visina"].value == "1286 m"
    assert outcome.result.fields["nadmorska_visina"].source == "dmv-dgu"
    # …and the unrounded value still leaves as a review row for SB.
    assert [u.value for u in outcome.result.sb_updates if u.column ==
            "Nepostojeći stupac"] == ["1285,92"]


# ── delivery ─────────────────────────────────────────────────────────
@pytest.fixture()
def drive(settings, tmp_path):
    """settings pointed at a fake Drive with the cave's intake leaf present."""
    root = tmp_path / "drive"
    leaf = root / "!Za digitalizirat" / "SB_1_Špilja Testovka"
    leaf.mkdir(parents=True)
    return dataclasses.replace(
        settings, local_drive_root=root,
        archive_dirs={"intake_dir": "!Za digitalizirat"},
    ), leaf


def test_delivers_into_the_intake_leaf(drive, run):
    settings, leaf = drive
    outcome = prefill.run_prefill(settings, 1)
    assert outcome.delivered_path == leaf / "SB_0001_sastavnica.pdf"
    assert outcome.delivered_path.exists()
    # Our own output is recognisable, so a re-run may replace it.
    assert prefill._is_ours(outcome.delivered_path)
    again = prefill.run_prefill(settings, 1)
    assert again.delivered_path == outcome.delivered_path


def test_refuses_to_overwrite_a_file_it_did_not_write(drive, run):
    settings, leaf = drive
    foreign = leaf / "SB_0001_sastavnica.pdf"
    doc = pymupdf.open()
    doc.new_page()
    foreign.write_bytes(doc.tobytes())

    outcome = prefill.run_prefill(settings, 1)
    assert outcome.delivered_path is None
    assert any("odbijena" in note for note in outcome.result.notes)
    assert prefill._is_ours(foreign) is False
    assert outcome.pdf_path.exists()          # the run copy is still the fallback

    forced = prefill.run_prefill(settings, 1, force=True)
    assert forced.delivered_path == foreign
    assert prefill._is_ours(foreign)


def test_local_only_skips_delivery(drive, run):
    settings, leaf = drive
    outcome = prefill.run_prefill(settings, 1, local_only=True)
    assert outcome.delivered_path is None
    assert not (leaf / "SB_0001_sastavnica.pdf").exists()
