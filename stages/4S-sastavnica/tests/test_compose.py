"""Composing the cSurvey Nacrt — plan + profile onto the sastavnica page.

The rule the whole step exists to keep is **true scale**: each design was
printed by cSurvey at a fixed 1:100 / 1:200 / …, so a 50 mm-wide feature on a
source page must still measure 50 mm on the composed sheet. Everything else
here — the centring, the refusals, the two-line Mjerilo — protects that rule or
the title block beside it.

Sources are built synthetically with PyMuPDF (a rectangle plus a label at a
known place per design), so the geometry is checked on every machine. One live
test composes the real SB 1103 outputs when the Drive leaf holds them.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

pytest.importorskip("pymupdf")

import pymupdf

from cave_dossier.geo.models import ElevationFinding, LocalityFinding
from cave_dossier.sastavnica import (
    addresses,
    compose as compose_mod,
    fonts,
    nacrt as nacrt_mod,
    prefill,
    render as render_mod,
)
from cave_dossier.sastavnica.compose import ComposeError, Layout

MM = compose_mod.MM
A4 = compose_mod.A4_PORTRAIT_PT

# The SB 1103 layout, as KORAK 3 actually produced it: both designs at 1:100,
# profile on top of the plan in the band below the title block.
LAYOUT_JSON = {
    "l": 10, "pl": 4, "nvr": 9, "pvr": 1, "drop": 10, "es": "2",
    "calculated": True, "cave": "GOLOBREŠKA_NANOEKSPEDICIJA",
    "mjerilo": "1:100", "arrangement": "vertical",
    "plan_scale": 100, "profile_scale": 100,
    "profile_mm": {"x": 69.5, "y": 62.9, "width": 70.9, "height": 122.2},
    "plan_mm": {"x": 54.4, "y": 195.1, "width": 101.2, "height": 61.0},
}


# ── synthetic source pages ───────────────────────────────────────────

def design_pdf(path, *, width_mm, height_mm, at=(60.0, 90.0), label="1"):
    """One A4 page with a `width_mm x height_mm` rectangle and a label.

    Shaped like what "Microsoft Print to PDF" leaves: a single page, the
    drawing somewhere on it, nothing else. `at` is the drawing's top-left in
    millimetres, so the ink bbox is never the page and the crop has to work.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    rect = pymupdf.Rect(at[0] * MM, at[1] * MM,
                        (at[0] + width_mm) * MM, (at[1] + height_mm) * MM)
    page.draw_rect(rect, color=(0, 0, 0), width=0.5)
    page.insert_text((rect.x0 + 2, rect.y1 - 2), label, fontsize=6)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture()
def font():
    if not addresses.BLANK_TEMPLATE.exists():
        pytest.skip("blank template not built (template-workbench/tools/build_blank.py)")
    try:
        return fonts.resolve(None)
    except fonts.FontUnavailable as exc:
        pytest.skip(str(exc))


@pytest.fixture()
def sastavnica_page(font):
    """A rendered title block, exactly what the composer is handed."""
    data, _placed = render_mod.render(
        addresses.BLANK_TEMPLATE,
        {"ime_objekta": "Testna jama", "mjerilo": "1:100"}, font.path)
    return data


@pytest.fixture()
def designs(tmp_path):
    """A plan and a profile that fit the SB 1103 layout with room to spare."""
    plan = design_pdf(tmp_path / "cave_plan.pdf", width_mm=100.0, height_mm=58.0)
    profile = design_pdf(tmp_path / "cave_profile.pdf", width_mm=68.0,
                         height_mm=120.0)
    return plan, profile


def layout_of(**overrides):
    data = {**LAYOUT_JSON, **overrides}
    return Layout.from_mapping(data)


def ink_of(path):
    with pymupdf.open(path) as doc:
        return compose_mod.ink_bbox(doc[0])


def placed_xobjects(data: bytes):
    """Every XObject on the composed page, as (name, rect).

    `show_pdf_page` inserts each source page as a Form XObject whose rect is
    where it landed, so comparing that rect against the ink is what proves the
    drawing was translated and not resized.
    """
    page = pymupdf.open("pdf", data)[0]
    return [(name, pymupdf.Rect(rect))
            for _xref, name, _n, rect in page.get_xobjects()]


# ── the ink bbox ─────────────────────────────────────────────────────

