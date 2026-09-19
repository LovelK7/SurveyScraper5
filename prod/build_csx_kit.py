r"""Build the TDX drag-and-drop kit — the 3N-nacrt operator surface.

    python prod/build_csx_kit.py                     # stage into prod/dist/csx-kit
    python prod/build_csx_kit.py --publish "G:/My Drive/Share/TDX"

A SELF-CONTAINED kit: the three .bat files are copied out into an operator's
TDX working folder, and the Python tools they drive go WITH them. That is what
makes `%~dp0` enough to find everything, and it is why the old arrangement
never worked off this machine — each .bat hardcoded

    set "TOOLS=C:\Users\<developer>\...\production\tools"

and their own headers said "this is a copy". Every copy handed to an operator
has therefore been inert since the day it was handed over. Generating them
makes that path a build-time value with a fallback chain behind it, the same
shape build_prod.py already uses for the cavedossier launchers.

The four tools are pure-stdlib and already resolve their own data files
relative to __file__, so nothing else has to travel.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "prod" / "csx_templates"
TOOLS_DIR = REPO_ROOT / "stages" / "3N-nacrt" / "production" / "tools"
DIST = REPO_ROOT / "prod" / "dist" / "csx-kit"

LAUNCHERS = ["preprocess_tdx.bat", "recover_tdx.bat", "fix_tdx.bat"]
# Pure-stdlib, self-locating. tdx-mapping.json is the user-owned mapping the
# pre/post-processors read from beside themselves.
TOOLS = [
    "preprocess_tdx_csx.py",
    "fix_imported_linetypes.py",
    "tdx_zip_to_csx.py",
    "parse_tdr.py",
    "tdx-mapping.json",
]
DOCS = ["READ ME FIRST - process a survey.txt"]


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def render(name: str, tokens: dict[str, str]) -> str:
    text = (TEMPLATES_DIR / f"{name}.template").read_text(encoding="utf-8")
    for key, value in tokens.items():
        text = text.replace(f"@{key}@", value)
    leftover = [t for t in ("@TOOLS@", "@DATE@", "@COMMIT@") if t in text]
    if leftover:
        raise SystemExit(f"{name}: unfilled tokens {leftover}")
    # The operator console is cp852/cp1250; these files must stay ASCII, the
    # same rule build_prod.py enforces for PROCITAJ_ME.txt.
    try:
        text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise SystemExit(f"{name}: non-ASCII at position {exc.start}: {exc.object[exc.start:exc.start+40]!r}")
    return text


def build(out: Path) -> int:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    tokens = {
        "TOOLS": str(TOOLS_DIR),
        "DATE": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "COMMIT": git_commit(),
    }
    n = 0
    for name in LAUNCHERS:
        (out / name).write_text(render(name, tokens), encoding="ascii", newline="\r\n")
        n += 1
    for name, src_dir in [(t, TOOLS_DIR) for t in TOOLS] + [(d, TEMPLATES_DIR) for d in DOCS]:
        src = src_dir / name
        if not src.exists():
            raise SystemExit(f"kit input missing: {src}")
        shutil.copy2(src, out / name)
        n += 1
    (out / "KIT_VERSION.txt").write_text(
        f"built: {tokens['DATE']}\ncommit: {tokens['COMMIT']}\n"
        f"source: SurveyScraper5 (prod/build_csx_kit.py)\n"
        f"\nThis whole folder travels together. Do not separate the .bat files\n"
        f"from the .py files beside them.\n",
        encoding="ascii", newline="\r\n")
    return n + 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--publish", metavar="DIR",
                    help="also copy the kit into this folder (the operator's TDX dir)")
    args = ap.parse_args(argv)

    count = build(DIST)
    print(f"staged {DIST}  ({count} files)")

    if args.publish:
        target = Path(args.publish)
        if not target.is_dir():
            raise SystemExit(f"--publish target is not a directory: {target}")
        for item in sorted(DIST.iterdir()):
            shutil.copy2(item, target / item.name)
        print(f"published to {target}")
        print("\nTell the operators once: delete the old .bat files in that folder\n"
              "and copy the whole new folder over. After this the kit is\n"
              "self-contained, so it is the last time.")
    else:
        print("(dry stage only - add --publish <TDX folder> to copy it out)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
