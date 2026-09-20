"""prod/build_csx_kit.py — the csurvey TDX drag-and-drop kit.

Builds into a tmp dir; nothing here touches the Drive (`--publish` is exercised
live, see STATUS/SESSIONS). The templates are the contract: a leftover @TOKEN@
or a non-ASCII byte in a `.bat` must fail the build loudly, because a cp852
console prints neither.

The KORAK numbers are the other contract. The digit in a launcher's filename is
the running order (user, 2026-09-20), so a renamed or re-numbered launcher that
no document follows is a bug the operator meets and nobody else does.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

PROD_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROD_ROOT.parent

spec = importlib.util.spec_from_file_location(
    "build_csx_kit", PROD_ROOT / "build_csx_kit.py"
)
build_csx_kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_csx_kit)

spec_prod = importlib.util.spec_from_file_location(
    "build_prod_for_csx", PROD_ROOT / "build_prod.py"
)
build_prod = importlib.util.module_from_spec(spec_prod)
spec_prod.loader.exec_module(build_prod)


@pytest.fixture()
def staged(tmp_path):
    out = tmp_path / "csx-kit"
    build_csx_kit.build(out)
    return out


def test_kit_layout(staged):
    for name in [
        "csurvey_0_PROCITAJ_ME.txt",
        "csurvey_1_pripremi_csx.bat",
        "csurvey_2_dovrsi_uvoz.bat",
        "csurvey_3_dovrsi_nacrt.bat",
        "csurvey_9_oporavi_iz_zipa.bat",
    ]:
        assert (staged / name).is_file(), name
    assert (staged / build_csx_kit.PAYLOAD_DIR / "KIT_VERSION.txt").is_file()


def test_rescue_moved_out_of_the_running_order(staged):
    # User decision 2026-09-20: the finisher is KORAK 3 and the zip rescue
    # leaves the running order for KORAK 9 — it is a repair, not a step.
    assert not (staged / "csurvey_3_oporavi_iz_zipa.bat").exists()
    assert not (PROD_ROOT / "csx_templates"
                / "csurvey_3_oporavi_iz_zipa.bat.template").exists()
    text = (staged / "csurvey_9_oporavi_iz_zipa.bat").read_text(encoding="ascii")
    assert "KORAK 9" in text
    assert "KORAK 3" not in text


def test_launchers_are_ascii_and_fully_rendered(staged):
    for path in sorted(staged.glob("*.bat")):
        text = path.read_bytes().decode("ascii")  # raises on any non-ASCII byte
        # @echo off is the one legitimate @ in a .bat; a token is @UPPER@.
        assert not re.search(r"@[A-Z_]+@", text), path.name
        assert build_csx_kit.KIT_VERSION in text, path.name


def test_nacrt_launcher_drives_the_whole_korak_3_chain(staged):
    text = (staged / "csurvey_3_dovrsi_nacrt.bat").read_text(encoding="ascii")
    # The three steps, in order, each by the tool that owns it.
    assert "nacrt_finish.py" in text
    assert "csurvey_driver.py" in text and "finish" in text
    # The last step is a cavedossier command, not a kit tool: found by name in
    # the Drive folder both kits publish into.
    assert "cavedossier_nacrt_v*.bat" in text
    # Double-click = the operator is watching, so the layout menu is shown;
    # --yes only on the dragged (unattended) path.
    assert "--sb %SB% --force" in text
    assert "--yes --force" in text
    # cSurvey missing must end in the manual print recipe, not a traceback.
    assert "File ^> Print" in text
    assert "Microsoft Print to PDF" in text
    assert text.rstrip().endswith("exit /b 0")


def test_kit_carries_the_five_korak_3_tools(staged):
    payload = staged / build_csx_kit.PAYLOAD_DIR
    for name in [
        "nacrt_layout.py",
        "nacrt_finish.py",
        "nacrt_finish_compass.xml",
        "csurvey_headless.ps1",
        "csurvey_driver.py",
    ]:
        assert name in build_csx_kit.TOOLS, f"TOOLS misses {name}"
        assert (payload / name).is_file(), f"kit misses {name}"


def test_guide_is_utf8_croatian_and_follows_the_same_numbers(staged):
    raw = (staged / "csurvey_0_PROCITAJ_ME.txt").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "missing UTF-8 BOM"
    text = raw.decode("utf-8-sig")
    assert "@VERSION@" not in text
    assert any(ch in text for ch in "čćšžđ"), "diacritics stripped from the guide"
    assert "csurvey_3_dovrsi_nacrt.bat" in text
    assert "csurvey_3_oporavi_iz_zipa.bat" not in text
    # The rescue is at the bottom, below the three steps (user, 2026-09-20).
    assert text.index("KORAK 3 - DOVRŠI NACRT") < text.index("KORAK 9 - POPRAVAK")


def test_nacrt_is_a_published_prod_command():
    # The kit's third step calls cavedossier_nacrt_v<X>.bat; without both of
    # these edits build_prod.py never publishes that launcher.
    assert build_prod.PROD_COMMANDS["nacrt"] == ("nacrt",)
    bootstrap = (PROD_ROOT / "prod_templates"
                 / "bootstrap.ps1.template").read_text(encoding="utf-8")
    assert "'nacrt' {" in bootstrap
    assert "$cliVerb = @('nacrt')" in bootstrap


def test_missing_tool_fails_the_build(tmp_path, monkeypatch):
    monkeypatch.setattr(build_csx_kit, "TOOLS",
                        build_csx_kit.TOOLS + ["nema_me.py"])
    with pytest.raises(SystemExit):
        build_csx_kit.build(tmp_path / "csx-kit")