def test_ink_bbox_is_the_drawing_not_the_page(tmp_path):
    path = design_pdf(tmp_path / "d.pdf", width_mm=50.0, height_mm=30.0,
                      at=(70.0, 100.0))
    ink = ink_of(path)
    width_mm, height_mm = ink.mm()
    # the label sticks out by a hair; the rectangle is what dominates
    assert width_mm == pytest.approx(50.0, abs=1.0)
    assert height_mm == pytest.approx(30.0, abs=1.0)
    assert ink.x0 / MM == pytest.approx(70.0, abs=1.0)


def test_an_empty_page_is_refused(tmp_path):
    doc = pymupdf.open()
    doc.new_page(width=A4[0], height=A4[1])
    path = tmp_path / "blank.pdf"
    doc.save(path)
    doc.close()
    with pymupdf.open(path) as opened:
        with pytest.raises(ComposeError, match="prazna"):
            compose_mod.ink_bbox(opened[0])


# ── placement ────────────────────────────────────────────────────────

def test_each_drawing_lands_centred_on_its_reserved_rectangle(designs):
    plan, profile = designs
    placed = compose_mod.placements(plan, profile, layout_of())
    by_design = {item.design: item for item in placed}
    for design in ("plan", "profile"):
        item = by_design[design]
        want_x, want_y = item.reserved.centre
        got_x, got_y = item.target.centre
        assert abs(got_x - want_x) / MM < 0.5
        assert abs(got_y - want_y) / MM < 0.5
        # and the target is the ink's own size — nothing is resized
        assert item.target.width == pytest.approx(item.ink.width)
        assert item.target.height == pytest.approx(item.ink.height)


def test_the_profile_is_the_primary_drawing_and_comes_first(designs):
    plan, profile = designs
    placed = compose_mod.placements(plan, profile, layout_of())
    assert [item.design for item in placed] == ["profile", "plan"]
    assert placed[0].target.y0 < placed[1].target.y0


def test_an_oversize_drawing_is_refused_rather_than_shrunk(tmp_path, designs):
    plan, _profile = designs
    # a profile far wider than its 70.9 mm rectangle, well past the 5 mm slack
    profile = design_pdf(tmp_path / "wide_profile.pdf", width_mm=110.0,
                         height_mm=120.0)
    with pytest.raises(ComposeError) as raised:
        compose_mod.placements(plan, profile, layout_of())
    message = str(raised.value)
    assert "Profil" in message and "110" in message and "70.9" in message
    assert "--layout" in message           # says what to do about it


def test_a_drawing_inside_the_padding_slack_is_accepted(tmp_path, designs):
    """The reserved rectangle carries pad_m on every side; 3 mm over is fine."""
    plan, _profile = designs
    profile = design_pdf(tmp_path / "snug.pdf", width_mm=73.0, height_mm=120.0)
    placed = compose_mod.placements(plan, profile, layout_of())
    assert placed[0].ink_mm[0] == pytest.approx(73.0, abs=1.0)


def test_a_drawing_that_would_cross_the_title_block_is_refused(designs):
    plan, profile = designs
    # push the profile's rectangle up into the block
    bad = layout_of(profile_mm={"x": 69.5, "y": 20.0, "width": 70.9,
                                "height": 122.2})
    with pytest.raises(ComposeError, match="sastavnicu|margina"):
        compose_mod.placements(plan, profile, bad)


def test_a_drawing_outside_the_page_margin_is_refused(designs):
    plan, profile = designs
    bad = layout_of(plan_mm={"x": 150.0, "y": 195.1, "width": 101.2,
                             "height": 61.0})
    with pytest.raises(ComposeError, match="margina"):
        compose_mod.placements(plan, profile, bad)


def test_overlapping_drawings_are_refused(designs):
    plan, profile = designs
    bad = layout_of(plan_mm={"x": 54.4, "y": 100.0, "width": 101.2,
                             "height": 61.0})
    with pytest.raises(ComposeError, match="preklapaju"):
        compose_mod.placements(plan, profile, bad)


def test_a_layout_without_placements_says_so():
    data = {k: v for k, v in LAYOUT_JSON.items() if k != "plan_mm"}
    with pytest.raises(ComposeError, match="plan_mm"):
        Layout.from_mapping(data)


# ── the composed page ────────────────────────────────────────────────

