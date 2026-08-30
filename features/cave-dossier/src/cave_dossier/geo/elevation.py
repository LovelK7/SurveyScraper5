"""Elevation finder: Kota ulaza from DGU's open INSPIRE Elevation grid.

New code (nothing to port — neither repo fetched elevation before). Source
per the user's decision 2026-08-30 (dgu.gov.hr open data): the anonymous
INSPIRE EL-COV ATOM service. Its GML index maps 84 GeoTIFF tiles
(``RH_ELEV_<n>.tif``, ~34 MB each) to their extents; the society's area of
interest needs 1–2 of them, downloaded lazily and cached under
``<geo.data_dir>/dem/``.

The tiles are **EPSG:3045 (ETRS89/TM33)** — the one place in this codebase
that needs a coordinate transformation. HTRS96/TM (EPSG:3765) and TM33
share the ETRS89 datum, so pyproj's transform is pure projection math.

Fail-soft by contract: any network / file / dependency problem returns a
finding with ``elevation_m=None`` and an explanatory note.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.geo.models import ElevationFinding

ATOM_BASE_URL = "https://geoportal.dgu.hr/services/atom/"
INDEX_GML_NAME = "INSPIRE_Elevation_Grid_Coverage_(EL-COV).gml"
_INDEX_CACHE_NAME = "el_cov_index.gml"
_TILE_RE = re.compile(r"RH_ELEV_(\d+)\.tif", re.IGNORECASE)
_DOWNLOAD_TIMEOUT_S = 300.0
_INDEX_TIMEOUT_S = 30.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TileExtent:
    """One GeoTIFF tile's bounding box in EPSG:3045 (easting/northing)."""

    name: str  # e.g. "RH_ELEV_17.tif"
    min_e: float
    min_n: float
    max_e: float
    max_n: float

    def contains(self, e: float, n: float) -> bool:
        return self.min_e <= e <= self.max_e and self.min_n <= n <= self.max_n


class ElevationFinder:
    """Sample the EL-COV grid at an HTRS96 point."""

    def __init__(self, data_dir: Path, source_label: str) -> None:
        self.data_dir = data_dir
        self.dem_dir = data_dir / "dem"
        self.source_label = source_label

    def kota(self, x_htrs: float, y_htrs: float) -> ElevationFinding:
        finding = ElevationFinding()

        transformed = _to_etrs_tm33(x_htrs, y_htrs)
        if transformed is None:
            finding.notes.append(
                "pyproj nije instaliran (extra [geo]) — kota se ne može odrediti."
            )
            return finding
        easting, northing = transformed

        tiles = self._tile_index(finding)
        if not tiles:
            return finding
        tile = next((t for t in tiles if t.contains(easting, northing)), None)
        if tile is None:
            finding.notes.append(
                f"Nijedna EL-COV pločica ne pokriva točku (E {easting:.0f}, N {northing:.0f})."
            )
            return finding
        finding.tile_name = tile.name

        tile_path = self._ensure_tile(tile.name, finding)
        if tile_path is None:
            return finding

        value = _sample_geotiff(tile_path, easting, northing, finding)
        if value is None:
            return finding
        finding.elevation_m = round(value)
        finding.source_label = self.source_label
        return finding

    # ── tile index ───────────────────────────────────────────────────
    def _tile_index(self, finding: ElevationFinding) -> list[TileExtent]:
        cache = self.data_dir / _INDEX_CACHE_NAME
        if not cache.exists():
            if not _download(ATOM_BASE_URL + INDEX_GML_NAME, cache, _INDEX_TIMEOUT_S):
                finding.notes.append(
                    "EL-COV GML indeks nije dohvatljiv (mreža?) — kota preskočena."
                )
                return []
        try:
            tiles = parse_tile_index(cache.read_bytes())
        except ET.ParseError as exc:
            logger.warning("EL-COV index parse failed: %s", exc)
            tiles = []
        if not tiles:
            finding.notes.append(
                f"EL-COV indeks ({cache.name}) ne sadrži čitljive pločice — kota preskočena."
            )
        return tiles

    def _ensure_tile(self, name: str, finding: ElevationFinding) -> Path | None:
        path = self.dem_dir / name
        if path.exists():
            return path
        logger.info("Downloading EL-COV tile %s (~34 MB, one-time)…", name)
        print(f"  Preuzimam EL-COV pločicu {name} (~34 MB, jednokratno) …")
        if not _download(ATOM_BASE_URL + name, path, _DOWNLOAD_TIMEOUT_S):
            finding.notes.append(f"EL-COV pločica {name} nije dohvatljiva — kota preskočena.")
            return None
        return path


