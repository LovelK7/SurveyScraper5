r"""Build the csurvey TDX drag-and-drop kit — the 3N-nacrt operator surface.

    python prod/build_csx_kit.py                     # stage into prod/dist/csx-kit
    python prod/build_csx_kit.py --publish           # + copy to the Drive
    python prod/build_csx_kit.py --publish-to DIR    # + copy somewhere else

Published shape, under <LOCAL_DRIVE_ROOT>/!!!Digitalizacija/SurveyScraper5/ —
the prod folder, beside the `cavedossier_*` launchers build_prod.py publishes
there:

    csurvey_0_PROCITAJ_ME.txt             <- the operator guide (Croatian)
    csurvey_1_pripremi_csx.bat            <- prepare a raw phone csx for import
    csurvey_2_dovrsi_uvoz.bat             <- finish the import, after "Save As"
    csurvey_3_oporavi_iz_zipa.bat         <- rescue: rebuild a broken csx from the zip
    csurvey_alati/                        <- the Python tools the .bat files drive

The `csurvey_` prefix keeps the launchers legible in a shared folder they do not
own, the same way `cavedossier_*` does; the machinery goes one level down so the
folder listing stays a listing of things a person opens. The **digit** is what
orders that listing by the workflow (user, 2026-09-20: alphabetically `fix_` sorted
above `preprocess_`, which reads as the wrong order). Operator-facing text is
Croatian — the .txt with diacritics, the .bat consoles without, since a cp852
console cannot print them.

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
from pathlib import Path, PureWindowsPath

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = REPO_ROOT / "prod" / "csx_templates"
TOOLS_DIR = REPO_ROOT / "stages" / "3N-nacrt" / "production" / "tools"
DIST = REPO_ROOT / "prod" / "dist" / "csx-kit"

# Drive-side location, relative to LOCAL_DRIVE_ROOT (.env). User decision
# 2026-09-20: the kit lives in the prod folder, beside the cavedossier
# launchers — one place for everything an operator double-clicks — not in a
# handoff folder of its own. Same dir as build_prod.TARGET_REL; the two kits'
# filenames never collide (`csurvey_*` vs `cavedossier_*`), and build_prod's
# _archive_old() only sweeps its own `cavedossier_*_v<X>.bat` / `v<X>/`.
TARGET_REL = Path("!!!Digitalizacija") / "SurveyScraper5"
# First prod version of the TopoDroid -> cSurvey kit (2026-09-20).
KIT_VERSION = "1.0"
# Subfolder holding the machinery, beside the launchers.
PAYLOAD_DIR = "csurvey_alati"

LAUNCHERS = [
    "csurvey_1_pripremi_csx.bat",
    "csurvey_2_dovrsi_uvoz.bat",
    "csurvey_3_oporavi_iz_zipa.bat",
]
# Pure-stdlib, self-locating. tdx-mapping.json is the user-owned mapping the
# pre/post-processors read from beside themselves.
TOOLS = [
    "preprocess_tdx_csx.py",
    "fix_imported_linetypes.py",
    "tdx_zip_to_csx.py",
    "parse_tdr.py",
    "sb_select.py",
    "tdx-mapping.json",
    # KORAK 3, the Nacrt finishing chain (project 0004). nacrt_finish.py imports
    # nacrt_layout.py and reads nacrt_finish_compass.xml from beside itself;
    # csurvey_driver.py runs csurvey_headless.ps1 the same way. Miss one and the
    # KORAK 3 launcher ImportErrors on an operator machine while working here.
    "nacrt_layout.py",
    "nacrt_finish.py",
    "nacrt_finish_compass.xml",
    "csurvey_headless.ps1",
    "csurvey_driver.py",
]
# Rendered like the launchers, but Croatian with real diacritics: UTF-8 BOM so
# Notepad is sure, exactly what build_prod.py does for PROCITAJ_ME.txt.
DOCS = ["csurvey_0_PROCITAJ_ME.txt"]


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def intake_leaf() -> str:
    r"""`..\!Za digitalizirat` — config.yaml's intake_dir, relative to the kit.

    A double-click scans this instead of the tree the kit happens to sit in, so
    the scan stays over the per-cave folders where the surveys actually are.
    """
    text = (REPO_ROOT / "config.yaml").read_text(encoding="utf-8")
    m = re.search(r'^\s*intake_dir:\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("config.yaml: archive.intake_dir not found")
    intake = PureWindowsPath(m.group(1).replace("/", "\\"))
    kit = PureWindowsPath(TARGET_REL)
    if intake.parts[0] != kit.parts[0]:
        raise SystemExit(
            f"intake_dir ({intake}) and the kit ({kit}) no longer share a Drive "
            f"folder — the double-click default has to be rethought, not "
            f"silently skewed.")
    # Both are Drive-root-relative; ".." hops out of the kit dir. A relative
    # path is what keeps the launchers movable with the folder they sit in.
    ups = "\\".join([".."] * (len(kit.parts) - 1))
    rest = str(PureWindowsPath(*intake.parts[1:]))
    return f"{ups}\\{rest}" if ups else rest


def render(name: str, tokens: dict[str, str], *, ascii_only: bool = True) -> str:
    text = (TEMPLATES_DIR / f"{name}.template").read_text(encoding="utf-8")
    for key, value in tokens.items():
        text = text.replace(f"@{key}@", value)
    leftover = [f"@{k}@" for k in tokens if f"@{k}@" in text]
    if leftover:
        raise SystemExit(f"{name}: unfilled tokens {leftover}")
    # A .bat runs in a cp852/cp1250 console that cannot print Croatian
    # diacritics, so the launchers stay ASCII (Croatian without them). The
    # .txt guide is read in Notepad and keeps its diacritics.
    if ascii_only:
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
        (out / name).write_text(render(name, tokens, ascii_only=False),
                                encoding="utf-8-sig", newline="\r\n")
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