def test_nothing_is_rescaled(sastavnica_page, designs):
    """A 100 mm drawing is 100 mm of paper — the whole point of a fixed scale."""
    plan, profile = designs
    data = compose_mod.compose_nacrt(sastavnica_page, plan, profile, layout_of())
    boxes = [box for _name, box in placed_xobjects(data)]
    # The blank template carries an XObject of its own, so look for each
    # drawing's own size rather than counting.
    for source in (plan, profile):
        want_w, want_h = ink_of(source).mm()
        assert any(abs(box.width / MM - want_w) < 0.05
                   and abs(box.height / MM - want_h) < 0.05 for box in boxes), (
            f"{source.name}: no {want_w:.1f} x {want_h:.1f} mm placement on the page"
        )


def test_the_title_block_survives_untouched(sastavnica_page, designs):
    plan, profile = designs
    block = pymupdf.Rect(*addresses.BLOCK)
    before = pymupdf.open("pdf", sastavnica_page)[0].get_text(clip=block)
    data = compose_mod.compose_nacrt(sastavnica_page, plan, profile, layout_of())
    after = pymupdf.open("pdf", data)[0].get_text(clip=block)
    assert after == before
    assert "Testna jama" in after


def test_the_composed_page_stays_a4_portrait(sastavnica_page, designs):
    plan, profile = designs
    data = compose_mod.compose_nacrt(sastavnica_page, plan, profile, layout_of())
    page = pymupdf.open("pdf", data)[0]
    assert page.rect.width == pytest.approx(A4[0], abs=0.1)
    assert page.rect.height == pytest.approx(A4[1], abs=0.1)


def test_a_missing_source_file_is_named(tmp_path, designs):
    plan, _profile = designs
    with pytest.raises(ComposeError, match="Nema datoteke"):
        compose_mod.placements(plan, tmp_path / "gone.pdf", layout_of())


# ── finding the inputs in the leaf ───────────────────────────────────

def _leaf_with_korak3(tmp_path, stem="Cave-1p", *, dimensions=None):
    leaf = tmp_path / "SB_1103_Cave"
    leaf.mkdir(exist_ok=True)
    design_pdf(leaf / f"{stem}_plan.pdf", width_mm=100.0, height_mm=58.0)
    design_pdf(leaf / f"{stem}_profile.pdf", width_mm=68.0, height_mm=120.0)
    (leaf / f"{stem}_dimenzije.json").write_text(
        json.dumps(dimensions if dimensions is not None else LAYOUT_JSON),
        encoding="utf-8")
    return leaf


def test_the_trio_is_found_by_stem(tmp_path):
    leaf = _leaf_with_korak3(tmp_path)
    found = compose_mod.find_inputs(leaf)
    assert found.stem == "Cave-1p"
    assert found.plan.name == "Cave-1p_plan.pdf"
    assert found.dimensions.name == "Cave-1p_dimenzije.json"


def test_a_half_finished_leaf_is_refused(tmp_path):
    leaf = _leaf_with_korak3(tmp_path)
    (leaf / "Cave-1p_profile.pdf").unlink()
    with pytest.raises(ComposeError, match="KORAKA 3"):
        compose_mod.find_inputs(leaf)


def test_two_runs_never_mix(tmp_path):
    """A plan of one run and a profile of another must not compose together."""
    leaf = _leaf_with_korak3(tmp_path, stem="Old")
    design_pdf(leaf / "New_plan.pdf", width_mm=100.0, height_mm=58.0)
    found = compose_mod.find_inputs(leaf)
    assert found.stem == "Old"            # the only COMPLETE trio


def test_pad_m_is_recovered_from_the_finisher_sidecar(tmp_path):
    leaf = _leaf_with_korak3(tmp_path)
    (leaf / "Cave-1p_lt_fin.layout.json").write_text(
        json.dumps({"pad_m": 0.25}), encoding="utf-8")
    found = compose_mod.find_inputs(leaf)
    assert compose_mod.read_pad_m(found.layout_sidecar) == 0.25
    assert compose_mod.read_pad_m(None) is None
    layout = Layout.from_mapping(LAYOUT_JSON,
                                 pad_m=compose_mod.read_pad_m(found.layout_sidecar))
    assert layout.pad_m == 0.25
    # and the default when neither source says
    assert Layout.from_mapping(LAYOUT_JSON).pad_m == compose_mod.DEFAULT_PAD_M


