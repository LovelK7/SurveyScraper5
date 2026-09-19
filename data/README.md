# data/ — downloaded geodata (gitignored, regenerable)

Everything under this folder except this README is **gitignored** and
provisioned by `cavedossier geo fetch-data` (see `cave_dossier/geo/provision.py`).
Delete the folder freely; a re-run restores it from open services.

## Contents (`data/geo/`)

| File | What | Source |
|---|---|---|
| `naselja.gpkg` | settlement polygons (`NA_IME`, + `JLS_IME`/`ZU_IME` hierarchy when converted from RPJ shapefiles) | DGU |
| `jls.gpkg` | gradovi/općine polygons (`JLS_IME`) | DGU |
| `zupanije.gpkg` | županije polygons (`ZU_IME`) | DGU |
| `rgi_named_places.gpkg` | RGI gazetteer, ~125k named-place points (offline fallback for the live WFS) | DGU RGI WFS `rgi.dgu.hr/geoserver/wfshr/wfs` |
| `el_cov_index.gml` | INSPIRE EL-COV tile index | DGU geoportal ATOM |
| `dem/RH_ELEV_<n>.tif` | elevation grid tiles (EPSG:3045), downloaded lazily per area of interest | DGU geoportal ATOM (`geoportal.dgu.hr/services/atom/`) |
| `temp/` | drop DGU RPJ shapefiles (`NA.shp`/`JLS.shp`/`ZU.shp` + sidecars) here for the shapefile conversion path | manual download |

All vector layers are (re)projected to **HTRS96/TM, EPSG:3765** — SB-native,
so no coordinate transformation happens at query time. The EL-COV tiles stay
in their native EPSG:3045; the elevation finder transforms the query point.

## Licence / attribution

DGU open data is published under the Croatian **Otvorena dozvola / Open
Licence** (data.gov.hr/otvorena-dozvola): free for commercial and
non-commercial use with attribution. Attribution: *„Sadrži javne podatke
Državne geodetske uprave (dgu.gov.hr)"*. Datasets used: Registar geografskih
imena (RGI), INSPIRE Administrative Units (AU), INSPIRE Elevation (EL-COV) /
digitalni model visina.
