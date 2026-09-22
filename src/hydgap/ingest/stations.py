"""One entry point for the station layer, whatever the source.

`ocm`  the cached OpenChargeMap fetch
`csv`  a CSV you supply (see csvstations.py for the columns)
`both` the two merged; a CSV row within `dedupe_m` of an OCM station is
       treated as the same charger and the OCM row is kept
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from hydgap.config import StationsConfig
from hydgap.ingest.csvstations import load_stations_csv
from hydgap.ingest.ocm import load_stations
from hydgap.spatial.crs import to_metric


def merge_stations(primary: gpd.GeoDataFrame, extra: gpd.GeoDataFrame, dedupe_m: float, crs_metric: str) -> tuple[gpd.GeoDataFrame, int]:
    if len(primary) == 0 or len(extra) == 0:
        return gpd.GeoDataFrame(pd.concat([primary, extra], ignore_index=True), geometry="geometry", crs=primary.crs), 0
    p, e = to_metric(primary, crs_metric), to_metric(extra, crs_metric)
    tree = cKDTree(np.column_stack([p.geometry.x, p.geometry.y]))
    dist, _ = tree.query(np.column_stack([e.geometry.x, e.geometry.y]), k=1)
    keep = extra[dist > dedupe_m]
    merged = gpd.GeoDataFrame(pd.concat([primary, keep], ignore_index=True), geometry="geometry", crs=primary.crs)
    return merged, int((dist <= dedupe_m).sum())


def load_station_layer(cfg: StationsConfig, raw_dir: Path | str, crs_metric: str) -> tuple[gpd.GeoDataFrame, dict]:
    raw = Path(raw_dir)
    meta: dict = {"source": cfg.source}
    if cfg.source in ("ocm", "both"):
        ocm, ocm_report = load_stations(raw / cfg.ocm_file)
        ocm["source"] = "ocm"
        meta["ocm"] = {"file": cfg.ocm_file, **ocm_report.as_dict()}
    if cfg.source in ("csv", "both"):
        path = raw / cfg.csv_file
        if not path.exists():
            raise FileNotFoundError(f"stations.source is {cfg.source} but {path} is missing")
        extra, csv_report = load_stations_csv(path)
        extra["source"] = "csv"
        meta["csv"] = {"file": cfg.csv_file, **csv_report.as_dict()}

    if cfg.source == "ocm":
        stations, dropped = ocm, ocm_report.dropped_no_coords
    elif cfg.source == "csv":
        stations, dropped = extra, csv_report.dropped_no_coords
    else:
        stations, duplicates = merge_stations(ocm, extra, cfg.dedupe_m, crs_metric)
        meta["duplicates_dropped"] = duplicates
        meta["dedupe_m"] = cfg.dedupe_m
        dropped = meta["ocm"]["dropped_no_coords"] + meta["csv"]["dropped_no_coords"]

    meta.update(
        {
            "total": len(stations),
            "kept": len(stations),
            "dropped_no_coords": dropped,
            "unknown_status": int(stations["is_operational"].isna().sum()) if len(stations) else 0,
            "unknown_power": int(stations["max_power_kw"].isna().sum()) if len(stations) else 0,
            "fetched_at": meta.get("ocm", {}).get("fetched_at"),
        }
    )
    return stations, meta
