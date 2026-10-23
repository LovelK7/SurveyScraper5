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

PROD_ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_prod", PROD_ROOT / "build_prod.py"
)
build_prod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_prod)


@pytest.fixture()
def staged(tmp_path, monkeypatch):
    monkeypatch.setattr(build_prod, "DIST_ROOT", tmp_path / "prod")
    return build_prod.stage("9.9")


def test_stage_layout(staged):
    # One launcher, no version in its name (the dashboard, user 2026-10-22).
    assert [p.name for p in staged.glob("*.bat")] == ["SurveyScraper5.bat"]
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
    text = (staged / "SurveyScraper5.bat").read_text(encoding="ascii")
    assert 'v9.9\\bootstrap.ps1' in text
    assert "-Command" not in text


def test_bootstrap_starts_or_reuses_a_hidden_dashboard(staged):
    text = (staged / "v9.9" / "bootstrap.ps1").read_text(encoding="ascii")
    # started without a window, found again through the state file, and it
    # stops itself when no page is open (user, 2026-10-22)
    assert "'gui', '--no-browser', '--state-file'" in text
    assert "'--idle-minutes', '10'" in text
    assert "-WindowStyle Hidden" in text
    assert "CaveDossier\\gui.json" in text
    assert "Invoke-Gui $running 'ping'" in text
    # an older version's server is asked to stop, never killed mid-job
    assert "Invoke-Gui $running 'shutdown'" in text and "-eq 409" in text
    # the launcher's own server is recognised by time, not pid (shims)
    assert "$s.started -ge $launched" in text


def test_bootstrap_runs_korak_0_once_per_install(staged):
    text = (staged / "v9.9" / "bootstrap.ps1").read_text(encoding="ascii")
    assert "csurvey_app_settings.py'), 'apply'" in text
    assert "csurvey_local.py'), 'install'" in text
    # KORAK 0's local cSurvey copy finds the Drive through .env, so it must
    # run after the .env is written.
    assert text.index("LOCAL_DRIVE_ROOT=$driveRoot") < text.index("csurvey_app_settings.py'), 'apply'")


def test_bootstrap_logs_and_sets_console_font(staged):
    # Every run must mirror output into the per-run log (that file is how a
    # failing run on a remote operator machine reaches the dev) and set a TrueType
    # console font (readability + Croatian glyphs).
    text = (staged / "v9.9" / "bootstrap.ps1").read_text(encoding="ascii")
    assert "CaveDossier\\logs" in text
    assert "function Run-Logged" in text and "Run-Logged $venvPy" in text
    assert "SetCurrentConsoleFontEx" in text
    # Redirected streams block-buffer Python output — without this the window
    # sits silent until the end (the very complaint the snake answers).
    assert "PYTHONUNBUFFERED" in text
    assert "~~o>" in text, "waiting snake missing"


def test_bootstrap_installs_karta_flow(staged):
    # Since v1.2 operator machines collect the isječak karte themselves:
    # the [karta] extra, the chromium download, and no unfilled GEOREF tokens.
    text = (staged / "v9.9" / "bootstrap.ps1").read_text(encoding="ascii")
    assert ".[osz,photos,geo,karta,sastavnica,sb-write]" in text
    assert "'playwright', 'install', 'chromium'" in text
    assert "@GEOREF_" not in text


def test_bundle_carries_the_runtime_tree(staged):
    with zipfile.ZipFile(staged / "v9.9" / "bundle.zip") as zf:
        names = set(zf.namelist())
    # Everything the prod commands stand on at runtime, at its FLATTENED
    # bundle path: dev spreads these across stages/*/src/cave_dossier/, the
    # bundle rewrites them all into one src/cave_dossier/ tree.
    for expected in [
        "pyproject.toml",
        "config.yaml",
        ".env.example",
        # workspace_root() walks up for this; without it every operator run
        # dies at startup.
        ".cavedossier-workspace",
        "src/cave_dossier/cli/__init__.py",
        "src/cave_dossier/core/paths.py",
        "src/cave_dossier/osz/prefill.py",
        "src/cave_dossier/photos/process.py",
        # Runtime inputs now travel INSIDE their subpackage rather than being
        # listed separately in the bundle manifest.
        "src/cave_dossier/osz/pristupi.yaml",
        "src/cave_dossier/osz/templates/Zapisnik_OSZ_v10.docx",
        "src/cave_dossier/georef/selectors.yaml",
        "src/cave_dossier/sastavnica/templates/sastavnica_blank_v2.pdf",
        "data/people/registry.json",
        "PROD_VERSION.txt",
        # the 3N tools the dashboard runs (gui/state.py tools_dir), with themes
        "csx-alati/nacrt_finish.py",
        "csx-alati/csurvey_headless.ps1",
        "csx-alati/inspect_survey.py",
        "csx-alati/tdx_zip_to_csx.py",
    ]:
        assert expected in names, f"bundle misses {expected}"
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    # Stale editable-install metadata shipped in every bundle up to v1.4 and
    # was pip-installed over on the operator machine. Never again.
    assert not any("egg-info" in n for n in names), "bundle carries egg-info"
    # The bundle must be FLAT: no stages/ prefix survives the rewrite.
    assert not any(n.startswith("stages/") for n in names)
    # The operator install must see a single-root pyproject, not the dev
    # package-dir map -- that map is what must NOT run on their machine.
    with zipfile.ZipFile(staged / "v9.9" / "bundle.zip") as zf:
        pyproj = zf.read("pyproject.toml").decode("utf-8")
    assert 'where = ["src"]' in pyproj
    assert "[tool.setuptools.package-dir]" not in pyproj
    # data/geo is provisioned per machine (cloud copy / fetch-data), never bundled.
    assert not any(n.startswith("data/geo/") for n in names)


def test_version_format_is_enforced():
    with pytest.raises(SystemExit):
        build_prod.main(["--version", "banana"])


def test_bundle_carries_every_tool_the_dashboard_runs(staged):
    from cave_dossier.gui import catalog

    with zipfile.ZipFile(staged / "v9.9" / "bundle.zip") as zf:
        names = set(zf.namelist())
    for action in catalog.ACTIONS:
        if action.tool not in ("cli", "manual"):
            assert f"csx-alati/{action.tool}" in names, f"{action.id}: {action.tool} not bundled"
    assert any(n.startswith("csx-alati/teme/") and n.endswith("/theme.json") for n in names)


def test_publish_sweeps_every_retired_launcher_into_the_archive(tmp_path):
    for name in ["cavedossier_osz_prefill_v1.10.bat", "cavedossier_nacrt_v1.10.bat",
                 "csurvey_0_postavi_csurvey.bat", "csurvey_3_dovrsi_nacrt.bat",
                 "csurvey_0_PROCITAJ_ME.txt", "SurveyScraper5.bat", "PROCITAJ_ME.txt",
                 "VERZIJE.txt"]:
        (tmp_path / name).write_text("x", encoding="ascii")
    for name in ["csurvey_alati", "v1.10", "v2.0", "podaci"]:
        (tmp_path / name).mkdir()
    build_prod._archive_old(tmp_path, "2.0")
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == ["PROCITAJ_ME.txt", "SurveyScraper5.bat", "VERZIJE.txt", "_arhiva",
                    "podaci", "v2.0"]
    assert (tmp_path / "_arhiva" / "csurvey_alati").is_dir()
    assert (tmp_path / "_arhiva" / "cavedossier_nacrt_v1.10.bat").is_file()
