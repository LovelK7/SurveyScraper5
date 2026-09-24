"""What the dashboard shows: the workspace, the SB workbook, the caves in work.

Everything here is read-only and fail-soft — a missing Drive, an SB open in
Excel, no cSurvey on this machine each become a note on the page, never an
error page. Files are classified by name only; nothing is opened or parsed.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import ConfigError, Settings, load_settings
from cave_dossier.core.matching import SB_SERIAL_RE
from cave_dossier.core.paths import repo_root, workspace, workspace_root
from cave_dossier.intake.scanner import find_leaf_folders

#: The live workbook family on Drive: "!Speleo_baza_SUE_v3.0.xlsm", "…_v2.4.xlsm".
SB_VERSION_RE = re.compile(r"^!?Speleo_baza_SUE_v(\d+)[._](\d+)\.xls[mx]$", re.IGNORECASE)

DEFAULT_CSURVEY_DIR = r"C:\csurvey64"

#: Drive folders the Pregled tab links to: config.yaml `archive` key -> label.
DRIVE_DIRS = (
    ("intake_dir", "Za digitalizirat"),
    ("osz_dir", "Osnovni zapisnici"),
    ("drawings_dir", "Nacrti"),
    ("statements_dir", "Izjave za katastar RH"),
    ("entry_photos_dir", "Fotografije ulaza"),
    ("queued_photos_dir", "Fotografije za istražit"),
    ("map_excerpts_dir", "Isječci karte"),
)

WORKSPACE_DIRS = (("runs", "runs/ (izlazi alata)"), ("sb-sync", "sb-sync/ (liste za SB)"))

_SURVEY_EXT = {".csx", ".csz"}
_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic"}
_SKIP_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}


def _survey_kind(stem: str) -> str:
    """Where a survey file sits in the 3N chain, from its name suffix."""
    low = stem.lower()
    if low.endswith("_backup"):
        return "backup"
    if low.endswith("_fin"):
        return "fin"
    if low.endswith("_lt"):
        return "lt"
    if low.endswith("_pp"):
        return "pp"
    return "raw"


#: `file_kind` of a catalog action -> the survey kinds it accepts.
FILE_KINDS = {
    "raw": {"raw"},
    "pp": {"pp"},
    "lt": {"lt"},
    "fin": {"fin"},
    "survey": {"raw", "pp", "lt", "fin"},
}


def classify(path: Path, broj: int) -> str:
    """One label per file in a cave leaf; the page groups and ticks by it."""
    name = path.name.lower()
    ext = path.suffix.lower()
    pad = f"sb_{broj:04d}"
    if ext in _SURVEY_EXT:
        return _survey_kind(path.stem)
    if name.endswith("_nacrt.pdf") and name.startswith(("sb_", pad)):
        return "nacrt"
    if name.endswith("_sastavnica.pdf"):
        return "sastavnica"
    if name.endswith("_plan.pdf"):
        return "plan"
    if name.endswith("_profile.pdf"):
        return "profile"
    if name.endswith("_dimenzije.json"):
        return "dimenzije"
    if ext == ".docx" and name.endswith("_osz.docx"):
        return "osz"
    if ext in (".docx", ".doc"):
        return "doc"
    if ext in _PHOTO_EXT:
        return "photo_processed" if name.startswith("sb_") else "photo"
    if ext == ".pdf":
        return "pdf"
    return "other"


@dataclass
class CaveLeaf:
    broj: int
    name: str
    path: Path
    relative: str
    group: str
    file_count: int

    def to_json(self) -> dict:
        return {
            "broj": self.broj, "name": self.name, "path": str(self.path),
            "relative": self.relative, "group": self.group,
            "file_count": self.file_count,
        }


def _leaf_name(folder: str) -> tuple[int, str] | None:
    match = SB_SERIAL_RE.match(folder)
    if not match:
        return None
    rest = folder[match.end():].lstrip("_ -.")
    return int(match.group(1)), rest


def sb_versions(drive_root: Path | None) -> list[dict]:
    """Every SB workbook version on Drive, newest first."""
    if drive_root is None or not drive_root.is_dir():
        return []
    found = []
    for path in drive_root.iterdir():
        match = SB_VERSION_RE.match(path.name)
        if match and path.is_file():
            stat = path.stat()
            found.append({
                "name": path.name, "path": str(path),
                "version": [int(match.group(1)), int(match.group(2))],
                "modified": stat.st_mtime, "size": stat.st_size,
            })
    return sorted(found, key=lambda v: v["version"], reverse=True)


def tools_dir() -> Path | None:
    """The 3N script folder: the repo's in dev, ``CSX_TOOLS`` otherwise."""
    override = os.environ.get("CSX_TOOLS")
    if override and Path(override, "nacrt_finish.py").is_file():
        return Path(override)
    root = repo_root()
    if root is not None:
        candidate = root / "stages" / "3N-nacrt" / "production" / "tools"
        if (candidate / "nacrt_finish.py").is_file():
            return candidate
    return None


