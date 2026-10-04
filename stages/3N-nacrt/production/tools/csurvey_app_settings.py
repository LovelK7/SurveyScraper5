#!/usr/bin/env python3
"""Prime cSurvey's APP settings (the registry half) from csurvey-app-settings.json.

cSurvey has two kinds of settings (stages/3N-nacrt/production/csurvey-settings.md):
FILE settings live inside the .csx and are written by KORAK 2 from tdx-mapping.json
`postimport`; APP settings live in HKCU\\Software\\Cepelabs\\cSurvey, per Windows user
per computer, and are what this tool writes.

cSurvey reads that key ONCE when its window starts and writes its in-memory copy
back when the window closes (cEnvironmentSettings, cEditTools.vb:154-201; frmMain2.vb
:2678 load, :2903 save). So a value written while cSurvey is open is overwritten on
exit -- `apply` refuses to run then. Written while it is closed, the value survives:
cSurvey starts with it and saves the same value back. One priming per user per
computer is enough; re-running is harmless.

Usage:
  python csurvey_app_settings.py apply    # csurvey_0_postavi_csurvey.bat
  python csurvey_app_settings.py check    # KORAK 2: warn if not primed, never writes
  python csurvey_app_settings.py show     # the profile next to what is set now

Value type in the json decides the registry type: string -> REG_SZ, integer ->
REG_DWORD. cSurvey stores decimals invariant ("0.01", modNumbers.NumberToString),
so numeric strings are compared as numbers.
"""

import argparse
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True

DEFAULT_PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "csurvey-app-settings.json")
CSURVEY_EXE = "cSurveyPC.exe"


def load_profile(path):
    """(registry_key, [(name, value, ui)]) -- raises ValueError on a bad entry."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for name, spec in data.get("settings", {}).items():
        if not isinstance(spec, dict) or "value" not in spec:
            raise ValueError("%s: entry has no `value`" % name)
        value = spec["value"]
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError("%s: value must be a string (REG_SZ) or an integer "
                             "(REG_DWORD), not %r" % (name, value))
        out.append((name, value, spec.get("ui", "")))
    return data.get("registry_key", r"Software\Cepelabs\cSurvey"), out


def same(current, wanted):
    """Registry value equals the profile value? Numeric strings compare as numbers."""
    if current is None:
        return False
    if isinstance(wanted, int):
        try:
            return int(current) == wanted
        except (TypeError, ValueError):
            return False
    try:
        return abs(float(str(current)) - float(wanted)) < 1e-9
    except ValueError:
        return str(current) == wanted


class WinRegistry:
    """HKCU\\<key>. Kept tiny so tests can swap in a dict."""

    def __init__(self, key):
        import winreg
        self._w = winreg
        self._key = key

    def read(self, name):
        try:
            with self._w.OpenKey(self._w.HKEY_CURRENT_USER, self._key) as k:
                return self._w.QueryValueEx(k, name)[0]
        except OSError:
            return None

    def write(self, name, value):
        kind = self._w.REG_DWORD if isinstance(value, int) else self._w.REG_SZ
        with self._w.CreateKeyEx(self._w.HKEY_CURRENT_USER, self._key, 0,
                                 self._w.KEY_SET_VALUE) as k:
            self._w.SetValueEx(k, name, 0, kind, value)


def csurvey_running():
    """True / False, or None when it cannot be told (no tasklist)."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq %s" % CSURVEY_EXE, "/NH"],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return CSURVEY_EXE.lower() in out.stdout.lower()


def mismatches(settings, reg):
    return [(n, v, u, reg.read(n)) for n, v, u in settings if not same(reg.read(n), v)]


def cmd_apply(settings, reg, running):
    if running:
        print("BLOCKED: cSurvey je otvoren. Spremi rad, zatvori SVE cSurvey prozore")
        print("         i pokreni ovo ponovo. (cSurvey bi kod zatvaranja prepisao")
        print("         postavke svojim starima.)")
        return 1
    if running is None:
        print("WARNING: ne mogu provjeriti je li cSurvey otvoren - ako jest,")
        print("         zatvori ga i pokreni ovo ponovo.")
    for name, value, ui in settings:
        old = reg.read(name)
        reg.write(name, value)
        note = "vec postavljeno" if same(old, value) else "bilo: %s" % (
            "-" if old is None else old)
        print("  %-14s = %-8s %s  (%s)" % (name, value, ui, note))
    print("OK: cSurvey je postavljen (%d postavki). Ovo ne moras ponavljati na"
          % len(settings))
    print("    ovom racunalu - osim ako netko rucno promijeni te postavke.")
    return 0


def cmd_check(settings, reg):
    bad = mismatches(settings, reg)
    if not bad:
        print("OK: cSurvey postavke su u redu.")
        return 0
    print("UPOZORENJE: cSurvey na ovom racunalu nije postavljen za 3N:")
    for name, value, ui, cur in bad:
        print("  %-14s je %s, treba %s  (%s)"
              % (name, "-" if cur is None else cur, value, ui))
    print("  -> zatvori cSurvey i dvoklikni csurvey_0_postavi_csurvey.bat")
    return 0  # a warning, never a stop: the _postp file is already written



def cmd_show(settings, reg):
    for name, value, ui in settings:
        cur = reg.read(name)
        mark = "ok" if same(cur, value) else "!!"
        print("%s %-14s profil=%-8s sada=%-8s %s"
              % (mark, name, value, "-" if cur is None else cur, ui))
    return 0


_DETECT = object()


def main(argv=None, reg=None, running=_DETECT):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["apply", "check", "show"])
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    args = ap.parse_args(argv)

    try:
        key, settings = load_profile(args.profile)
    except (OSError, ValueError) as e:
        print("ERROR: %s: %s" % (os.path.basename(args.profile), e))
        return 0 if args.command == "check" else 1
    if reg is None:
        try:
            reg = WinRegistry(key)
        except ImportError:
            print("WARNING: nema Windows registra - cSurvey postavke preskocene.")
            return 0 if args.command == "check" else 1

    if args.command == "apply":
        return cmd_apply(settings, reg,
                         csurvey_running() if running is _DETECT else running)
    if args.command == "check":
        return cmd_check(settings, reg)
    return cmd_show(settings, reg)


if __name__ == "__main__":
    sys.exit(main())
