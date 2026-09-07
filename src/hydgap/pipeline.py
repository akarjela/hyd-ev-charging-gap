"""ingest -> grid -> demand -> coverage -> wards, written to data/processed."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd

from hydgap.config import ModelConfig, config_hash
from hydgap.ingest.population import join_population, load_population
from hydgap.ingest.stations import load_station_layer
from hydgap.ingest.wards import load_wards, report_ward_gaps
from hydgap.spatial.aggregate import aggregate_wards
from hydgap.spatial.coverage import score_cells
from hydgap.spatial.crs import to_metric
from hydgap.spatial.demand import assign_demand
from hydgap.spatial.grid import build_hex_grid

WARDS_FILE = "ghmc-wards.geojson"
STATIONS_FILE = "ocm_stations.json"
STATIONS_CSV = "stations.csv"
POPULATION_FILE = "ward_population_2011.csv"


@dataclass
class Artifacts:
    cells: gpd.GeoDataFrame
    wards: gpd.GeoDataFrame
    stations: gpd.GeoDataFrame
    meta: dict


def build_artifacts(cfg: ModelConfig, raw_dir: Path | str, out_dir: Path | str) -> dict:
    raw, out = Path(raw_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    wards = load_wards(raw / WARDS_FILE)
    gaps = report_ward_gaps(wards, cfg.expected_wards)

    population_meta: dict = {"file": None, "matched": 0, "unmatched": []}
    pop_path = raw / POPULATION_FILE
    if pop_path.exists():
        wards, unmatched = join_population(wards, load_population(pop_path))
        population_meta = {"file": pop_path.name, "matched": int(wards["population"].notna().sum()), "unmatched": unmatched}
    elif cfg.demand.mode == "population":
        raise FileNotFoundError(f"demand.mode is population but {pop_path} is missing")

    stations, station_meta = load_station_layer(cfg.stations, raw, cfg.crs_metric)

    cells = build_hex_grid(wards, cfg.h3_resolution, cfg.crs_metric)
    cells, demand_report = assign_demand(cells, wards, cfg.demand)
    stations_m = to_metric(stations, cfg.crs_metric)
    cells = score_cells(cells, stations_m, cfg.coverage)
    wards_m = to_metric(wards, cfg.crs_metric)
    ward_summary = aggregate_wards(cells, wards_m, cfg)

    covered = cells["score"] >= cfg.optimizer.coverage_threshold
    meta = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "config_hash": config_hash(cfg),
        "config": cfg.model_dump(),
        "wards": gaps.as_dict(),
        "population": population_meta,
        "stations": station_meta,
        "demand": demand_report.as_dict(),
        "grid": {"h3_resolution": cfg.h3_resolution, "n_cells": len(cells)},
        "coverage": {
            "mean_score": float(cells["score"].mean()),
            "share_cells_covered": float(covered.mean()),
            "share_demand_covered": float(cells.loc[covered, "demand"].fillna(0).sum() / max(cells["demand"].fillna(0).sum(), 1e-9)),
            "share_cells_zero_chargers": float((cells["n_within"] == 0).mean()),
            "median_nearest_m": float(cells["nearest_m"].median()),
        },
    }

    cells.to_parquet(out / "cells.parquet")
    ward_summary.to_parquet(out / "wards_scored.parquet")
    stations_m.to_parquet(out / "stations.parquet")
    (out / "build_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def load_artifacts(out_dir: Path | str) -> Artifacts:
    out = Path(out_dir)
    if not (out / "build_meta.json").exists():
        raise FileNotFoundError(f"no build in {out}; run `hydgap build` first")
    return Artifacts(
        cells=gpd.read_parquet(out / "cells.parquet"),
        wards=gpd.read_parquet(out / "wards_scored.parquet"),
        stations=gpd.read_parquet(out / "stations.parquet"),
        meta=json.loads((out / "build_meta.json").read_text(encoding="utf-8")),
    )
