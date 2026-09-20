"""What one sastavnica prefill run produced — the JSON sidecar's shape."""

from __future__ import annotations

from pydantic import BaseModel, Field

from cave_dossier.osz.models import FieldValue, SBUpdate

__all__ = ["FieldValue", "SBUpdate", "PlacedField", "SastavnicaResult",
           "PlacedDrawing", "NacrtResult"]


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
    # The KORAK 3 dimensions JSON, when `cavedossier nacrt` read one.
    dimensions_source: str | None = None
    notes: list[str] = Field(default_factory=list)
    sb_updates: list[SBUpdate] = Field(default_factory=list)


class PlacedDrawing(BaseModel):
    """One printed design as it landed on the composed sheet.

    ``ink_mm`` vs ``reserved_mm`` is the number worth keeping: the layout was
    chosen from the survey's bounding box plus a padding guess, and this pair
    says how close that guess was on a real print.
    """

    design: str                       # "plan" | "profile"
    source: str
    scale: int                        # the denominator it was printed at
    ink_mm: list[float]               # [width, height] of the cropped drawing
    reserved_mm: list[float]          # [width, height] the layout kept free
    x_mm: float                       # where the crop landed, from the page's
    y_mm: float                       # top-left corner


class NacrtResult(BaseModel):
    """``nacrt.json`` for one cave's composition run."""

    serial: int
    cave_name: str
    sue_number: str | None = None
    # The title block exactly as it was prefilled onto this sheet.
    sastavnica: SastavnicaResult
    inputs: list[str] = Field(default_factory=list)
    mjerilo: str = ""
    arrangement: str = ""
    plan_scale: int | None = None
    profile_scale: int | None = None
    drawings: list[PlacedDrawing] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
