"""Workbook-wide audits (`sb audit-authors`, `sb unclassified`) and the 2.1d
staged-photo matcher.

The photo tests use synthetic filenames modelled on the real staging folder:
free-form names, some carrying a plaque number, some an old Za-istražit broj
that the v3.0 renumbering made stale.
"""

from __future__ import annotations

from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.photos import CaveCandidate, build_candidates, match_photos
from cave_dossier.sb.audit import audit_authors, audit_unclassified
from cave_dossier.sb.loader import SBReader


# ── sb audit-authors ──────────────────────────────────────────────────


def test_audit_flags_the_cells_a_human_must_look_at(
    reader: SBReader, settings: Settings
) -> None:
    by_name = {f.object_name: f for f in audit_authors(reader, settings)}

    # "Malez, M. (1960)" is a literature source, not a survey author.
    assert "citation" in by_name["Pećina žedna"].flags
    # "/" means nobody.
    assert "placeholder" in by_name["Đulin ponor mali"].flags
    # "Renata" — a bare first name, unresolvable to a person.
    assert "single_name" in by_name["Jama bez broja"].flags
    # A clean cell must not be reported at all.
    assert "Ponor pod Kukom" not in by_name


def test_audit_records_the_parsed_result_next_to_the_raw_cell(
    reader: SBReader, settings: Settings
) -> None:
    finding = next(f for f in audit_authors(reader, settings) if f.object_name == "Pećina žedna")
    assert finding.raw == "Malez, M. (1960)"
    assert finding.parsed == ["Malez M. (1960)"]
    assert finding.serial_number is None or isinstance(finding.serial_number, int)


# ── sb unclassified ───────────────────────────────────────────────────


def test_unclassified_finds_rows_in_none_of_the_three_views(
    reader: SBReader, settings: Settings
) -> None:
    rows = audit_unclassified(reader, settings)
    assert [row.object_name for row in rows] == ["Jama bez broja"]
    assert rows[0].locality == "Testni kras"


# ── 2.1d staged-photo matcher ─────────────────────────────────────────


def _candidates() -> list[CaveCandidate]:
    from cave_dossier.core.normalization import normalize_lookup_key

    def make(serial, name, sue=None, plaque=None, old=None):
        return CaveCandidate(serial, name, sue, plaque, old, normalize_lookup_key(name))

    return [
        make(954, "Podbudišinac", old="478"),
        make(955, "Puhalica kod Breškog dola", old="479"),
        make(1035, "Sik Šits", plaque="051-550"),
        make(811, "Possibile Grotta", sue="811", plaque="051 418"),
        make(879, "Poljička Kosa"),
    ]


def test_stale_old_queue_prefix_is_replaced_by_redni_broj() -> None:
    match = match_photos([Path("478_Podbudišinac_SKnaus.jpg")], _candidates())[0]
    assert match.cave.serial_number == 954
    # Name AND old number agree — the strongest signal available.
    assert match.confidence == "high"
    assert match.proposed_name == "954_Podbudišinac_SKnaus.jpg"


def test_old_number_alone_still_resolves() -> None:
    match = match_photos([Path("479 (1).jpg")], _candidates())[0]
    assert match.cave.serial_number == 955
    assert match.stale_prefix == "479"
    assert match.proposed_name == "955_(1).jpg"


def test_plaque_number_is_not_mistaken_for_a_stale_prefix() -> None:
    """`051-550_…` starts with a number that belongs to the plaque, not a queue broj."""
    match = match_photos([Path("051-550_Goli breg 4.jpg")], _candidates())[0]
    assert match.cave.object_name == "Sik Šits"
    assert match.stale_prefix is None
    assert match.proposed_name == "1035_051-550_Goli breg 4.jpg"


def test_plaque_with_a_space_matches_and_corroborates_the_name() -> None:
    match = match_photos([Path("Possibile Grotta_13 ulaz 051 418 (1 of 1).jpg")], _candidates())[0]
    assert match.confidence == "high"
    assert match.cave.serial_number == 811


