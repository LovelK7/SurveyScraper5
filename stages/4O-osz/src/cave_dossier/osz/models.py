"""Prefill result models — what was written, from where, and why not."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldValue(BaseModel):
    """One OSZ field as resolved by the precedence rule (SB wins)."""

    value: str | None = None
    # "sb" | "geo-admin" | "geo-rgi" | "dmv-dgu" | "nacrt" (the 3N dimensions
    # file) | "stari-osz" | … | None (nothing available)
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
    # Migration of an older OSZ found in the intake leaf (user, 2026-08-30):
    # the file the useful content was lifted from, and the checkbox labels
    # carried into the fresh document.
    migrated_from: str | None = None
    ticked_checkboxes: list[str] = Field(default_factory=list)
    # The 3N ``<name>_dimenzije.json`` the measured Duljina / Dubina /
    # Horizontalna duljina / Visinska razlika came from (user, 2026-10-02).
    dimensions_source: str | None = None
    # The finisher's `entrance_size` block from that file (project 0005) and
    # which reading filled Širina/Visina ulaza: "pit" | "horizontal" | None.
    entrance_size: dict | None = None
    entrance_kind: str | None = None
    mismatches: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    sb_updates: list[SBUpdate] = Field(default_factory=list)