def _env_value(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    try:
        env_path = workspace(".env")
    except Exception:  # noqa: BLE001 — no workspace: no .env either
        return None
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.partition("=")[2].strip().strip('"').strip("'")
    return None


def csurvey_exe() -> Path | None:
    directory = Path(_env_value("CSURVEY_DIR") or DEFAULT_CSURVEY_DIR)
    exe = directory / "cSurveyPC.exe"
    return exe if exe.is_file() else None


class Workspace:
    """Settings + caches for one server process. Reload with ``refresh()``."""

    CAVE_TTL = 60.0

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._settings_error: str | None = None
        self._caves: tuple[float, list[CaveLeaf], list[str]] | None = None

    # ── settings ────────────────────────────────────────────────────
    @property
    def settings(self) -> Settings | None:
        if self._settings is None and self._settings_error is None:
            try:
                self._settings = load_settings()
            except (ConfigError, Exception) as exc:  # noqa: BLE001 — shown on the page
                self._settings_error = str(exc)
        return self._settings

    def refresh(self) -> None:
        self._settings = None
        self._settings_error = None
        self._caves = None

    @property
    def drive_root(self) -> Path | None:
        s = self.settings
        return s.local_drive_root if s else None

    def drive_dir(self, key: str) -> Path | None:
        s = self.settings
        if s is None or s.local_drive_root is None or key not in s.archive_dirs:
            return None
        return s.local_drive_root / s.archive_dirs[key]

    def intake_root(self) -> Path | None:
        return self.drive_dir("intake_dir")

    # ── the summary for the header + Pregled tab ────────────────────
    def summary(self) -> dict:
        s = self.settings
        data: dict = {
            "workspace": _safe(lambda: str(workspace_root())),
            "repo": _safe(lambda: str(repo_root()) if repo_root() else None),
            "settings_error": self._settings_error,
            "tools_dir": str(tools_dir()) if tools_dir() else None,
            "csurvey": str(csurvey_exe()) if csurvey_exe() else None,
        }
        if s is None:
            return data
        live_name = _live_filename()
        live = (s.local_drive_root / live_name) if s.local_drive_root and live_name else None
        versions = sb_versions(s.local_drive_root)
        data.update({
            "drive_root": str(s.local_drive_root) if s.local_drive_root else None,
            "drive_ok": bool(s.local_drive_root and s.local_drive_root.is_dir()),
            "sb": {
                "mode": s.sb_mode,
                "reason": s.sb_mode_reason,
                "reading": str(s.sb_workbook_path),
                "live": str(live) if live else None,
                "live_exists": bool(live and live.is_file()),
                "versions": versions,
                "newer_than_live": [
                    v["name"] for v in versions
                    if live and v["name"] != live.name
                    and v["version"] > _version_of(live.name)
                ],
            },
            "drive_dirs": [
                {"key": k, "label": label, "path": str(p) if p else None,
                 "exists": bool(p and p.is_dir())}
                for k, label in DRIVE_DIRS
                for p in [self.drive_dir(k)]
            ],
            "workspace_dirs": [
                {"key": k, "label": label, "path": _safe(lambda k=k: str(workspace(k)))}
                for k, label in WORKSPACE_DIRS
            ],
        })
        return data

    # ── caves in work ───────────────────────────────────────────────
    def caves(self, force: bool = False) -> tuple[list[CaveLeaf], list[str]]:
        """(SB_-prefixed leaves, relative paths of leaves still unprefixed)."""
        if not force and self._caves and time.monotonic() - self._caves[0] < self.CAVE_TTL:
            return self._caves[1], self._caves[2]
        root = self.intake_root()
        caves: list[CaveLeaf] = []
        unprefixed: list[str] = []
        if root is not None and root.is_dir():
            ignore = self.settings.intake_ignore_folders if self.settings else []
            for leaf in find_leaf_folders(root, ignore):
                if leaf.ignored:
                    continue
                parsed = _leaf_name(leaf.path.name)
                if parsed is None:
                    unprefixed.append(leaf.relative.as_posix())
                    continue
                broj, name = parsed
                caves.append(CaveLeaf(broj, name, leaf.path, leaf.relative.as_posix(),
                                      leaf.group, leaf.file_count))
        caves.sort(key=lambda c: (c.broj, c.relative))
        self._caves = (time.monotonic(), caves, unprefixed)
        return caves, unprefixed

    def cave_leaves(self, broj: int) -> list[CaveLeaf]:
        return [c for c in self.caves()[0] if c.broj == broj]

    def cave_detail(self, broj: int) -> dict:
        leaves = self.cave_leaves(broj)
        if not leaves:
            # The cache may predate a folder made a minute ago.
            leaves = [c for c in self.caves(force=True)[0] if c.broj == broj]
        files = []
        for leaf in leaves:
            for path in sorted(leaf.path.rglob("*"), key=lambda p: p.name.lower()):
                if not path.is_file() or path.name.lower() in _SKIP_NAMES:
                    continue
                stat = path.stat()
                files.append({
                    "name": path.name, "path": str(path),
                    "relative": path.relative_to(leaf.path).as_posix(),
                    "kind": classify(path, broj),
                    "modified": stat.st_mtime, "size": stat.st_size,
                })
        karta = None
        excerpts = self.drive_dir("map_excerpts_dir")
        if excerpts is not None:
            png = excerpts / f"SB_{broj:04d}.png"
            karta = {"path": str(png), "exists": png.is_file()}
        return {
            "broj": broj,
            "leaves": [leaf.to_json() for leaf in leaves],
            "files": files,
            "karta": karta,
        }

    def candidate_files(self, broj: int, file_kind: str) -> list[str]:
        """Files a ``{file}`` action may take, newest first."""
        kinds = FILE_KINDS.get(file_kind, set())
        detail = self.cave_detail(broj)
        chosen = [f for f in detail["files"] if f["kind"] in kinds]
        chosen.sort(key=lambda f: f["modified"], reverse=True)
        return [f["path"] for f in chosen]

    # ── path guard ──────────────────────────────────────────────────
    def allowed_roots(self) -> list[Path]:
        roots: list[Path] = []
        for candidate in (self.drive_root, _safe(workspace_root), _safe(repo_root)):
            if candidate:
                roots.append(Path(candidate).resolve())
        return roots

    def is_allowed(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return any(resolved == r or r in resolved.parents for r in self.allowed_roots())


def _live_filename() -> str:
    """config.yaml sb.workbook_filename — re-read so a config edit shows on refresh."""
    try:
        import yaml
        cfg = yaml.safe_load(workspace("config.yaml").read_text(encoding="utf-8-sig")) or {}
        return (cfg.get("sb") or {}).get("workbook_filename") or ""
    except Exception:  # noqa: BLE001
        return ""


def _version_of(name: str) -> list[int]:
    match = SB_VERSION_RE.match(name)
    return [int(match.group(1)), int(match.group(2))] if match else [0, 0]


def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001 — a missing root is a blank on the page
        return None
