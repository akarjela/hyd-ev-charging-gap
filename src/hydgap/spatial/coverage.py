"""Per-cell coverage: nearest charger, chargers within the service radius, a score in [0, 1]."""

from __future__ import annotations

import geopandas as gpd
import numpy as np

from hydgap.config import CoverageConfig
from hydgap.spatial.crs import assert_metric
from hydgap.spatial.network import Reachability, StraightLineReachability, xy


def coverage_score(n_within: np.ndarray, nearest_m: np.ndarray, cfg: CoverageConfig) -> np.ndarray:
    count_term = np.minimum(1.0, np.asarray(n_within, dtype=float) / cfg.target_chargers)
    distance_term = np.exp(-np.asarray(nearest_m, dtype=float) / cfg.distance_decay_m)
    return cfg.w_count * count_term + cfg.w_distance * distance_term


def usable_stations(stations: gpd.GeoDataFrame, cfg: CoverageConfig) -> gpd.GeoDataFrame:
    if cfg.require_operational and "is_operational" in stations.columns:
        return stations[stations["is_operational"].eq(True)]
    return stations


def score_cells(
    cells: gpd.GeoDataFrame,
    stations: gpd.GeoDataFrame,
    cfg: CoverageConfig,
    reach: Reachability | None = None,
) -> gpd.GeoDataFrame:
    assert_metric(cells)
    assert_metric(stations)
    reach = reach or StraightLineReachability()
    origins = xy(cells)
    targets = xy(usable_stations(stations, cfg))
    out = cells.copy()
    out["nearest_m"] = reach.nearest(origins, targets)
    out["n_within"] = np.asarray(reach.within(origins, targets, cfg.service_radius_m).sum(axis=1)).ravel().astype(int)
    out["score"] = coverage_score(out["n_within"].to_numpy(), out["nearest_m"].to_numpy(), cfg)
    return out
