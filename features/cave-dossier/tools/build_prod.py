"""Build + publish the PROD launchers for operator-facing cavedossier commands.

Part of the dev/prod duality (ARCHITECTURE.md §Dev vs prod): operators work on
the registry Drive and never see this repo. This tool renders **versioned,
double-clickable launchers** and a self-contained code bundle, and publishes
them into the shared folder

    <LOCAL_DRIVE_ROOT>/!!!Digitalizacija/SurveyScraper5/

Drive-side layout (all generated here, nothing hand-edited on the Drive):

    SurveyScraper5/
    ├─ cavedossier_osz_prefill_v<X>.bat      ← operators double-click these
    ├─ cavedossier_photos_process_v<X>.bat
    ├─ PROCITAJ_ME.txt                        ← operator guide (Croatian)
    ├─ VERZIJE.txt                            ← publish log, one line per release
    ├─ v<X>/                                  ← support for the current version
    │  ├─ bootstrap.ps1                       ← all setup/run logic (shared)
    │  └─ bundle.zip                          ← feature tree subset (see below)
    ├─ podaci/geo/                            ← cloud copy of data/geo runtime
    └─ _arhiva/                               ← superseded launchers + v-dirs

First double-click on a machine installs to %LOCALAPPDATA%\\CaveDossier\\v<X>
(bundle extracted, venv + pip install of [osz,photos,geo], .env generated with
LOCAL_DRIVE_ROOT derived from the launcher's own location, podaci/geo copied
locally). The [karta] extra is deliberately NOT installed: georef.hr excerpt
collection (browser + shared credentials + server-side saves) stays a dev
step; prefill embeds already-collected excerpts and degrades with a note
otherwise.

Usage (dev machine, repo venv):

    python tools/build_prod.py --version 1.0             # stage dist/prod/v1.0
    python tools/build_prod.py --version 1.0 --publish   # + copy to the Drive
    python tools/build_prod.py --version 1.1 --publish --skip-geo

Bump the version for every regeneration that operators should pick up — the
launcher filename IS the version indicator; same-version republishes are for
dev iteration only (bootstrap detects the newer bundle.zip and reinstalls).

Adding a prod command later: add it to PROD_COMMANDS below AND give it a
branch in the `switch ($Command)` of prod_templates/bootstrap.ps1.template.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

FEATURE_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = FEATURE_ROOT / "tools" / "prod_templates"
DIST_ROOT = FEATURE_ROOT / "dist" / "prod"

# Drive-side location, relative to LOCAL_DRIVE_ROOT (.env). User decision
# 2026-09-02: a dedicated SurveyScraper5 folder inside !!!Digitalizacija.
TARGET_REL = Path("!!!Digitalizacija") / "SurveyScraper5"

# command id (launcher filename + bootstrap -Command) -> cavedossier argv.
# The Croatian label lives in bootstrap.ps1.template's switch.
PROD_COMMANDS = {
    "osz_prefill": ("osz", "prefill"),
    "photos_process": ("photos", "process"),
}

# What the code bundle carries — everything FEATURE_ROOT-relative that the two
# commands stand on at runtime (config.py resolves against FEATURE_ROOT, which
# after extraction is %LOCALAPPDATA%\CaveDossier\v<X>).
BUNDLE_FILES = [
    "pyproject.toml",
    "config.yaml",
    ".env.example",
    "data/README.md",
    "osz-template/templates/Zapisnik_OSZ_v10.docx",
]
BUNDLE_DIRS = [
    "src",
    "config",
    "data/people",
]
BUNDLE_EXCLUDE_DIRS = {"__pycache__", ".venv", ".pytest_cache"}

# Cloud copy of data/geo: the runtime datasets only. inspire_au/ + the raw
# INSPIRE_AU.zip are build material for the GeoPackages, not runtime inputs.
GEO_ITEMS = [
    "naselja.gpkg",
    "jls.gpkg",
    "zupanije.gpkg",
    "rgi_named_places.gpkg",
    "el_cov_index.gml",
    "dem",
]

VERSION_RE = re.compile(r"^\d+\.\d+$")


def _render(template_name: str, **tokens: str) -> str:
    """Fill @TOKEN@ placeholders (str.format would trip on PS/bat braces)."""
    text = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
    for name, value in tokens.items():
        text = text.replace(f"@{name.upper()}@", value)
    leftover = re.search(r"@[A-Z_]+@", text)
    if leftover:
        raise SystemExit(f"{template_name}: unfilled placeholder {leftover.group(0)}")
    return text


def _georef_env() -> dict[str, str]:
    """The shared georef.hr login, read from the dev .env at build time.

    Injected into bootstrap.ps1 so operator machines can run the karta flow
    themselves (user decision 2026-09-02). Never committed — the values ride
    only in the generated script on the society-internal Drive. Missing values
    render as empty strings: bootstrap then skips the GEOREF lines and the
    karta flow degrades with its note.
    """
    values = {"GEOREF_BASE_URL": "", "GEOREF_USERNAME": "", "GEOREF_PASSWORD": ""}
    env_file = FEATURE_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key in values:
                values[key] = value.strip().strip('"').strip("'")
    if not all(values.values()):
        print("WARN: GEOREF_* incomplete in .env — prod karta flow will be inert")
    return values


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=FEATURE_ROOT, capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 — provenance stamp is best-effort
        return "unknown"


def build_bundle(zip_path: Path, version: str) -> int:
    """Write bundle.zip; returns the number of members."""
    stamp = (
        f"version: {version}\n"
        f"built: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"commit: {_git_commit()}\n"
        "source: SurveyScraper5 features/cave-dossier (tools/build_prod.py)\n"
    )
    members = 0
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in BUNDLE_FILES:
            src = FEATURE_ROOT / rel
            if not src.exists():
                raise SystemExit(f"bundle input missing: {src}")
            zf.write(src, rel)
            members += 1
        for rel in BUNDLE_DIRS:
            root = FEATURE_ROOT / rel
            if not root.is_dir():
                raise SystemExit(f"bundle input missing: {root}")
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                parts = path.relative_to(FEATURE_ROOT).parts
                if any(p in BUNDLE_EXCLUDE_DIRS for p in parts):
                    continue
                if path.suffix in {".pyc", ".pyo"}:
                    continue
                zf.write(path, path.relative_to(FEATURE_ROOT).as_posix())
                members += 1
        zf.writestr("PROD_VERSION.txt", stamp)
        members += 1
    return members


def launcher_name(command_id: str, version: str) -> str:
    return f"cavedossier_{command_id}_v{version}.bat"


def stage(version: str) -> Path:
    """Render everything into dist/prod/v<version>/ mirroring the Drive layout."""
    out = DIST_ROOT / f"v{version}"
    if out.exists():
        shutil.rmtree(out)
    (out / f"v{version}").mkdir(parents=True)

    bootstrap = _render("bootstrap.ps1.template", version=version, **_georef_env())
    # PS 5.1 wants a BOM to read a script as UTF-8; content is ASCII anyway,
    # so write ASCII and let any future non-ASCII edit fail loudly here.
    (out / f"v{version}" / "bootstrap.ps1").write_text(bootstrap, encoding="ascii")

    for command_id in PROD_COMMANDS:
        bat = _render("launcher.bat.template", version=version, command_id=command_id)
        # cmd.exe reads .bat in the OEM codepage; keep launchers pure ASCII.
        (out / launcher_name(command_id, version)).write_text(bat, encoding="ascii", newline="\r\n")

    readme = _render("PROCITAJ_ME.txt.template", version=version)
    # Real Croatian diacritics (user, 2026-09-02); UTF-8 BOM so Notepad is sure.
    (out / "PROCITAJ_ME.txt").write_text(readme, encoding="utf-8-sig", newline="\r\n")

    members = build_bundle(out / f"v{version}" / "bundle.zip", version)
    print(f"staged {out}  (bundle: {members} members)")
    return out


# ── publishing ─────────────────────────────────────────────────────────


def _drive_root() -> Path:
    env_file = FEATURE_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("LOCAL_DRIVE_ROOT=") and not line.startswith("#"):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    return Path(value)
    raise SystemExit("LOCAL_DRIVE_ROOT not set in .env — cannot publish.")


def _archive_old(target: Path, version: str) -> None:
    """Move superseded launchers and v-dirs into _arhiva/ (latest stays visible)."""
    arhiva = target / "_arhiva"
    stale: list[Path] = []
    for item in target.iterdir():
        if item.is_file() and re.fullmatch(r"cavedossier_\w+_v[\d.]+\.bat", item.name):
            if not item.name.endswith(f"_v{version}.bat"):
                stale.append(item)
        elif item.is_dir() and re.fullmatch(r"v[\d.]+", item.name) and item.name != f"v{version}":
            stale.append(item)
    for item in stale:
        arhiva.mkdir(exist_ok=True)
        dest = arhiva / item.name
        try:
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
            print(f"  archived {item.name} -> _arhiva/")
        except OSError as exc:
            # Hand-managed Drive dir: a locked/open file must not kill the
            # publish — the versioned filenames still disambiguate.
            print(f"  WARN: could not archive {item.name}: {exc}")


def _sync_geo(target: Path) -> None:
    """Incremental copy of the runtime geo datasets into podaci/geo/."""
    src_root = FEATURE_ROOT / "data" / "geo"
    dst_root = target / "podaci" / "geo"
    copied = skipped = 0

    def _sync_file(src: Path, dst: Path) -> None:
        nonlocal copied, skipped
        if dst.exists():
            s, d = src.stat(), dst.stat()
            if s.st_size == d.st_size and int(s.st_mtime) <= int(d.st_mtime):
                skipped += 1
                return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    for item in GEO_ITEMS:
        src = src_root / item
        if not src.exists():
            print(f"  WARN: data/geo/{item} missing locally — run `cavedossier geo fetch-data`")
            continue
        if src.is_file():
            _sync_file(src, dst_root / item)
        else:
            for path in sorted(src.rglob("*")):
                if path.is_file():
                    _sync_file(path, dst_root / path.relative_to(src_root))
    print(f"  podaci/geo: {copied} copied, {skipped} up to date")


def publish(staged: Path, version: str, *, skip_geo: bool) -> None:
    target = _drive_root() / TARGET_REL
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit(
            f"Drive folder unreachable ({exc}).\n"
            f"Staged copy remains at {staged} — publish again when the mount is back."
        )
    print(f"publishing to {target}")

    _archive_old(target, version)

    vdir = target / f"v{version}"
    vdir.mkdir(exist_ok=True)
    for name in ("bootstrap.ps1", "bundle.zip"):
        shutil.copy2(staged / f"v{version}" / name, vdir / name)
    for command_id in PROD_COMMANDS:
        name = launcher_name(command_id, version)
        shutil.copy2(staged / name, target / name)
    shutil.copy2(staged / "PROCITAJ_ME.txt", target / "PROCITAJ_ME.txt")

    if skip_geo:
        print("  podaci/geo: skipped (--skip-geo)")
    else:
        _sync_geo(target)

    line = (
        f"v{version}  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        f"  commit {_git_commit()}  ({', '.join(PROD_COMMANDS)})\n"
    )
    verzije = target / "VERZIJE.txt"
    with verzije.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(f"published v{version}: {len(PROD_COMMANDS)} launchers + bundle + bootstrap")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="release version, e.g. 1.0")
    parser.add_argument("--publish", action="store_true",
                        help="copy the staged release to the Drive folder")
    parser.add_argument("--skip-geo", action="store_true",
                        help="publish without syncing podaci/geo (~280 MB)")
    args = parser.parse_args(argv)
    if not VERSION_RE.fullmatch(args.version):
        parser.error("--version must look like 1.0 (major.minor)")

    staged = stage(args.version)
    if args.publish:
        publish(staged, args.version, skip_geo=args.skip_geo)
    else:
        print("(dry stage only — add --publish to copy to the Drive)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
