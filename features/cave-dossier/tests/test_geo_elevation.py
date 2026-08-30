"""geo/elevation.py: index parsing (pure) and grid sampling (needs [geo]).

The GML index parser is namespace-agnostic and runs on synthetic bytes; the
sampling test builds a tiny EPSG:3045 GeoTIFF around the transformed test
point, so it skips unless rasterio + pyproj (the [geo] extra) are present.
"""

from __future__ import annotations

import pytest

from cave_dossier.geo.elevation import (
    ElevationFinder,
    _corner_pair,
    parse_tile_index,
)

_GML = b"""<?xml version="1.0" encoding="UTF-8"?>
<gml:FeatureCollection xmlns:gml="http://www.opengis.net/gml/3.2"
                       xmlns:xlink="http://www.w3.org/1999/xlink">
  <gml:featureMember>
    <gml:boundedBy>
      <gml:Envelope srsName="EPSG:3045">
        <gml:lowerCorner>5000000 400000</gml:lowerCorner>
        <gml:upperCorner>5100000 500000</gml:upperCorner>
      </gml:Envelope>
    </gml:boundedBy>
    <gml:fileReference xlink:href="https://geoportal.dgu.hr/services/atom/RH_ELEV_7.tif"/>
  </gml:featureMember>
  <gml:featureMember>
    <gml:boundedBy>
      <gml:Envelope srsName="EPSG:3045">
        <gml:lowerCorner>4900000 500000</gml:lowerCorner>
        <gml:upperCorner>5000000 600000</gml:upperCorner>
      </gml:Envelope>
    </gml:boundedBy>
    <gml:fileReference>RH_ELEV_8.tif</gml:fileReference>
  </gml:featureMember>
</gml:FeatureCollection>
"""


def test_corner_pair_normalizes_axis_order():
    # EPSG:3045 lists northing first; the parser puts easting first.
    assert _corner_pair("5023000 450000") == (450000.0, 5023000.0)
    assert _corner_pair("450000 5023000") == (450000.0, 5023000.0)
    assert _corner_pair("garbage") is None
    assert _corner_pair(None) is None


def test_parse_tile_index_reads_both_reference_styles():
    tiles = parse_tile_index(_GML)
    assert [t.name for t in tiles] == ["RH_ELEV_7.tif", "RH_ELEV_8.tif"]
    seven = tiles[0]
    assert (seven.min_e, seven.min_n, seven.max_e, seven.max_n) == (
        400000.0, 5000000.0, 500000.0, 5100000.0
    )
    assert seven.contains(450000.0, 5050000.0)
    assert not seven.contains(450000.0, 4950000.0)


def test_kota_without_pyproj_or_data_is_failsoft(tmp_path, monkeypatch):
    # Regardless of installed extras: no index and no network → notes, no value.
    import cave_dossier.geo.elevation as elevation_mod

    monkeypatch.setattr(elevation_mod, "_download", lambda *a, **k: False)
    finder = ElevationFinder(tmp_path, "DMV (DGU)")
    finding = finder.kota(450123.0, 5023456.0)
    assert finding.elevation_m is None
    assert finding.notes  # says WHY it has no answer


