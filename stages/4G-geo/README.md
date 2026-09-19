# 4G — Geo

**Where a cave is, administratively and vertically.** Two finders over open
Croatian government data, consumed by both 4O-osz and 4S-sastavnica.

## What it does

- **Locality finder** — županija / grad-općina / najbliže mjesto / lokalitet for
  a point, from the DGU administrative boundary GeoPackages plus the RGI
  gazetteer of named places.
- **Elevation finder** — *Kota ulaza* from DGU's open INSPIRE EL-COV elevation
  grid, compared against SB's own `Z` value.

## Commands

```powershell
cavedossier geo fetch-data      # provision data/geo -- once per machine
cavedossier geo locate 1220     # what the locality finder says for one cave
cavedossier geo kota 1220       # what the elevation finder says vs SB's Z
```

`locate` and `kota` are **debug commands**: they feed nothing and change
nothing. They exist so you can check what the finders would say before trusting
them inside an OSZ prefill.

## How it works

`fetch-data` provisions the gitignored `data/geo/` at the workspace root:
boundary GeoPackages, the RGI gazetteer, and DEM tiles fetched lazily per
region. Every dataset is **regenerable from open services by that one command** —
which is what lets a prod machine be provisioned by running it once, or by
copying the ready-made bundle from the Drive.

Precedence matters: **SB wins.** Where SB already holds a value, the finder's
result is offered as a *supplement* (`dopune-sb.csv`), never silently
substituted.

Every import here is lazy. A base install without the `[geo]` extra works fine —
the finders simply report "unavailable" rather than crashing an OSZ prefill.

## Why it is its own stage

It was written as "the `geo/` modules of the OSZ builder", but both 4O-osz and
4S-sastavnica consume it, and its dataset has its own provisioning lifecycle.
It is not the OSZ builder's private helper.

## Where things are

- Code: [`src/cave_dossier/geo/`](src/cave_dossier/geo/)
- Tests: [`tests/`](tests/)
- Data (gitignored, regenerable): `data/geo/` at the workspace root — provenance
  and licences in [`data/README.md`](../../data/README.md)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)

## Status

Operational.
