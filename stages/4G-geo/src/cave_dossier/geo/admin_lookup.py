"""Point-in-polygon administrative lookup over DGU boundary GeoPackages.

Adapted from crospeleo-automation ``locality/admin_lookup.py`` (docs/
PORTING.md). One simplification: ``naselja.gpkg`` as produced by the DGU
conversion carries the full hierarchy (``NA_IME`` + ``JLS_IME`` + ``ZU_IME``),
so a single point-in-polygon resolves naselje, općina and županija at once;
the separate ``jls.gpkg`` / ``zupanije.gpkg`` remain as fallbacks for a
naselja file without those columns (or a point in a naselja gap).

Kept from the original: lazy geopandas import, the stale ``.gpkg-journal``
temp-copy workaround, ``nearby_naselje_names`` (settlement screening), and
graceful degradation to ``source="unavailable"`` when nothing loads.
All files are EPSG:3765 — HTRS96 in, no transformation.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from cave_dossier.geo.models import AdminPlacement

_LAYER_CONFIG: dict[str, dict[str, str]] = {
    "naselja": {"filename": "naselja.gpkg", "name_col": "NA_IME"},
    "opcine": {"filename": "jls.gpkg", "name_col": "JLS_IME"},
    "zupanije": {"filename": "zupanije.gpkg", "name_col": "ZU_IME"},
}

# Hierarchy columns the naselja layer may carry beyond its own name.
_NASELJA_OPCINA_COL = "JLS_IME"
_NASELJA_ZUPANIJA_COL = "ZU_IME"

logger = logging.getLogger(__name__)


class AdminLookup:
    """Lazy, fail-soft admin hierarchy lookup (geopandas + shapely)."""

    def __init__(self, boundaries_dir: Path) -> None:
        self.boundaries_dir = boundaries_dir
        self._gdfs: dict[str, object] | None = None

    def lookup(self, x_htrs: float, y_htrs: float) -> AdminPlacement:
        """AdminPlacement for an HTRS96/EPSG:3765 point;
        ``source="unavailable"`` when no boundary file could be loaded."""
        if not self._ensure_loaded():
            return AdminPlacement(source="unavailable")
        gdfs = self._gdfs  # type: ignore[assignment]

        naselje = opcina = zupanija = None
        naselja_gdf = gdfs.get("naselja")
        row = self._pip_row(naselja_gdf, x_htrs, y_htrs, "naselja")
        if row is not None:
            naselje = self._row_value(row, naselja_gdf.attrs.get("_name_col"))  # type: ignore[union-attr]
            opcina = self._row_value(row, _NASELJA_OPCINA_COL)
            zupanija = self._row_value(row, _NASELJA_ZUPANIJA_COL)

        if opcina is None:
            row = self._pip_row(gdfs.get("opcine"), x_htrs, y_htrs, "opcine")
            if row is not None:
                opcina = self._row_value(row, "JLS_IME")
        if zupanija is None:
            row = self._pip_row(gdfs.get("zupanije"), x_htrs, y_htrs, "zupanije")
            if row is not None:
                zupanija = self._row_value(row, "ZU_IME")

        return AdminPlacement(
            naselje=naselje, opcina=opcina, zupanija=zupanija, source="shapefile"
        )

    def nearby_naselje_names(self, x_htrs: float, y_htrs: float, radius_m: float) -> list[str]:
        """All naselje polygon names intersecting a buffer around the point.

        Used to validate "Najbliže mjesto" and to detect settlement names
        smuggled into "Lokalitet": a token that fuzzy-matches one of these
        is a settlement, not a landform. ``[]`` when unavailable.
        """
        if not self._ensure_loaded():
            return []
        gdf = self._gdfs.get("naselja")  # type: ignore[union-attr]
        if gdf is None:
            return []
        try:
            from shapely.geometry import Point  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("shapely not installed — nearby_naselje_names returning []")
            return []
        try:
            buffer = Point(x_htrs, y_htrs).buffer(radius_m)
            matches = gdf[gdf.intersects(buffer)]  # type: ignore[index]
            name_col = gdf.attrs.get("_name_col")  # type: ignore[union-attr]
            if not name_col:
                return []
            seen: list[str] = []
            for value in matches[name_col].tolist():
                name = str(value).strip() if value is not None else ""
                if name and name not in seen:
                    seen.append(name)
            return seen
        except Exception as exc:  # noqa: BLE001
            logger.warning("nearby_naselje_names failed: %s", exc)
            return []

    @property
    def is_available(self) -> bool:
        self._ensure_loaded()
        return bool(self._gdfs)

    # ── internals ────────────────────────────────────────────────────
    def _ensure_loaded(self) -> bool:
        if self._gdfs is not None:
            return bool(self._gdfs)
        self._gdfs = {}
        for layer_key, cfg in _LAYER_CONFIG.items():
            gdf = self._load_one(layer_key, cfg)
            if gdf is not None:
                self._gdfs[layer_key] = gdf
        return bool(self._gdfs)

    def _load_one(self, layer_key: str, cfg: dict[str, str]) -> object | None:
        path = self.boundaries_dir / cfg["filename"]
        if not path.exists():
            logger.debug("Boundary file not found: %s", path)
            return None

        try:
            import geopandas as gpd  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("geopandas is not installed — admin lookup unavailable")
            return None

        # GeoPackage files with a stale journal (e.g. interrupted QGIS write)
        # cause GDAL to fail when it tries to write metadata tables. Copy to a
        # temp path to get a clean, writable copy.
        read_path = path
        tmp_path: str | None = None
        journal = path.with_suffix(".gpkg-journal")
        if journal.exists():
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=".gpkg")
                import os
                os.close(fd)
                shutil.copy2(path, tmp_path)
                read_path = Path(tmp_path)
                logger.debug("Copied %s to temp to bypass stale journal", path.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not create temp copy of %s: %s", path.name, exc)
                tmp_path = None

        try:
            gdf = gpd.read_file(read_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load %s: %s", path.name, exc)
            return None
        finally:
            if tmp_path:
                try:
                    import os
                    os.unlink(tmp_path)
                except OSError:
                    pass

        name_col = cfg["name_col"]
        if name_col not in gdf.columns:
            logger.warning(
                "Expected column %r not found in %s (columns: %s)",
                name_col, path.name, list(gdf.columns),
            )
            return None

        gdf.attrs["_name_col"] = name_col
        logger.debug("Loaded %s (%d features, name col: %s)", path.name, len(gdf), name_col)
        return gdf

    def _pip_row(self, gdf: object | None, x: float, y: float, layer_key: str):
        """The first row whose polygon contains the point, or None."""
        if gdf is None:
            return None
        try:
            from shapely.geometry import Point  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("shapely not installed — PIP skipped for %s", layer_key)
            return None
        try:
            matches = gdf[gdf.contains(Point(x, y))]  # type: ignore[index]
            if len(matches) == 0:
                return None
            return matches.iloc[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("PIP failed for %s: %s", layer_key, exc)
            return None

    @staticmethod
    def _row_value(row, column: str | None) -> str | None:
        if row is None or not column:
            return None
        try:
            value = row[column]
        except (KeyError, IndexError):
            return None
        text = str(value).strip() if value is not None else ""
        return text or None
