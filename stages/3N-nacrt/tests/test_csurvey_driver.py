"""csurvey_driver — the Python side of the headless cSurvey driver.

Everything that touches cSurvey is in `csurvey_headless.ps1`, so the wrapper is
tested against a **fake PowerShell**: `subprocess.run` is monkeypatched to hand
back canned stdout/stderr/exit codes, which covers the contract that actually
breaks in the field — exit-code mapping, JSON parsing, the `.env` fallback,
output naming, the timeout. One end-to-end test drives the real installed
cSurvey and skips everywhere it is absent.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import csurvey_driver  # noqa: E402
from csurvey_driver import DriverError  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "example" / "finishing"
RAW = FIXTURES / "SB_1103_golobreska_lt_raw.csx"

DIMENSIONS_JSON = (
    '{"cave": "GOLOBREŠKA_NANOEKSPEDICIJA", "l": 10, "pl": 4, "ml": 102, '
    '"pvr": 1, "nvr": 9, "drop": 10, "vr": 10, "qmx": 7.53, "qmn": -2.06, '
    '"es": "2", "caves": 1, "calculated": true}')


# ---------------------------------------------------------------------------
# the fake PowerShell


class FakeRun(object):
    """Stands in for `subprocess.run`, recording the argv it was handed."""

    def __init__(self, stdout="", stderr="", returncode=0, timeout=False,
                 writes=()):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.timeout = timeout
        self.writes = writes          # files the "printer" produces
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if self.timeout:
            raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 0))
        for path in self.writes:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"%PDF-1.4 fake\n")
        return subprocess.CompletedProcess(argv, self.returncode,
                                           self.stdout, self.stderr)

    def arg(self, name):
        """The value the last call passed for a `-Name` switch."""
        argv = self.calls[-1]
        return argv[argv.index(name) + 1]


@pytest.fixture()
def install(tmp_path, monkeypatch):
    """A directory that looks like a cSurvey install, and no ambient settings."""
    directory = tmp_path / "csurvey"
    directory.mkdir()
    (directory / "cSurveyPC.exe").write_bytes(b"MZ fake")
    monkeypatch.setattr(csurvey_driver, "_powershell", lambda: "powershell.exe")
    monkeypatch.setenv("CSURVEY_DIR", str(directory))
    monkeypatch.setenv("CSURVEY_PRINTER", "Fake PDF Printer")
    # No .env is consulted while the environment answers, but make sure a
    # developer's real one can never leak into a unit test either.
    monkeypatch.setattr(csurvey_driver, "workspace_root", lambda start=None: None)
    return directory


@pytest.fixture()
def survey(tmp_path):
    path = tmp_path / "SB_1103_golobreska_lt_fin.csx"
    path.write_text("<csurvey />", encoding="utf-8")
    return path


def fake(monkeypatch, **kwargs):
    runner = FakeRun(**kwargs)
    monkeypatch.setattr(csurvey_driver.subprocess, "run", runner)
    return runner


# ---------------------------------------------------------------------------
# what the script gets handed


def test_the_script_is_run_sta_with_the_resolved_settings(install, survey,
                                                          monkeypatch):
    runner = fake(monkeypatch, stdout="ok\n")
    csurvey_driver.info(str(survey))
    argv = runner.calls[0]
    assert argv[0] == "powershell.exe"
    assert "-STA" in argv and "-NoProfile" in argv
    assert argv[argv.index("-File") + 1] == str(csurvey_driver.SCRIPT)
    assert runner.arg("-Command") == "info"
    assert runner.arg("-Survey") == str(survey)
    assert runner.arg("-CSurveyDir") == str(install)
    assert runner.arg("-Printer") == "Fake PDF Printer"
    assert "-Out" not in argv


def test_print_overrides_are_only_passed_when_asked(install, survey, monkeypatch,
                                                    tmp_path):
    runner = fake(monkeypatch, writes=[tmp_path / "out" / "SB_1103_golobreska_plan.pdf",
                                       tmp_path / "out" / "SB_1103_golobreska_profile.pdf"])
    csurvey_driver.print_pdfs(str(survey), str(tmp_path / "out"))
    assert "-ScaleMode" not in runner.calls[-1]
    assert "-Landscape" not in runner.calls[-1]
    csurvey_driver.print_pdfs(str(survey), str(tmp_path / "out"),
                              scale_mode=99, scale=400, landscape=True)
    assert runner.arg("-ScaleMode") == "99"
    assert runner.arg("-Scale") == "400"
    assert "-Landscape" in runner.calls[-1]


def test_a_missing_install_is_a_readable_error(tmp_path, survey, monkeypatch):
    monkeypatch.setattr(csurvey_driver, "_powershell", lambda: "powershell.exe")
    monkeypatch.setenv("CSURVEY_DIR", str(tmp_path / "nowhere"))
    monkeypatch.setattr(csurvey_driver, "workspace_root", lambda start=None: None)
    with pytest.raises(DriverError) as raised:
        csurvey_driver.info(str(survey))
    assert "cSurvey is not installed" in str(raised.value)


def test_a_missing_survey_is_reported_before_powershell_starts(install, tmp_path,
                                                               monkeypatch):
    runner = fake(monkeypatch)
    with pytest.raises(DriverError):
        csurvey_driver.info(str(tmp_path / "gone.csx"))
    assert runner.calls == []


# ---------------------------------------------------------------------------
# exit codes


@pytest.mark.parametrize("code, needle", [
    (2, "usage or environment"),
    (3, "cSurvey internals changed"),
    (4, "cannot load the survey"),
    (5, "calculation failed"),
    (6, "printing failed"),
    (9, "exit 9"),
])
def test_every_exit_code_becomes_a_named_driver_error(install, survey, monkeypatch,
                                                      code, needle):
    fake(monkeypatch, returncode=code,
         stderr="csurvey_headless: something specific went wrong\n")
    with pytest.raises(DriverError) as raised:
        csurvey_driver.info(str(survey))
    assert needle in str(raised.value)
    # the script's own last line survives into the message and onto the object
    assert "something specific went wrong" in str(raised.value)
    assert raised.value.code == code
    assert "something specific" in raised.value.stderr


def test_a_failure_with_no_stderr_still_reads(install, survey, monkeypatch):
    fake(monkeypatch, returncode=4, stderr="")
    with pytest.raises(DriverError) as raised:
        csurvey_driver.info(str(survey))
    assert "no message" in str(raised.value)


def test_a_hang_is_killed_and_reported(install, survey, monkeypatch):
    fake(monkeypatch, timeout=True)
    with pytest.raises(DriverError) as raised:
        csurvey_driver.recalc(str(survey), str(survey), timeout=7)
    assert "did not answer within 7 s" in str(raised.value)
    assert raised.value.code is None


def test_stderr_on_a_successful_run_is_not_an_error(install, survey, monkeypatch):
    """A machine without therion on PATH prints to stderr and still succeeds."""
    result = None
    fake(monkeypatch, stdout="ok\n",
         stderr="'cavern' is not recognized as an internal or external command\n")
    result = csurvey_driver.info(str(survey))
    assert result.returncode == 0
    assert "cavern" in result.stderr


# ---------------------------------------------------------------------------
# dimensions


def test_dimensions_parses_the_json(install, survey, monkeypatch):
    fake(monkeypatch, stdout=DIMENSIONS_JSON + "\n")
    data = csurvey_driver.dimensions(str(survey))
    assert data["l"] == 10 and data["pl"] == 4 and data["nvr"] == 9
    assert data["drop"] == data["pvr"] + data["nvr"]
    assert data["es"] == "2"
    assert data["cave"].startswith("GOLOBRE")


def test_dimensions_survives_a_stray_line_on_stdout(install, survey, monkeypatch):
    fake(monkeypatch, stdout="'cavern' is not recognized\n" + DIMENSIONS_JSON + "\n")
    assert csurvey_driver.dimensions(str(survey))["l"] == 10


def test_dimensions_without_json_is_an_error(install, survey, monkeypatch):
    fake(monkeypatch, stdout="nothing useful here\n")
    with pytest.raises(DriverError) as raised:
        csurvey_driver.dimensions(str(survey))
    assert "no JSON on stdout" in str(raised.value)


def test_broken_json_is_an_error(install, survey, monkeypatch):
    fake(monkeypatch, stdout='{"l": 10, "pl": }\n')
    with pytest.raises(DriverError) as raised:
        csurvey_driver.dimensions(str(survey))
    assert "cannot parse" in str(raised.value)


# ---------------------------------------------------------------------------
# names and outputs


@pytest.mark.parametrize("stem, expected", [
    ("SB_1103_golobreska_lt_fin", "SB_1103_golobreska"),
    ("SB_1103_golobreska_lt", "SB_1103_golobreska"),
    ("cave_pp", "cave"),
    ("cave_recovered_pp_lt_fin", "cave_recovered"),
    ("plain", "plain"),
    ("_lt", "_lt"),                      # nothing left to name it by
])
def test_the_pipeline_suffix_chain_is_stripped(stem, expected):
    assert csurvey_driver.survey_base_name(stem + ".csx") == expected


def test_print_returns_both_pdfs_named_after_the_cave(install, survey, tmp_path,
                                                      monkeypatch):
    out = tmp_path / "pdf"
    fake(monkeypatch, writes=[out / "SB_1103_golobreska_plan.pdf",
                              out / "SB_1103_golobreska_profile.pdf"])
    found = csurvey_driver.print_pdfs(str(survey), str(out))
    assert Path(found["plan"]).name == "SB_1103_golobreska_plan.pdf"
    assert Path(found["profile"]).name == "SB_1103_golobreska_profile.pdf"


def test_a_silent_printer_is_caught(install, survey, tmp_path, monkeypatch):
    """Exit 0 with no file is the failure mode a print driver actually has."""
    fake(monkeypatch, writes=[])
    with pytest.raises(DriverError) as raised:
        csurvey_driver.print_pdfs(str(survey), str(tmp_path / "pdf"))
    assert "wrote no plan/profile PDF" in str(raised.value)
    assert raised.value.code == 6


def test_one_design_does_not_demand_the_other(install, survey, tmp_path,
                                              monkeypatch):
    out = tmp_path / "pdf"
    runner = fake(monkeypatch, writes=[out / "SB_1103_golobreska_profile.pdf"])
    found = csurvey_driver.print_pdfs(str(survey), str(out), design="Profile")
    assert found["profile"] and found["plan"] is None
    assert runner.arg("-Design") == "Profile"


# ---------------------------------------------------------------------------
# settings


def test_env_wins_over_the_default(install, survey, monkeypatch):
    runner = fake(monkeypatch, stdout="ok\n")
    csurvey_driver.info(str(survey))
    assert runner.arg("-Printer") == "Fake PDF Printer"


def test_an_explicit_argument_wins_over_the_env(install, survey, monkeypatch):
    runner = fake(monkeypatch, stdout="ok\n")
    csurvey_driver.info(str(survey), printer="Some Other Printer")
    assert runner.arg("-Printer") == "Some Other Printer"


def test_dotenv_fills_in_what_the_environment_does_not(tmp_path, survey,
                                                       monkeypatch):
    directory = tmp_path / "installed"
    directory.mkdir()
    (directory / "cSurveyPC.exe").write_bytes(b"MZ fake")
    root = tmp_path / "workspace"
    root.mkdir()
    (root / ".cavedossier-workspace").write_text("", encoding="utf-8")
    (root / ".env").write_text(
        "# per-machine\nCSURVEY_DIR=%s\nCSURVEY_PRINTER='Drive PDF'\n"
        % directory, encoding="utf-8")
    monkeypatch.setattr(csurvey_driver, "_powershell", lambda: "powershell.exe")
    monkeypatch.delenv("CSURVEY_DIR", raising=False)
    monkeypatch.delenv("CSURVEY_PRINTER", raising=False)
    monkeypatch.setattr(csurvey_driver, "workspace_root",
                        lambda start=None: str(root))
    runner = fake(monkeypatch, stdout="ok\n")
    csurvey_driver.info(str(survey))
    assert runner.arg("-CSurveyDir") == str(directory)
    assert runner.arg("-Printer") == "Drive PDF"


def test_defaults_when_nothing_is_configured(monkeypatch):
    monkeypatch.delenv("CSURVEY_DIR", raising=False)
    monkeypatch.setattr(csurvey_driver, "workspace_root", lambda start=None: None)
    assert csurvey_driver.setting("CSURVEY_DIR",
                                  csurvey_driver.DEFAULT_CSURVEY_DIR) \
        == csurvey_driver.DEFAULT_CSURVEY_DIR


def test_the_driver_refuses_politely_off_windows(monkeypatch):
    monkeypatch.setattr(csurvey_driver.os, "name", "posix")
    with pytest.raises(DriverError) as raised:
        csurvey_driver._powershell()
    assert "only be driven on Windows" in str(raised.value)


# ---------------------------------------------------------------------------
# finish_and_print


def _staged(tmp_path, monkeypatch, layout=None):
    """A survey plus the PDFs a print would leave, and optionally T1's sidecar."""
    survey = tmp_path / "SB_1103_golobreska_lt_fin.csx"
    survey.write_text("<csurvey />", encoding="utf-8")
    if layout is not None:
        (tmp_path / "SB_1103_golobreska_lt_fin.layout.json").write_text(
            json.dumps(layout), encoding="utf-8")
    out = tmp_path / "pdf"
    runner = fake(monkeypatch, stdout=DIMENSIONS_JSON + "\n",
                  writes=[out / "SB_1103_golobreska_plan.pdf",
                          out / "SB_1103_golobreska_profile.pdf"])
    return survey, out, runner