def test_kota_samples_local_tile(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    pyproj = pytest.importorskip("pyproj")
    from rasterio.transform import from_origin

    x_htrs, y_htrs = 450123.0, 5023456.0
    transformer = pyproj.Transformer.from_crs("EPSG:3765", "EPSG:3045", always_xy=True)
    easting, northing = transformer.transform(x_htrs, y_htrs)

    # A 20×20 grid of 25 m cells centred on the point, constant value 777.
    dem_dir = tmp_path / "dem"
    dem_dir.mkdir()
    tile = dem_dir / "RH_ELEV_7.tif"
    transform = from_origin(easting - 250, northing + 250, 25, 25)
    import numpy as np

    with rasterio.open(
        tile, "w", driver="GTiff", height=20, width=20, count=1,
        dtype="float32", crs="EPSG:3045", transform=transform, nodata=-9999.0,
    ) as dst:
        dst.write(np.full((1, 20, 20), 777.0, dtype="float32"))

    index = f"""<?xml version="1.0"?>
<root xmlns:gml="http://www.opengis.net/gml/3.2">
  <gml:lowerCorner>{northing - 250:.0f} {easting - 250:.0f}</gml:lowerCorner>
  <gml:upperCorner>{northing + 250:.0f} {easting + 250:.0f}</gml:upperCorner>
  <file>RH_ELEV_7.tif</file>
</root>"""
    (tmp_path / "el_cov_index.gml").write_text(index, encoding="utf-8")

    finder = ElevationFinder(tmp_path, "DMV (DGU)")
    finding = finder.kota(x_htrs, y_htrs)
    assert finding.elevation_m == 777
    assert finding.source_label == "DMV (DGU)"
    assert finding.tile_name == "RH_ELEV_7.tif"


def test_kota_nodata_is_reported(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    pyproj = pytest.importorskip("pyproj")
    from rasterio.transform import from_origin
    import numpy as np

    x_htrs, y_htrs = 450123.0, 5023456.0
    transformer = pyproj.Transformer.from_crs("EPSG:3765", "EPSG:3045", always_xy=True)
    easting, northing = transformer.transform(x_htrs, y_htrs)

    dem_dir = tmp_path / "dem"
    dem_dir.mkdir()
    with rasterio.open(
        dem_dir / "RH_ELEV_7.tif", "w", driver="GTiff", height=4, width=4, count=1,
        dtype="float32", crs="EPSG:3045",
        transform=from_origin(easting - 50, northing + 50, 25, 25), nodata=-9999.0,
    ) as dst:
        dst.write(np.full((1, 4, 4), -9999.0, dtype="float32"))
    (tmp_path / "el_cov_index.gml").write_text(
        f"""<?xml version="1.0"?><root xmlns:gml="http://www.opengis.net/gml/3.2">
<gml:lowerCorner>{northing - 50:.0f} {easting - 50:.0f}</gml:lowerCorner>
<gml:upperCorner>{northing + 50:.0f} {easting + 50:.0f}</gml:upperCorner>
<file>RH_ELEV_7.tif</file></root>""",
        encoding="utf-8",
    )

    finding = ElevationFinder(tmp_path, "DMV").kota(x_htrs, y_htrs)
    assert finding.elevation_m is None
    assert any("nodata" in note for note in finding.notes)


def test_kota_nodata_rescued_from_neighbor_cell(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    pyproj = pytest.importorskip("pyproj")
    from rasterio.transform import from_origin
    import numpy as np

    x_htrs, y_htrs = 450123.0, 5023456.0
    transformer = pyproj.Transformer.from_crs("EPSG:3765", "EPSG:3045", always_xy=True)
    easting, northing = transformer.transform(x_htrs, y_htrs)

    # Valid terrain everywhere except a nodata hole on the entrance cell.
    data = np.full((10, 10), 444.0, dtype="float32")
    transform = from_origin(easting - 125, northing + 125, 25, 25)
    dem_dir = tmp_path / "dem"
    dem_dir.mkdir()
    with rasterio.open(
        dem_dir / "RH_ELEV_7.tif", "w", driver="GTiff", height=10, width=10,
        count=1, dtype="float32", crs="EPSG:3045", transform=transform,
        nodata=-9999.0,
    ) as dst:
        row, col = dst.index(easting, northing)
        data[row, col] = -9999.0
        dst.write(data[np.newaxis, :, :])
    (tmp_path / "el_cov_index.gml").write_text(
        f"""<?xml version="1.0"?><root xmlns:gml="http://www.opengis.net/gml/3.2">
<gml:lowerCorner>{northing - 125:.0f} {easting - 125:.0f}</gml:lowerCorner>
<gml:upperCorner>{northing + 125:.0f} {easting + 125:.0f}</gml:upperCorner>
<file>RH_ELEV_7.tif</file></root>""",
        encoding="utf-8",
    )

    finding = ElevationFinder(tmp_path, "DMV").kota(x_htrs, y_htrs)
    assert finding.elevation_m == 444
    assert any("najbliža valjana" in note for note in finding.notes)
