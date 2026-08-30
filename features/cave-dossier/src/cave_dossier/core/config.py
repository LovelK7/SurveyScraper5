"""Configuration: committed config.yaml + gitignored .env, deliberately slim.

crospeleo-automation's multi-society profile system (~900 lines across
core/profile.py + core/config.py) is NOT ported — this tool serves one society.
Field names (``sb_sheet_name``, ``sb_object_name_column``, …) are kept identical
to crospeleo's Settings so ported modules read naturally.

Workbook resolution (the LIVE-first switch, user 2026-08-30):
- ``SB_WORKBOOK_PATH`` set in .env  → that file, mode ``SANDBOX`` (explicit
                                      override for development)
- otherwise → the LIVE workbook ``LOCAL_DRIVE_ROOT / sb.workbook_filename`` is
  probed first (reachable? open in Excel? readable?).  Healthy → mode ``LIVE``,
  and the ``SB_SANDBOX_PATH`` copy is refreshed to match it.  In conflict →
  mode ``FALLBACK`` reading that copy, with the reason on ``sb_mode_reason``.
  No ``SB_SANDBOX_PATH`` configured → always LIVE (conflicts surface at read).
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
    # Part 2.1c — georef.hr (isječak karte). Credentials come from .env
    # (GEOREF_BASE_URL / GEOREF_USERNAME / GEOREF_PASSWORD); the field names
    # mirror crospeleo-automation's Settings so the ported georef/ modules
    # read naturally. Timeouts are the values calibrated over there.
    georef_base_url: str | None = None
    georef_username: str | None = None
    georef_password: str | None = None
    georef_navigation_timeout_ms: int = 90000
    georef_post_save_wait_ms: int = 3000
    # Browser window for the map capture. The excerpt is a square crop of the
    # live map area, one screen pixel per map pixel — so a bigger window IS
    # the excerpt resolution. Headless runs honour this fully; headed (--debug)
    # runs are clamped to the physical display and the crop adapts.
    georef_window_width: int = 2560
    georef_window_height: int = 1600
    georef_selectors_path: Path = FEATURE_ROOT / "config" / "selectors.yaml"
    playwright_browser: str = "chromium"
    playwright_slow_mo_ms: int = 0
    # Part 2.1b — locality + elevation finders (config.yaml `geo`). The data
    # dir holds the gitignored boundary GeoPackages / RGI gazetteer / DEM
    # tiles that `cavedossier geo fetch-data` provisions.
    geo_data_dir: Path = FEATURE_ROOT / "data" / "geo"
    # People registry (authors + curated aliases + izjava linkage) — the
    # committed JSON people/registry.py loads. config.yaml `people.registry_path`.
    people_registry_path: Path = FEATURE_ROOT / "data" / "people" / "registry.json"
    geo_rgi_radius_m: float = 2000.0
    geo_elevation_tolerance_m: float = 10.0
    geo_elevation_source_label: str = "DMV"
    # Why the workbook is not the live one (mode FALLBACK); None for LIVE and
    # for an explicit SANDBOX override. Printed by the CLI banner.
    sb_mode_reason: str | None = None


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


def resolve_live_workbook(
    live_path: Path, fallback_path: Path | None
) -> tuple[Path, str, str | None]:
    """(workbook, mode, reason): LIVE when the live workbook is healthy,
    FALLBACK onto the local copy when it is not (user, 2026-08-30).

    While LIVE is healthy the fallback copy is refreshed to match it, so a
    later fallback always reads the *last good* live state, not a stale
    manual snapshot.  With no usable fallback the answer is LIVE regardless —
    the conflict then surfaces at read time with the safe_io diagnosis.
    """
    from cave_dossier.sb.safe_io import probe_live_workbook, refresh_fallback_copy

    reason = probe_live_workbook(live_path)
    if reason is None:
        if fallback_path is not None:
            refresh_fallback_copy(live_path, fallback_path)
        return live_path, "LIVE", None
    if fallback_path is not None and fallback_path.exists():
        return fallback_path, "FALLBACK", reason
    return live_path, "LIVE", None


def load_settings() -> Settings:
    if not CONFIG_YAML.exists():
        raise ConfigError(f"config.yaml not found at {CONFIG_YAML}")
    raw = yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8")) or {}
    sb = raw.get("sb") or {}
    archive = raw.get("archive") or {}
    geo = raw.get("geo") or {}
    people = raw.get("people") or {}

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

    def _feature_relative(raw: str) -> Path:
        # Relative paths resolve against the feature root, so the sandbox
        # copy under example/ survives renames/moves of the repo folder.
        path = Path(raw)
        return path if path.is_absolute() else FEATURE_ROOT / path

    mode_reason: str | None = None
    sandbox_raw = get_env("SB_WORKBOOK_PATH")
    if sandbox_raw:
        workbook_path = _feature_relative(sandbox_raw)
        mode = "SANDBOX"
    else:
        workbook_filename = sb.get("workbook_filename")
        if not local_drive_root or not workbook_filename:
            raise ConfigError(
                "No SB workbook configured.\n"
                "  Set LOCAL_DRIVE_ROOT in .env so the live workbook resolves as\n"
                f"  <LOCAL_DRIVE_ROOT>/{workbook_filename or '<sb.workbook_filename>'},\n"
                "  or set SB_WORKBOOK_PATH to force a sandbox copy.\n"
                f"  (.env template: {FEATURE_ROOT / '.env.example'})"
            )
        live_path = local_drive_root / workbook_filename
        fallback_raw = get_env("SB_SANDBOX_PATH")
        fallback_path = _feature_relative(fallback_raw) if fallback_raw else None
        workbook_path, mode, mode_reason = resolve_live_workbook(live_path, fallback_path)

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
        geo_data_dir=_feature_relative(str(geo.get("data_dir") or "data/geo")),
        people_registry_path=_feature_relative(
            str(people.get("registry_path") or "data/people/registry.json")
        ),
        geo_rgi_radius_m=float(geo.get("rgi_radius_m") or 2000.0),
        geo_elevation_tolerance_m=float(geo.get("elevation_tolerance_m") or 10.0),
        geo_elevation_source_label=str(geo.get("elevation_source_label") or "DMV"),
        georef_base_url=get_env("GEOREF_BASE_URL"),
        georef_username=get_env("GEOREF_USERNAME"),
        georef_password=get_env("GEOREF_PASSWORD"),
        playwright_slow_mo_ms=int(get_env("PLAYWRIGHT_SLOW_MO_MS") or 0),
        sb_mode_reason=mode_reason,
    )
