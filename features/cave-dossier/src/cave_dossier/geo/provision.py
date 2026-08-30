"""Provision the gitignored geo data dir (`cavedossier geo fetch-data`).

Three sources, tried in order per artifact (see data/README.md for the
provenance and licence notes):

1. **Local copy** from the read-only ``../crospeleo-automation/data/geo``
   checkout, when that machine already generated the GeoPackages (copying
   data OUT of the reference repo is allowed; writing into it never is).
2. **RGI gazetteer** — paged download of the open RGI WFS
   (``rgi_named_places.gpkg``, ~125k point features). Ported from
   crospeleo-automation ``scripts/fetch_rgi.py`` (docs/PORTING.md).
3. **Admin boundaries** (``naselja/jls/zupanije.gpkg``) — either converted
   from DGU RPJ shapefiles dropped into ``<data_dir>/temp/`` (NA.shp /
   JLS.shp / ZU.shp — the column layout crospeleo's converter used), or
   best-effort from the open INSPIRE AU GML zip (~209 MB, EPSG:3035,
   reprojected here to 3765). The INSPIRE path is schema-tolerant and
   reports what it found when it cannot classify layers.

Everything requires the ``[geo]`` extra; imports are lazy so the rest of the
CLI works without it.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.geo.rgi_client import OFFLINE_GPKG_NAME

RGI_WFS_URL = "http://rgi.dgu.hr/geoserver/wfshr/wfs"
RGI_TYPENAME = "wfshr:nippimenovanomjesto"
RGI_PAGE_SIZE = 5000
RGI_PAUSE_BETWEEN_PAGES_S = 1.0
RGI_TIMEOUT_S = 120

AU_ZIP_URL = "https://geoportal.dgu.hr/services/atom/INSPIRE_Administrative_Units_(AU).zip"

# ../crospeleo-automation sits beside the SurveyScraper5 repo root
# (provision.py -> geo -> cave_dossier -> src -> cave-dossier -> features
#  -> SurveyScraper5 -> Programming).
CROSPELEO_GEO_DIR = Path(__file__).resolve().parents[6] / "crospeleo-automation" / "data" / "geo"

ADMIN_GPKGS = ("naselja.gpkg", "jls.gpkg", "zupanije.gpkg")

# DGU RPJ shapefile -> (gpkg, columns kept). The keep-lists mirror
# crospeleo-automation scripts/convert_dgu_shapefiles.py, so a gpkg produced
# by either tool reads identically (naselja carries the full hierarchy —
# admin_lookup resolves all three levels from it in one point-in-polygon).
SHAPEFILE_SPECS: dict[str, tuple[str, tuple[str, ...]]] = {
    "NA.shp": ("naselja.gpkg", ("NA_ID", "NA_MB", "NA_IME", "JLS_MB", "JLS_IME", "JLS_ST", "ZU_RB", "ZU_IME")),
    "JLS.shp": ("jls.gpkg", ("JLS_ID", "JLS_MB", "JLS_IME", "JLS_ST", "JLS_SJ", "ZU_RB", "ZU_IME")),
    "ZU.shp": ("zupanije.gpkg", ("ZU_ID", "ZU_RB", "ZU_IME", "ZU_SJ")),
}


def fetch_data(settings: Settings, *, include_au: bool = True) -> int:
    """Provision everything that is missing; returns a CLI exit code."""
    data_dir = settings.geo_data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    _copy_from_crospeleo(data_dir)

    ok = True
    if not (data_dir / OFFLINE_GPKG_NAME).exists():
        ok = _fetch_rgi(data_dir) and ok
    else:
        print(f"✓ {OFFLINE_GPKG_NAME} already present")

    missing_admin = [n for n in ADMIN_GPKGS if not (data_dir / n).exists()]
    if not missing_admin:
        print("✓ admin boundary GeoPackages already present")
    elif _convert_shapefiles(data_dir):
        pass
    elif include_au:
        ok = _convert_inspire_au(data_dir) and ok
    else:
        ok = False

    still_missing = [n for n in ADMIN_GPKGS if not (data_dir / n).exists()]
    if still_missing:
        print()
        print(f"Missing after this run: {', '.join(still_missing)}")
        print("Fallback: download the DGU RPJ shapefiles (NA.shp / JLS.shp / ZU.shp")
        print(f"with sidecars) into {data_dir / 'temp'} and re-run `geo fetch-data`.")
        ok = False
    return 0 if ok else 99


# ── source 1: the crospeleo checkout ─────────────────────────────────
def _copy_from_crospeleo(data_dir: Path) -> None:
    if not CROSPELEO_GEO_DIR.is_dir():
        return
    for name in (*ADMIN_GPKGS, OFFLINE_GPKG_NAME):
        src = CROSPELEO_GEO_DIR / name
        dst = data_dir / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"✓ {name} copied from ../crospeleo-automation/data/geo")


# ── source 2: RGI paged WFS download ─────────────────────────────────
def _fetch_rgi(data_dir: Path) -> bool:
    """rgi_named_places.gpkg via paged GetFeature (Session + Retry + resume).

    Pages are persisted under ``<data_dir>/rgi_pages/`` so an interrupted
    run resumes instead of restarting — the pattern (page size, politeness
    pause, hits-count probe) is crospeleo's fetch_rgi.py.
    """
    try:
        import geopandas as gpd  # type: ignore[import-untyped]
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
    except ImportError as exc:
        print(f"✗ RGI download needs the [geo] extra ({exc.name} missing)")
        return False
    import json
    import time

    pages_dir = data_dir / "rgi_pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[500, 502, 503, 504],
                  allowed_methods=["GET"])
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))

    base_params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": RGI_TYPENAME,
        "outputFormat": "application/json",
    }

    print(f"Fetching {RGI_TYPENAME} from {RGI_WFS_URL} (pages of {RGI_PAGE_SIZE}) …")
    features: list[dict] = []
    start = 0
    page = 0
    while True:
        page_file = pages_dir / f"page_{page:04d}.json"
        if page_file.exists():
            data = json.loads(page_file.read_text(encoding="utf-8"))
        else:
            try:
                resp = session.get(
                    RGI_WFS_URL,
                    params={**base_params, "count": str(RGI_PAGE_SIZE), "startIndex": str(start)},
                    timeout=RGI_TIMEOUT_S,
                )
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, ValueError) as exc:
                print(f"✗ RGI page {page} failed: {exc} (re-run to resume)")
                return False
            page_file.write_text(json.dumps(data), encoding="utf-8")
            time.sleep(RGI_PAUSE_BETWEEN_PAGES_S)
        got = data.get("features") or []
        features.extend(got)
        print(f"  page {page}: {len(got)} features (total {len(features)})")
        if len(got) < RGI_PAGE_SIZE:
            break
        start += RGI_PAGE_SIZE
        page += 1

    if not features:
        print("✗ RGI returned no features")
        return False
    gdf = gpd.GeoDataFrame.from_features(features, crs="EPSG:3765")
    target = data_dir / OFFLINE_GPKG_NAME
    gdf.to_file(target, driver="GPKG")
    shutil.rmtree(pages_dir, ignore_errors=True)
    print(f"✓ {target.name} written ({len(gdf)} features)")
    return True


# ── source 3a: DGU RPJ shapefiles dropped into temp/ ─────────────────
def _convert_shapefiles(data_dir: Path) -> bool:
    """True when every missing admin gpkg was produced from temp/ shapefiles."""
    temp_dir = data_dir / "temp"
    if not temp_dir.is_dir():
        return False
    try:
        import geopandas as gpd  # type: ignore[import-untyped]
    except ImportError:
        return False

    produced_all = True
    converted_any = False
    for shp_name, (gpkg_name, keep_cols) in SHAPEFILE_SPECS.items():
        target = data_dir / gpkg_name
        if target.exists():
            continue
        shp = temp_dir / shp_name
        if not shp.exists():
            produced_all = False
            continue
        gdf = gpd.read_file(shp)
        cols = [c for c in keep_cols if c in gdf.columns] + ["geometry"]
        gdf = gdf[cols]
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:3765")
        elif gdf.crs.to_epsg() != 3765:
            gdf = gdf.to_crs("EPSG:3765")
        # Interrupted-write shards make invalid geometries; buffer(0) heals them
        gdf["geometry"] = gdf.geometry.buffer(0)
        gdf.to_file(target, driver="GPKG")
        converted_any = True
        print(f"✓ {gpkg_name} converted from temp/{shp_name} ({len(gdf)} features)")
    return converted_any and produced_all


# ── source 3b: open INSPIRE AU GML ───────────────────────────────────
# Verified against the live archive 2026-08-30: one 600 MB GML of 50,192
# au:AdministrativeUnit features. GDAL's GML driver drops both the level
# (an xlink:title ATTRIBUTE on au:nationalLevel) and the name (nested
# gn:text), so this is a hand-rolled lxml.iterparse stream instead.
# Croatia's hierarchy in the dataset: 1stOrder = država, 2ndOrder =
# županije, 3rdOrder = gradovi/općine, 4thOrder = naselja (deeper orders
# are statistical circles — skipped). au:upperLevelUnit's xlink:title
# carries the parent unit's NAME, which is how naselja get JLS_IME and
# JLS rows get ZU_IME without a second pass.
_AU_NS = "http://inspire.ec.europa.eu/schemas/au/4.0"
_GN_NS = "http://inspire.ec.europa.eu/schemas/gn/4.0"
_GML_NS = "http://www.opengis.net/gml/3.2"
_XLINK_NS = "http://www.w3.org/1999/xlink"

_AU_LEVELS = {
    "2ndOrder": ("zupanije.gpkg", "ZU_IME", None),
    "3rdOrder": ("jls.gpkg", "JLS_IME", "ZU_IME"),
    "4thOrder": ("naselja.gpkg", "NA_IME", "JLS_IME"),
}


def _convert_inspire_au(data_dir: Path) -> bool:
    try:
        import geopandas as gpd  # type: ignore[import-untyped]
        from lxml import etree
        from shapely.geometry import MultiPolygon, Polygon  # type: ignore[import-untyped]
    except ImportError as exc:
        print(f"✗ INSPIRE AU conversion needs the [geo]+[osz] extras ({exc.name} missing)")
        return False
    from cave_dossier.geo.elevation import _download  # same fail-soft downloader

    zip_path = data_dir / "INSPIRE_AU.zip"
    if not zip_path.exists():
        print(f"Downloading {AU_ZIP_URL} (~209 MB, one-time) …")
        if not _download(AU_ZIP_URL, zip_path, 1800.0):
            print("✗ INSPIRE AU download failed")
            return False

    extract_dir = data_dir / "inspire_au"
    if not extract_dir.is_dir():
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)
    gml_files = sorted(extract_dir.rglob("*.gml"))
    if not gml_files:
        print(f"✗ No .gml inside {zip_path.name}")
        return False

    print(f"Parsing {gml_files[0].name} (~600 MB, a few minutes) …")
    rows: dict[str, list[dict]] = {level: [] for level in _AU_LEVELS}
    count = 0
    for gml in gml_files:
        # huge_tree: the archive is one 600 MB line; without it lxml stops at
        # "huge text node" around the 570 MB mark (seen live 2026-08-30).
        context = etree.iterparse(str(gml), events=("end",),
                                  tag=f"{{{_AU_NS}}}AdministrativeUnit",
                                  huge_tree=True)
        for _event, unit in context:
            count += 1
            level_el = unit.find(f"{{{_AU_NS}}}nationalLevel")
            level = _au_level(level_el)
            if level in rows:
                name = unit.findtext(f".//{{{_GN_NS}}}text")
                upper = unit.find(f"{{{_AU_NS}}}upperLevelUnit")
                upper_name = upper.get(f"{{{_XLINK_NS}}}title") if upper is not None else None
                geometry = _au_geometry(unit, Polygon, MultiPolygon)
                if name and geometry is not None:
                    rows[level].append(
                        {"name": name.strip(), "upper": (upper_name or "").strip() or None,
                         "geometry": geometry}
                    )
            # Free the streamed tree as we go — 600 MB does not fit nicely.
            unit.clear()
            parent = unit.getparent()
            while parent is not None and parent.getprevious() is not None:
                del parent.getparent()[0]
        del context
    print(f"  {count} units read: " + ", ".join(
        f"{level} {len(found)}" for level, found in rows.items()))

    produced = False
    for level, (gpkg_name, name_col, upper_col) in _AU_LEVELS.items():
        target = data_dir / gpkg_name
        if target.exists():
            continue
        found = rows[level]
        if not found:
            print(f"  ! no {level} units for {gpkg_name}")
            continue
        frame = {
            name_col: [row["name"] for row in found],
            "geometry": [row["geometry"] for row in found],
        }
        if upper_col:
            frame[upper_col] = [row["upper"] for row in found]
        gdf = gpd.GeoDataFrame(frame, crs="EPSG:3035")
        gdf["geometry"] = gdf.geometry.buffer(0)  # heal self-intersections
        gdf = gdf.to_crs("EPSG:3765")
        gdf.to_file(target, driver="GPKG")
        produced = True
        print(f"✓ {gpkg_name} from INSPIRE AU ({len(gdf)} features)")
    return produced


def _au_level(level_el) -> str | None:
    """'4thOrder' from au:nationalLevel's xlink:title (or its codelist href)."""
    if level_el is None:
        return None
    title = level_el.get(f"{{{_XLINK_NS}}}title")
    if title:
        return title.strip()
    href = level_el.get(f"{{{_XLINK_NS}}}href") or ""
    return href.rsplit("/", 1)[-1] or None