def build_finder(settings: Settings) -> ElevationFinder:
    return ElevationFinder(settings.geo_data_dir, settings.geo_elevation_source_label)


def parse_tile_index(gml_bytes: bytes) -> list[TileExtent]:
    """Tile name -> extent pairs out of the EL-COV GML index.

    Namespace-agnostic linear scan: within each feature the GML lists the
    envelope (``lowerCorner`` / ``upperCorner``) before the file reference,
    so the last seen corner pair belongs to the next ``RH_ELEV_<n>.tif``
    mention. EPSG:3045's official axis order is northing-first, and GML
    honours CRS axis order — the coordinate > 2 000 000 is the northing
    (Croatia spans E ~250–750 km, N ~4 700–5 200 km in TM33).
    """
    root = ET.fromstring(gml_bytes)
    tiles: list[TileExtent] = []
    lower: tuple[float, float] | None = None
    upper: tuple[float, float] | None = None
    seen: set[str] = set()
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag in ("lowercorner", "uppercorner"):
            pair = _corner_pair(element.text)
            if pair is not None:
                if tag == "lowercorner":
                    lower = pair
                else:
                    upper = pair
            continue
        candidates = [element.text or ""] + [str(v) for v in element.attrib.values()]
        for text in candidates:
            match = _TILE_RE.search(text)
            if not match:
                continue
            name = f"RH_ELEV_{match.group(1)}.tif"
            if name in seen or lower is None or upper is None:
                continue
            seen.add(name)
            tiles.append(
                TileExtent(
                    name=name,
                    min_e=min(lower[0], upper[0]),
                    min_n=min(lower[1], upper[1]),
                    max_e=max(lower[0], upper[0]),
                    max_n=max(lower[1], upper[1]),
                )
            )
            break
    return tiles


def _corner_pair(text: str | None) -> tuple[float, float] | None:
    """'a b' -> (easting, northing), the larger value being the northing."""
    if not text:
        return None
    parts = text.split()
    if len(parts) < 2:
        return None
    try:
        a, b = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    return (b, a) if a > 2_000_000 else (a, b)


def _to_etrs_tm33(x_htrs: float, y_htrs: float) -> tuple[float, float] | None:
    try:
        from pyproj import Transformer
    except ImportError:
        logger.warning("pyproj is not installed — elevation finder unavailable")
        return None
    transformer = Transformer.from_crs("EPSG:3765", "EPSG:3045", always_xy=True)
    easting, northing = transformer.transform(x_htrs, y_htrs)
    return float(easting), float(northing)


def _sample_geotiff(
    path: Path, easting: float, northing: float, finding: ElevationFinding
) -> float | None:
    try:
        import rasterio
    except ImportError:
        finding.notes.append("rasterio nije instaliran (extra [geo]) — kota preskočena.")
        return None
    try:
        with rasterio.open(path) as src:
            value = float(next(src.sample([(easting, northing)]))[0])
            nodata = src.nodata
    except Exception as exc:  # noqa: BLE001 — fail-soft by contract
        logger.warning("Sampling %s failed: %s", path.name, exc)
        finding.notes.append(f"Očitavanje visine iz {path.name} nije uspjelo: {exc}")
        return None
    if nodata is not None and value == nodata:
        finding.notes.append(f"{path.name}: točka pada na nodata vrijednost.")
        return None
    # EL-COV nodata is conventionally a large negative sentinel even when the
    # header omits it; no Croatian entrance is below the Dead Sea.
    if value < -500:
        finding.notes.append(f"{path.name}: očitana vrijednost {value} nije vjerodostojna.")
        return None
    return value


def _download(url: str, target: Path, timeout_s: float) -> bool:
    try:
        import requests
    except ImportError:
        logger.warning("requests is not installed — cannot download %s", url)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=timeout_s) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    handle.write(chunk)
        tmp.replace(target)
        return True
    except Exception as exc:  # noqa: BLE001 — fail-soft by contract
        logger.warning("Download failed for %s: %s", url, exc)
        tmp.unlink(missing_ok=True)
        return False