# ── the two-line Mjerilo ─────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("profil/tlocrt: 1:200/1:100", ["profil 1:200", "tlocrt 1:100"]),
    ("profil/tlocrt: 1:250/1:200", ["profil 1:250", "tlocrt 1:200"]),
    ("1:100", ["1:100"]),
    ("1:", ["1:"]),                       # the Illustrator route's stub
    ("", [""]),
])
def test_mjerilo_splits_only_when_it_is_two_values(text, expected):
    assert render_mod.split_lines("mjerilo", text) == expected


def test_no_other_cell_ever_splits():
    two_value = "profil/tlocrt: 1:200/1:100"
    for key in addresses.V1:
        if key in render_mod.MULTILINE:
            continue
        assert render_mod.split_lines(key, two_value) == [two_value]


def _mjerilo_spans(data: bytes):
    cell = addresses.V1["mjerilo"]
    page = pymupdf.open("pdf", data)[0]
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["size"] < 6:
                    continue              # a template label
                mid_x = (span["bbox"][0] + span["bbox"][2]) / 2
                mid_y = (span["bbox"][1] + span["bbox"][3]) / 2
                if cell.x0 <= mid_x <= cell.x1 and cell.y0 <= mid_y <= cell.y1:
                    spans.append(span)
    return sorted(spans, key=lambda s: s["bbox"][1])


def test_two_value_mjerilo_renders_two_lines_inside_the_cell(font):
    data, placed = render_mod.render(
        addresses.BLANK_TEMPLATE, {"mjerilo": "profil/tlocrt: 1:200/1:100"},
        font.path)
    spans = _mjerilo_spans(data)
    assert [span["text"] for span in spans] == ["profil 1:200", "tlocrt 1:100"]
    cell = addresses.V1["mjerilo"]
    for span in spans:
        x0, y0, x1, y1 = span["bbox"]
        assert cell.y0 < y0 and y1 < cell.y1, "a line touches a cell rule"
        assert cell.x0 <= x0 and x1 <= cell.x1
        # centred, like every other value in this template
        assert abs((x0 + x1) / 2 - cell.centre_x) < 0.5
    assert spans[0]["bbox"][3] <= spans[1]["bbox"][1] + 0.1, "the lines overlap"
    # one record per cell, carrying the tightest line
    record = next(p for p in placed if p.key == "mjerilo")
    assert record.text == "profil/tlocrt: 1:200/1:100"
    assert record.font_size < addresses.MAX_FONT_SIZE


def test_single_value_mjerilo_is_unchanged(font):
    """The Illustrator route's cell must render exactly as it does today."""
    one, _ = render_mod.render(addresses.BLANK_TEMPLATE, {"mjerilo": "1:500"},
                               font.path)
    spans = _mjerilo_spans(one)
    assert len(spans) == 1
    assert spans[0]["text"] == "1:500"
    assert spans[0]["size"] == pytest.approx(addresses.MAX_FONT_SIZE)
    # the one-line rule: baseline a constant lift above the cell's bottom rule
    baseline = addresses.V1["mjerilo"].y1 - addresses.BASELINE_LIFT
    assert spans[0]["origin"][1] == pytest.approx(baseline, abs=0.01)


# ── the dimensions JSON as a field source ────────────────────────────

class _Locality:
    def locate(self, x, y, sb_lokalitet=None, sb_najblize_mjesto=None):
        return LocalityFinding(
            zupanija="Istarska", grad_opcina="Lanišće",
            najblize_mjesto=sb_najblize_mjesto or "Selo",
            najblize_mjesto_source="sb", lokalitet=sb_lokalitet or "Dolac",
            lokalitet_source="sb")


class _Elevation:
    def kota(self, x, y):
        return ElevationFinding(elevation_m=505, source_label="DMV",
                                tile_name="t.tif")


@pytest.fixture()
def wired(tmp_path, monkeypatch, font):
    monkeypatch.setattr(prefill, "RUNS_DIR", tmp_path / "runs" / "sastavnica")
    monkeypatch.setattr(prefill.locality_mod, "build_finder",
                        lambda settings, **kw: _Locality())
    monkeypatch.setattr(prefill.elevation_mod, "build_finder",
                        lambda settings, **kw: _Elevation())
    monkeypatch.setattr(prefill, "_read_osz", lambda folder, result: {
        "duljina": "44", "horizontalna_duljina": "31", "visinska_razlika": "-13,5",
    })
    return tmp_path


