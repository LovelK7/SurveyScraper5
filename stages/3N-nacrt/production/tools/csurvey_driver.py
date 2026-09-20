#!/usr/bin/env python3
"""Python side of the headless cSurvey driver: recalculate, print, read dimensions.

T2 of projects/0004-nacrt-finishing. Everything that touches cSurvey lives in
`csurvey_headless.ps1` next door; this module runs it, enforces the timeout the
script cannot enforce on itself, maps its exit codes onto `DriverError` and
parses its JSON. The XML side of KORAK 3 (`nacrt_finish.py`) never touches
cSurvey, and this side never touches XML — the two meet through files.

    from csurvey_driver import finish_and_print
    result = finish_and_print("SB_1103_..._lt_fin.csx", out_dir)
    # -> {"plan": ..._plan.pdf, "profile": ..._profile.pdf,
    #     "dimensions": {...}, "json": ..._dimenzije.json}

Fail-soft by design (brief sec. 3.2): when cSurvey is not installed, or the
machine is not Windows, every call raises `DriverError` with one readable line
and the caller can still hand the operator the finished `.csx` to open and
print in two clicks.

Per-machine facts come from the environment, then from the workspace `.env`:

    CSURVEY_DIR       install folder      (default C:\\csurvey64)
    CSURVEY_PRINTER   printer to print to (default "Microsoft Print to PDF")

Stdlib only and free of repo imports, like its siblings here: it travels into
the operator kit beside the tools that call it.

Usage:
  python csurvey_driver.py info       <survey>
  python csurvey_driver.py recalc     <survey> -o <saved.csx>
  python csurvey_driver.py print      <survey> -o <dir> [--design Plan|Profile|Both]
  python csurvey_driver.py dimensions <survey>
  python csurvey_driver.py finish     <survey> -o <dir>      (recalc -> print -> dimensions)
  python csurvey_driver.py finish     <intake> --sb 1103
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The kit runs from a shared Drive folder; don't litter it with __pycache__.
sys.dont_write_bytecode = True
import sb_select                                               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "csurvey_headless.ps1")

DEFAULT_CSURVEY_DIR = r"C:\csurvey64"
DEFAULT_PRINTER = "Microsoft Print to PDF"
DEFAULT_TIMEOUT = 180

# The marker at the top of the workspace (dev repo root, or an operator's
# extracted prod bundle). Absent in the kit, where the environment is all there is.
WORKSPACE_MARKER = ".cavedossier-workspace"

# csurvey_headless.ps1's contract, one message per code.
EXIT_MESSAGES = {
    2: "usage or environment",
    3: "cSurvey internals changed (reflection)",
    4: "cannot load the survey",
    5: "calculation failed",
    6: "printing failed",
}

# The suffix chain the pipeline appends; stripped so outputs are named after the
# cave. Same rule as Get-SurveyBaseName in the .ps1 — keep the two in step.
STEP_SUFFIXES = ("_fin", "_lt", "_pp")

# What finish_and_print copies out of nacrt_finish.py's sidecar into the
# dimensions JSON, so 4S and the compositor read one file.
LAYOUT_KEYS = ("mjerilo", "plan_scale", "profile_scale", "arrangement",
               "plan_mm", "profile_mm")


class DriverError(RuntimeError):
    """The driver could not do what was asked. `code` is the .ps1's exit code
    (or None when it never ran); `stderr` is what it said."""

    def __init__(self, message, code=None, stderr=""):
        super(DriverError, self).__init__(message)
        self.code = code
        self.stderr = stderr


class DriverResult(object):
    """One completed run of csurvey_headless.ps1."""

    __slots__ = ("command", "stdout", "stderr", "returncode")

    def __init__(self, command, stdout, stderr, returncode):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    @property
    def lines(self):
        return [line for line in self.stdout.splitlines() if line.strip()]

    def __repr__(self):
        return "DriverResult(%r, rc=%d, %d bytes)" % (
            self.command, self.returncode, len(self.stdout))


# ---------------------------------------------------------------------------
# per-machine settings


def workspace_root(start=None):
    """The nearest ancestor holding the workspace marker, or None.

    Deliberately not `cave_dossier.core.paths.workspace_root()`: this file
    travels into the operator kit, where the package does not exist.
    """
    for base in ([start] if start else [HERE, os.getcwd()]):
        path = os.path.abspath(base)
        while True:
            if os.path.exists(os.path.join(path, WORKSPACE_MARKER)):
                return path
            parent = os.path.dirname(path)
            if parent == path:
                break
            path = parent
    return None


def read_dotenv(root=None):
    """`KEY=VALUE` lines of the workspace `.env`, or {} when there is none."""
    root = root or workspace_root()
    if not root:
        return {}
    path = os.path.join(root, ".env")
    if not os.path.exists(path):
        return {}
    values = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _sep, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def setting(name, default, override=None):
    """Explicit argument, then the environment, then the workspace `.env`."""
    if override:
        return override
    value = os.environ.get(name)
    if value:
        return value
    value = read_dotenv().get(name)
    return value or default


# ---------------------------------------------------------------------------
# names


def survey_base_name(path):
    """`X_lt_fin.csx` -> `X`, so the PDFs are named after the cave."""
    stem = os.path.splitext(os.path.basename(path))[0]
    name = stem
    changed = True
    while changed:
        changed = False
        for suffix in STEP_SUFFIXES:
            if name.lower().endswith(suffix):
                name = name[:-len(suffix)]
                changed = True
    return name or stem


def layout_sidecar(survey):
    """nacrt_finish.py's `<name>_fin.layout.json`, when it is beside the survey."""
    path = os.path.splitext(survey)[0] + ".layout.json"
    return path if os.path.exists(path) else None


