"""Run-artifact layout + persistence for georef runs — adapted from
crospeleo-automation ``georef/artifacts.py`` (see docs/PORTING.md).

crospeleo lays artifacts under its per-run ``data/runs/<run_id>/`` tree;
this tool has no run machinery, so each cave gets one gitignored folder
``runs/georef/<padded Redni broj>/`` under the feature root, overwritten
on re-run.  The delivered products live on Drive (worker.py) — this
folder is the local working record: full result JSON, raw record text,
Playwright trace + browser log, debug screenshots.
"""

from __future__ import annotations

import json
from pathlib import Path

from cave_dossier.core.config import FEATURE_ROOT
from cave_dossier.georef.models import GeorefArtifacts, GeorefResult

RUNS_ROOT = FEATURE_ROOT / "runs" / "georef"


def build_georef_artifacts(serial_label: str) -> GeorefArtifacts:
    root_dir = RUNS_ROOT / serial_label
    screenshots_dir = root_dir / "screenshots"
    traces_dir = root_dir / "traces"
    debug_dir = screenshots_dir / "debug"

    artifacts = GeorefArtifacts(
        root_dir=root_dir,
        screenshots_dir=screenshots_dir,
        traces_dir=traces_dir,
        debug_dir=debug_dir,
        georef_record_path=root_dir / "georef_record.txt",
        result_json_path=root_dir / "georef_result.json",
        map_screenshot_path=root_dir / "map_screenshot.png",
        trace_path=traces_dir / "playwright_trace.zip",
        browser_log_path=traces_dir / "playwright.log",
    )

    for path in (
        artifacts.root_dir,
        artifacts.screenshots_dir,
        artifacts.traces_dir,
        artifacts.debug_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)

    return artifacts


def save_debug_screenshot(page: object, path: Path) -> Path:
    # Viewport-only screenshot: full_page=True resizes the viewport in
    # headed mode and causes a visible zoom-out/zoom-in flicker on every
    # step.  See georef flow notes.
    page.screenshot(path=str(path), full_page=False)
    return path


def persist_georef_result(artifacts: GeorefArtifacts, result: GeorefResult) -> GeorefResult:
    if result.georef_record:
        artifacts.georef_record_path.write_text(result.georef_record, encoding="utf-8")
        result.georef_record_path = str(artifacts.georef_record_path)

    if not result.map_screenshot_path and artifacts.map_screenshot_path.exists():
        result.map_screenshot_path = str(artifacts.map_screenshot_path)
    if not result.trace_path and artifacts.trace_path.exists():
        result.trace_path = str(artifacts.trace_path)
    if not result.browser_log_path and artifacts.browser_log_path.exists():
        result.browser_log_path = str(artifacts.browser_log_path)

    artifacts.result_json_path.write_text(
        json.dumps(result.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    result.result_json_path = str(artifacts.result_json_path)
    return result
