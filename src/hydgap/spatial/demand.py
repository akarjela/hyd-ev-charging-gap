"""Demand weight per cell.

uniform:    demand = cell area in km^2.
population: demand = ward population * cell area / ward area, for wards with a
            census row. Wards without one get NaN and are excluded, and the
            exclusion is reported. Nothing is imputed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import geopandas as gpd
import numpy as np

from hydgap.config import DemandConfig


@dataclass
class DemandReport:
    mode: str
    total_demand: float
    excluded_wards: list[int] = field(default_factory=list)
    excluded_cells: int = 0

    def as_dict(self) -> dict:
        return asdict(self)


def assign_demand(cells: gpd.GeoDataFrame, wards: gpd.GeoDataFrame, cfg: DemandConfig) -> tuple[gpd.GeoDataFrame, DemandReport]:
    out = cells.copy()
    if cfg.mode == "uniform":
        out["demand"] = out["area_m2"] / 1e6
        return out, DemandReport(mode="uniform", total_demand=float(out["demand"].sum()))

    if "population" not in wards.columns:
        raise ValueError("population mode needs a 'population' column on wards (run join_population)")
    pop = wards.set_index("ward_no")["population"]
    ward_area = out.groupby("ward_no")["area_m2"].transform("sum")
    ward_pop = out["ward_no"].map(pop).astype(float)
    out["demand"] = ward_pop * out["area_m2"] / ward_area
    excluded = out.loc[out["demand"].isna(), "ward_no"]
    report = DemandReport(
        mode="population",
        total_demand=float(np.nansum(out["demand"].to_numpy())),
        excluded_wards=sorted(int(w) for w in excluded.dropna().unique()),
        excluded_cells=int(out["demand"].isna().sum()),
    )
    return out, report
