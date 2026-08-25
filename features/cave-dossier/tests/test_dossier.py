"""M2 dossier skeleton: SB mapping, gating, and the report renderer.

Everything runs against the synthetic mini workbook (tests/fixtures) — the
real-data checks stay manual, via `cavedossier report` against the sandbox.
"""

from __future__ import annotations

import pytest

from cave_dossier.core.config import Settings
from cave_dossier.core.people import split_person_names
from cave_dossier.dossier import (
    ArchiveFile,
    CaveDossier,
    FileRole,
    Georeference,
    IssueCode,
    Severity,
    Source,
    SurveyResult,
    build_from_sb,
    evaluate,
    parse_queue_flag,
    render,
)
from cave_dossier.sb.loader import SBReader


def _dossier(reader: SBReader, settings: Settings, query: str) -> CaveDossier:
    matches = reader.find_caves(query)
    assert len(matches) == 1, f"{query!r} must resolve to exactly one row"
    return build_from_sb(matches[0], settings)


# ── SB → dossier mapping ──────────────────────────────────────────────


def test_sb_mapping_fills_every_configured_column(reader: SBReader, settings: Settings) -> None:
    dossier = _dossier(reader, settings, "Špilja Testovka")

    assert dossier.sb_row_number == 3
    assert dossier.object_name == "Špilja Testovka"
    assert dossier.sue_number == "001"
    assert dossier.plaque_number == "T-01"
    assert dossier.marker_value == "unesen"
    assert dossier.crospeleo_round == "1. krug"
    assert dossier.synonyms == ["Testovka mala"]
    assert dossier.locality == "Testni kras"
    assert dossier.nearest_place == "Testno Selo"
    assert dossier.length_m == 40
    assert dossier.depth_m == 12
    assert dossier.exploration_period == "2015"
    assert dossier.last_exploration_year == "2015"
    assert dossier.entrance_photo_flag == "DA"
    assert dossier.note == "ok"
    assert dossier.georeference is not None
    assert (dossier.georeference.x_htrs, dossier.georeference.y_htrs) == (450123.0, 5023456.0)
    assert dossier.georeference.z_m == 500
    assert dossier.has(Source.SB)
    # Sources nobody has gathered yet must stay unmarked.
    assert not dossier.has(Source.ARCHIVE)


def test_sb_mapping_splits_authors_and_drops_placeholders(
    reader: SBReader, settings: Settings
) -> None:
    assert _dossier(reader, settings, "Jama Čavlić").drawing_authors == ["Ivo Ivić", "Ana Anić"]
    # "/" means "no author" in SB, not an author called "/".
    assert _dossier(reader, settings, "Đulin ponor mali").drawing_authors == []
    # Surname-first legacy form must not tear into two people.
    assert _dossier(reader, settings, "Pećina žedna").drawing_authors == ["Malez M. (1960)"]


def test_missing_coordinates_leave_georeference_none(
    reader: SBReader, settings: Settings
) -> None:
    assert _dossier(reader, settings, "Đulin ponor mali").georeference is None


# ── Queue flag (SB v3.0 Napomena) ─────────────────────────────────────


@pytest.mark.parametrize(
    ("note", "queued", "old_number", "parsed_note"),
    [
        ("za istražit, 268, dužina 13 m", True, "268", "dužina 13 m"),
        # The old Broj is optional — Ponor Gotovž has none.
        ("za istražit, detalji u literaturi", True, None, "detalji u literaturi"),
        ("Za Istražit, 42, ", True, "42", None),
        ("za istražit", True, None, None),
        ("ok", False, None, None),
        (None, False, None, None),
    ],
)
def test_parse_queue_flag(
    note: str | None, queued: bool, old_number: str | None, parsed_note: str | None
) -> None:
    flag = parse_queue_flag(note)
    assert flag.queued is queued
    assert flag.old_number == old_number
    assert flag.note == parsed_note


def test_queue_row_reports_a_context_warning(reader: SBReader, settings: Settings) -> None:
    dossier = _dossier(reader, settings, "Đulin ponor mali")
    assert dossier.queue_flag.queued is True
    assert dossier.queue_flag.old_number == "268"

    report = evaluate(dossier)
    queue_notes = [i for i in report.issues if i.code is IssueCode.QUEUE_ITEM]
    assert len(queue_notes) == 1
    assert queue_notes[0].severity is Severity.WARNING


# ── Gating ────────────────────────────────────────────────────────────


def test_ungathered_sources_are_unchecked_not_failed(
    reader: SBReader, settings: Settings
) -> None:
    dossier = _dossier(reader, settings, "Špilja Testovka")
    report = evaluate(dossier)

    # SB-fed rules all pass for this row; nothing SB-related may fail.
    assert [i.message for i in report.blockers] == []
    # …but the dossier is not ready: rules for the four ungathered sources
    # are pending, and several of them can block.
    assert report.ready is False
    assert {rule.source for rule in report.unchecked} == {
        Source.ARCHIVE,
        Source.SURVEY,
        Source.OSZ,
        Source.MAP,
    }
    assert report.unchecked_blocking


def test_missing_sb_mandatories_block(reader: SBReader, settings: Settings) -> None:
    report = evaluate(_dossier(reader, settings, "Đulin ponor mali"))
    labels = {issue.label for issue in report.blockers}
    assert "Interni katastarski broj objekta u udruzi" in labels  # no SUE on queue rows
    assert "Dubina" in labels
    assert "Autori nacrta" in labels


