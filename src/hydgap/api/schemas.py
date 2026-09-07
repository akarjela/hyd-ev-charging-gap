from __future__ import annotations

from pydantic import BaseModel


class SiteOut(BaseModel):
    order: int
    cell_id: str
    ward_no: int | None
    marginal_gain: float
    cumulative_gain: float
    cost: float
    spent: float
    lat: float
    lon: float


class OptimizeOut(BaseModel):
    budget: float
    site_cost: float
    radius_m: float
    total_demand: float
    baseline_covered: float
    covered_after: float
    spent: float
    sites: list[SiteOut]
    sites_geojson: dict
