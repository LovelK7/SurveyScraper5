"""Prefill result models — what was written, from where, and why not."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldValue(BaseModel):
    """One OSZ field as resolved by the precedence rule (SB wins)."""

    value: str | None = None
    # "sb" | "geo-admin" | "geo-rgi" | "dmv-dgu" | None (nothing available)
    source: str | None = None
    note: str | None = None


class SBUpdate(BaseModel):
    """One row of dopune-sb.csv: an empty SB cell a finder can fill."""

    column: str      # the SB column header, e.g. "Z"
    value: str
    source: str
    note: str = ""


class PrefillResult(BaseModel):
    """The JSON sidecar (prefill.json) for one cave's prefill run."""

    serial: int
    cave_name: str
    sue_number: str | None = None
    template_version: str = "v10"
    fields: dict[str, FieldValue] = Field(default_factory=dict)
    karta_status: str = "missing"  # "reused" | "fetched" | "missing"
    mismatches: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    sb_updates: list[SBUpdate] = Field(default_factory=list)
