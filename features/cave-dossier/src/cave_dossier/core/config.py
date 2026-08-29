"""Configuration: committed config.yaml + gitignored .env, deliberately slim.

crospeleo-automation's multi-society profile system (~900 lines across
core/profile.py + core/config.py) is NOT ported — this tool serves one society.
Field names (``sb_sheet_name``, ``sb_object_name_column``, …) are kept identical
to crospeleo's Settings so ported modules read naturally.

Workbook resolution (the SANDBOX/LIVE switch):
- ``SB_WORKBOOK_PATH`` set in .env  → that file, mode ``SANDBOX``
- otherwise                         → ``LOCAL_DRIVE_ROOT / sb.workbook_filename``,
                                      mode ``LIVE``
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Feature root = parent of src/ (config.py sits at src/cave_dossier/core/).
FEATURE_ROOT = Path(__file__).resolve().parents[3]
CONFIG_YAML = FEATURE_ROOT / "config.yaml"
ENV_FILE = FEATURE_ROOT / ".env"


class ConfigError(RuntimeError):
    """Configuration is missing or inconsistent; message is CLI-ready."""


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings. ``sb_*`` names mirror crospeleo-automation."""

    sb_workbook_path: Path
    sb_mode: str  # "SANDBOX" | "LIVE"
    sb_sheet_name: str
    sb_object_name_column: str
    sb_archive_reference_column: str | None
    sb_filter_column: str | None
    sb_marker_column: str | None
    sb_plaque_column: str | None
    sb_drawing_authors_column: str | None
    sb_exploration_period_column: str | None
    sb_x_htrs_column: str | None
    sb_y_htrs_column: str | None
    local_drive_root: Path | None
    # Extra SB columns the dossier reads: canonical field -> column header
    # (config.yaml `sb.field_columns`); see dossier/sb_mapper.py.
    sb_field_columns: dict[str, str] = field(default_factory=dict)
    # Older column spellings -> the canonical name they are renamed to on load,
    # so one config reads both the live workbook and an older copy of it.
    sb_column_aliases: dict[str, str] = field(default_factory=dict)
    archive_dirs: dict[str, str] = field(default_factory=dict)
    # Part 2.1d: processing targets (long edge, output size) and the hand-made
    # filename-fragment -> Redni broj map for photos automatic evidence cannot reach.
    photo_targets: dict[str, int] = field(default_factory=dict)
    photo_manual_matches: dict[str, int] = field(default_factory=dict)
    # Field-data intake: folder-name fragment -> Redni broj, for leaves whose
    # name carries no cave name at all (a LIDAR id, a surveyor first name).
    intake_manual_matches: dict[str, int] = field(default_factory=dict)
    # Folder fragments confirmed to hold data for caves not yet in SB.
    intake_new_entries: list[str] = field(default_factory=list)
    # Cached CSV of the Liburnija LIDAR sheet; see intake/liburnija.py.
    intake_sheet_csv: str | None = None
    # Per-satellite overrides (config.yaml `satellites`): satellite name ->
    # {confirmed_new, manual_matches, out_of_scope}. See satellites/resolver.py.
    satellites: dict[str, dict] = field(default_factory=dict)


def _load_env_file(path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE lines, # comments). Real env vars win."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings() -> Settings:
    if not CONFIG_YAML.exists():
        raise ConfigError(f"config.yaml not found at {CONFIG_YAML}")
    raw = yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8")) or {}
    sb = raw.get("sb") or {}
    archive = raw.get("archive") or {}

    env = _load_env_file(ENV_FILE)

    def get_env(key: str) -> str | None:
        # Real environment variables override .env file entries; an env var
        # explicitly set to EMPTY masks the .env value entirely (lets
        # `$env:SB_WORKBOOK_PATH=""` force LIVE mode without editing .env).
        if key in os.environ:
            return os.environ[key] or None
        return env.get(key) or None

    drive_root_raw = get_env("LOCAL_DRIVE_ROOT")
    local_drive_root = Path(drive_root_raw) if drive_root_raw else None

    sandbox_raw = get_env("SB_WORKBOOK_PATH")
    if sandbox_raw:
        # Relative paths resolve against the feature root, so the sandbox
        # copy under example/ survives renames/moves of the repo folder.
        workbook_path = Path(sandbox_raw)
        if not workbook_path.is_absolute():
            workbook_path = FEATURE_ROOT / workbook_path
        mode = "SANDBOX"
    else:
        workbook_filename = sb.get("workbook_filename")
        if not local_drive_root or not workbook_filename:
            raise ConfigError(
                "No SB workbook configured.\n"
                "  Either set SB_WORKBOOK_PATH in .env (sandbox copy — recommended\n"
                "  during development), or set LOCAL_DRIVE_ROOT in .env so the live\n"
                f"  workbook resolves as <LOCAL_DRIVE_ROOT>/{workbook_filename or '<sb.workbook_filename>'}.\n"
                f"  (.env template: {FEATURE_ROOT / '.env.example'})"
            )
        workbook_path = local_drive_root / workbook_filename
        mode = "LIVE"

    return Settings(
        sb_workbook_path=workbook_path,
        sb_mode=mode,
        sb_sheet_name=sb.get("sheet_name", "Svi objekti"),
        sb_object_name_column=sb.get("object_name_column", "Ime objekta"),
        sb_archive_reference_column=sb.get("archive_reference_column"),
        sb_filter_column=sb.get("filter_column"),
        sb_marker_column=sb.get("marker_column"),
        sb_plaque_column=sb.get("plaque_column"),
        sb_drawing_authors_column=sb.get("drawing_authors_column"),
        sb_exploration_period_column=sb.get("exploration_period_column"),
        sb_x_htrs_column=sb.get("x_htrs_column"),
        sb_y_htrs_column=sb.get("y_htrs_column"),
        local_drive_root=local_drive_root,
        sb_field_columns={
            str(key): str(value)
            for key, value in (sb.get("field_columns") or {}).items()
            if value
        },
        sb_column_aliases={
            str(key): str(value)
            for key, value in (sb.get("column_aliases") or {}).items()
            if value
        },
        archive_dirs=dict(archive),
        photo_targets={
            str(key): int(value)
            for key, value in (raw.get("photos") or {}).items()
            if isinstance(value, int)
        },
        photo_manual_matches={
            str(key): int(value)
            for key, value in ((raw.get("photos") or {}).get("manual_matches") or {}).items()
            if value is not None
        },
        intake_manual_matches={
            str(key): int(value)
            for key, value in ((raw.get("intake") or {}).get("manual_matches") or {}).items()
            if value is not None
        },
        intake_new_entries=[
            str(value) for value in ((raw.get("intake") or {}).get("new_entries") or []) if value
        ],
        intake_sheet_csv=((raw.get("intake") or {}).get("sheet_csv") or None),
        satellites={
            str(name): dict(values or {})
            for name, values in (raw.get("satellites") or {}).items()
        },
    )