def test_finish_recalculates_before_it_prints(install, tmp_path, monkeypatch):
    survey, out, runner = _staged(tmp_path, monkeypatch)
    csurvey_driver.finish_and_print(str(survey), str(out))
    commands = [argv[argv.index("-Command") + 1] for argv in runner.calls]
    # the recalc must come first: only it fills <sms> with pvr/nvr/es
    assert commands == ["recalc", "print", "dimensions"]
    # and it saves back over the survey, so the printed file is the calculated one
    assert runner.calls[0][runner.calls[0].index("-Out") + 1] == str(survey)


def test_finish_merges_the_finisher_sidecar_into_one_json(install, tmp_path,
                                                          monkeypatch):
    layout = {"mjerilo": "1:100", "plan_scale": 100, "profile_scale": 100,
              "arrangement": "vertical",
              "plan_mm": {"x": 54.4, "y": 195.1, "width": 101.2, "height": 61.0},
              "profile_mm": {"x": 69.5, "y": 62.9, "width": 70.9, "height": 122.2},
              "warnings": ["not copied"], "entrance": "2"}
    survey, out, _runner = _staged(tmp_path, monkeypatch, layout=layout)
    result = csurvey_driver.finish_and_print(str(survey), str(out))

    written = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
    assert Path(result["json"]).name == "SB_1103_golobreska_dimenzije.json"
    assert written["nvr"] == 9 and written["es"] == "2"       # from cSurvey
    assert written["mjerilo"] == "1:100"                      # from the sidecar
    assert written["profile_mm"]["height"] == 122.2
    # only the keys the compositor and 4S need travel across
    assert "warnings" not in written and "entrance" not in written
    assert written["cave"].startswith("GOLOBRE")              # UTF-8 survives
    assert result["dimensions"] == written


