"""Geo finding models.

``NamedPlaceHit`` / ``AdminPlacement`` are ported near-verbatim from
crospeleo-automation ``locality/models.py``; ``LocalityFinding`` and
``ElevationFinding`` are new — this tool synthesizes values for a possibly
empty SB row instead of correcting a parsed OSZ, so each field carries its
own provenance and the SB-vs-computed verdict travels with the finding.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NamedPlaceHit(BaseModel):
    """One result from the RGI gazetteer spatial query (WFS or offline)."""

    identifikator: str
    geografskoime: str
    vrstaobiljezja: str | None = None
    distance_m: float | None = None


class AdminPlacement(BaseModel):
    """Administrative hierarchy from DGU boundary point-in-polygon lookup."""

    naselje: str | None = None
    opcina: str | None = None
    zupanija: str | None = None
    source: str = "shapefile"  # "shapefile" | "unavailable"


class LocalityFinding(BaseModel):
    """The locality finder's answer for one entrance point.

    Values are what the OSZ should say AFTER the SB-wins precedence rule:
    an SB value is kept (with a note when it disagrees with the evidence),
    a missing one is filled from DGU/RGI. ``*_source`` says which happened
    ("sb" | "geo-admin" | "geo-rgi" | None when nothing could be determined).
    """

    zupanija: str | None = None
    grad_opcina: str | None = None
    najblize_mjesto: str | None = None
    najblize_mjesto_source: str | None = None
    lokalitet: str | None = None
    lokalitet_source: str | None = None
    rgi_hits: list[NamedPlaceHit] = Field(default_factory=list)
    admin_available: bool = True
    rgi_available: bool = True
    rgi_offline_fallback: bool = False
    notes: list[str] = Field(default_factory=list)


class ElevationFinding(BaseModel):
    """The elevation finder's answer (or its reason for having none)."""

    elevation_m: float | None = None
    source_label: str | None = None  # e.g. "DMV (DGU)" — the Izvor kote value
    tile_name: str | None = None
    notes: list[str] = Field(default_factory=list)
