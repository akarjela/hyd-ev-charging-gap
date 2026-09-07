"""Cells rolled up to wards, ranked worst first."""

from __future__ import annotations

import geopandas as gpd
import numpy as np

from hydgap.config import ModelConfig


def aggregate_wards(cells: gpd.GeoDataFrame, wards: gpd.GeoDataFrame, cfg: ModelConfig) -> gpd.GeoDataFrame:
    threshold = cfg.optimizer.coverage_threshold
    c = cells.copy()
    c["demand"] = c["demand"].fillna(0.0)
    c["uncovered"] = c["score"] < threshold
    c["uncovered_demand"] = c["demand"] * c["uncovered"]
    c["zero_chargers"] = c["n_within"] == 0

    g = c.groupby("ward_no")
    summary = g.agg(
        n_cells=("h3", "size"),
        demand=("demand", "sum"),
        uncovered_demand=("uncovered_demand", "sum"),
        share_uncovered=("uncovered", "mean"),
        share_zero_chargers=("zero_chargers", "mean"),
        nearest_m_median=("nearest_m", "median"),
    )
    weighted = g.apply(lambda x: np.average(x["score"], weights=x["demand"]) if x["demand"].sum() > 0 else x["score"].mean())
    summary["mean_score"] = weighted
    summary = summary.reset_index()

    keep = [col for col in ("ward_no", "ward_name", "population", "geometry") if col in wards.columns]
    out = wards[keep].merge(summary, on="ward_no", how="left")
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=wards.crs)
    out = out.sort_values(["uncovered_demand", "mean_score"], ascending=[False, True], na_position="last")
    out["rank"] = np.arange(1, len(out) + 1)
    return out.reset_index(drop=True)
