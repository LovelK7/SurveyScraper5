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
    assert match.proposed_name == "1035_Sik Šits_Sara"


def test_word_order_difference_still_resolves(tmp_path: Path) -> None:
    """`Grotta possibile` is SB's *Possibile Grotta*; the name is not duplicated."""
    _tree(tmp_path)
    leaves = [leaf for leaf in find_leaf_folders(tmp_path) if leaf.path.name == "Grotta possibile"]
    match = match_leaves(leaves, CANDIDATES)[0]
    assert match.cave.serial_number == 811
    assert match.proposed_name == "811_Grotta possibile"


def test_suggestions_rank_a_spelling_variant_first() -> None:
    ranked = suggest("Bilova ponikva_Cico", CANDIDATES)
    assert ranked[0][0].object_name == "Billova ponikva"
    assert ranked[0][1] > 0.7


def test_manual_mapping_resolves_a_folder_with_no_cave_name(tmp_path: Path) -> None:
    _tree(tmp_path)
    leaves = [leaf for leaf in find_leaf_folders(tmp_path) if leaf.path.name == "108_Renata"]
    match = match_leaves(leaves, CANDIDATES, {"108_Renata": 752})[0]
    assert match.cave.object_name == "Malenica"
    assert match.proposed_name == "752_Malenica_108_Renata"