@pytest.fixture()
def drive(settings, tmp_path):
    """settings pointed at a fake Drive whose leaf holds the KORAK 3 trio."""
    root = tmp_path / "drive"
    leaf = root / "!Za digitalizirat" / "SB_1_Špilja Testovka"
    leaf.mkdir(parents=True)
    design_pdf(leaf / "Cave-1p_plan.pdf", width_mm=100.0, height_mm=58.0)
    design_pdf(leaf / "Cave-1p_profile.pdf", width_mm=68.0, height_mm=120.0)
    (leaf / "Cave-1p_dimenzije.json").write_text(json.dumps(LAYOUT_JSON),
                                                 encoding="utf-8")
    return dataclasses.replace(
        settings, local_drive_root=root,
        archive_dirs={"intake_dir": "!Za digitalizirat"},
    ), leaf


def test_the_measured_numbers_outrank_the_zapisnik_and_sb(drive, wired):
    settings, _leaf = drive
    fields = prefill.run_prefill(settings, 1, use_dimensions=True).result.fields
    assert fields["stvarna_duljina"].value == "10 m"     # not the zapisnik's 44
    assert fields["tlocrtna_duljina"].value == "4 m"     # not 31
    assert fields["dubina"].value == "-9/+1 m"           # not -13,5
    assert fields["mjerilo"].value == "1:100"            # not the "1:" stub
    assert all(fields[k].source == "nacrt" for k in
               ("stvarna_duljina", "tlocrtna_duljina", "dubina", "mjerilo"))


def test_the_sastavnica_command_is_untouched(drive, wired):
    """Same cave, same leaf, WITHOUT use_dimensions: today's behaviour exactly."""
    settings, _leaf = drive
    fields = prefill.run_prefill(settings, 1).result.fields
    assert fields["stvarna_duljina"].value == "44 m"     # the zapisnik's
    assert fields["mjerilo"].value == "1:"               # decision 3's stub
    assert fields["mjerilo"].source == "constant"


def test_a_cave_without_korak3_falls_back_and_says_so(settings, wired, tmp_path):
    root = tmp_path / "bare"
    (root / "!Za digitalizirat" / "SB_1_Špilja Testovka").mkdir(parents=True)
    bare = dataclasses.replace(
        settings, local_drive_root=root,
        archive_dirs={"intake_dir": "!Za digitalizirat"})
    outcome = prefill.run_prefill(bare, 1, use_dimensions=True)
    assert outcome.result.fields["stvarna_duljina"].value == "44 m"
    assert outcome.result.dimensions_source is None
    assert any("dimenzije.json" in note for note in outcome.result.notes)


@pytest.mark.parametrize("nvr, pvr, expected", [
    (9, 1, "-9/+1 m"),
    (9, 0, "-9 m"),
    (9, None, "-9 m"),
    (0, 3, "+3 m"),                 # a cave that only goes up
    (0, 0, None),
    (None, None, None),
])
def test_depth_from_the_speleometrics(nvr, pvr, expected, font):
    measuring = prefill._measuring_font(font.path)
    assert prefill._drop(nvr, pvr, measuring) == expected


@pytest.mark.parametrize("nvr, pvr, expected", [
    (123, 45, "-123/+45 m"),        # shrinks to 8 pt and is still worth showing
    (1234, 5678, "-1234 m"),        # would only fit at the 6 pt floor
])
def test_the_combined_drop_is_dropped_when_it_stops_being_legible(
        nvr, pvr, expected, font):
    """The cell is 43 pt wide; below MIN_COMBINED_SIZE the depth alone, at the
    authored 10 pt, reads better than both numbers squeezed to the floor."""
    assert prefill._drop(nvr, pvr, prefill._measuring_font(font.path)) == expected


# ── the command ──────────────────────────────────────────────────────

