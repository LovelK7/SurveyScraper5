"""Georef flow models — ported near-verbatim from crospeleo-automation
``georef/models.py`` (see docs/PORTING.md)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field


class GeorefStatus(StrEnum):
    READY = "ready"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


class GeorefInput(BaseModel):
    object_id: str
    object_name: str
    locality: str | None = None
    x_htrs: float | None = None
    y_htrs: float | None = None
    source: str | None = None
    notes: list[str] = Field(default_factory=list)

    @staticmethod
    def coordinate_variants(value: float | None) -> list[str]:
        """Render an HTRS coordinate for the Georef X/Y inputs.

        Always emits the integer (rounded) value.  The Georef form
        rejects decimal coordinates (crospeleo lesson, object 796 /
        SUE 960 Surlice, 2026-05-26: SB carried ``x=361433.72
        y=5033946.56`` and the record-fetch timed out twice because
        Georef silently refused the input).  Rounding to integer metres
        is well within the cadastre's positional tolerance — Georef
        itself stores rasterised HTRS for the marker.
        """
        if value is None:
            return []
        return [str(round(value))]

    @computed_field
    @property
    def x_input_variants(self) -> list[str]:
        return self.coordinate_variants(self.x_htrs)

    @computed_field
    @property
    def y_input_variants(self) -> list[str]:
        return self.coordinate_variants(self.y_htrs)


class GeorefResult(BaseModel):
    success: bool = False
    georef_record: str | None = None
    georef_status: str = GeorefStatus.SKIPPED
    warnings: list[str] = Field(default_factory=list)
    debug_screenshots: list[str] = Field(default_factory=list)
    trace_path: str | None = None
    browser_log_path: str | None = None
    map_screenshot_path: str | None = None
    georef_record_path: str | None = None
    result_json_path: str | None = None
    error_message: str | None = None


class GeorefLoginResult(BaseModel):
    success: bool = False
    georef_status: str = GeorefStatus.ERROR
    warnings: list[str] = Field(default_factory=list)
    error_message: str | None = None
    screenshot_path: str | None = None
    trace_path: str | None = None
    browser_log_path: str | None = None


@dataclass
class GeorefSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any
    trace_path: Path
    browser_log_path: Path


@dataclass(frozen=True)
class GeorefArtifacts:
    root_dir: Path
    screenshots_dir: Path
    traces_dir: Path
    debug_dir: Path
    georef_record_path: Path
    result_json_path: Path
    map_screenshot_path: Path
    trace_path: Path
    browser_log_path: Path
