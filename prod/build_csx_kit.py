r"""Build the csurvey TDX drag-and-drop kit — the 3N-nacrt operator surface.

    python prod/build_csx_kit.py                     # stage into prod/dist/csx-kit
    python prod/build_csx_kit.py --publish           # + copy to the Drive
    python prod/build_csx_kit.py --publish-to DIR    # + copy somewhere else

Published shape, under <LOCAL_DRIVE_ROOT>/!!!Digitalizacija/ — the society's
digitalization folder, beside the `cavedossier_*` launchers in `SurveyScraper5/`:

    csurvey_preprocess_tdx.bat            <- STEP 2, double-click or drag
    csurvey_recover_tdx.bat               <- STEP 1b, only when a csx is broken
    csurvey_fix_tdx.bat                   <- STEP 4, after cSurvey "Save As"
    csurvey_READ ME FIRST - process a survey.txt
    csurvey_alati/                        <- the Python tools the .bat files drive

The `csurvey_` prefix is what keeps the launchers legible in a shared folder
they do not own, the same way `cavedossier_*` does; the machinery goes one level
down so the folder listing stays a listing of things a person opens.

A SELF-CONTAINED kit: the tools travel WITH the launchers. That is what makes
`%~dp0` enough to find everything, and it is why the old arrangement never
worked off this machine — each .bat hardcoded

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
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "prod" / "csx_templates"
TOOLS_DIR = REPO_ROOT / "stages" / "3N-nacrt" / "production" / "tools"
DIST = REPO_ROOT / "prod" / "dist" / "csx-kit"

# Drive-side location, relative to LOCAL_DRIVE_ROOT (.env). User decision
# 2026-09-20: the kit lives in the digitalization folder itself, next to the
# surveys it processes, not in a handoff folder of its own.
TARGET_REL = Path("!!!Digitalizacija")
# First prod version of the TopoDroid -> cSurvey kit (2026-09-20).
KIT_VERSION = "1.0"
# Subfolder holding the machinery, beside the launchers.
PAYLOAD_DIR = "csurvey_alati"

LAUNCHERS = [
    "csurvey_preprocess_tdx.bat",
    "csurvey_recover_tdx.bat",
    "csurvey_fix_tdx.bat",
]
# Pure-stdlib, self-locating. tdx-mapping.json is the user-owned mapping the
# pre/post-processors read from beside themselves.
TOOLS = [
    "preprocess_tdx_csx.py",
    "fix_imported_linetypes.py",
    "tdx_zip_to_csx.py",
    "parse_tdr.py",
    "tdx-mapping.json",
]
DOCS = ["csurvey_READ ME FIRST - process a survey.txt"]


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def intake_leaf() -> str:
    """`!Za digitalizirat` — config.yaml's intake_dir with TARGET_REL stripped.

    A double-click scans this instead of the whole digitalization tree, so the
    scan stays over the per-cave folders where the surveys actually are.
    """
    text = (REPO_ROOT / "config.yaml").read_text(encoding="utf-8")
    m = re.search(r'^\s*intake_dir:\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("config.yaml: archive.intake_dir not found")
    value = m.group(1).replace("/", "\\")
    prefix = f"{TARGET_REL}\\"
    if not value.startswith(prefix):
        raise SystemExit(
            f"intake_dir ({value}) is not under {TARGET_REL} — the kit's "
            f"double-click default has to be rethought, not silently skewed.")
    return value[len(prefix):]


def render(name: str, tokens: dict[str, str]) -> str:
    text = (TEMPLATES_DIR / f"{name}.template").read_text(encoding="utf-8")
    for key, value in tokens.items():
        text = text.replace(f"@{key}@", value)
    leftover = [f"@{k}@" for k in tokens if f"@{k}@" in text]
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
    payload = out / PAYLOAD_DIR
    payload.mkdir()

    tokens = {
        "TOOLS": str(TOOLS_DIR),
        "DATE": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "COMMIT": git_commit(),
        "VERSION": KIT_VERSION,
        "PAYLOAD": PAYLOAD_DIR,
        "INTAKE": intake_leaf(),
    }
    n = 0
    for name in LAUNCHERS:
        (out / name).write_text(render(name, tokens), encoding="ascii", newline="\r\n")
        n += 1
    for name in DOCS:
        shutil.copy2(TEMPLATES_DIR / name, out / name)
        n += 1
    for name in TOOLS:
        src = TOOLS_DIR / name
        if not src.exists():
            raise SystemExit(f"kit input missing: {src}")
        shutil.copy2(src, payload / name)
        n += 1
    (payload / "KIT_VERSION.txt").write_text(
        f"csurvey TDX kit v{KIT_VERSION}\n"
        f"built: {tokens['DATE']}\ncommit: {tokens['COMMIT']}\n"
        f"source: SurveyScraper5 (prod/build_csx_kit.py)\n"
        f"\nThis folder belongs beside the csurvey_*.bat files. Do not move or\n"
        f"rename it - the launchers look for it by name.\n",
        encoding="ascii", newline="\r\n")
    return n + 1


def drive_root() -> Path:
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("LOCAL_DRIVE_ROOT=") and not line.startswith("#"):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return Path(value)
    raise SystemExit("LOCAL_DRIVE_ROOT not set in .env — cannot publish.")


def publish(target: Path) -> None:
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit(
            f"publish target unreachable ({exc}).\n"
            f"Staged copy remains at {DIST} — publish again when the mount is back.")
    for item in sorted(DIST.iterdir()):
        if item.is_dir():
            shutil.copytree(item, target / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target / item.name)
    print(f"published to {target}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--publish", action="store_true",
                    help=f"also copy the kit into <LOCAL_DRIVE_ROOT>\\{TARGET_REL}")
    ap.add_argument("--publish-to", metavar="DIR",
                    help="publish into this folder instead of the Drive location")
    args = ap.parse_args(argv)

    count = build(DIST)
    print(f"staged {DIST}  ({count} files)")

    if args.publish or args.publish_to:
        target = Path(args.publish_to) if args.publish_to else drive_root() / TARGET_REL
        publish(target)
    else:
        print("(dry stage only - add --publish to copy it to the Drive)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
