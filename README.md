# Hyderabad E2W charging gap analysis

Where can an electric two-wheeler in Hyderabad not charge, and where should
the next N stations go on a fixed budget?

This started as an economics extended essay on the total cost of owning an
electric scooter in Hyderabad, where charger coverage was judged by eye on a
map. This replaces the eyeballing with spatial analysis: real charger
locations from OpenChargeMap, real GHMC ward boundaries, an H3 hexagon
grid, a per-cell coverage score, a ward ranking, and a greedy
maximal-covering optimizer with a diminishing-returns curve, served as
GeoJSON to a Leaflet map with a budget slider.

## Run it

```bash
make setup                 # uv sync (Python 3.12)
export OCM_API_KEY=...     # free: https://openchargemap.org/site/profile/applications
make fetch                 # one network call; caches data/raw/ocm_stations.json
make build                 # grid, score, rank -> data/processed/ (offline, reproducible)
make test                  # 22 tests on synthetic fixtures, no network
make serve                 # http://127.0.0.1:8000
```

`make up` runs setup, build and serve. Once `data/raw/ocm_stations.json`
is cached, nothing needs the network or the key again.

`docker compose up` builds the same thing in a container. It was written
to the same spec as the Makefile but has not been run on the author's
machine, which has no Docker; treat it as unverified until you have.

CLI: `uv run hydgap --help` (`fetch`, `build`, `optimize --budget N`,
`serve`, `meta`).

## Method

1. **Reproject.** Everything is reprojected to EPSG:32644 (UTM 44N, metres)
   before any distance or area is computed. Nothing is buffered in degrees.
2. **Grid.** H3 hexagons at resolution 8 (about 0.74 km² each) over the
   union of the ward polygons. Each cell is tagged with the ward containing
   its centroid.
3. **Per cell.** Distance to the nearest charger, number of chargers within
   the service radius (default 2 km, a short detour on a scooter), and a
   score in [0, 1]:

   ```
   score = w_count · min(1, chargers_within / target_chargers)
         + w_distance · exp(−nearest_m / distance_decay_m)
   ```

   Defaults: `w_count` 0.6, `w_distance` 0.4, `target_chargers` 2,
   `distance_decay_m` 1500. A cell counts as **covered** at score ≥ 0.5.
4. **Demand.** Each cell carries a demand weight: its area in km² by
   default, or its share of the ward's 2011 census population when
   `demand.mode: population` and the ward has a census row. Wards without
   one are excluded in population mode and listed in the build report;
   nothing is imputed.
5. **Wards.** Cells roll up to wards: demand-weighted mean score, share of
   cells uncovered, share with no charger in reach, and uncovered demand.
   Wards rank by uncovered demand, worst first, because that is what a
   siting budget buys down.
6. **Siting.** Greedy maximal covering: at each step, place a station at the
   cell that newly covers the most demand within the service radius, until
   the budget is spent or no site adds coverage. Each step's marginal gain
   is recorded, which is the diminishing-returns curve on the map. A
   uniform cost per site is the default; the `CostModel` interface takes a
   cell id so a variable cost layer drops in. `optimize/ilp.py` documents
   the exact integer programme (PuLP) that swaps in behind the same
   `Siter` protocol.

Every threshold and weight lives in `config/model.yaml`. The build writes
`data/processed/build_meta.json` with the config hash, the counts, and
every data gap it found.

## Bring your own station list

