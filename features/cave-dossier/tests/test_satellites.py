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


def test_sb_fills_the_photo_gap_and_the_sheet_claiming_more_is_a_decision(
    tmp_path: Path,
) -> None:
    """`Fotografija ulaza` is a DA/NE claim, so it disagrees in both directions."""
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS))
    differences, _ = sync.sheet_differences(resolved["43"])
    photo = next(d for d in differences if d.column == liburnija.COL_PHOTO)
    assert (photo.current, photo.proposed) == ("FALSE", "TRUE")
    # Row 61 says nothing; SB 823 has a SUE number, so it is explored.
    explored, _ = sync.sheet_differences(resolved["61"])
    assert not [d for d in explored if d.column == liburnija.COL_EXPLORED]


def test_an_empty_link_cell_is_not_evidence_of_a_missing_document(
    tmp_path: Path,
) -> None:
    """`Link Zapisnik` records only whether a DIGITAL copy is on file.

    Every *Istraženi* object has a zapisnik and a nacrt, analog or digital
    (user, 2026-08-29), so an empty link cell must never contradict the sheet,
    and a SUE number is enough on its own to say both exist.
    """
    # Sheet 43 says Nacrt TRUE and Zapisnik TRUE; SB has neither link and no
    # SUE number. Not a disagreement: SB simply has not filed a digital copy.
    bare = [_record(1257, "LiDAR Kristal 43", plaque="051-742")]
    differences, decisions = sync.sheet_differences(
        _by_id(resolver.resolve_rows(_rows(tmp_path), bare))["43"]
    )
    assert not [
        d
        for d in differences
        if d.column in (liburnija.COL_NACRT, liburnija.COL_ZAPISNIK)
    ]
    assert not decisions

    # Sheet 61 says both FALSE while SB 823 holds a SUE number -> both proposed.
    proposed, _ = sync.sheet_differences(
        _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS))["61"]
    )
    documents = [
        d
        for d in proposed
        if d.column in (liburnija.COL_NACRT, liburnija.COL_ZAPISNIK)
    ]
    assert {d.column for d in documents} == {liburnija.COL_NACRT, liburnija.COL_ZAPISNIK}
    assert all(d.proposed == "TRUE" for d in documents)
    assert "SUE" in documents[0].reason


def test_a_digital_link_counts_even_without_a_sue_number() -> None:
    record = _record(1257, "LiDAR Kristal 43", plaque="051-742", nacrt="843")
    assert sync._sb_has_document(record, record.nacrt_link)
    assert not sync._sb_has_document(record, record.zapisnik_link)


def test_build_numbers_new_rows_consecutively_from_the_next_free(tmp_path: Path) -> None:
    resolutions = resolver.resolve_rows(_rows(tmp_path), RECORDS)
    result = sync.build(resolutions, next_serial=1314)
    serials = [int(row.values["Redni broj"]) for row in result.to_sb]
    assert serials == list(range(1314, 1314 + len(serials)))
    assert result.counts["total"] == 8
    assert result.counts[LinkStatus.OUT_OF_SCOPE.value] == 1


def test_the_block_is_real_csv_commas_and_quotes_and_all(tmp_path: Path) -> None:
    """Napomena is full of commas, so only proper quoting survives the trip."""
    import csv
    import io as _io

    result = sync.build(resolver.resolve_rows(_rows(tmp_path), RECORDS), next_serial=1314)
    rows = list(csv.reader(_io.StringIO(sync.to_csv(result.to_sb))))
    assert rows[0] == list(sync.NEW_ROW_COLUMNS)
    assert all(len(row) == len(sync.NEW_ROW_COLUMNS) for row in rows)
    # The comma inside a Napomena must not become a column break.
    note = dict(zip(rows[0], rows[1]))["Napomena"]
    assert note.startswith("za istražit, ")


