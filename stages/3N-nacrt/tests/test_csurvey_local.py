"""csurvey_local — KORAK 0's local copy of the Drive's cSurvey (opened by hand
from G: cSurvey crashes on its lowercased gallery paths)."""

import io
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import csurvey_local as cl  # noqa: E402


def _drive(tmp_path):
    src = tmp_path / "drive" / "csurvey64"
    (src / "Objects" / "Cliparts" / "Signs").mkdir(parents=True)
    (src / "cSurveyPC.exe").write_bytes(b"exe-v1")
    (src / "Objects" / "Cliparts" / "Signs" / "acqua.svg").write_text("<svg/>")
    (src / "desktop.ini").write_text("[x]")
    return src


def _install(src, dest, monkeypatch):
    monkeypatch.setattr(cl, "running_from", lambda d: False)
    out = io.StringIO()
    rc = cl.cmd_install(str(src), str(dest), out, shortcut=False)
    return rc, out.getvalue()


def test_install_copies_once_then_only_when_the_drive_exe_changes(tmp_path, monkeypatch):
    src, dest = _drive(tmp_path), tmp_path / "local" / "csurvey64"
    assert cl.state(str(src), str(dest)) == "missing"
    rc, text = _install(src, dest, monkeypatch)
    assert rc == 0 and "kopiran" in text
    assert (dest / "Objects" / "Cliparts" / "Signs" / "acqua.svg").exists()
    assert not (dest / "desktop.ini").exists()          # Drive's folder icons stay behind
    assert cl.state(str(src), str(dest)) == "ok"
    rc, text = _install(src, dest, monkeypatch)
    assert rc == 0 and "vec azuran" in text
    (src / "cSurveyPC.exe").write_bytes(b"exe-v2-longer")   # a new cSurvey on the Drive
    assert cl.state(str(src), str(dest)) == "old"
    rc, text = _install(src, dest, monkeypatch)
    assert "osvjezen" in text and (dest / "cSurveyPC.exe").read_bytes() == b"exe-v2-longer"
    assert not (tmp_path / "local" / "csurvey64.novo").exists()


def test_install_is_blocked_while_the_local_copy_runs(tmp_path, monkeypatch):
    src, dest = _drive(tmp_path), tmp_path / "local"
    monkeypatch.setattr(cl, "running_from", lambda d: True)
    out = io.StringIO()
    assert cl.cmd_install(str(src), str(dest), out, shortcut=False) == 1
    assert "BLOCKED" in out.getvalue() and not dest.exists()


def test_no_drive_is_an_error_for_install_but_fine_with_a_copy(tmp_path, monkeypatch):
    src, dest = tmp_path / "nowhere", tmp_path / "local"
    out = io.StringIO()
    assert cl.cmd_install(str(src), str(dest), out, shortcut=False) == 1
    assert "ERROR" in out.getvalue()
    dest.mkdir()
    (dest / "cSurveyPC.exe").write_bytes(b"x")
    assert cl.state(str(src), str(dest)) == "ok"       # offline: the copy is what we have


def test_check_only_warns(tmp_path):
    src = _drive(tmp_path)
    out = io.StringIO()
    assert cl.cmd_check(str(src), str(tmp_path / "local"), out) == 0
    assert "nema lokalnog cSurveya" in out.getvalue()


def test_local_dir_is_beside_the_prod_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert cl.local_dir() == os.path.join(str(tmp_path), "CaveDossier", "csurvey64")