OpenChargeMap is the default because it is open and has an API, but it is
thin for Hyderabad. If you have a better list you are allowed to use (a
government release, an operator's published locations, your own survey),
put it at `data/raw/stations.csv` and set `stations.source` in
`config/model.yaml` to `csv`, or to `both` to merge it with the
OpenChargeMap fetch (rows within `dedupe_m` of an existing station are
treated as the same charger). The columns are in
`config/stations.template.csv`; only `latitude` and `longitude` are
required, and common variants such as `lat`, `lng`, `title`, `network`
are recognised. Rows without coordinates are dropped and counted, and the
build report names which source produced the numbers.

Do not put scraped data here. PlugShare, CarDekho, ZigWheels and the
operators' own apps all have terms that forbid it, and the point of this
project is that every number traces to a source you can name.

## Data sources

| Layer | Source | Notes |
| --- | --- | --- |
| Charging stations | [OpenChargeMap API](https://openchargemap.org/site/develop/api), bounding box lat 17.20–17.65, lon 78.20–78.70 | Needs a free API key. Cached raw response committed as `data/raw/ocm_stations.json` with its fetch date |
| Ward boundaries | [datameet Municipal_Spatial_Data, `Hyderabad/ghmc-wards.geojson`](https://github.com/datameet/Municipal_Spatial_Data/blob/master/Hyderabad/ghmc-wards.geojson) (OpenStreetMap, 2017, ODbL) | The old 150-ward GHMC layout. GHMC was re-delimited to 300 wards in 2025; no public GeoJSON of that layout was found |
| Ward population (optional) | [Hyderabad Census 2011 data, data.opencity.in](https://data.opencity.in/dataset/hyderabad-census-2011-data) | Hyderabad district only |
| Basemap tiles | [OpenStreetMap standard tiles](https://www.openstreetmap.org/copyright) | Display only; desaturated under the choropleth |

## What the build says today

From the checked-in files, `make build` reports: 144 of 150 wards present,
99 with population, 9 chargers, 728 hex cells; mean coverage score 0.10,
5.5% of cells covered, 85% of cells with no charger within 2 km, median
distance to the nearest charger 4.4 km. Ten new stations would lift
covered demand from 5.5% to 31.6% under uniform demand.

## What the data cannot tell you

These are printed by `make build`, written to `build_meta.json`, and shown
on the map. Numbers below are from the checked-in files.

- **Six wards have no boundary.** The OpenStreetMap file holds 145
  polygons for the 150-ward layout: ward numbers 3, 4, 11, 13, 31 and 113
  are absent, and ward 37 appears twice (Kurmaguda and Rein Bazar, adjacent
  polygons both numbered 37 at source). Missing wards are not assessed;
  the duplicate is kept under its number and reported.
- **Population covers 99 of 150 wards.** The census file is Hyderabad
  district only, so wards in the Ranga Reddy and Medchal parts of GHMC
  (including 1–17) have no row. Population weighting is off by default and
  illustrative when on: the data is from 2011 and on a layout that has
  since changed.
- **Charger data is crowd-sourced and sparse.** The cached fetch
  (2026-09-07) holds **nine** stations inside the bounding box, none with
  an operational status or an operator, one of them explicitly for
  two-wheelers. Commercial directories list well over a hundred for
  Hyderabad, so OpenChargeMap badly undercounts the city; the coverage
  numbers here describe OpenChargeMap's picture of Hyderabad, not
  Hyderabad. Reliability, uptime and connector fit are unknown.
  `coverage.require_operational` drops unknown-status chargers, which with
  this file drops all of them. Swapping in a fuller source is a matter of
  writing another loader that returns the same station table.
- **Reach is straight-line.** A 2 km radius is Euclidean in UTM, not road
  distance, which is longer and asymmetric around lakes, railways and the
  Musi. The extension point is the `Reachability` protocol in
  `src/hydgap/spatial/network.py`: an OSMnx implementation would build the
  ride network for the bbox and answer `within` and `nearest` with network
  distance, and no caller changes.
- **Cells are assigned to a ward by centroid**, so a boundary cell can
  count toward the neighbouring ward.
- **Greedy is not optimal.** It is within 1 − 1/e of the optimum for this
  objective; `ilp.py` documents the exact formulation.

## Layout

```
config/model.yaml        every threshold and weight
data/raw/                cached inputs (committed)     data/processed/  build outputs (ignored)
src/hydgap/ingest/       ocm.py wards.py population.py
src/hydgap/spatial/      crs.py grid.py demand.py network.py coverage.py aggregate.py
src/hydgap/optimize/     base.py (problem, Siter, CostModel) greedy.py ilp.py
src/hydgap/pipeline.py   build_artifacts / load_artifacts
src/hydgap/api/          app.py (FastAPI) static/index.html (Leaflet)
tests/                   synthetic fixtures: three 3 km wards, four stations, a tiny census
```

API: `/api/meta`, `/api/cells`, `/api/wards`, `/api/wards/ranking`,
`/api/stations`, `/api/optimize?budget=&site_cost=&radius_m=`. All layers
are GeoJSON in WGS84; the optimizer runs per request on the in-memory
cells and is cached by its parameters.

## Why no PostGIS

145 wards, one to two thousand hex cells and a few hundred chargers fit in
memory and rebuild in seconds. GeoPandas with GeoParquet on disk gives the
same spatial operations with no server to run, so a clean checkout comes up
with one command and the results are a pure function of the cached inputs
and the config. PostGIS would earn its place with a road network, tiles
for a much larger area, or concurrent writers; none apply here.
