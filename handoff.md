# hyd-ev-charging-gap — handoff

_Last updated: 2026-09-07. Built in one session on 2026-09-06 from an
approved plan (`~/.claude/plans/wiggly-chasing-hammock.md`), real data
fetched 2026-09-07, a bring-your-own station loader added the same night.
Four commits, no remote. 28 tests pass, ruff is clean, the tree is clean.
Nothing is mid-edit._

**Every session starts with:** `make test`, then `make build` and read
what it prints. The build report is the truth about the data; the README
and this file quote it.

## Status at a glance

### Done

- **Ingestion.** OpenChargeMap stations (needs a free API key once; raw
  JSON cached and committed with its fetch date), GHMC ward boundaries
  from the datameet/OSM GeoJSON, optional Census 2011 ward population.
  Every gap is reported, never filled.
- **A second station source.** `stations.source: ocm | csv | both` in
  the config. The CSV loader takes common column-name variants, needs
  only latitude and longitude, drops and counts bad rows; `both` merges
  with a distance dedupe. Template in `config/stations.template.csv`.
- **Spatial model.** EPSG:32644 before any distance; H3 res-8 hexagons
  over the ward union, each tagged with a ward by centroid; nearest
  charger, chargers within 2 km, a coverage score in [0, 1]; demand per
  cell (area, or population where matched); wards ranked by uncovered
  demand.
- **Siting.** Greedy maximal covering behind a `Siter` protocol with a
  `CostModel`; marginal gain per station for the diminishing-returns
  curve; `ilp.py` documents the exact PuLP formulation as the swap-in.
- **API and map.** FastAPI serving cells, wards, ranking, stations and
  the optimizer as GeoJSON; a single-file Leaflet page with a budget
  slider, the gains strip, the worst-ten wards, layer toggles and a
  plain-language gaps panel. Checked in Chrome.
- **Packaging.** uv, Makefile (`setup fetch build test serve up`),
  Dockerfile and docker-compose written to the same spec, README with
  method, sources, limitations and the numbers the build prints.

### What is left

Ordered by how much a reader of the project would notice.

1. **The charger data is thin.** OpenChargeMap has nine stations in the
   box; OpenStreetMap has three. Commercial directories list about 190
   but PlugShare, CarDekho and ZigWheels all forbid reuse and PlugShare
   sells commercial licences only. The honest position, which the README
   takes, is that the numbers describe OpenChargeMap's picture of the
   city. The fix is a licensed or self-collected list through the CSV
   loader, or contributing stations to OpenChargeMap.
2. **No remote, no screenshot.** The repo has never been pushed and the
   README has no image of the map.
3. **`docker compose up` is unverified.** Docker is not installed on the
   author's Mac.
4. **Reach is straight-line.** The `Reachability` protocol in
   `spatial/network.py` is the extension point for OSMnx road distance.
5. **The gains curve is flat for the first ~15 sites** on real data,
   because 2 km discs fit in the city without overlapping under uniform
   demand. It tapers from about 20. A demand layer with real structure
   (population, traffic) would change that.

### What is next

1. Push to GitHub, add a screenshot to the README.
2. Find a station list you are allowed to use, or add stations to
   OpenChargeMap from sources you can verify, then `stations.source: both`.
3. OSMnx reachability, then the ILP, in that order.

## Goal

A portfolio project for a software engineer's resume that grew out of an
IB economics extended essay on electric two-wheeler total cost of
ownership in Hyderabad, where charger coverage was judged by eye on a
map. Given real charging station locations and ward boundaries, compute
where coverage is weakest and recommend where the next N stations should
go under a fixed budget.

Decisions settled with the author before code was written:

| | |
| --- | --- |
| Ward layout | The **old 150-ward GHMC layout**, because it is the only one with a public boundary file and the 2011 census matches it. GHMC went to 300 wards in 2025 |
| Charger source | OpenChargeMap by default; a CSV you supply, or both, by config |
| Storage | **No PostGIS.** GeoPandas in memory, GeoParquet on disk. 145 wards and 728 cells rebuild in under three seconds |
| Bring-up | `make up` (uv) is the verified path. Docker files exist but are unverified |
| Rules | Never fabricate coordinates, counts or population. A gap is reported as a gap |

### The architectural commitment

> **Every number traces to a source you can name, and every gap is
> surfaced, not filled.**

The build writes `build_meta.json` with the config hash, the counts, the
missing ward numbers, the unmatched census rows, the station source and
its dropped rows. The README quotes it; the map's gaps panel reads it.
If a future change makes a number look better, check the meta before
believing it.