# ---------------------------------------------------------------------------
# running the script


def _powershell():
    """Windows PowerShell 5.1. `pwsh` is not a substitute: the reflection
    bootstrap needs .NET Framework, and `-STA` is 5.1-only."""
    if os.name != "nt":
        raise DriverError("cSurvey can only be driven on Windows "
                          "(this is %s)" % sys.platform)
    root = os.environ.get("SystemRoot", r"C:\Windows")
    path = os.path.join(root, "System32", "WindowsPowerShell", "v1.0",
                        "powershell.exe")
    return path if os.path.exists(path) else "powershell"


def run(command, survey, out=None, design="Both", timeout=DEFAULT_TIMEOUT,
        csurvey_dir=None, printer=None, scale_mode=None, scale=None,
        landscape=False):
    """One csurvey_headless.ps1 invocation. Raises DriverError unless it exits 0."""
    if not os.path.exists(SCRIPT):
        raise DriverError("csurvey_headless.ps1 is missing next to %s" % __file__)
    if not os.path.exists(survey):
        raise DriverError("survey not found: %s" % survey)
    directory = setting("CSURVEY_DIR", DEFAULT_CSURVEY_DIR, csurvey_dir)
    if not os.path.exists(os.path.join(directory, "cSurveyPC.exe")):
        raise DriverError(
            "cSurvey is not installed in %s — set CSURVEY_DIR in .env or pass "
            "--csurvey-dir" % directory)

    argv = [_powershell(), "-STA", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", SCRIPT,
            "-Survey", os.path.abspath(survey),
            "-Command", command,
            "-Design", design,
            "-CSurveyDir", directory,
            "-Printer", setting("CSURVEY_PRINTER", DEFAULT_PRINTER, printer)]
    if out:
        argv += ["-Out", os.path.abspath(out)]
    if scale_mode is not None:
        argv += ["-ScaleMode", str(scale_mode)]
    if scale:
        argv += ["-Scale", str(scale)]
    if landscape:
        argv += ["-Landscape"]

    try:
        done = subprocess.run(argv, capture_output=True, timeout=timeout,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        # The script cannot interrupt itself: the calculation runs on its own
        # single-threaded apartment, and cSurvey's sync ExecuteTherion blocks
        # behind a MsgBox on a huge survey. Killing the process is the watchdog.
        raise DriverError("cSurvey did not answer within %d s (%s %s)"
                          % (timeout, command, os.path.basename(survey)),
                          code=None, stderr="")
    except OSError as e:
        raise DriverError("cannot start PowerShell: %s" % e)

    if done.returncode != 0:
        detail = (done.stderr or "").strip().splitlines()
        reason = detail[-1] if detail else "no message"
        raise DriverError(
            "%s failed (%s): %s" % (command,
                                    EXIT_MESSAGES.get(done.returncode,
                                                      "exit %d" % done.returncode),
                                    reason),
            code=done.returncode, stderr=done.stderr or "")
    return DriverResult(command, done.stdout or "", done.stderr or "",
                        done.returncode)


def info(survey, **kw):
    return run("info", survey, **kw)


def recalc(survey, out, **kw):
    """Re-run the calculation and save — this is what fills `<sms>` with the
    entrance-relative numbers (pvr/nvr/es), so it must follow nacrt_finish.py."""
    return run("recalc", survey, out=out, **kw)


def dimensions(survey, **kw):
    """The cave's speleometrics as a dict (see csurvey_headless.ps1)."""
    result = run("dimensions", survey, **kw)
    text = result.stdout.strip()
    if not text.startswith("{"):
        # The script promises JSON and nothing else on stdout, but cSurvey
        # shells out to therion and a stray line would poison the parse.
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise DriverError("no JSON on stdout from `dimensions`: %r"
                              % text[:200], stderr=result.stderr)
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except ValueError as e:
        raise DriverError("cannot parse the dimensions JSON (%s): %r"
                          % (e, text[:200]), stderr=result.stderr)


def print_pdfs(survey, out_dir, design="Both", **kw):
    """Print to `<out_dir>/<name>_plan.pdf` and `<name>_profile.pdf`.

    Returns {"plan": path|None, "profile": path|None} — None for a design that
    was not asked for.
    """
    run("print", survey, out=out_dir, design=design, **kw)
    name = survey_base_name(survey)
    found = {}
    for view in ("plan", "profile"):
        path = os.path.join(out_dir, "%s_%s.pdf" % (name, view))
        found[view] = path if os.path.exists(path) else None
    wanted = ("plan", "profile") if design.lower() == "both" else (design.lower(),)
    missing = [v for v in wanted if found[v] is None]
    if missing:
        raise DriverError("cSurvey reported success but wrote no %s PDF in %s"
                          % ("/".join(missing), out_dir), code=6)
    return found


def finish_and_print(survey, out_dir, timeout=DEFAULT_TIMEOUT, **kw):
    """recalc -> print -> dimensions, and one `<name>_dimenzije.json` beside the PDFs.

    The recalc comes first and writes back into the survey: only after it does
    the per-cave `<sm>` row carry the entrance-relative depth the dossier wants.
    The JSON merges those numbers with the layout keys nacrt_finish.py left in
    its sidecar, so 4S and the compositor read one file instead of two.
    """
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    recalc(survey, survey, timeout=timeout, **kw)
    pdfs = print_pdfs(survey, out_dir, timeout=timeout, **kw)
    numbers = dimensions(survey, timeout=timeout, **kw)

    sidecar = layout_sidecar(survey)
    if sidecar:
        try:
            with open(sidecar, encoding="utf-8") as f:
                layout = json.load(f)
        except (OSError, ValueError):
            layout = {}
        for key in LAYOUT_KEYS:
            if key in layout:
                numbers[key] = layout[key]

    name = survey_base_name(survey)
    json_path = os.path.join(out_dir, "%s_dimenzije.json" % name)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(numbers, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return {"plan": pdfs["plan"], "profile": pdfs["profile"],
            "dimensions": numbers, "json": json_path}


# ---------------------------------------------------------------------------
# CLI


def finished_state(path):
    """Short Croatian label for the --sb menu."""
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    if stem.endswith("_fin"):
        return "dovrseno (_fin) - ovo se ispisuje"
    if stem.endswith("_lt"):
        return "jos nije dovrseno - prvo nacrt_finish.py"
    return "nije iz ovog koraka"


def pick_by_sb(inputs, sb):
    """--sb: intake folder + Redni broj -> the `_lt_fin` file(s), or None."""
    dirs = [a for a in inputs if os.path.isdir(a)]
    if len(dirs) != len(inputs) or len(dirs) != 1:
        print("ERROR: --sb takes exactly one folder (the intake dir) as input",
              file=sys.stderr)
        return None
    intake = dirs[0]
    leaves = sb_select.resolve(intake, sb)
    if leaves is None:
        return None
    files = [f for f in sb_select.list_files(leaves, (".csz", ".csx"))
             if os.path.splitext(f)[0].lower().endswith("_fin")]
    if not files:
        print("nothing to do - u toj mapi nema dovrsene (_fin) datoteke; "
              "prvo pokreni nacrt_finish.py")
        return None
    return sb_select.choose(files, labels=[finished_state(f) for f in files],
                            root=intake, prompt="Koju datoteku ispisati? ")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Pokreni cSurvey bez dijaloga: izracun, ispis u PDF, dimenzije.")
    ap.add_argument("command",
                    choices=["info", "recalc", "print", "dimensions", "finish"])
    ap.add_argument("input", nargs="+", help="survey file, or the intake folder with --sb")
    ap.add_argument("-o", "--out", help="output file (recalc) or folder (print/finish)")
    ap.add_argument("--design", default="Both", choices=["Plan", "Profile", "Both"])
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="seconds before cSurvey is killed (default %d)" % DEFAULT_TIMEOUT)
    ap.add_argument("--csurvey-dir", help="overrides CSURVEY_DIR")
    ap.add_argument("--printer", help="overrides CSURVEY_PRINTER")
    ap.add_argument("--scale-mode", type=int,
                    help="print-dialog combo index override (99 = custom + --scale)")
    ap.add_argument("--scale", type=int, help="scale denominator override")
    ap.add_argument("--landscape", action="store_true")
    ap.add_argument("--sb", nargs="+", metavar="BROJ",
                    help="with a folder input: pick the cave's _fin file")
    args = ap.parse_args(argv)

    if args.sb:
        picked = pick_by_sb(args.input, args.sb)
        if picked is None:
            return 1
        args.input = picked
    if len(args.input) > 1 and args.out:
        print("ERROR: -o/--out works with a single input only", file=sys.stderr)
        return 1

    options = {"timeout": args.timeout, "csurvey_dir": args.csurvey_dir,
               "printer": args.printer}
    if args.command == "print":
        options.update({"scale_mode": args.scale_mode, "scale": args.scale,
                        "landscape": args.landscape})

    rc = 0
    for survey in args.input:
        try:
            if args.command == "dimensions":
                print(json.dumps(dimensions(survey, **options),
                                 ensure_ascii=False, sort_keys=True))
            elif args.command == "finish":
                out_dir = args.out or os.path.dirname(os.path.abspath(survey))
                result = finish_and_print(survey, out_dir, **options)
                print("OK  %s" % result["plan"])
                print("OK  %s" % result["profile"])
                print("OK  %s" % result["json"])
            elif args.command == "print":
                out_dir = args.out or os.path.dirname(os.path.abspath(survey))
                for view, path in sorted(print_pdfs(survey, out_dir,
                                                    design=args.design,
                                                    **options).items()):
                    if path:
                        print("OK  %s" % path)
            elif args.command == "recalc":
                if not args.out:
                    print("ERROR: recalc needs -o <saved.csx|csz>", file=sys.stderr)
                    return 1
                print(recalc(survey, args.out, **options).stdout.rstrip())
            else:
                print(info(survey, **options).stdout.rstrip())
        except DriverError as e:
            print("ERROR: %s" % e, file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
