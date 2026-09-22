"""The siting problem and the interface every solver implements.

A cell is *covered* when its coverage score is at or above the configured
threshold. Placing a station at a candidate cell covers every cell within
the service radius of it. The objective is newly covered demand: binary
maximal covering, the same formulation an ILP would use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import geopandas as gpd
import numpy as np
from scipy.sparse import csr_matrix

from hydgap.config import ModelConfig
from hydgap.spatial.network import Reachability, StraightLineReachability, xy


class CostModel(Protocol):
    def cost(self, cell_ids: np.ndarray) -> np.ndarray:
        """Cost of a station at each candidate cell, same order as cell_ids."""


@dataclass
class UniformCost:
    per_site: float = 1.0

    def cost(self, cell_ids: np.ndarray) -> np.ndarray:
        return np.full(len(cell_ids), float(self.per_site))


@dataclass
class SitingProblem:
    cell_ids: np.ndarray
    demand: np.ndarray
    covered0: np.ndarray
    neighbors: csr_matrix
    costs: np.ndarray
    budget: float
    candidates: np.ndarray

    @property
    def n(self) -> int:
        return len(self.cell_ids)


@dataclass
class SiteChoice:
    order: int
    cell_id: str
    marginal_gain: float
    cumulative_gain: float
    cost: float
    spent: float


@dataclass
class SitingResult:
    sites: list[SiteChoice] = field(default_factory=list)
    baseline_covered: float = 0.0
    total_demand: float = 0.0
    total_gain: float = 0.0
    spent: float = 0.0

    @property
    def covered_after(self) -> float:
        return self.baseline_covered + self.total_gain


class Siter(Protocol):
    def solve(self, problem: SitingProblem) -> SitingResult: ...


def build_problem(
    cells: gpd.GeoDataFrame,
    cfg: ModelConfig,
    budget: float,
    cost_model: CostModel | None = None,
    reach: Reachability | None = None,
    radius_m: float | None = None,
) -> SitingProblem:
    """Cells must be scored (score column) and in the metric CRS."""
    reach = reach or StraightLineReachability()
    cost_model = cost_model or UniformCost(cfg.optimizer.site_cost)
    radius = radius_m or cfg.coverage.service_radius_m
    ids = cells["h3"].to_numpy()
    demand = np.nan_to_num(cells["demand"].to_numpy(dtype=float), nan=0.0)
    covered0 = cells["score"].to_numpy(dtype=float) >= cfg.optimizer.coverage_threshold
    pts = xy(cells)
    neighbors = reach.within(pts, pts, radius).tocsr()
    candidates = np.arange(len(ids)) if cfg.optimizer.candidate_pool == "all" else np.flatnonzero(~covered0)
    return SitingProblem(
        cell_ids=ids,
        demand=demand,
        covered0=covered0,
        neighbors=neighbors,
        costs=cost_model.cost(ids),
        budget=float(budget),
        candidates=candidates,
    )