def test_a_value_with_a_quote_round_trips(tmp_path: Path) -> None:
    row = sync.NewRow(row_id="x", values={"Napomena": 'za istražit, "Opasna" 6metarka'})
    import csv
    import io as _io

    parsed = list(csv.reader(_io.StringIO(sync.to_csv([row], ("Napomena",)))))
    assert parsed[1] == ['za istražit, "Opasna" 6metarka']


def test_the_block_carries_the_workbooks_own_columns_in_its_own_order(
    tmp_path: Path,
) -> None:
    """A subset cannot be pasted into `Svi objekti` - every column must be there.

    Columns we have no value for come out empty; that is what keeps the block
    aligned with the table.
    """
    workbook_columns = ("Redni broj", "Ime objekta", "Duljina", "Napomena", "Sinonimi")
    result = sync.build(resolver.resolve_rows(_rows(tmp_path), RECORDS), next_serial=1313)
    import csv
    import io as _io

    parsed = list(csv.reader(_io.StringIO(sync.to_csv(result.to_sb, workbook_columns))))
    assert parsed[0] == list(workbook_columns)
    first = dict(zip(workbook_columns, parsed[1]))
    assert first["Redni broj"] == "1313"
    assert first["Duljina"] == ""            # nothing known, so nothing invented
    assert first["Ime objekta"].startswith("LiDAR Kristal")


def test_a_linked_row_missing_the_synonym_becomes_an_sb_addition(
    tmp_path: Path,
) -> None:
    """The convention that turns a fuzzy match into a permanent hard key."""
    plain = [_record(733, "Jama u Puharima", plaque="051-742", synonyms=("stari naziv",))]
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), plain))["43"]
    edit = sync.synonym_edit(resolved)
    assert edit is not None
    assert edit.serial_number == 733 and edit.column == "Sinonimi"
    # An addition, never a replacement: what is there already survives.
    assert edit.current == "stari naziv"
    assert edit.proposed == "stari naziv; LiDAR Kristal 43"

    # A row that already carries it proposes nothing.
    already = _by_id(resolver.resolve_rows(_rows(tmp_path), RECORDS))["43"]
    assert sync.synonym_edit(already) is None


def test_an_exact_name_inside_the_review_radius_is_the_same_cave(
    tmp_path: Path,
) -> None:
    """Two signals that agree beat either alone.

    Sheet 285 *Jama u Puharima* is SB 733 at 5.1 m - a tenth of a metre outside
    the auto band, and plainly the same cave (user, 2026-08-29).
    """
    # 8 m away, so past AUTO_LINK_M, but the name matches exactly.
    twin = _record(733, "Guštićeva jama", x=323000, y=5026008)
    resolved = _by_id(
        resolver.resolve_rows(_rows(tmp_path), [twin], use_coordinates=True)
    )["70"]
    assert resolved.status is LinkStatus.LINKED
    assert resolved.key == "name+coordinate"


def test_a_confirmed_new_row_is_not_re_raised_as_a_near_miss(
    tmp_path: Path,
) -> None:
    """*Špiljuljak* sits 4.7 m from a known cave and is still its own cave.

    Without this the same proximity is raised on every run forever.
    """
    neighbour = _record(1172, "Susjed", x=323000, y=5026002)
    rows = _rows(tmp_path)
    raised = _by_id(resolver.resolve_rows(rows, [neighbour], use_coordinates=True))["70"]
    assert raised.status is LinkStatus.LINKED  # nearest, unambiguous

    confirmed = _by_id(
        resolver.resolve_rows(
            rows, [neighbour], use_coordinates=True, confirmed_new={"70"}
        )
    )["70"]
    assert confirmed.status is LinkStatus.CANDIDATE


def test_next_serial_spans_rows_with_no_name(settings) -> None:
    """SB carries a blank pre-numbered row; numbering must not collide with it."""

    class _Reader:
        def load_rows(self) -> pd.DataFrame:
            return pd.DataFrame(
                {"Redni broj": [1, 2, 1313], "Ime objekta": ["A", "B", None]}
            )

    assert resolver.next_serial_number(_Reader(), settings) == 1314


