"""6P predaja: allocation, the Napomena rule, stamping, the guard and apply.

No Excel and no Drive: the SB write is a fake writer, the archive dirs are a
tmp tree, the Nacrt is a synthetic PDF built the way the sastavnica draws its
cell (label above, ``0000`` below), the OSZ is the real v10 template.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from cave_dossier.predaja import apply as apply_mod
from cave_dossier.predaja import plan as plan_mod
from cave_dossier.predaja import stamp
from cave_dossier.predaja.plan import (
    CellChange,
    DeliveryPlan,
    FileMove,
    allocate,
    napomena_after,
    photo_target,
    sequence_stats,
)

pymupdf = pytest.importorskip("pymupdf")

FONT_CANDIDATES = (r"C:\Windows\Fonts\micross.ttf", r"C:\Windows\Fonts\arial.ttf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _font() -> Path:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return Path(candidate)
    pytest.skip("no TrueType font on this machine")


# ── allocation ──────────────────────────────────────────────────────


def test_dense_sequence_proposes_next():
    stats = sequence_stats([1, 2.0, "3", None, float("nan"), ""])
    assert (stats["max"], stats["count"], stats["gaps"], stats["duplicates"]) == (3, 3, [], [])
    assert allocate(stats)[:2] == (4, "proposed")


@pytest.mark.parametrize("values, word", [([1, 2, 2], "dvostruki"), ([1, 3], "rupe"), ([1, "x"], "nečitljivo")])
def test_broken_sequence_refuses_to_propose(values, word):
    number, _source, issues = allocate(sequence_stats(values))
    assert number is None
    assert issues[0].severity == "blocker" and word in issues[0].text


def test_override_must_be_free():
    stats = sequence_stats([1, 2, 3])
    assert allocate(stats, 2)[0] is None
    number, source, issues = allocate(stats, 10)
    assert (number, source) == (10, "override") and issues[0].severity == "warning"
    # Confirming the proposal is not an override.
    assert allocate(stats, 4) == (4, "proposed", [])


# ── SB cells ────────────────────────────────────────────────────────


def test_napomena_queue_flag_becomes_ok():
    assert napomena_after("za istražit, 12, ispod ceste", "ispod ceste", True) == ("ok, ispod ceste", None)
    assert napomena_after("za istražit", None, True) == ("ok", None)
    assert napomena_after(None, None, False) == ("ok", None)
    assert napomena_after("ok, sudjelovanje", None, False) == (None, None)
    after, warning = napomena_after("skica", None, False)
    assert after is None and "skica" in warning


def test_photo_target_swaps_prefix():
    assert photo_target("SB_1234_Jama_LKukuljan_1.jpg", 1234, 7) == "007_Jama_LKukuljan_1.jpg"
    assert photo_target("SB_0968_Češki turist_NM_2.jpg", 968, 902) == "902_Češki turist_NM_2.jpg"


# ── stamping ────────────────────────────────────────────────────────


def _nacrt(path: Path, *, illustrator: bool = False, placeholders: int = 1) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((82, 48), "Katastarski broj:", fontsize=6)
    page.insert_text((90, 58), "0000", fontsize=10)
    for extra in range(placeholders - 1):
        page.insert_text((400, 600 + 20 * extra), "0000", fontsize=10)
    page.draw_rect(pymupdf.Rect(81, 41, 120, 61))
    if illustrator:
        doc.xref_set_key(page.xref, "PieceInfo", "<< /Illustrator << /LastModified (D:2026) >> >>")
    doc.save(path)
    return path


def _words(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [w[4] for w in doc[0].get_text("words")]


def test_stamp_pdf_replaces_placeholder_and_keeps_label(tmp_path):
    src = _nacrt(tmp_path / "SB_1234_nacrt.pdf")
    assert stamp.check_pdf(src, 902).status == "placeholder"
    stamp.stamp_pdf(src, tmp_path / "902.pdf", 902, _font())
    words = _words(tmp_path / "902.pdf")
    assert "902" in words and "0000" not in words
    assert "Katastarski" in words and "broj:" in words
    assert stamp.check_pdf(tmp_path / "902.pdf", 902).status == "already"


def test_stamp_pdf_strips_illustrator_artwork(tmp_path):
    src = _nacrt(tmp_path / "n.pdf", illustrator=True)
    assert stamp.check_pdf(src).illustrator
    stamp.stamp_pdf(src, tmp_path / "out.pdf", 15, _font())
    with pymupdf.open(tmp_path / "out.pdf") as doc:
        assert doc.xref_get_key(doc[0].xref, "PieceInfo")[0] == "null"
    assert "015" in _words(tmp_path / "out.pdf")


def test_stamp_pdf_picks_placeholder_nearest_the_label(tmp_path):
    src = _nacrt(tmp_path / "n.pdf", placeholders=2)
    stamp.stamp_pdf(src, tmp_path / "out.pdf", 902, _font())
    assert _words(tmp_path / "out.pdf").count("0000") == 1


def test_check_pdf_without_placeholder(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "nacrt bez sastavnice")
    doc.save(tmp_path / "n.pdf")
    assert stamp.check_pdf(tmp_path / "n.pdf", 5).status == "missing"
    with pytest.raises(stamp.StampError):
        stamp.stamp_pdf(tmp_path / "n.pdf", tmp_path / "out.pdf", 5, _font())


def _osz(tmp_path: Path) -> Path:
    pytest.importorskip("lxml")
    from cave_dossier.osz.prefill import TEMPLATE_PATH

    return Path(shutil.copy2(TEMPLATE_PATH, tmp_path / "SB_1234_OSZ.docx"))


def test_stamp_osz_fills_cell(tmp_path):
    from cave_dossier.osz.reader import read_osz_content

    src = _osz(tmp_path)
    assert stamp.stamp_osz(src, tmp_path / "902.docx", 902) is None
    assert read_osz_content(tmp_path / "902.docx").fields["katastarski_broj"] == "902"
    # Re-stamping the same number is a no-op; another number is refused.
    assert stamp.stamp_osz(tmp_path / "902.docx", tmp_path / "again.docx", 902) == "902"
    with pytest.raises(stamp.StampError):
        stamp.stamp_osz(tmp_path / "902.docx", tmp_path / "x.docx", 903)


# ── the in-session guard ────────────────────────────────────────────


class FakeSession:
    def __init__(self, column, row):
        self._column, self._row = column, row

    def column(self, header):
        return self._column

    def get(self, header):
        return self._row.get(header)


def _guard_plan(source="proposed"):
    return DeliveryPlan(serial=1234, state="ready", sue=4, sue_source=source, sb_changes=[
        CellChange("Katastarski broj SUE", None, 4, ""),
        CellChange("Napomena", "za istražit, x", "ok, x", ""),
    ])


def test_guard_passes_unchanged_row(settings):
    from cave_dossier.sb.safe_io import SBWriteRefused  # noqa: F401 — import check

    guard = apply_mod.sb_guard(_guard_plan(), settings)
    guard(FakeSession([1, 2, 3, None], {"Katastarski broj SUE": None, "Napomena": "za istražit,  x"}))


@pytest.mark.parametrize("column, row, word", [
    ([1, 2, 3, 4], {"Katastarski broj SUE": None, "Napomena": "za istražit, x"}, "zauzet"),
    ([1, 2, 3, 5], {"Katastarski broj SUE": None, "Napomena": "za istražit, x"}, "Sljedeći"),
    ([1, 2, 3], {"Katastarski broj SUE": 3, "Napomena": "za istražit, x"}, "već ima"),
    ([1, 2, 3], {"Katastarski broj SUE": None, "Napomena": "netko piše"}, "promijenio"),
])
def test_guard_refuses_moved_workbook(settings, column, row, word):
    from cave_dossier.sb.safe_io import SBWriteRefused

    with pytest.raises(SBWriteRefused, match=word):
        apply_mod.sb_guard(_guard_plan(), settings)(FakeSession(column, row))


# ── apply, end to end on a tmp "Drive" ──────────────────────────────


@pytest.fixture()
def drive(tmp_path, settings, monkeypatch):
    root = tmp_path / "drive"
    dirs = {"osz_dir": "!!Osnovni zapisnici", "drawings_dir": "!!Nacrti",
            "entry_photos_dir": "!!Fotografije ulaza", "intake_dir": "!Za digitalizirat",
            "arhiva_dir": "Arhiva"}
    for rel in dirs.values():
        (root / rel).mkdir(parents=True)
    leaf = root / dirs["intake_dir"] / "SB_1234_Jama"
    leaf.mkdir()
    _nacrt(leaf / "SB_1234_nacrt.pdf")
    osz = _osz(tmp_path)
    shutil.move(osz, leaf / "SB_1234_OSZ.docx")
    (leaf / "SB_1234_Jama_LK_1.jpg").write_bytes(b"jpeg")
    (leaf / "original.jpg").write_bytes(b"raw")
    runs = tmp_path / "runs"
    monkeypatch.setattr(plan_mod, "run_dir", lambda sue: runs / f"{sue:03d}")
    monkeypatch.setattr(apply_mod, "run_dir", lambda sue: runs / f"{sue:03d}")
    s = dataclasses.replace(settings, local_drive_root=root, archive_dirs=dirs, sb_mode="LIVE")
    return s, root, leaf, runs


def _plan(s, root, leaf) -> DeliveryPlan:
    plan = DeliveryPlan(serial=1234, name="Jama", state="ready", sue=7, sue_source="proposed",
                        leaf=str(leaf), material={"nacrt": {"stamp": {"illustrator": False}}})
    plan.moves = [
        FileMove("osz", str(leaf / "SB_1234_OSZ.docx"), str(root / "!!Osnovni zapisnici" / "007.docx"), True),
        FileMove("nacrt", str(leaf / "SB_1234_nacrt.pdf"), str(root / "!!Nacrti" / "007.pdf"), True),
        FileMove("foto", str(leaf / "SB_1234_Jama_LK_1.jpg"), str(root / "!!Fotografije ulaza" / "007_Jama_LK_1.jpg")),
        FileMove("leaf", str(leaf), str(root / "Arhiva" / "007_Jama")),
    ]
    plan.sb_changes = [CellChange("Katastarski broj SUE", None, 7, ""), CellChange("Napomena", None, "ok", "")]
    return plan


def test_apply_files_everything_and_moves_leaf(drive):
    from cave_dossier.osz.reader import read_osz_content

    s, root, leaf, runs = drive
    written = {}

    def writer(settings, plan, cells):
        written.update(cells)
        return {k: None for k in cells}, "sb.backup.xlsm"

    out = apply_mod.apply_plan(s, _plan(s, root, leaf), expected_sue=7, sb_writer=writer, font_path=_font())
    assert written == {"Katastarski broj SUE": 7, "Napomena": "ok"}
    assert "007" in _words(root / "!!Nacrti" / "007.pdf")
    assert read_osz_content(root / "!!Osnovni zapisnici" / "007.docx").fields["katastarski_broj"] == "007"
    assert (root / "!!Fotografije ulaza" / "007_Jama_LK_1.jpg").read_bytes() == b"jpeg"
    archived = root / "Arhiva" / "007_Jama"
    assert not leaf.exists() and (archived / "original.jpg").is_file()
    # The archived leaf says the same as the archive.
    assert read_osz_content(archived / "SB_1234_OSZ.docx").fields["katastarski_broj"] == "007"
    manifest = json.loads((runs / "007" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["steps"][-1]["step"] == "gotovo" and out.sb_backup == "sb.backup.xlsm"


def test_apply_refuses_another_number(drive):
    s, root, leaf, _runs = drive
    with pytest.raises(apply_mod.DeliveryError, match="osvježi"):
        apply_mod.apply_plan(s, _plan(s, root, leaf), expected_sue=8, sb_writer=None)


def test_sb_refusal_leaves_drive_untouched(drive):
    from cave_dossier.sb.safe_io import SBWriteRefused

    s, root, leaf, runs = drive

    def writer(settings, plan, cells):
        raise SBWriteRefused("Broj 7 je u međuvremenu zauzet.")

    with pytest.raises(apply_mod.DeliveryError, match="SB nije promijenjen"):
        apply_mod.apply_plan(s, _plan(s, root, leaf), expected_sue=7, sb_writer=writer, font_path=_font())
    assert leaf.is_dir() and not any((root / "!!Nacrti").iterdir())
    assert "0000" in _words(leaf / "SB_1234_nacrt.pdf")
    steps = json.loads((runs / "007" / "manifest.json").read_text(encoding="utf-8"))["steps"]
    assert steps[-1]["status"] == "failed"


def test_target_appearing_after_review_stops_filing(drive):
    s, root, leaf, _runs = drive
    (root / "!!Nacrti" / "007.pdf").write_bytes(b"someone else's")
    with pytest.raises(apply_mod.DeliveryError, match="rezerviran"):
        apply_mod.apply_plan(s, _plan(s, root, leaf), expected_sue=7,
                             sb_writer=lambda *a: ({}, None), font_path=_font())
    assert (root / "!!Nacrti" / "007.pdf").read_bytes() == b"someone else's"
    assert leaf.is_dir()


def test_not_ready_plan_is_refused(drive):
    s, root, leaf, _runs = drive
    plan = _plan(s, root, leaf)
    plan.block("Nema fotografije.")
    with pytest.raises(apply_mod.DeliveryError, match="Nema fotografije"):
        apply_mod.apply_plan(s, plan, expected_sue=7, sb_writer=lambda *a: ({}, None))


# ── the SUE gate (6P's own; 5D judges CroSpeleo only) ───────────────


def _sb_dossier(**over):
    from cave_dossier.dossier import CaveDossier, Georeference

    fields = dict(object_name="Jama", locality="Mlake", nearest_place="Klana",
                  exploration_period="2026", drawing_authors=["F.Karabaić"], depth_m=13,
                  plaque_number="051-869", georeference=Georeference(x_htrs=338316, y_htrs=5037330))
    fields.update(over)
    return CaveDossier(**fields)


def test_sue_gate_needs_no_izjava():
    """User, 2026-10-22: izjave are a CroSpeleo requirement, never a SUE one."""
    from cave_dossier.predaja.gate import sue_issues

    # An author with no izjava anywhere – and nothing to say about it.
    assert sue_issues(_sb_dossier()) == []


def test_sue_gate_sb_fields_and_dubina():
    from cave_dossier.predaja.gate import sue_issues

    issues = sue_issues(_sb_dossier(locality=None, drawing_authors=[], depth_m=None))
    texts = " | ".join(t for _s, t in issues)
    assert all(s == "blocker" for s, _t in issues)
    assert "Lokalitet" in texts and "Autori nacrta" in texts and "Dubina" in texts
    # Dubina in the zapisnik is enough: delivery fills SB from it.
    assert not [t for _s, t in sue_issues(_sb_dossier(depth_m=None), {"dubina": "13"}) if "Dubina" in t]


def test_sue_gate_plaque_and_coordinates_follow_5_1():
    from cave_dossier.predaja.gate import sue_issues

    modern = sue_issues(_sb_dossier(plaque_number=None, georeference=None))
    assert [s for s, _t in modern] == ["blocker", "blocker"]
    old = sue_issues(_sb_dossier(plaque_number=None, exploration_period="1968"))
    assert [s for s, _t in old] == ["warning"]
    # A kaverna needs no pločica (ticked in the zapisnik).
    assert sue_issues(_sb_dossier(plaque_number=None), {}, ("kaverna",)) == []
