"""What one sastavnica prefill run produced — the JSON sidecar's shape."""

from __future__ import annotations

from pydantic import BaseModel, Field

from cave_dossier.osz.models import FieldValue, SBUpdate

__all__ = ["FieldValue", "SBUpdate", "PlacedField", "SastavnicaResult"]


class PlacedField(BaseModel):
    """One value as it was actually set on the page — the record that makes a
    cramped cell visible without opening the PDF."""

    key: str
    text: str
    font_size: float
    width_pt: float
    overflowed: bool = False


class SastavnicaResult(BaseModel):
    """``sastavnica.json`` for one cave's run."""

    serial: int
    cave_name: str
    sue_number: str | None = None
    template_version: str = "v1"
    font: str | None = None
    font_tier: str | None = None
    # Field key -> the resolved value and where it came from ("sb", "osz",
    # "geo-admin", "geo-rgi", "dmv-dgu", "constant", "default").
    fields: dict[str, FieldValue] = Field(default_factory=dict)
    placed: list[PlacedField] = Field(default_factory=list)
    osz_source: str | None = None       # the filled OSZ the survey data came from
    notes: list[str] = Field(default_factory=list)
    sb_updates: list[SBUpdate] = Field(default_factory=list)
