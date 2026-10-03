"""csurvey_app_settings — priming cSurvey's registry (APP) settings.

The registry is swapped for a dict, so nothing here touches the developer's
cSurvey. The live path was validated by hand (csurvey-settings.md).
"""

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import csurvey_app_settings as cas  # noqa: E402


class FakeReg:
    def __init__(self, **values):
        self.values = dict(values)
        self.writes = []

    def read(self, name):
        return self.values.get(name)

    def write(self, name, value):
        self.writes.append((name, value))
        self.values[name] = value


@pytest.fixture
def profile(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"settings": {
        "pens.smooth": {"value": "0.01", "ui": "Pen > Smoothing factor"},
        "design.rulers": {"value": 1},
    }}), encoding="utf-8")
    return str(p)


def test_shipped_profile_loads_and_turns_pen_smoothing_off():
    key, settings = cas.load_profile(cas.DEFAULT_PROFILE)
    assert key == r"Software\Cepelabs\cSurvey"
    values = {n: v for n, v, _ in settings}
    # cSurvey writes the toggle as REG_SZ "0"/"1" (frmMain2.vb:2904)
    assert values["pens.smooting"] == "0"


@pytest.mark.parametrize("current, wanted, expected", [
    ("0.01", "0.01", True),
    ("0.0100", "0.01", True),      # cSurvey writes "0.00" format
    ("0.75", "0.01", False),
    (None, "0.01", False),
    (1, 1, True),                  # REG_DWORD read back as int
    ("1", 1, True),
    ("abc", 1, False),
    ("Arial", "Arial", True),
])
def test_same(current, wanted, expected):
    assert cas.same(current, wanted) is expected


def test_bad_value_type_is_rejected(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"settings": {"x": {"value": 0.01}}}))
    with pytest.raises(ValueError):
        cas.load_profile(str(p))


def test_apply_writes_every_setting(profile, capsys):
    reg = FakeReg(**{"pens.smooth": "0.75"})
    assert cas.main(["apply", "--profile", profile], reg=reg, running=False) == 0
    assert reg.values == {"pens.smooth": "0.01", "design.rulers": 1}
    assert "OK:" in capsys.readouterr().out


def test_apply_refuses_while_csurvey_is_open(profile, capsys):
    reg = FakeReg(**{"pens.smooth": "0.75"})
    assert cas.main(["apply", "--profile", profile], reg=reg, running=True) == 1
    assert reg.writes == []
    assert "BLOCKED" in capsys.readouterr().out


def test_apply_proceeds_with_a_warning_when_unknown(profile, capsys):
    reg = FakeReg()
    assert cas.main(["apply", "--profile", profile], reg=reg, running=None) == 0
    assert len(reg.writes) == 2
    assert "WARNING" in capsys.readouterr().out


def test_check_warns_but_never_writes_or_fails(profile, capsys):
    reg = FakeReg(**{"pens.smooth": "0.75", "design.rulers": 1})
    assert cas.main(["check", "--profile", profile], reg=reg) == 0
    out = capsys.readouterr().out
    assert reg.writes == []
    assert "UPOZORENJE" in out and "pens.smooth" in out
    assert "design.rulers" not in out
    assert "csurvey_0_postavi_csurvey.bat" in out


def test_check_ok_when_primed(profile, capsys):
    reg = FakeReg(**{"pens.smooth": "0.01", "design.rulers": 1})
    assert cas.main(["check", "--profile", profile], reg=reg) == 0
    assert "OK:" in capsys.readouterr().out


def test_check_survives_a_missing_profile(tmp_path, capsys):
    missing = str(tmp_path / "nope.json")
    assert cas.main(["check", "--profile", missing], reg=FakeReg()) == 0
    assert cas.main(["apply", "--profile", missing], reg=FakeReg(),
                    running=False) == 1