def test_write_lists_produces_every_list(tmp_path: Path) -> None:
    result = sync.build(resolver.resolve_rows(_rows(tmp_path), RECORDS), next_serial=1313)
    written = sync.write_lists(result, tmp_path / "run")
    assert set(written) == {"za-sb", "dopune-sb", "za-tablicu", "za-odluku"}
    assert all(path.is_file() for path in written.values())
    # List 1 stays machine-pasteable; the rest are worksheets for a human.
    assert written["za-sb"].read_text(encoding="utf-8-sig").startswith("Redni broj,")
    assert "ZA TABLICU" in written["za-tablicu"].read_text(encoding="utf-8-sig")


def test_every_file_carries_a_bom_so_excel_reads_croatian(tmp_path: Path) -> None:
    """Without it Excel reads UTF-8 as the local codepage and č/š/ž break."""
    result = sync.build(resolver.resolve_rows(_rows(tmp_path), RECORDS), next_serial=1313)
    bom = bytes([0xEF, 0xBB, 0xBF])
    for path in sync.write_lists(result, tmp_path / "run").values():
        assert path.read_bytes().startswith(bom), path.name
    text = (tmp_path / "run" / "1-za-sb.csv").read_text(encoding="utf-8-sig")
    assert "Špiljkotina" in text  # round-trips intact


def test_an_existing_sb_name_stops_the_add_and_asks(tmp_path: Path) -> None:
    """Sheet 70 is *Guštićeva jama*; if SB already has that name, do not paste a twin.

    A name is too weak to link on, and far too strong to ignore when the
    alternative is duplicating a cave (sheet 285 = SB 733, same name, 5 m apart).
    """
    records = [_record(500, "Guštićeva jama")]
    resolved = _by_id(resolver.resolve_rows(_rows(tmp_path), records))
    assert resolved["70"].status is LinkStatus.CONFLICT
    assert resolved["70"].key == "name"
    assert "500" in resolved["70"].evidence
    # It stops the add without becoming a link — the row is not claimed.
    assert resolved["70"].record is None
    # A nameless candidate is unaffected.
    assert resolved["10"].status is LinkStatus.CANDIDATE


def test_neistrazeno_in_napomena_means_not_explored() -> None:
    """SB 914 said "neistraženo" and the tool proposed istraženo = 1 anyway.

    The queue flag is not the only way SB says "not explored" — the Nesređeni
    keyword does too, and the reason line would otherwise contradict itself.
    """
    queued = _record(1, "A", note="za istražit, LiDAR")
    keyword = _record(2, "B", note="neistraženo, ponoviti - dubina 8 m")
    unfiled = _record(3, "C", note="fali nacrt i zapisnik, ponoviti")
    numbered = _record(4, "D", sue="512", note="za istražit, stale")
    assert not queued.is_explored
    assert not keyword.is_explored
    assert unfiled.is_explored          # visited and surveyed, just not filed
    assert numbered.is_explored         # a SUE number settles it
    # The bare word must not trip it: "istraženo 3.10.2000" is a date, not a flag.
    assert _record(5, "E", note="istraženo 3.10.2000., tal. Katastar 1445").is_explored


def test_the_default_out_dir_is_one_dated_folder_per_satellite() -> None:
    from datetime import date

    path = sync.default_out_dir("liburnija", date(2026, 8, 29))
    assert path.parts[-3:] == ("sb-sync", "liburnija", "2026-08-29")


def test_the_written_csv_parses_back_to_the_rows_it_was_given(tmp_path: Path) -> None:
    """Windows newline translation once turned every CRLF into CR-CRLF.

    The file still looked fine in an editor, but each record gained a blank line
    and 126 rows parsed back as 253.
    """
    import csv
    import io as _io

    result = sync.build(resolver.resolve_rows(_rows(tmp_path), RECORDS), next_serial=1313)
    path = sync.write_lists(result, tmp_path / "run")["za-sb"]
    assert bytes([13, 13, 10]) not in path.read_bytes()
    parsed = list(
        csv.reader(_io.open(path, encoding="utf-8-sig", newline=""))
    )
    assert len(parsed) == len(result.to_sb) + 1
    assert all(len(row) == len(parsed[0]) for row in parsed)


