"""M2 dossier skeleton: SB mapping, lifecycle, two-gate gating, report renderer.

Everything runs against the synthetic mini workbook (tests/fixtures) — the
real-data checks stay manual, via `cavedossier report` against the sandbox.
"""

from __future__ import annotations

import pytest

from cave_dossier.core.config import Settings
from cave_dossier.core.people import split_authors, split_person_names
from cave_dossier.dossier import (
    ArchiveFile,
    CaveDossier,
    FileRole,
    GateLevel,
    Georeference,
    IssueCode,
    LifecycleState,
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
    assert dossier.serial_number == 1          # "Redni broj" — the pre-SUE ID
    assert dossier.working_id == "001"         # once a SUE number exists, it wins
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


def test_society_bracket_is_a_flag_not_part_of_the_name() -> None:
    names, societies = split_authors("A.Lipovac (SOV), D.Reš")
    assert names == ["A.Lipovac", "D.Reš"]
    assert societies == {"A.Lipovac": "SOV"}
    # A year in brackets is a different animal — it stays glued to the name by
    # the initials rule, so it must not be mistaken for a society.
    assert split_person_names("Malez, M. (1960)") == ["Malez M. (1960)"]


def test_missing_coordinates_leave_georeference_none(
    reader: SBReader, settings: Settings
) -> None:
    assert _dossier(reader, settings, "Đulin ponor mali").georeference is None


# ── Lifecycle (mirrors SB's own Power Query views) ────────────────────


def test_lifecycle_sue_number_means_istrazeni(reader: SBReader, settings: Settings) -> None:
    dossier = _dossier(reader, settings, "Špilja Testovka")
    assert dossier.lifecycle is LifecycleState.ISTRAZENI
    assert dossier.is_queued is False


def test_lifecycle_queue_flag_means_za_istrazit(reader: SBReader, settings: Settings) -> None:
    dossier = _dossier(reader, settings, "Đulin ponor mali")
    assert dossier.lifecycle is LifecycleState.ZA_ISTRAZIT
    assert dossier.is_queued is True
    # No SUE number yet, so the Redni broj is the working ID.
    assert dossier.working_id == "4"
    assert dossier.queue_flag.old_number == "268"
    # "ponoviti" also matches the Nesređeni keyword list; SUE-then-queue order
    # decides, and the keyword hit is still recorded.
    assert "ponoviti" in dossier.nesredeni_keywords


def test_lifecycle_precedence_sue_beats_nesredeni_keyword() -> None:
    from cave_dossier.dossier import derive_lifecycle

    assert derive_lifecycle("570", False, True) is LifecycleState.ISTRAZENI
    assert derive_lifecycle(None, True, True) is LifecycleState.ZA_ISTRAZIT
    assert derive_lifecycle(None, False, True) is LifecycleState.NESREDENI
    assert derive_lifecycle(None, False, False) is LifecycleState.UNCLASSIFIED


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
    report = evaluate(_dossier(reader, settings, "Đulin ponor mali"))
    queue_notes = [i for i in report.issues if i.code is IssueCode.QUEUE_ITEM]
    assert len(queue_notes) == 1
    assert queue_notes[0].severity is Severity.WARNING


# ── Gating ────────────────────────────────────────────────────────────


def test_ungathered_sources_are_unchecked_not_failed(
    reader: SBReader, settings: Settings
) -> None:
    dossier = _dossier(reader, settings, "Špilja Testovka")
    report = evaluate(dossier)

    # SB-fed gate-1 rules all pass for this row; nothing SB-related may fail.
    assert [i.message for i in report.blockers_for(GateLevel.SUE)] == []
    # …but it is not ready: rules for the ungathered sources are pending.
    assert report.ready_sue is False
    # A rule reports the FIRST source it is missing, so the 2.1d photo rule
    # (ARCHIVE + PHOTOS) shows up under ARCHIVE — fix the archive first and it
    # re-reports as PHOTOS.
    assert {rule.source for rule in report.unchecked} == {
        Source.ARCHIVE,
        Source.SURVEY,
        Source.OSZ,
        Source.MAP,
    }


def test_sue_number_is_gate_2_only_never_gate_1(reader: SBReader, settings: Settings) -> None:
    """Gate 1 PRODUCES the SUE number, so requiring it there would be circular."""
    report = evaluate(_dossier(reader, settings, "Đulin ponor mali"))  # queue row, no SUE

    gate1 = {issue.label for issue in report.blockers_for(GateLevel.SUE)}
    gate2 = {issue.label for issue in report.blockers_for(GateLevel.CROSPELEO)}
    assert "Interni katastarski broj (SUE)" not in gate1
    assert "Interni katastarski broj (SUE)" in gate2


def test_missing_sb_mandatories_block_gate_1(reader: SBReader, settings: Settings) -> None:
    report = evaluate(_dossier(reader, settings, "Đulin ponor mali"))
    labels = {issue.label for issue in report.blockers_for(GateLevel.SUE)}
    assert "Dubina" in labels
    assert "Autori nacrta ili izvor" in labels  # renamed in the live workbook 2026-08-26
    assert "Lokalitet" in labels


def test_plaque_rule_is_year_conditional(reader: SBReader, settings: Settings) -> None:
    # 2021 exploration, no plaque in SB → hard blocker (Protokol §5.1).
    modern = evaluate(_dossier(reader, settings, "Ponor pod Kukom"))
    plaque = [i for i in modern.issues if i.code is IssueCode.MISSING_PLAQUE]
    assert [i.severity for i in plaque] == [Severity.BLOCKER]

    # Unknown year and no plaque → warning: an old cave can still earn a SUE
    # number without one.
    old = evaluate(_dossier(reader, settings, "Đulin ponor mali"))
    plaque = [i for i in old.issues if i.code is IssueCode.MISSING_PLAQUE]
    assert [i.severity for i in plaque] == [Severity.WARNING]


def test_coordinates_rule_is_year_conditional(reader: SBReader, settings: Settings) -> None:
    with_coordinates = evaluate(_dossier(reader, settings, "Špilja Testovka"))
    assert not [i for i in with_coordinates.issues if i.code is IssueCode.MISSING_COORDINATES]

    without = evaluate(_dossier(reader, settings, "Đulin ponor mali"))
    coordinates = [i for i in without.issues if i.code is IssueCode.MISSING_COORDINATES]
    assert [i.severity for i in coordinates] == [Severity.WARNING]  # unknown year


def test_a_fully_gathered_dossier_passes_both_gates() -> None:
    """The rule table must be satisfiable — otherwise nothing ever ships."""
    report = evaluate(_complete_dossier())
    assert report.unchecked == []
    assert [i.message for i in report.blockers] == []
    assert report.ready_sue is True
    assert report.ready_crospeleo is True


def test_gate_1_can_pass_while_gate_2_still_fails() -> None:
    """The everyday case: society-ready, not yet CroSpeleo-ready."""
    dossier = _complete_dossier()
    dossier.map_excerpt = None                      # isječak karte is CroSpeleo-only
    dossier.georeference.georef_record = None
    report = evaluate(dossier)
    assert report.ready_sue is True
    assert report.ready_crospeleo is False
    assert {i.label for i in report.blockers_for(GateLevel.CROSPELEO)} == {
        "Isječak karte",
        "Georef zapis",
    }


def test_missing_izjava_blocks_per_author() -> None:
    dossier = _complete_dossier()
    dossier.drawing_authors = ["Ana Anić", "Ivo Ivić"]  # only Ana has an izjava
    report = evaluate(dossier)
    statements = [i for i in report.issues if i.code is IssueCode.MISSING_STATEMENT]
    assert len(statements) == 1
    assert "Ivo Ivić" in statements[0].message
    assert report.ready_sue is False


def test_unprocessed_entrance_photos_are_flagged_for_2_1d() -> None:
    dossier = _complete_dossier()
    dossier.entrance_photos = [
        ArchiveFile(
            path=_p("IMG_5498.JPG"),  # camera name, never renamed
            role=FileRole.ENTRANCE_PHOTO,
            size_bytes=8_000_000,     # never downsized
        )
    ]
    report = evaluate(dossier)
    photo_notes = [i for i in report.issues if "2.1d" in (i.label or "")]
    assert len(photo_notes) == 1
    assert "budget" in photo_notes[0].message
    assert "not renamed" in photo_notes[0].message
    assert photo_notes[0].severity is Severity.WARNING  # hygiene, not a gate
    assert report.ready_sue is True


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


def test_render_shows_identity_lifecycle_and_both_gates(
    reader: SBReader, settings: Settings
) -> None:
    dossier = _dossier(reader, settings, "Špilja Testovka")
    evaluate(dossier)
    text = render(dossier)

    assert "Špilja Testovka (SUE 001)" in text
    assert "SB status: istraženi" in text
    assert "Gate 1 — katastarski broj (SUE): NOT READY" in text
    assert "Gate 2 — CroSpeleo: NOT READY" in text
    assert "not gathered yet" in text
    # 7-digit HTRS96 northings must not degrade to scientific notation.
    assert "5023456" in text


def _complete_dossier() -> CaveDossier:
    """A dossier with every source gathered and every mandatory field filled."""
    izjava = ArchiveFile(path=_p("Izjava_Ana Anić.pdf"), role=FileRole.STATEMENT_DRAWING_AUTHOR)
    return CaveDossier(
        gathered=set(Source),
        sb_row_number=3,
        object_name="Špilja Testovka",
        sue_number="001",
        lifecycle=LifecycleState.ISTRAZENI,
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
        osz_document=ArchiveFile(path=_p("001.docx"), role=FileRole.OSZ_DOCX),
        nacrt_pdfs=[ArchiveFile(path=_p("001.pdf"), role=FileRole.NACRT_PDF)],
        entrance_photos=[
            ArchiveFile(
                path=_p("001_Testovka_ulaz_AAnić.jpg"),
                role=FileRole.ENTRANCE_PHOTO,
                size_bytes=900_000,
            )
        ],
        entrance_photo_flag="DA",
        statement_files=[izjava],
        drawing_author_statement_files=[izjava],
        map_excerpt=ArchiveFile(path=_p("001_isjecak.png"), role=FileRole.MAP_EXCERPT),
    )


def _p(name: str):
    from pathlib import Path

    return Path("C:/tmp/arhiva") / name
