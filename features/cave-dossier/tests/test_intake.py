"""Field-data intake: leaf discovery and folder→SB mapping.

The intake tree is 1–3 levels deep and its folder names carry local ids (LIDAR
points, expedition sequences) that must never be read as SB numbers.
"""

from __future__ import annotations

from pathlib import Path

from cave_dossier.core.matching import CaveCandidate
from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.intake import find_leaf_folders, match_leaves, suggest


def _cave(serial: int, name: str, sue: str | None = None) -> CaveCandidate:
    return CaveCandidate(serial, name, sue, None, None, normalize_lookup_key(name))


CANDIDATES = [
    _cave(1035, "Sik Šits"),
    _cave(811, "Possibile Grotta"),
    _cave(752, "Malenica", sue="547"),
    _cave(976, "Billova ponikva"),
    _cave(108, "Neka posve druga jama"),  # the trap: Redni broj 108 exists…
]


def _tree(root: Path) -> None:
    """Mirrors the real shape: groups, a nested group, and top-level leaves."""
    (root / "!!Goli breg" / "Sik Šits_Sara").mkdir(parents=True)
    (root / "!!Goli breg" / "Sik Šits_Sara" / "survey.tdx").write_bytes(b"x")
    (root / "!!Lidarke" / "108_Renata").mkdir(parents=True)
    (root / "Tin" / "Tingen-BP" / "Penj").mkdir(parents=True)
    (root / "Grotta possibile").mkdir()
    (root / "Grotta possibile" / "desktop.ini").write_bytes(b"x")


def test_leaves_are_found_at_any_depth(tmp_path: Path) -> None:
    _tree(tmp_path)
    leaves = {str(leaf.relative) for leaf in find_leaf_folders(tmp_path)}
    assert leaves == {
        str(Path("!!Goli breg") / "Sik Šits_Sara"),
        str(Path("!!Lidarke") / "108_Renata"),
        str(Path("Tin") / "Tingen-BP" / "Penj"),
        "Grotta possibile",
    }
    # A group folder is not a leaf, and system files do not count as data.
    by_name = {leaf.path.name: leaf for leaf in find_leaf_folders(tmp_path)}
    assert by_name["Sik Šits_Sara"].file_count == 1
    assert by_name["Grotta possibile"].file_count == 0
    assert by_name["Tin" if "Tin" in by_name else "Penj"].group == str(Path("Tin") / "Tingen-BP")


def test_leading_number_is_never_read_as_a_redni_broj(tmp_path: Path) -> None:
    """`108_Renata` is a LIDAR/expedition id — matching it to row 108 would be wrong."""
    _tree(tmp_path)
    leaves = [leaf for leaf in find_leaf_folders(tmp_path) if leaf.path.name == "108_Renata"]
    match = match_leaves(leaves, CANDIDATES)[0]
    assert match.cave is None


def test_proposal_prepends_and_never_strips(tmp_path: Path) -> None:
    _tree(tmp_path)
    leaves = [leaf for leaf in find_leaf_folders(tmp_path) if leaf.path.name == "Sik Šits_Sara"]
    match = match_leaves(leaves, CANDIDATES)[0]
    assert match.proposed_name == "SB_1035_Sik Šits_Sara"


def test_word_order_difference_still_resolves(tmp_path: Path) -> None:
    """`Grotta possibile` is SB's *Possibile Grotta*; the name is not duplicated."""
    _tree(tmp_path)
    leaves = [leaf for leaf in find_leaf_folders(tmp_path) if leaf.path.name == "Grotta possibile"]
    match = match_leaves(leaves, CANDIDATES)[0]
    assert match.cave.serial_number == 811
    assert match.proposed_name == "SB_811_Grotta possibile"


def test_suggestions_rank_a_spelling_variant_first() -> None:
    ranked = suggest("Bilova ponikva_Cico", CANDIDATES)
    assert ranked[0][0].object_name == "Billova ponikva"
    assert ranked[0][1] > 0.7


def test_manual_mapping_resolves_a_folder_with_no_cave_name(tmp_path: Path) -> None:
    _tree(tmp_path)
    leaves = [leaf for leaf in find_leaf_folders(tmp_path) if leaf.path.name == "108_Renata"]
    match = match_leaves(leaves, CANDIDATES, {"108_Renata": 752})[0]
    assert match.cave.object_name == "Malenica"
    assert match.proposed_name == "SB_752_Malenica_108_Renata"