def test_the_found_year_comes_out_of_datum_provjere(tmp_path: Path) -> None:
    """Hand-typed dates in several shapes; only the year is ever wanted."""
    rows = {row.row_id: row for row in _rows(tmp_path)}
    assert rows["10"].checked_year == "2024"     # 10/10/2024
    assert rows["70"].checked_year == "2025"     # 03/03/2025
    assert rows["50"].checked_year is None       # nobody has been there


def test_campaign_defaults_fill_columns_no_row_can_supply(tmp_path: Path) -> None:
    """`Lokalitet` is a property of the campaign, not of any one point."""
    rows = {row.row_id: row for row in _rows(tmp_path)}
    new = sync.new_sb_row(rows["10"], 1313, {"Lokalitet": "Ćićarija"})
    assert new.values["Lokalitet"] == "Ćićarija"
    assert new.values["Godina ili period istraživanja"] == "2024"
    # A default never overwrites something the row itself decides.
    shadowed = sync.new_sb_row(rows["10"], 1313, {"Ime objekta": "krivo"})
    assert shadowed.values["Ime objekta"] == "LiDAR Kristal 10"


def test_defaults_reach_every_new_row_in_a_run(tmp_path: Path) -> None:
    result = sync.build(
        resolver.resolve_rows(_rows(tmp_path), RECORDS),
        next_serial=1313,
        row_defaults={"Lokalitet": "Ćićarija"},
    )
    assert result.to_sb
    assert all(row.values["Lokalitet"] == "Ćićarija" for row in result.to_sb)


def test_a_row_already_pasted_into_sb_is_never_proposed_again(tmp_path: Path) -> None:
    """The round trip: propose -> paste -> re-run must find nothing to do.

    *Špiljuljak* is a `confirmed_new` cave 4.7 m from a known one. Once it was
    pasted into SB, the override kept suppressing the coordinate key and the run
    proposed adding it a second time. A row sitting on the same point IS that
    row, whatever the override says.
    """
    rows = _rows(tmp_path)
    confirmed = {"70"}

    # Before the paste: the near neighbour must not claim it.
    neighbour = _record(1172, "Susjed", x=323000, y=5026004)
    before = _by_id(
        resolver.resolve_rows(
            rows, [neighbour], use_coordinates=True, confirmed_new=confirmed
        )
    )["70"]
    assert before.status is LinkStatus.CANDIDATE

    # After the paste SB carries it at its own coordinates — and the rival is
    # still right there, which is exactly the case that used to re-propose.
    pasted = _record(1439, "Guštićeva jama", x=323000, y=5026000)
    after = _by_id(
        resolver.resolve_rows(
            rows, [neighbour, pasted], use_coordinates=True, confirmed_new=confirmed
        )
    )["70"]
    assert after.status is LinkStatus.LINKED
    assert after.record.serial_number == 1439


def test_an_exact_point_outranks_a_nearby_rival(tmp_path: Path) -> None:
    """0.0 m with a rival 11 m away is decisive, not ambiguous.

    *Puhalica kraj 41* sat on its own SB row and 11 m from *LiDAR Kristal 41*;
    the flat 15 m ambiguity radius called that a conflict.
    """
    exact = _record(1435, "Puhalica kraj 41", x=323000, y=5026000)
    rival = _record(1330, "LiDAR Kristal 41", x=323000, y=5026011)
    resolved = _by_id(
        resolver.resolve_rows(_rows(tmp_path), [exact, rival], use_coordinates=True)
    )["70"]
    assert resolved.status is LinkStatus.LINKED
    assert resolved.record.serial_number == 1435