def test_run_nacrt_composes_delivers_and_records(drive, wired, monkeypatch):
    settings, leaf = drive
    outcome = nacrt_mod.run_nacrt(settings, 1)

    assert outcome.delivered_path == leaf / "SB_0001_nacrt.pdf"
    assert outcome.delivered_path.exists()
    assert outcome.pdf_path.exists() and outcome.sidecar_path.exists()
    # the sastavnica itself is NOT delivered on this route — the nacrt is
    assert not (leaf / "SB_0001_sastavnica.pdf").exists()

    result = outcome.result
    assert result.mjerilo == "1:100" and result.arrangement == "vertical"
    assert sorted(d.design for d in result.drawings) == ["plan", "profile"]
    assert result.inputs == ["Cave-1p_plan.pdf", "Cave-1p_profile.pdf",
                             "Cave-1p_dimenzije.json"]
    assert result.sastavnica.fields["stvarna_duljina"].value == "10 m"
    sidecar = json.loads(outcome.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["drawings"][0]["scale"] == 100

    # its own stamp: a nacrt and a sastavnica must not replace each other
    assert prefill._is_ours(outcome.delivered_path, nacrt_mod.STAMP)
    assert not prefill._is_ours(outcome.delivered_path, prefill.STAMP)
    again = nacrt_mod.run_nacrt(settings, 1)
    assert again.delivered_path == outcome.delivered_path


def test_run_nacrt_refuses_to_overwrite_a_file_it_did_not_write(drive, wired):
    settings, leaf = drive
    foreign = leaf / "SB_0001_nacrt.pdf"
    doc = pymupdf.open()
    doc.new_page()
    foreign.write_bytes(doc.tobytes())

    outcome = nacrt_mod.run_nacrt(settings, 1)
    assert outcome.delivered_path is None
    assert any("odbijena" in note for note in outcome.result.notes)
    assert outcome.pdf_path.exists()          # the run copy is the fallback

    forced = nacrt_mod.run_nacrt(settings, 1, force=True)
    assert forced.delivered_path == foreign


def test_run_nacrt_local_only_keeps_the_run_copy(drive, wired):
    settings, leaf = drive
    outcome = nacrt_mod.run_nacrt(settings, 1, local_only=True)
    assert outcome.delivered_path is None
    assert not (leaf / "SB_0001_nacrt.pdf").exists()
    assert outcome.pdf_path.exists()


def test_run_nacrt_refuses_a_leaf_without_korak3(settings, wired, tmp_path):
    root = tmp_path / "bare"
    (root / "!Za digitalizirat" / "SB_1_Špilja Testovka").mkdir(parents=True)
    bare = dataclasses.replace(
        settings, local_drive_root=root,
        archive_dirs={"intake_dir": "!Za digitalizirat"})
    with pytest.raises(ComposeError, match="KORAKA 3"):
        nacrt_mod.run_nacrt(bare, 1)


# ── the real SB 1103 outputs ─────────────────────────────────────────

def _live_leaf():
    try:
        from cave_dossier.core.config import load_settings
        from cave_dossier.intake.scanner import find_cave_leaf

        settings = load_settings()
        if not settings.local_drive_root:
            return None
        subdir = settings.archive_dirs.get("intake_dir")
        root = settings.local_drive_root / subdir if subdir else None
        if root is None or not root.is_dir():
            return None
        leaf = find_cave_leaf(root, 1103)
        if leaf is None:
            return None
        compose_mod.find_inputs(leaf)
        return leaf
    except Exception:       # noqa: BLE001 - no Drive, no live test
        return None


LIVE_LEAF = _live_leaf()

live = pytest.mark.skipif(
    LIVE_LEAF is None,
    reason="SB 1103's KORAK 3 outputs are not in the Drive leaf on this machine")


@live
def test_sb1103_composes_at_true_scale(sastavnica_page):
    """The acceptance check from brief §3.3: a 5 m bar measures 50 mm at 1:100."""
    found = compose_mod.find_inputs(LIVE_LEAF)
    dims = compose_mod.read_dimensions(found.dimensions)
    layout = Layout.from_mapping(dims,
                                 pad_m=compose_mod.read_pad_m(found.layout_sidecar))
    data = compose_mod.compose_nacrt(sastavnica_page, found.plan, found.profile,
                                     layout)
    assert len(data) < 500_000

    page = pymupdf.open("pdf", data)[0]
    bars = [d["rect"] for d in page.get_drawings(extended=True)
            if d.get("rect") is not None and d["rect"].height < 6
            and 130 < d["rect"].width < 155]
    assert bars, "the horizontal scale bar is not on the composed page"
    assert max(bar.width for bar in bars) / MM == pytest.approx(50.0, abs=0.2)

    # the title block is still readable text, not covered by a drawing
    block = pymupdf.Rect(*addresses.BLOCK)
    assert "Testna jama" in page.get_text(clip=block)
