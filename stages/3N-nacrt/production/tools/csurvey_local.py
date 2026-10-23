#!/usr/bin/env python3
"""A local copy of the shared cSurvey, so it can be opened by hand.

The registry's cSurvey lives once on the shared Drive
(!!!Digitalizacija/Software/csurvey64). Headless steps run from there fine, but
cSurvey OPENED BY HAND from the Drive crashes: its sign gallery loads every
gallery SVG through a lowercased full path (cCliparts.vb:388), and Google
Drive's G: filesystem is case-sensitive in folder names ("speleo baza sue" is
not "Speleo baza SUE") -> "Could not find a part of the path ...acqua.svg"
(found 2026-10-12, docs/design-decisions.md). A copy on the local disk has no
such problem.

Usage:
  python csurvey_local.py install   # KORAK 0: copy (or refresh) + desktop shortcut
  python csurvey_local.py ensure    # KORAK 1-4: the same, but silent when current
  python csurvey_local.py check     # only say if the copy is missing or old
  python csurvey_local.py where     # print the folder cSurvey should be opened from

The copy goes to %LOCALAPPDATA%\\CaveDossier\\csurvey64, with a stamp of the
Drive's cSurveyPC.exe (size + mtime). It is copied again only when that changes,
so updating cSurvey for everyone stays "replace it on the Drive, run KORAK 0".
Stdlib only - the kit runs on operators' machines.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import csurvey_driver  # noqa: E402

EXE = "cSurveyPC.exe"
STAMP = ".csurvey-local.json"
SHORTCUT = "cSurvey.lnk"


def local_dir():
    return csurvey_driver.local_csurvey_dir()


def drive_dir():
    """The shared copy on the Drive (beside the kit, or under LOCAL_DRIVE_ROOT)."""
    return csurvey_driver.drive_csurvey_dir()


def exe_stamp(folder):
    st = os.stat(os.path.join(folder, EXE))
    return {"exe_size": st.st_size, "exe_mtime": int(st.st_mtime)}


def read_stamp(folder):
    try:
        with open(os.path.join(folder, STAMP), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def state(src, dest):
    """'missing' | 'old' | 'ok' | 'no-source' (the Drive copy is not reachable)."""
    have = os.path.exists(os.path.join(dest, EXE))
    if not os.path.exists(os.path.join(src, EXE)):
        return "ok" if have else "no-source"
    if not have:
        return "missing"
    old = read_stamp(dest) or {}
    new = exe_stamp(src)
    return "ok" if all(old.get(k) == v for k, v in new.items()) else "old"


def running_from(dest):
    """True when a cSurvey started from `dest` is running (its files are locked)."""
    if os.name != "nt":
        return False
    ps = ("Get-Process cSurveyPC -ErrorAction SilentlyContinue | "
          "ForEach-Object { $_.Path }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    d = os.path.normcase(os.path.abspath(dest))
    return any(os.path.normcase(p.strip()).startswith(d) for p in out.splitlines() if p.strip())


def copy(src, dest, out=sys.stdout):
    """Copy src -> dest through a sibling temp folder, then swap it in."""
    tmp = dest + ".novo"
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    files = sum(len(fs) for _, _, fs in os.walk(src))
    print("  kopiram cSurvey s Drivea (%d datoteka, ~175 MB) - moze potrajati..." % files,
          file=out, flush=True)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns("desktop.ini"))
    with open(os.path.join(tmp, STAMP), "w", encoding="utf-8") as f:
        json.dump(dict(exe_stamp(src), source=os.path.abspath(src)), f)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.replace(tmp, dest)


def desktop_shortcut(dest):
    """A cSurvey.lnk on the user's desktop pointing at the local copy. -> path or None."""
    if os.name != "nt":
        return None
    ps = ("$d=[Environment]::GetFolderPath('Desktop');"
          "$l=Join-Path $d '%s';"
          "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($l);"
          "$s.TargetPath='%s';$s.WorkingDirectory='%s';$s.Save();$l"
          % (SHORTCUT, os.path.join(dest, EXE).replace("'", "''"), dest.replace("'", "''")))
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


PROGID = "CaveDossier.cSurvey"
EXTENSIONS = (".csx", ".csz")