The second commitment: **all distance maths in metres.** `to_metric()`
in `spatial/crs.py` reprojects to EPSG:32644 and `assert_metric()` guards
the scoring; nothing buffers in degrees.

## Current state

| | |
| --- | --- |
| Repo | Local git, `main`, four commits. **No remote** |
| Tests | 28 passing (`make test`), ~3.5s, synthetic fixtures only, no network |
| Lint | `uv run ruff check src tests` clean |
| Build | `make build` on the committed raw data: 2.6s |
| Serve | `make serve` → http://127.0.0.1:8000 |
| Python | 3.12 via uv; geopandas 1.1, shapely 2.1, h3 4.5, scipy, pyarrow, fastapi, typer |
| Source | ~1,150 lines in `src/hydgap`, ~450 in `tests`, one ~330-line HTML page |
| Data | `data/raw/`: `ghmc-wards.geojson` (586 KB), `ward_population_2011.csv` (49 KB), `ocm_stations.json` (11 KB, 9 stations, fetched 2026-09-07). `data/processed/` is gitignored |

### What the build reports (2026-09-07)

| | |
| --- | --- |
| Wards | 145 polygons, **144 unique numbers** of 150; missing 3, 4, 11, 13, 31, 113; **37 appears twice** (Kurmaguda and Rein Bazar, adjacent, both numbered 37 at source) |
| Population | 99 of 150 wards matched; 46 present wards without a row. The census file is Hyderabad district only, so wards 1–17 and others in Ranga Reddy and Medchal have none |
| Stations | 9 from OpenChargeMap, all with unknown operator and status, 3 with unknown power; one explicitly for two-wheelers (Blaze, LB Nagar) |
| Grid | 728 H3 cells at res 8 |
| Coverage | mean score 0.099; 5.5% of cells covered (score ≥ 0.5); 85.0% with no charger within 2 km; median nearest 4,377 m |
| Ten new stations | covered demand 5.5% → 31.6%, each of the first ten adding 14.3 km² of newly covered area |

### Measured before the numbers were set

- The pool of charger sources, 2026-09-07: OpenChargeMap 9 in the box,
  Overpass (OSM `amenity=charging_station`) 3, CarDekho and ZigWheels
  about 190, Statiq claims 496 of its own. Only the first two are usable.
- Resolution 8 gives 728 cells over the ward union; the plan's estimate
  was about 1,000. Resolution 9 would be roughly 5,000 and the cells
  GeoJSON several MB.
- The optimizer at budget 25 on real data ran well under 100 ms per
  request; the API caches by parameters anyway.

## Files that matter

In dependency order.

**Configuration**

- `config/model.yaml` — every threshold and weight: bbox, CRS, H3 res,
  the coverage formula's four terms, demand mode, optimizer settings, the
  station source, expected ward count, source URLs
- `src/hydgap/config.py` — pydantic models for the above, `load_config`,
  `config_hash`. Coverage weights must sum to 1

**Ingestion** (`src/hydgap/ingest/`)

- `wards.py` — `load_wards` parses "Ward 91 Khairatabad" into number and
  name; `report_ward_gaps` lists missing, duplicate and unparsed
- `population.py` — `load_population` keeps GHMC ward rows only;
  `join_population` returns the unmatched numbers, keeps NaN
- `ocm.py` — `fetch_stations` (key via `X-API-Key`, writes a wrapper with
  `fetched_at`), `load_stations` (drops rows without coordinates, counts
  unknown status and power), `StationReport`
- `csvstations.py` — `load_stations_csv`, the column aliases, status words
- `stations.py` — `load_station_layer` picks by `stations.source`;
  `merge_stations` dedupes by cKDTree distance

**Spatial** (`src/hydgap/spatial/`), all in metres

- `crs.py` — `to_metric`, `to_wgs84`, `assert_metric`
- `grid.py` — `build_hex_grid`: `h3.geo_to_cells` on the ward union in
  4326, boundaries reprojected, ward by centroid sjoin
- `demand.py` — `assign_demand`: uniform (km²) or population share;
  wards without population get NaN and are listed
- `network.py` — the `Reachability` protocol (`within` → sparse bool
  matrix, `nearest`), `StraightLineReachability` on cKDTree. **The
  road-network extension point**
- `coverage.py` — `coverage_score`, `score_cells`, `usable_stations`
  (`require_operational` drops unknowns, which today drops all nine)
- `aggregate.py` — `aggregate_wards`: demand-weighted mean score, shares,
  uncovered demand, rank

**Optimizer** (`src/hydgap/optimize/`)

- `base.py` — `SitingProblem` (ids, demand, covered0, sparse neighbours,
  costs, budget, candidates), `SiteChoice`, `SitingResult`, the `Siter`
  and `CostModel` protocols, `UniformCost`, `build_problem`
