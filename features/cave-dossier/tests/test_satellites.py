"""The SB ↔ satellite hub: lifecycle, join keys, and the three review lists.

The rules under test are the ones that cost real mistakes to learn — a rejected
LIDAR point must never link to the cave 20 m away, a local row number is never a
key, and `LiDAR Kristal N` is a placeholder that must not be written back to the
sheet as if it were a name. Design: docs/sb-liburnija-hub.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cave_dossier.satellites import liburnija, resolver, sync
from cave_dossier.satellites.model import CandidateState, LinkStatus

HEADER = (
    "name,x,y,z,vjerojatnost,provjereno (1/0),provjerio,datum provjere,"
    "speleo_obj (1/0),istrazeno (1/0),Istražili,Naziv_novi,Naziv_stari,Br.pl,"
    "Komentar,Zapisnik,Nacrt,Foto ulaza"
)

# One row per lifecycle state, plus the cases that have bitten: a rejected point
# sitting next to a real cave, a joint trip, a field find with a text id.
SHEET_CSV = "\n".join(
    [
        HEADER,
        # confirmed, unexplored, no plaque -> the "add to SB" case
        "10,321883,5024617,900,visoka,1,Tin,10/10/2024,1,,,,,,otvor u pukotini,FALSE,FALSE,FALSE",
        # confirmed, explored, plaque -> links into SB
        "43,321860,5024370,1021,niska,1,Dino,21/10/2024,1,1,SUE,,,051-742,,TRUE,TRUE,FALSE",
        # checked and rejected, 3 m from cave 43 -> must NOT link to anything
        "44,321863,5024370,1021,niska,1,Dino,21/10/2024,0,,,,,,nije objekt,FALSE,FALSE,FALSE",
        # nobody has been there
        "50,321000,5024000,800,srednja,0,,,,,,,,,,FALSE,FALSE,FALSE",
        # another society explored it, and SB has no row -> stays out
        "60,322000,5025000,700,visoka,1,Dino,01/02/2025,1,1,SUS,Tuđa jama,,,,FALSE,FALSE,FALSE",
        # joint trip, already in SB -> scope must not break the link
        "61,322100,5025100,700,visoka,1,Dino,01/02/2025,1,1,\"Karsterra, SUE\",Zajednička,,051-900,,FALSE,FALSE,FALSE",
        # named confirmed cave, unexplored, no key -> add with name + synonym
        "70,323000,5026000,650,visoka,1,Tin,03/03/2025,1,,,Guštićeva jama,,,lijep ulaz,FALSE,FALSE,FALSE",
        # a field find: text id, so the LiDAR Kristal convention cannot reach it
        "Špiljkotina,323500,5026500,600,nije na Lidaru,1,Tin,04/03/2025,1,,,Špiljkotina,,,dva kanalića,FALSE,FALSE,FALSE",
        # blank filler, as the real export carries 240 of
        ",,,,,,,,,,,,,,,,,",
    ]
)


def _record(
    serial: int,
    name: str,
    *,
    plaque: str | None = None,
    synonyms: tuple[str, ...] = (),
    sue: str | None = None,
    x: float | None = None,
    y: float | None = None,
    note: str | None = None,
    nacrt: str | None = None,
    zapisnik: str | None = None,
    photo: str | None = None,
) -> resolver.SBRecord:
    kristal = tuple(
        match.group(1).lstrip("0")
        for field in (name, *synonyms)
        for match in resolver.KRISTAL_RE.finditer(field)
    )
    return resolver.SBRecord(
        serial_number=serial,
        name=name,
        synonyms=synonyms,
        plaque=plaque,
        sue_number=sue,
        x=x,
        y=y,
        note=note,
        nacrt_link=nacrt,
        zapisnik_link=zapisnik,
        photo_flag=photo,
        kristal_numbers=kristal,
    )


RECORDS = [
    _record(
        1257, "LiDAR Kristal 43", plaque="051-742", x=321860, y=5024370,
        note="za istražit, LiDAR", nacrt="843", zapisnik="843", photo="DA",
    ),
    _record(823, "Zajednička", plaque="051-900", x=322100, y=5025100, sue="512"),
    _record(914, "Jama kod Anđeli", x=323000, y=5026003),
]


def _rows(tmp_path: Path) -> list[liburnija.SheetRow]:
    path = tmp_path / "sheet.csv"
    path.write_text(SHEET_CSV, encoding="utf-8")
    return liburnija.load(path)


def _by_id(resolutions: list[resolver.Resolution]) -> dict[str, resolver.Resolution]:
    return {item.row.row_id: item for item in resolutions}


# ── the reader and the lifecycle ───────────────────────────────────


def test_blank_filler_rows_are_not_rows(tmp_path: Path) -> None:
    assert len(_rows(tmp_path)) == 8


def test_the_four_states_come_from_two_flags(tmp_path: Path) -> None:
    rows = {row.row_id: row for row in _rows(tmp_path)}
    assert rows["50"].state is CandidateState.UNCHECKED
    assert rows["44"].state is CandidateState.NOT_A_CAVE
    assert rows["10"].state is CandidateState.TO_EXPLORE
    assert rows["43"].state is CandidateState.EXPLORED
    # Only the last two are entitled to an SB row — the crossing rule.
    assert [r.state.is_cave for r in (rows["50"], rows["44"], rows["10"], rows["43"])] == [
        False, False, True, True,
    ]


def test_a_text_id_carries_no_kristal_number(tmp_path: Path) -> None:
    rows = {row.row_id: row for row in _rows(tmp_path)}
    assert rows["43"].kristal_name == "LiDAR Kristal 43"
    assert rows["Špiljkotina"].kristal_number is None
    assert rows["Špiljkotina"].kristal_name is None


def test_a_joint_trip_still_counts_as_ours(tmp_path: Path) -> None:
    """`Karsterra, SUE` is a list — membership decides, not the first name."""
    rows = {row.row_id: row for row in _rows(tmp_path)}
    assert rows["61"].is_own_society
    assert not rows["60"].is_own_society
    assert rows["10"].is_own_society  # unexplored: the column is simply empty


# ── the resolver ───────────────────────────────────────────────────


def test_a_rejected_point_never_links_to_the_cave_beside_it(tmp_path: Path) -> None:
    """Row 44 is 3 m from cave 43 and was checked to be no cave at all.

    This is the guard that killed 10 of 17 coordinate proposals on live data.
    """
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS, use_coordinates=True))
    assert resolved["44"].status is LinkStatus.NOT_A_CAVE
    assert resolved["44"].record is None
    assert resolved["50"].status is LinkStatus.UNCHECKED


def test_plaque_links_and_the_kristal_synonym_corroborates(tmp_path: Path) -> None:
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS))
    match = resolved["43"]
    assert match.status is LinkStatus.LINKED
    assert match.record.serial_number == 1257
    assert match.key == "plaque"
    assert "sinonim" in match.evidence  # both keys agreed


def test_two_keys_that_disagree_produce_a_conflict_not_a_choice(tmp_path: Path) -> None:
    records = [
        _record(1257, "Nešto drugo", plaque="051-742"),
        _record(999, "LiDAR Kristal 43"),
    ]
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), records))
    assert resolved["43"].status is LinkStatus.CONFLICT
    assert resolved["43"].record is None


def test_scope_decides_adding_not_linking(tmp_path: Path) -> None:
    """Another society's cave stays out of SB — unless SB already has it.

    Row 60 is SUS's and unknown to SB, so it is out of scope. Row 61 is a joint
    trip that SB already carries: dropping that link would stop syncing a row
    that exists.
    """
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS))
    assert resolved["60"].status is LinkStatus.OUT_OF_SCOPE
    assert resolved["61"].status is LinkStatus.LINKED
    assert resolved["61"].record.serial_number == 823


def test_a_confirmed_cave_nothing_reaches_is_a_candidate(tmp_path: Path) -> None:
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS))
    assert resolved["10"].status is LinkStatus.CANDIDATE
    assert resolved["70"].status is LinkStatus.CANDIDATE


def test_coordinates_link_only_when_close_and_unambiguous(tmp_path: Path) -> None:
    rows = _rows(tmp_path)
    near = _record(914, "Jama kod Anđeli", x=323000, y=5026003)      # 3 m from row 70
    far = _record(915, "Nešto podalje", x=323000, y=5026012)         # 12 m — review band
    rival = _record(916, "Susjed", x=323000, y=5026010)              # 10 m — ambiguity

    auto = _by_id(resolver.resolve_rows(rows, [near], use_coordinates=True))["70"]
    assert auto.status is LinkStatus.LINKED and auto.key == "coordinate"

    review = _by_id(resolver.resolve_rows(rows, [far], use_coordinates=True))["70"]
    assert review.status is LinkStatus.CONFLICT  # inside 15 m, outside 5 m

    ambiguous = _by_id(resolver.resolve_rows(rows, [near, rival], use_coordinates=True))["70"]
    assert ambiguous.status is LinkStatus.CONFLICT
    assert ambiguous.rival is not None


def test_coordinates_are_off_unless_asked_for(tmp_path: Path) -> None:
    near = _record(914, "Jama kod Anđeli", x=323000, y=5026003)
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), [near]))
    assert resolved["70"].status is LinkStatus.CANDIDATE


def test_a_local_row_number_is_never_a_key(tmp_path: Path) -> None:
    """SB `Redni broj` 43 exists and has nothing to do with sheet row 43."""
    trap = _record(43, "Neka posve druga jama")
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), [trap]))
    assert resolved["43"].status is LinkStatus.CANDIDATE


# ── the three lists ────────────────────────────────────────────────


def test_a_nameless_candidate_becomes_lidar_kristal_n(tmp_path: Path) -> None:
    rows = {row.row_id: row for row in _rows(tmp_path)}
    new = sync.new_sb_row(rows["10"], 1314)
    assert new.values["Ime objekta"] == "LiDAR Kristal 10"
    assert new.values["Sinonimi"] == ""
    # The queue flag SB's own Power Query files it under "Za istražit" by.
    assert new.values["Napomena"].startswith("za istražit,")
    assert new.values["Autori nacrta ili izvor"] == "Tin"   # the finder, not an author
    assert new.warning is None


def test_a_named_candidate_keeps_its_name_and_carries_the_synonym(tmp_path: Path) -> None:
    rows = {row.row_id: row for row in _rows(tmp_path)}
    new = sync.new_sb_row(rows["70"], 1315)
    assert new.values["Ime objekta"] == "Guštićeva jama"
    assert new.values["Sinonimi"] == "LiDAR Kristal 70"


def test_a_field_find_cannot_carry_the_convention_and_says_so(tmp_path: Path) -> None:
    rows = {row.row_id: row for row in _rows(tmp_path)}
    new = sync.new_sb_row(rows["Špiljkotina"], 1316)
    assert new.values["Ime objekta"] == "Špiljkotina"
    assert new.values["Sinonimi"] == ""
    assert new.warning and "LiDAR broj" in new.warning


def test_the_placeholder_name_is_never_written_back_as_a_name(tmp_path: Path) -> None:
    """SB holding `LiDAR Kristal 43` means nobody has named it — not a name."""
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS))
    differences, _ = sync.sheet_differences(resolved["43"])
    assert not [d for d in differences if d.column == liburnija.COL_NAME_NEW]


def test_sb_wins_on_a_real_name(tmp_path: Path) -> None:
    records = [_record(1257, "Prava jama", plaque="051-742")]
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), records))
    differences, _ = sync.sheet_differences(resolved["43"])
    name = next(d for d in differences if d.column == liburnija.COL_NAME_NEW)
    assert name.proposed == "Prava jama"


def test_the_deliverable_flags_flow_both_ways(tmp_path: Path) -> None:
    """SB fills a gap in the sheet; the sheet claiming more is a decision."""
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS))
    differences, decisions = sync.sheet_differences(resolved["43"])
    photo = next(d for d in differences if d.column == liburnija.COL_PHOTO)
    assert (photo.current, photo.proposed) == ("FALSE", "TRUE")
    # Row 61 says nothing; SB 823 has a SUE number, so it is explored.
    explored, _ = sync.sheet_differences(resolved["61"])
    assert not [d for d in explored if d.column == liburnija.COL_EXPLORED]

    claims_more = [
        _record(1257, "LiDAR Kristal 43", plaque="051-742", note="za istražit, LiDAR")
    ]
    _, decisions = sync.sheet_differences(
        _by_id(resolver.resolve_rows(_rows(tmp_path), claims_more))["43"]
    )
    assert any("Nacrt" in decision.issue for decision in decisions)


def test_build_numbers_new_rows_consecutively_from_the_next_free(tmp_path: Path) -> None:
    resolutions = resolver.resolve_rows(_rows(tmp_path), RECORDS)
    result = sync.build(resolutions, next_serial=1314)
    serials = [int(row.values["Redni broj"]) for row in result.to_sb]
    assert serials == list(range(1314, 1314 + len(serials)))
    assert result.counts["total"] == 8
    assert result.counts[LinkStatus.OUT_OF_SCOPE.value] == 1


def test_tsv_is_tab_separated_so_a_paste_splits_into_cells(tmp_path: Path) -> None:
    result = sync.build(resolver.resolve_rows(_rows(tmp_path), RECORDS), next_serial=1314)
    text = sync.to_tsv(result.to_sb)
    lines = text.splitlines()
    assert lines[0].split("\t") == list(sync.NEW_ROW_COLUMNS)
    assert all(len(line.split("\t")) == len(sync.NEW_ROW_COLUMNS) for line in lines)


def test_next_serial_spans_rows_with_no_name(settings) -> None:
    """SB carries a blank pre-numbered row; numbering must not collide with it."""

    class _Reader:
        def load_rows(self) -> pd.DataFrame:
            return pd.DataFrame(
                {"Redni broj": [1, 2, 1313], "Ime objekta": ["A", "B", None]}
            )

    assert resolver.next_serial_number(_Reader(), settings) == 1314