# ── The Liburnija sheet bridge ────────────────────────────────────────


SHEET_CSV = """name,x,y,z,vjerojatnost,provjereno (1/0),provjerio,datum provjere,speleo_obj (1/0),istrazeno (1/0),Istražili,Naziv_novi,Naziv_stari,Br.pl,Komentar,Zapisnik,Nacrt,Foto ulaza
4,1,2,3,visoka,1,Tin,16/11/2024,1,1,SUE,Integral,,051-679,13 m dubine,TRUE,TRUE,TRUE
43,1,2,3,niska,1,Dino,15/12/2024,1,1,SUE,,,051-742,"7 m , OBJEKT",TRUE,TRUE,TRUE
79,1,2,3,niska,1,Fero,15/12/2024,1,1,SUE,,Jamorinke,051-814,SUE docrtala,TRUE,TRUE,TRUE
14,1,2,3,visoka,1,Dino,15/12/2024,1,0,,,,,"Velikih 7 metara, OBJEKT",FALSE,FALSE,FALSE
"""


def _sheet(tmp_path: Path) -> dict:
    from cave_dossier.intake import liburnija

    path = tmp_path / "sheet.csv"
    path.write_text(SHEET_CSV, encoding="utf-8")
    return liburnija.load_rows(path)


def test_sheet_row_resolves_into_sb_through_its_plaque(tmp_path: Path) -> None:
    from cave_dossier.intake import liburnija

    kristal = CaveCandidate(
        1257, "LiDAR Kristal 43", None, "051-742", None, normalize_lookup_key("LiDAR Kristal 43")
    )
    row, cave = liburnija.resolve("43", _sheet(tmp_path), [kristal])
    assert row.plaque == "051-742"
    assert cave.serial_number == 1257


def test_sheet_row_with_no_sb_row_is_the_add_to_sb_case(tmp_path: Path) -> None:
    """Sheet 79 (*Jamorinke*, 051-814) is a real cave SB does not have."""
    from cave_dossier.intake import liburnija

    row, cave = liburnija.resolve("79", _sheet(tmp_path), CANDIDATES)
    assert row.name == "Jamorinke"
    assert row.is_cave and row.explored
    assert cave is None


def test_sheet_row_without_a_plaque_cannot_reach_sb(tmp_path: Path) -> None:
    """No plaque means no bridge — which is what keeps other numbering schemes out."""
    from cave_dossier.intake import liburnija

    row, cave = liburnija.resolve("14", _sheet(tmp_path), CANDIDATES)
    assert row.plaque is None
    assert cave is None


def test_a_number_glued_inside_a_word_is_not_a_sheet_row() -> None:
    """`Mune_Nat4_Natalija` must not offer "4" — it matched *Integral* on the live run."""
    from cave_dossier.intake import sheet_number_tokens

    assert sheet_number_tokens("Mune_Nat4_Natalija") == []
    assert sheet_number_tokens("108_Renata") == ["108"]
    assert sheet_number_tokens("Jasnina jam lidar 43") == ["43"]
    assert sheet_number_tokens("lisina L366") == ["366"]      # LIDAR marker letter
    assert sheet_number_tokens("79_89_Jamorinke_Fero") == ["79", "89"]


def test_folder_named_after_a_sheet_row_maps_through_the_sheet(tmp_path: Path) -> None:
    from cave_dossier.intake import find_leaf_folders, match_leaves

    (tmp_path / "!!Lidarke" / "43_Jasna").mkdir(parents=True)
    kristal = CaveCandidate(
        1257, "LiDAR Kristal 43", None, "051-742", None, normalize_lookup_key("LiDAR Kristal 43")
    )
    leaves = find_leaf_folders(tmp_path)
    match = match_leaves(leaves, [kristal], sheet_rows=_sheet(tmp_path))[0]
    assert match.cave.serial_number == 1257
    assert match.sheet_number == "43"
    assert match.proposed_name == "SB_1257_LiDAR Kristal 43_Jasna"