- `greedy.py` — `GreedySiter`: `gains = neighbors @ (demand * ~covered)`,
  argmax over affordable unchosen candidates, stop at budget or zero gain
- `ilp.py` — the PuLP formulation in the docstring; `solve` raises

**Pipeline, CLI, API**

- `pipeline.py` — `build_artifacts` writes three parquet files and
  `build_meta.json`; `load_artifacts` reads them back
- `cli.py` — typer: `fetch`, `build`, `optimize`, `serve`, `meta`
- `api/app.py` — `create_app(processed, config)`; layers converted once at
  startup (`feature_collection` turns NaN into null), optimizer per
  request with `lru_cache`
- `api/static/index.html` — Leaflet, one file, OSM tiles desaturated under
  the choropleth, Bricolage Grotesque, plum-to-sand ramp

**Tests** (`tests/`)

- Fixtures: three 3 km square wards numbered 1, 2 and 4 (so 3 is missing
  on purpose), four OCM POIs (one without coordinates), a five-row CSV
  (two bad rows), a three-row census matching wards 1 and 2 only
- `test_ingest`, `test_csvstations`, `test_grid`, `test_demand`,
  `test_coverage` (a hand-computed 2,997 m distance), `test_aggregate`
  (ward 4 ranks worst), `test_greedy` (a five-cell toy problem with
  hand-checked gains), `test_pipeline`, `test_api` (TestClient on
  artifacts built in tmp_path)

## Failed attempts and traps

**1. The tier thresholds problem, in another project the same day.**
Not here, but the lesson applied: measure a source before trusting its
shape. The ward file was assumed to have 145 of 150 wards; it has 144
unique numbers and one duplicate. The gap report caught it because it
counts numbers, not rows.

**2. OpenChargeMap without a key.** Returns 403 for everything, including
a tiny bounding box. Community threads from 2023 say keys were only
needed above 250 results; that is no longer true. The fetch fails loudly
if the key is unset.

**3. The wrong OpenChargeMap URLs.** `openchargemap.org/site/profile/...`
404s; the site has no `/site` prefix. Applications and API keys are at
`/profile/applications` under "My profile → my apps", visible only when
signed in.

**4. CARTO basemap tiles.** They now watermark "API KEY REQUIRED". The
page uses OpenStreetMap's standard tiles, greyed and at 75% opacity so
the choropleth reads over them.

**5. The Chrome extension's tab does not run PlugShare or the
OpenChargeMap map.** Both rely on JavaScript the throttled tab never
finishes; the OCM map rendered blank and PlugShare showed a registration
wall. Do not conclude anything about a site's data from that tab.

**6. Screenshotting a smoke build with fixture stations on real wards.**
Done once, in the scratchpad, to see the page render before the key
existed. Useful, and dangerous if anyone mistakes it for a result. Never
build fixture stations into `data/processed`.

**7. `ruff --fix` changed the file under a planned edit.** A replacement
keyed on a `# noqa` comment failed silently after ruff removed the
comment. Assert the old text is present before replacing.

**8. Committing to a licence you cannot get.** PlugShare would have
solved the data problem and explicitly does not license personal or
non-commercial use. Check the licence before checking the data.

## Known rough edges

- **`require_operational: true` empties the station layer today**,
  because every OCM entry has null status.
- **The duplicate ward 37** is two polygons under one number; the ranking
  merges their cells, and both rows get the same summary.
- **Population mode excludes 46 wards** rather than imputing; the
  optimizer then treats them as zero demand. That is by design and it
  makes population mode illustrative only.
- **Boundary cells** belong to whichever ward holds their centroid.
- **The gains strip is uniform** for the first ~15 sites on real data;
  it only starts to taper when discs overlap.
- **`/api/cells` is ~1 MB** of GeoJSON at res 8. Fine; res 9 would not be.
- **The CSV loader does not validate that points fall inside the bbox.**
  A station in Delhi would score Hyderabad cells as far away. Cheap to
  add if it ever bites.
- **`sources` in the config are strings for the README**, not fetched.
- **Docker files are unverified.**

## Running it

```bash
make setup                  # uv sync
export OCM_API_KEY=...      # only for `make fetch`
make fetch                  # once; caches data/raw/ocm_stations.json
make build                  # 2.6s; prints the gap report
make test                   # 28 tests, no network
make serve                  # http://127.0.0.1:8000
uv run hydgap optimize --budget 10        # the gains table in the terminal
uv run hydgap optimize --budget 10 --out sites.geojson
```

To use your own station list: copy `config/stations.template.csv` to
`data/raw/stations.csv`, set `stations.source: csv` or `both`, rebuild.