def associate(dest, reg=None):
    """Double-click on a .csx/.csz opens the local copy, for this Windows user
    (HKCU, no admin). The file goes in as `filename="%1"`: a bare path is
    lowercased by cSurvey (cCommandLineParameters.vb:142, upstream/0001) and a
    survey under the shared Drive folder is then not found. An extension
    another program already owns is left alone. -> extensions set."""
    if reg is None:
        if os.name != "nt":
            return []
        import winreg as reg
    root = reg.HKEY_CURRENT_USER
    exe = os.path.join(dest, EXE)
    done = []
    for ext in EXTENSIONS:
        try:
            with reg.OpenKey(root, r"Software\Classes\%s" % ext) as k:
                current = reg.QueryValueEx(k, "")[0]
        except OSError:
            current = ""
        if current and current != PROGID:
            continue
        with reg.CreateKey(root, r"Software\Classes\%s" % ext) as k:
            reg.SetValueEx(k, "", 0, reg.REG_SZ, PROGID)
        done.append(ext)
    if done:
        base = r"Software\Classes\%s" % PROGID
        with reg.CreateKey(root, base) as k:
            reg.SetValueEx(k, "", 0, reg.REG_SZ, "cSurvey")
        with reg.CreateKey(root, base + r"\DefaultIcon") as k:
            reg.SetValueEx(k, "", 0, reg.REG_SZ, '"%s",0' % exe)
        with reg.CreateKey(root, base + r"\shell\open\command") as k:
            reg.SetValueEx(k, "", 0, reg.REG_SZ, '"%s" "filename=%%1"' % exe)
    return done


def cmd_install(src, dest, out=sys.stdout, shortcut=True):
    st = state(src, dest)
    if st == "no-source":
        print("ERROR: ne vidim cSurvey na Driveu (%s). Je li Google Drive pokrenut?" % src,
              file=out)
        return 1
    if st == "ok":
        print("OK: lokalni cSurvey je vec azuran: %s" % dest, file=out)
    else:
        if running_from(dest):
            print("BLOCKED: lokalni cSurvey je otvoren. Zatvori SVE cSurvey prozore i"
                  " pokreni ovo ponovo.", file=out)
            return 1
        try:
            copy(src, dest, out)
        except OSError as e:
            print("ERROR: kopiranje nije uspjelo (%s)" % e, file=out)
            return 1
        print("OK: cSurvey %s u %s" % ("kopiran" if st == "missing" else "osvjezen", dest),
              file=out)
    if shortcut:
        lnk = desktop_shortcut(dest)
        if lnk:
            print("    precac na radnoj povrsini: %s" % lnk, file=out)
        try:
            exts = associate(dest)
        except OSError as e:
            exts = []
            print("    (dvoklik na .csx nije postavljen: %s)" % e, file=out)
        if exts:
            print("    dvoklik na %s otvara ovaj cSurvey" % "/".join(exts), file=out)
    print("    Otvaraj cSurvey s tog precaca, NE s Drivea (s Drivea se srusi:"
          " 'Could not find a part of the path ...').", file=out)
    return 0


def cmd_check(src, dest, out=sys.stdout):
    st = state(src, dest)
    if st == "missing":
        print("UPOZORENJE: na ovom racunalu nema lokalnog cSurveya - otvoren s Drivea se"
              " srusi.\n  -> dvoklikni csurvey_0_postavi_csurvey.bat (KORAK 0)", file=out)
    elif st == "old":
        print("UPOZORENJE: lokalni cSurvey je stariji od onoga na Driveu.\n"
              "  -> zatvori cSurvey i dvoklikni csurvey_0_postavi_csurvey.bat (KORAK 0)", file=out)
    return 0    # a warning, never a stop


def cmd_ensure(src, dest, out=sys.stdout, shortcut=True):
    """Every KORAK runs this: silent when the copy is current, copies when it is
    missing or the Drive has a newer cSurvey. Never stops the step it runs in."""
    st = state(src, dest)
    if st in ("ok", "no-source"):
        return 0
    if st == "old" and running_from(dest):
        print("NAPOMENA: na Driveu je noviji cSurvey; lokalni se osvjezi kad ga zatvoris"
              " i pokrenes bilo koji KORAK.", file=out)
        return 0
    cmd_install(src, dest, out, shortcut=shortcut)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["install", "ensure", "check", "where"])
    ap.add_argument("--source", default=None, help="the shared cSurvey folder (default: the kit's)")
    ap.add_argument("--dest", default=None, help="the local folder (default: %%LOCALAPPDATA%%)")
    ap.add_argument("--no-shortcut", action="store_true")
    a = ap.parse_args(argv)
    src, dest = a.source or drive_dir(), a.dest or local_dir()
    if a.command == "install":
        return cmd_install(src, dest, shortcut=not a.no_shortcut)
    if a.command == "ensure":
        return cmd_ensure(src, dest, shortcut=not a.no_shortcut)
    if a.command == "check":
        return cmd_check(src, dest)
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
