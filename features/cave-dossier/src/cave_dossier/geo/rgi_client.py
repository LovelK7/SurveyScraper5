"""RGI (Registar geografskih imena) gazetteer: named places near a point.

Ported near-verbatim from crospeleo-automation ``locality/rgi_client.py``
(docs/PORTING.md), plus an offline fallback that repo did not wire into its
enricher (user decision 2026-08-30): when the live WFS is unreachable, the
same query runs against the locally provisioned ``rgi_named_places.gpkg``
(~125k point features, EPSG:3765 — `cavedossier geo fetch-data`).

The WFS endpoint speaks HTRS96/EPSG:3765 natively — easting/northing go in
directly, no coordinate transformation anywhere. Both paths are fail-soft:
any network, file or parse trouble returns ``[]``, never raises.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.geo.models import NamedPlaceHit

_WFS_ENDPOINT = "http://rgi.dgu.hr/geoserver/wfshr/wfs"
_DEFAULT_RADIUS_M = 2000.0
_DEFAULT_TIMEOUT_S = 10.0

OFFLINE_GPKG_NAME = "rgi_named_places.gpkg"

logger = logging.getLogger(__name__)


@dataclass
class RGIClientConfig:
    endpoint: str = _WFS_ENDPOINT
    radius_m: float = _DEFAULT_RADIUS_M
    timeout_s: float = _DEFAULT_TIMEOUT_S
    # Directory holding rgi_named_places.gpkg; None disables the fallback.
    offline_dir: Path | None = None


class RGIClient:
    """Query RGI for named places near an HTRS96 coordinate."""

    def __init__(self, config: RGIClientConfig | None = None) -> None:
        self.config = config or RGIClientConfig()
        self._offline_gdf: object | None = None
        # True after a query was answered by the offline gpkg (reported in
        # the finding so the operator knows the hits may lag the registry).
        self.used_offline_fallback = False

    def query_nearby(self, x_htrs: float, y_htrs: float) -> list[NamedPlaceHit]:
        """NamedPlaceHits within radius_m, closest first; [] on any failure."""
        self.used_offline_fallback = False
        hits = self._query_wfs(x_htrs, y_htrs)
        if hits is None:
            hits = self._query_offline(x_htrs, y_htrs)
            if hits:
                self.used_offline_fallback = True
        hits = hits or []
        hits.sort(key=lambda h: h.distance_m if h.distance_m is not None else float("inf"))
        return hits

    # ── live WFS ─────────────────────────────────────────────────────
    def _query_wfs(self, x: float, y: float) -> list[NamedPlaceHit] | None:
        """Hits from the live WFS, or None when the service was unreachable
        (the one case the offline fallback should cover — a parse problem on
        a *successful* response is not improved by stale local data)."""
        try:
            import requests
        except ImportError:
            logger.warning("requests is not installed — RGI WFS unavailable")
            return None
        try:
            resp = requests.get(
                self.config.endpoint,
                params=self._build_params(x, y),
                timeout=self.config.timeout_s,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.warning("RGI WFS request failed: %s", exc)
            return None
        except ValueError as exc:
            logger.warning("RGI WFS response is not valid JSON: %s", exc)
            return None

        try:
            return self._parse_response(data, x, y)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("RGI WFS response parse error: %s", exc)
            return []

    def _build_params(self, x: float, y: float) -> dict[str, str]:
        return {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "wfshr:nippimenovanomjesto",
            "outputFormat": "application/json",
            "CQL_FILTER": f"DWITHIN(geom, POINT({x} {y}), {self.config.radius_m:.0f}, meters)",
        }

    def _parse_response(
        self, data: dict, query_x: float, query_y: float
    ) -> list[NamedPlaceHit]:
        features = data.get("features") or []
        hits: list[NamedPlaceHit] = []
        for feature in features:
            props = feature.get("properties") or {}
            geom = feature.get("geometry") or {}
            coords = geom.get("coordinates")
            distance_m: float | None = None
            if coords and len(coords) >= 2:
                # Geometry is HTRS96 (projected, metres) — Euclidean is accurate
                dx = coords[0] - query_x
                dy = coords[1] - query_y
                distance_m = math.sqrt(dx * dx + dy * dy)
            hits.append(
                NamedPlaceHit(
                    identifikator=str(props.get("identifikator") or ""),
                    geografskoime=str(props.get("geografskoime") or ""),
                    vrstaobiljezja=props.get("vrstaobiljezja") or None,
                    distance_m=distance_m,
                )
            )
        return hits

    # ── offline gpkg fallback ────────────────────────────────────────
    def _query_offline(self, x: float, y: float) -> list[NamedPlaceHit]:
        gdf = self._load_offline()
        if gdf is None:
            return []
        try:
            from shapely.geometry import Point  # type: ignore[import-untyped]
        except ImportError:
            return []
        try:
            r = self.config.radius_m
            candidates = gdf.iloc[
                list(gdf.sindex.intersection((x - r, y - r, x + r, y + r)))
            ]
            point = Point(x, y)
            hits: list[NamedPlaceHit] = []
            for _, row in candidates.iterrows():
                distance = float(row.geometry.distance(point))
                if distance > r:
                    continue
                hits.append(
                    NamedPlaceHit(
                        identifikator=str(row.get("identifikator") or ""),
                        geografskoime=str(row.get("geografskoime") or ""),
                        vrstaobiljezja=row.get("vrstaobiljezja") or None,
                        distance_m=distance,
                    )
                )
            logger.info("RGI offline fallback answered with %d hits", len(hits))
            return hits
        except Exception as exc:  # noqa: BLE001 — fail-soft by contract
            logger.warning("RGI offline query failed: %s", exc)
            return []

    def _load_offline(self) -> object | None:
        if self._offline_gdf is not None:
            return self._offline_gdf or None
        if self.config.offline_dir is None:
            return None
        path = self.config.offline_dir / OFFLINE_GPKG_NAME
        if not path.exists():
            logger.debug("RGI offline gpkg not found: %s", path)
            return None
        try:
            import geopandas as gpd  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("geopandas is not installed — RGI offline fallback unavailable")
            return None
        try:
            gdf = gpd.read_file(path)
            gdf.sindex  # build the spatial index up front  # noqa: B018
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load %s: %s", path.name, exc)
            self._offline_gdf = False  # remember the failure, don't retry
            return None
        self._offline_gdf = gdf
        return gdf