def test_free_form_name_match() -> None:
    match = match_photos([Path("Poljička Kosa_SKnaus_246165741_n.jpg")], _candidates())[0]
    assert match.cave.serial_number == 879
    assert match.proposed_name.startswith("879_")


def test_conflicting_evidence_proposes_nothing() -> None:
    """A plaque pointing one way and a name the other is a finding, not a rename."""
    match = match_photos([Path("051-550_Podbudišinac.jpg")], _candidates())[0]
    assert match.confidence == "conflict"
    assert match.conflict_with is not None
    assert match.proposed_name is None


def test_already_correct_prefix_is_left_alone() -> None:
    match = match_photos([Path("954_Podbudišinac_SKnaus.jpg")], _candidates())[0]
    assert match.already_correct is True
    assert match.proposed_name is None


def test_unmatched_file_is_reported_not_guessed() -> None:
    match = match_photos([Path("ak 47.jpg")], _candidates())[0]
    assert match.cave is None
    assert match.confidence == "none"
    assert match.proposed_name is None


def test_build_candidates_reads_redni_broj(reader: SBReader, settings: Settings) -> None:
    candidates = {c.object_name: c for c in build_candidates(reader, settings)}
    assert candidates["Špilja Testovka"].plaque_number == "T-01"
    assert candidates["Đulin ponor mali"].old_queue_number == "268"


def test_synonym_matches_as_readily_as_the_name() -> None:
    """`051-550_Goli breg 4.jpg` is Sik Šits — "Goli breg 4" is its synonym."""
    from cave_dossier.core.normalization import normalize_lookup_key

    sik = CaveCandidate(
        1035, "Sik Šits", None, "051-550", None,
        normalize_lookup_key("Sik Šits"),
        (normalize_lookup_key("Goli breg 4"),),
    )
    match = match_photos([Path("Goli breg 4_ulaz.jpg")], [sik])[0]
    assert match.cave.serial_number == 1035
    assert "sinonim" in match.evidence


def test_exact_short_key_matches_where_a_substring_would_be_too_generic() -> None:
    """"ak 47.jpg" → AK-47: too short to hunt for inside a name, exact is safe."""
    from cave_dossier.core.normalization import normalize_lookup_key

    ak = CaveCandidate(770, "AK-47", None, None, None, normalize_lookup_key("AK-47"))
    assert match_photos([Path("ak 47.jpg")], [ak])[0].cave.serial_number == 770
    # The same key inside a longer filename stays unmatched — that is the point.
    assert match_photos([Path("neka jama ak 47 blizu.jpg")], [ak])[0].cave is None


def test_manual_mapping_wins_over_everything() -> None:
    """"Jama GB 1" is Goli breg 1 — an abbreviation no evidence can reach."""
    from cave_dossier.core.normalization import normalize_lookup_key

    goli = CaveCandidate(812, "Goli breg 1", None, None, None, normalize_lookup_key("Goli breg 1"))
    match = match_photos([Path("Jama GB 1.jpg")], [goli], {"Jama GB 1": 812})[0]
    assert match.cave.serial_number == 812
    assert match.confidence == "high"
    assert match.proposed_name == "812_Jama GB 1.jpg"


# ── Lifecycle: sudjelovanje ───────────────────────────────────────────


def test_participation_is_its_own_state() -> None:
    from cave_dossier.dossier import LifecycleState, derive_lifecycle
    from cave_dossier.dossier.sb_mapper import is_participation

    assert is_participation("ok, sudjelovanje") is True
    assert is_participation("ok") is False
    assert derive_lifecycle(None, False, False, True) is LifecycleState.SUDJELOVANJE
    # Outstanding work outranks provenance.
    assert derive_lifecycle(None, False, True, True) is LifecycleState.NESREDENI
    # A SUE number still wins over everything.
    assert derive_lifecycle("570", False, True, True) is LifecycleState.ISTRAZENI
