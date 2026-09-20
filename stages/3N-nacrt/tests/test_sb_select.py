"""sb_select — picking intake leaves by Redni broj.

The operator types SB numbers into csurvey_1_pripremi_csx.bat; everything that
can go wrong with that (padding, nesting, junk, a number with no folder) is
decided here, not in the .bat.
"""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import sb_select  # noqa: E402


@pytest.fixture
def intake(tmp_path):
    for rel in ("SB_811_Nozata jama",
                "podmapa/SB_0908_Druga spilja",
                "SB_5_Treca",
                "Arhiva/nije SB mapa"):
        (tmp_path / rel).mkdir(parents=True)
    return tmp_path


def test_parse_numbers_splits_on_spaces_and_commas():
    assert sb_select.parse_numbers(["811", "0908, 9"]) == [811, 908, 9]


def test_parse_numbers_rejects_junk():
    with pytest.raises(ValueError):
        sb_select.parse_numbers(["811", "spilja"])


@pytest.mark.parametrize("name,expected", [
    ("SB_811_Nozata jama", 811),
    ("SB_00811", 811),
    ("SB-811-nesto", 811),
    ("Arhiva", None),
    ("SBX_811", None),
])
def test_leaf_number(name, expected):
    assert sb_select.leaf_number(name) == expected


def test_find_dirs_matches_padding_and_nesting(intake):
    dirs, missing = sb_select.find_dirs(str(intake), [811, 908])
    assert missing == []
    assert sorted(Path(d).name for d in dirs) == ["SB_0908_Druga spilja",
                                                  "SB_811_Nozata jama"]


def test_find_dirs_reports_numbers_without_a_folder(intake):
    dirs, missing = sb_select.find_dirs(str(intake), [811, 777])
    assert missing == [777]
    assert len(dirs) == 1


def test_resolve_returns_none_when_nothing_matches(intake, capsys):
    assert sb_select.resolve(str(intake), ["777"]) is None
    assert "nema mape SB_777_" in capsys.readouterr().out


def test_resolve_returns_none_on_junk(intake, capsys):
    assert sb_select.resolve(str(intake), ["spilja"]) is None
    assert "nije broj" in capsys.readouterr().out


def test_resolve_selects_only_the_named_caves(intake):
    dirs = sb_select.resolve(str(intake), ["811"])
    assert [Path(d).name for d in dirs] == ["SB_811_Nozata jama"]


@pytest.fixture
def files(tmp_path):
    leaf = tmp_path / "SB_1103_Nova jama"
    leaf.mkdir()
    for name in ("nova.csx", "nova_pp.csx", "nova_rad.csz", "nova_rad_lt.csz",
                 "biljeske.txt"):
        (leaf / name).write_bytes(b"x")
    return tmp_path, leaf


def test_list_files_keeps_surveys_and_drops_its_own_output(files):
    root, leaf = files
    got = sb_select.list_files([str(leaf)], (".csz", ".csx"),
                               skip_suffixes=("_lt",))
    assert [Path(p).name for p in got] == ["nova.csx", "nova_pp.csx",
                                           "nova_rad.csz"]


def test_choose_takes_the_only_file_without_asking(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("asked anyway"))
    assert sb_select.choose(["a.csz"]) == ["a.csz"]
    assert "datoteka: a.csz" in capsys.readouterr().out


@pytest.mark.parametrize("typed,expected", [
    ("2", ["b.csz"]),
    ("SVE", ["a.csz", "b.csz"]),
    ("", None),
    ("7", None),
    ("nesto", None),
])
def test_choose_reads_the_operator_answer(monkeypatch, typed, expected):
    monkeypatch.setattr("builtins.input", lambda *a: typed)
    assert sb_select.choose(["a.csz", "b.csz"]) == expected


def test_choose_cancels_on_eof(monkeypatch):
    def boom(*a):
        raise EOFError
    monkeypatch.setattr("builtins.input", boom)
    assert sb_select.choose(["a.csz", "b.csz"]) is None