def _au_geometry(unit, Polygon, MultiPolygon):
    """shapely (Multi)Polygon from the unit's gml:MultiSurface.

    The GML honours EPSG:3035's official northing-first axis order, so each
    posList pair is (N, E) and is swapped to (E, N) for shapely/pyproj's
    traditional order.
    """
    polygons = []
    for poly_el in unit.findall(f".//{{{_GML_NS}}}Polygon"):
        exterior = poly_el.find(
            f"{{{_GML_NS}}}exterior/{{{_GML_NS}}}LinearRing/{{{_GML_NS}}}posList"
        )
        shell = _pos_list_coords(exterior)
        if len(shell) < 3:
            continue
        holes = []
        for interior in poly_el.findall(
            f"{{{_GML_NS}}}interior/{{{_GML_NS}}}LinearRing/{{{_GML_NS}}}posList"
        ):
            ring = _pos_list_coords(interior)
            if len(ring) >= 3:
                holes.append(ring)
        polygons.append(Polygon(shell, holes))
    if not polygons:
        return None
    return polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)


def _pos_list_coords(pos_list_el) -> list[tuple[float, float]]:
    if pos_list_el is None or not pos_list_el.text:
        return []
    values = pos_list_el.text.split()
    if len(values) < 6:
        return []
    try:
        floats = [float(v) for v in values]
    except ValueError:
        return []
    # (northing, easting) pairs → (easting, northing)
    return [(floats[i + 1], floats[i]) for i in range(0, len(floats) - 1, 2)]
