"""tools/build_prod.py — the prod launcher/bundle generator.

Renders into a tmp dir; nothing here touches the Drive (publish is exercised
live, see STATUS/SESSIONS). The templates are part of the contract: a leftover
@TOKEN@ or non-ASCII character in a .bat/.ps1 must fail the build loudly.
"""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

FEATURE_ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_prod", FEATURE_ROOT / "tools" / "build_prod.py"
)
build_prod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_prod)


@pytest.fixture()
def staged(tmp_path, monkeypatch):
    monkeypatch.setattr(build_prod, "DIST_ROOT", tmp_path / "prod")
    return build_prod.stage("9.9")


def test_stage_layout(staged):
    assert (staged / "cavedossier_osz_prefill_v9.9.bat").is_file()
    assert (staged / "cavedossier_photos_process_v9.9.bat").is_file()
    assert (staged / "PROCITAJ_ME.txt").is_file()
    assert (staged / "v9.9" / "bootstrap.ps1").is_file()
    assert (staged / "v9.9" / "bundle.zip").is_file()


def test_launchers_are_ascii_and_fully_rendered(staged):
    for path in list(staged.glob("*.bat")) + [staged / "v9.9" / "bootstrap.ps1"]:
        text = path.read_bytes().decode("ascii")  # raises on any non-ASCII byte
        assert "@VERSION@" not in text and "@COMMAND_ID@" not in text, path.name
        assert "9.9" in text, path.name


def test_procitaj_me_is_utf8_croatian(staged):
    # The operator guide is real Croatian (user, 2026-09-02) — UTF-8 with BOM
    # so Notepad can't misread it; only cmd/PS scripts stay ASCII.
    raw = (staged / "PROCITAJ_ME.txt").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "missing UTF-8 BOM"
    text = raw.decode("utf-8-sig")
    assert "@VERSION@" not in text
    assert "9.9" in text
    assert any(ch in text for ch in "čćšžđ"), "diacritics stripped from the guide"


def test_launcher_calls_its_own_version_bootstrap(staged):
    text = (staged / "cavedossier_osz_prefill_v9.9.bat").read_text(encoding="ascii")
    assert 'v9.9\\bootstrap.ps1' in text
    assert '-Command "osz_prefill"' in text


def test_bootstrap_covers_every_prod_command(staged):
    text = (staged / "v9.9" / "bootstrap.ps1").read_text(encoding="ascii")
    for command_id in build_prod.PROD_COMMANDS:
        assert f"'{command_id}'" in text, f"bootstrap switch misses {command_id}"


def test_bootstrap_logs_and_sets_console_font(staged):
    # Every run must mirror output into the per-run log (that file is how a
    # failing run on a remote operator machine reaches the dev) and set a TrueType
    # console font (readability + Croatian glyphs).
    text = (staged / "v9.9" / "bootstrap.ps1").read_text(encoding="ascii")
    assert "CaveDossier\\logs" in text
    assert "function Run-Logged" in text and "Run-Logged $cli" in text
    assert "SetCurrentConsoleFontEx" in text


def test_bootstrap_installs_karta_flow(staged):
    # Since v1.2 operator machines collect the isječak karte themselves:
    # the [karta] extra, the chromium download, and no unfilled GEOREF tokens.
    text = (staged / "v9.9" / "bootstrap.ps1").read_text(encoding="ascii")
    assert ".[osz,photos,geo,karta]" in text
    assert "'playwright', 'install', 'chromium'" in text
    assert "@GEOREF_" not in text


def test_bundle_carries_the_runtime_tree(staged):
    with zipfile.ZipFile(staged / "v9.9" / "bundle.zip") as zf:
        names = set(zf.namelist())
    # Everything FEATURE_ROOT-relative the two commands stand on at runtime.
    for expected in [
        "pyproject.toml",
        "config.yaml",
        ".env.example",
        "src/cave_dossier/cli.py",
        "src/cave_dossier/osz/prefill.py",
        "src/cave_dossier/photos/process.py",
        "config/pristupi.yaml",
        "config/selectors.yaml",
        "data/people/registry.json",
        "osz-template/templates/Zapisnik_OSZ_v10.docx",
        "PROD_VERSION.txt",
    ]:
        assert expected in names, f"bundle misses {expected}"
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    # data/geo is provisioned per machine (cloud copy / fetch-data), never bundled.
    assert not any(n.startswith("data/geo/") for n in names)


def test_version_format_is_enforced():
    with pytest.raises(SystemExit):
        build_prod.main(["--version", "banana"])