def test_plaque_rule_is_year_conditional(reader: SBReader, settings: Settings) -> None:
    # 2021 exploration, no plaque in SB → hard blocker (Protokol §5.1).
    modern = evaluate(_dossier(reader, settings, "Ponor pod Kukom"))
    plaque = [i for i in modern.issues if i.code is IssueCode.MISSING_PLAQUE]
    assert [i.severity for i in plaque] == [Severity.BLOCKER]

    # 1960 exploration has a plaque, so no issue at all; the queue row has
    # neither plaque nor a modern year → warning, never a blocker.
    old = evaluate(_dossier(reader, settings, "Đulin ponor mali"))
    plaque = [i for i in old.issues if i.code is IssueCode.MISSING_PLAQUE]
    assert [i.severity for i in plaque] == [Severity.WARNING]


def test_coordinates_rule_is_year_conditional(reader: SBReader, settings: Settings) -> None:
    with_coordinates = evaluate(_dossier(reader, settings, "Špilja Testovka"))
    assert not [i for i in with_coordinates.issues if i.code is IssueCode.MISSING_COORDINATES]

    without = evaluate(_dossier(reader, settings, "Đulin ponor mali"))
    coordinates = [i for i in without.issues if i.code is IssueCode.MISSING_COORDINATES]
    assert [i.severity for i in coordinates] == [Severity.WARNING]  # unknown year


def test_a_fully_gathered_dossier_can_be_ready() -> None:
    """The rule table must be satisfiable — otherwise nothing ever ships."""
    dossier = _complete_dossier()
    report = evaluate(dossier)
    assert report.unchecked == []
    assert [i.message for i in report.blockers] == []
    assert report.ready is True


def test_missing_izjava_blocks_per_author() -> None:
    dossier = _complete_dossier()
    dossier.drawing_authors = ["Ana Anić", "Ivo Ivić"]  # only Ana has an izjava
    report = evaluate(dossier)
    statements = [i for i in report.issues if i.code is IssueCode.MISSING_STATEMENT]
    assert len(statements) == 1
    assert "Ivo Ivić" in statements[0].message
    assert report.ready is False


def test_survey_dimensions_win_over_sb() -> None:
    dossier = CaveDossier(length_m=18, depth_m=11)
    assert dossier.effective_depth_m() == 11
    # Vertikalna razlika falls back to depth when nobody measured it.
    assert dossier.effective_vertical_difference_m() == 11

    dossier.survey = SurveyResult(length_m=21.5, depth_m=13.2, vertical_difference_m=12.0)
    assert dossier.effective_depth_m() == 13.2
    assert dossier.effective_vertical_difference_m() == 12.0


def test_negative_dimension_is_treated_as_invalid() -> None:
    dossier = _complete_dossier()
    dossier.survey = SurveyResult(horizontal_length_m=-5, vertical_difference_m=3)
    report = evaluate(dossier)
    assert any("negative" in issue.message for issue in report.blockers)


# ── Report renderer ───────────────────────────────────────────────────


def test_render_shows_identity_sources_and_verdict(
    reader: SBReader, settings: Settings
) -> None:
    dossier = _dossier(reader, settings, "Špilja Testovka")
    evaluate(dossier)
    text = render(dossier)

    assert "Špilja Testovka (SUE 001)" in text
    assert "NOT READY" in text
    assert "not gathered yet" in text
    # 7-digit HTRS96 northings must not degrade to scientific notation.
    assert "5023456" in text


def _complete_dossier() -> CaveDossier:
    """A dossier with every source gathered and every mandatory field filled."""
    izjava = ArchiveFile(path=_p("Izjava_Ana Anić.pdf"), role=FileRole.STATEMENT_DRAWING_AUTHOR)
    return CaveDossier(
        gathered={Source.SB, Source.ARCHIVE, Source.SURVEY, Source.OSZ, Source.MAP},
        sb_row_number=3,
        object_name="Špilja Testovka",
        sue_number="001",
        plaque_number="T-01",
        locality="Testni kras",
        nearest_place="Testno Selo",
        exploration_period="2015",
        drawing_authors=["Ana Anić"],
        depth_m=12,
        georeference=Georeference(
            x_htrs=450123.0,
            y_htrs=5023456.0,
            source="GPS",
            georef_record="HTRS96/TM 450123, 5023456",
        ),
        survey=SurveyResult(length_m=40, depth_m=12, horizontal_length_m=38, vertical_difference_m=12),
        origin_of_name="po obližnjem selu",
        location_access_text="Od ceste 200 m uz padinu.",
        object_type="jama",
        hydrogeological_function="nepoznata",
        hydrological_characteristic="suh objekt",
        technical_description="Vertikala 12 m, dvorana na dnu.",
        future_exploration_perspective="nema perspektive",
        recorder="Ana Anić",
        team_members=["Ana Anić", "Ivo Ivić"],
        organizations=["SU Testni"],
        entrance_width_m=1.2,
        entrance_height_or_length_m=0.8,
        osz_document=ArchiveFile(path=_p("001_Zapisnik.docx"), role=FileRole.OSZ_DOCX),
        nacrt_pdfs=[ArchiveFile(path=_p("001_Nacrt.pdf"), role=FileRole.NACRT_PDF)],
        entrance_photos=[ArchiveFile(path=_p("001_ulaz.jpg"), role=FileRole.ENTRANCE_PHOTO)],
        entrance_photo_flag="DA",
        statement_files=[izjava],
        drawing_author_statement_files=[izjava],
        map_excerpt=ArchiveFile(path=_p("001_isjecak.png"), role=FileRole.MAP_EXCERPT),
    )


def _p(name: str):
    from pathlib import Path

    return Path("C:/tmp/arhiva") / name
