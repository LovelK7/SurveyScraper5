"""The guest route (sastavnica/gost.py): a nacrt with no SB, no Drive, no OSZ."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("pymupdf")

import pymupdf

from cave_dossier.sastavnica import addresses, compose as compose_mod, fonts, gost
from cave_dossier.sastavnica.models import SastavnicaResult

MM = compose_mod.MM
A4 = compose_mod.A4_PORTRAIT_PT

# The SB 1103 KORAK 3 result (same as test_compose): both designs at 1:100.
DIMS = {
    "l": 10, "pl": 4, "nvr": 9, "pvr": 0, "calculated": True,
    "mjerilo": "1:100", "arrangement": "vertical",
    "plan_scale": 100, "profile_scale": 100,
    "profile_mm": {"x": 69.5, "y": 62.9, "width": 70.9, "height": 122.2},
    "plan_mm": {"x": 54.4, "y": 195.1, "width": 101.2, "height": 61.0},
}


def _design(path, width_mm, height_mm):
    doc = pymupdf.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    page.draw_rect(pymupdf.Rect(60 * MM, 90 * MM, (60 + width_mm) * MM,
                                (90 + height_mm) * MM), color=(0, 0, 0), width=0.5)
    doc.save(path)
    doc.close()


@pytest.fixture()
def root(tmp_path, monkeypatch):
    monkeypatch.setenv(gost.GOST_DIR_ENV, str(tmp_path / "gost"))
    return tmp_path / "gost"


@pytest.fixture()
def project(root):
    """A guest project that has been through KORAK 3b."""
    if not addresses.BLANK_TEMPLATE.exists():
        pytest.skip("blank template not built")
    try:
        fonts.resolve(None)
    except fonts.FontUnavailable as exc:
        pytest.skip(str(exc))
    folder = gost.create_project("Jama Gošća")
    _design(folder / "jama_plan.pdf", 100.0, 58.0)
    _design(folder / "jama_profile.pdf", 68.0, 120.0)
    (folder / "jama_dimenzije.json").write_text(json.dumps(DIMS), encoding="utf-8")
    return folder


# ── projects ─────────────────────────────────────────────────────────

def test_a_project_is_a_folder_named_after_the_cave(root):
    folder = gost.create_project("Jama: pod/Kukom?")
    assert folder.parent == root
    assert folder.name == "Jama pod Kukom"
    assert gost.load_data(folder) == {"ime_objekta": "Jama: pod/Kukom?"}


def test_a_second_project_of_the_same_name_never_reuses_the_folder(root):
    first = gost.create_project("Jama")
    second = gost.create_project("Jama")
    assert first != second and second.name == "Jama (2)"
    assert {p["id"] for p in gost.list_projects()} == {"Jama", "Jama (2)"}


def test_a_project_id_cannot_escape_the_root(root):
    gost.create_project("Jama")
    (root.parent / "outside").mkdir()
    for bad in ("../outside", "..", "Nema"):
        with pytest.raises(gost.GostError):
            gost.project_folder(bad)


def test_only_known_non_empty_cells_are_saved(root):
    folder = gost.create_project("Jama")
    saved = gost.save_data(folder, {"crtali": " Ana Kovač ", "datum": "",
                                    "nepoznato": "x", "dubina": None})
    assert saved == {"crtali": "Ana Kovač"}
    assert gost.load_data(folder) == saved


def test_a_hand_broken_data_file_is_not_fatal(root):
    folder = gost.create_project("Jama")
    (folder / gost.DATA_FILE).write_text("{ne json", encoding="utf-8")
    assert gost.load_data(folder) == {}


@pytest.mark.parametrize("raw, expected", [
    ("345678 4987654", (345678.0, 4987654.0)),
    ("X=345678, Y=4987654", (345678.0, 4987654.0)),
    ("4987654 345678", (345678.0, 4987654.0)),     # typed the other way round
    ("345678,5 4987654", (345678.5, 4987654.0)),
    ("45.3 14.4 12", None),
    ("", None),
])
def test_htrs_parsing(raw, expected):
    assert gost.parse_htrs(raw) == expected


# ── the field precedence ─────────────────────────────────────────────

def _fields(typed, measured=None):
    page = SastavnicaResult(serial=0, cave_name="x")
    gost.resolve_fields(page, typed, measured or {}, settings=None, offline=True,
                        font_path=None)
    return page


def test_typed_beats_measured_and_measured_fills_the_rest():
    page = _fields({"stvarna_duljina": "25", "dubina": "12"},
                   {"stvarna_duljina": "18 m", "tlocrtna_duljina": "16 m",
                    "dubina": "-5 m", "mjerilo": "1:200"})
    f = page.fields
    assert (f["stvarna_duljina"].value, f["stvarna_duljina"].source) == ("25 m", "ručno")
    assert f["dubina"].value == "-12 m"                 # a depth is signed
    assert (f["tlocrtna_duljina"].value, f["tlocrtna_duljina"].source) == ("16 m", "nacrt")
    assert f["mjerilo"].value == "1:200"


def test_people_are_abbreviated_and_ekipa_drops_the_credited():
    f = _fields({"crtali": "Ivan Horvat", "mjerili": "Ivan Horvat, Ana Kovač",
                 "ekipa": "Ivan Horvat, Ana Kovač, Marko Marić"}).fields
    assert f["crtali"].value == "I. Horvat"
    assert f["ekipa"].value == "M. Marić"


def test_nothing_is_left_empty_and_the_gaps_are_named():
    page = _fields({"ime_objekta": "Jama"})
    assert all(page.fields[key].value for key in addresses.V2)
    assert page.fields["katastarski_broj"].value == "0000"
    assert page.fields["htrs"].value == "?"
    assert any("Bez podatka" in note and "HTRS" in note for note in page.notes)


def test_a_typed_katastarski_broj_is_printed():
    assert _fields({"katastarski_broj": "HR-1234"}).fields["katastarski_broj"].value == "HR-1234"


def test_unparseable_htrs_is_printed_as_typed_with_a_note():
    page = _fields({"htrs": "negdje kod Ogulina"})
    assert page.fields["htrs"].value == "negdje kod Ogulina"
    assert any("HTRS" in note for note in page.notes)


# ── the composed nacrt ───────────────────────────────────────────────

def _logo_drawings(pdf_path):
    with pymupdf.open(pdf_path) as doc:
        page = doc[0]
        box = pymupdf.Rect(*gost.LOGO_BOX)
        drawings = [d for d in page.get_drawings() if box.contains(d["rect"])]
        images = page.get_images(full=True)
        return drawings, images


def test_the_nacrt_lands_in_the_project_folder(project):
    gost.save_data(project, {"ime_objekta": "Jama Gošća", "crtali": "Ana Kovač"})
    outcome = gost.run_gost_nacrt(project, None, offline=True)
    assert outcome.pdf_path == project / "Jama Gošća_nacrt.pdf"
    assert outcome.sidecar_path.parent == project
    fields = outcome.result.sastavnica.fields
    assert fields["stvarna_duljina"].value == "10 m"      # measured
    assert fields["crtali"].value == "A. Kovač"           # typed
    with pymupdf.open(outcome.pdf_path) as doc:
        text = doc[0].get_text().replace(" ", " ")
        assert "Jama Gošća" in text and "A. Kovač" in text
        assert doc.metadata["creator"] == gost.STAMP


def test_the_archive_logo_is_removed_and_the_border_kept(project):
    outcome = gost.run_gost_nacrt(project, None, offline=True)
    drawings, images = _logo_drawings(outcome.pdf_path)
    assert drawings == [] and images == []
    # The title block's frame still runs past the logo cell.
    with pymupdf.open(outcome.pdf_path) as doc:
        frame = [d for d in doc[0].get_drawings()
                 if d["rect"].x0 < gost.LOGO_BOX[0] and d["rect"].y1 > gost.LOGO_BOX[3]]
        assert frame


def test_the_guests_own_logo_takes_its_place(project):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 60), False)
    pix.set_rect(pix.irect, (200, 30, 30))
    pix.save(project / "Logo.PNG")
    outcome = gost.run_gost_nacrt(project, None, offline=True)
    _drawings, images = _logo_drawings(outcome.pdf_path)
    assert len(images) == 1


def test_an_edited_nacrt_is_not_overwritten_without_force(project):
    target = gost.run_gost_nacrt(project, None, offline=True).pdf_path
    doc = pymupdf.open()
    doc.new_page()
    doc.save(target)              # somebody's own PDF under our name
    doc.close()
    with pytest.raises(gost.GostError, match="--force"):
        gost.run_gost_nacrt(project, None, offline=True)
    assert gost.run_gost_nacrt(project, None, offline=True, force=True).pdf_path == target


def test_a_project_without_korak3_says_what_is_missing(root):
    folder = gost.create_project("Prazna")
    with pytest.raises(gost.ComposeError, match="KORAKA 3"):
        gost.run_gost_nacrt(folder, None, offline=True)