def test_finish_without_a_sidecar_still_writes_the_numbers(install, tmp_path,
                                                           monkeypatch):
    survey, out, _runner = _staged(tmp_path, monkeypatch)
    result = csurvey_driver.finish_and_print(str(survey), str(out))
    written = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
    assert written["l"] == 10
    assert "mjerilo" not in written


# ---------------------------------------------------------------------------
# the real thing


CSURVEY_EXE = Path(csurvey_driver.setting(
    "CSURVEY_DIR", csurvey_driver.DEFAULT_CSURVEY_DIR)) / "cSurveyPC.exe"

live = pytest.mark.skipif(
    not (CSURVEY_EXE.exists() and RAW.exists()),
    reason="needs the installed cSurvey (CSURVEY_DIR) and the gitignored SB 1103 fixture")


@live
def test_end_to_end_on_sb1103(tmp_path):
    """nacrt_finish.py -> recalc -> print -> dimensions, against real cSurvey."""
    sys.path.insert(0, str(TOOLS))
    import nacrt_finish

    survey = tmp_path / "SB_1103_golobreska_lt.csx"
    survey.write_bytes(RAW.read_bytes())
    assert nacrt_finish.main([str(survey), "--yes"]) == 0
    finished = tmp_path / "SB_1103_golobreska_lt_fin.csx"
    assert finished.exists()

    out = tmp_path / "pdf"
    result = csurvey_driver.finish_and_print(str(finished), str(out), timeout=300)

    for view in ("plan", "profile"):
        pdf = Path(result[view])
        assert pdf.name == "SB_1103_golobreska_%s.pdf" % view
        assert pdf.stat().st_size > 10_000
        assert pdf.read_bytes().startswith(b"%PDF")

    numbers = result["dimensions"]
    # the manual Survey > Informations numbers for this cave
    assert numbers["l"] == 10
    assert numbers["pl"] == 4
    assert numbers["nvr"] == 9
    assert numbers["pvr"] == 1
    assert numbers["es"] == "2"          # the entrance nacrt_finish.py chose
    assert numbers["drop"] == numbers["vr"] == 10
    assert numbers["calculated"] is True

    written = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
    assert written["mjerilo"] == "1:100"
    assert written["plan_scale"] == written["profile_scale"] == 100
