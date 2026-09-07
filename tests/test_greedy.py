import numpy as np
from scipy.sparse import csr_matrix

from hydgap.ingest.ocm import load_stations
from hydgap.ingest.wards import load_wards
from hydgap.optimize import GreedySiter, UniformCost, build_problem
from hydgap.optimize.base import SitingProblem
from hydgap.spatial.coverage import score_cells
from hydgap.spatial.crs import to_metric
from hydgap.spatial.demand import assign_demand
from hydgap.spatial.grid import build_hex_grid


def toy(budget=1.0, cost=1.0):
    # five cells in a line, each reaches itself and its immediate neighbours
    n = 5
    rows, cols = [], []
    for i in range(n):
        for j in (i - 1, i, i + 1):
            if 0 <= j < n:
                rows.append(i)
                cols.append(j)
    neighbors = csr_matrix((np.ones(len(rows), dtype=bool), (rows, cols)), shape=(n, n))
    demand = np.array([1.0, 5.0, 1.0, 1.0, 10.0])
    covered0 = np.array([False, False, False, False, True])
    return SitingProblem(
        cell_ids=np.array([f"c{i}" for i in range(n)]),
        demand=demand,
        covered0=covered0,
        neighbors=neighbors,
        costs=np.full(n, cost),
        budget=budget,
        candidates=np.arange(n),
    )


def test_budget_one_picks_the_richest_neighbourhood():
    r = GreedySiter().solve(toy(budget=1))
    assert [s.cell_id for s in r.sites] == ["c1"]
    assert r.sites[0].marginal_gain == 7.0
    assert r.baseline_covered == 10.0
    assert r.covered_after == 17.0
    assert r.spent == 1.0


def test_gains_are_non_increasing_and_budget_stops_it():
    r = GreedySiter().solve(toy(budget=10))
    gains = [s.marginal_gain for s in r.sites]
    assert gains == sorted(gains, reverse=True)
    assert r.covered_after == r.total_demand
    assert len(r.sites) == 2
    assert r.spent == 2.0


def test_cost_two_halves_the_sites():
    r = GreedySiter().solve(toy(budget=2, cost=2))
    assert len(r.sites) == 1
    r2 = GreedySiter().solve(toy(budget=2, cost=1))
    assert len(r2.sites) == 2


def test_problem_from_scored_cells_sites_the_empty_ward(fixtures, tiny_config):
    wards = load_wards(fixtures / "wards_tiny.geojson")
    stations, _ = load_stations(fixtures / "stations_tiny.json")
    cells = build_hex_grid(wards, tiny_config.h3_resolution, tiny_config.crs_metric)
    cells, _ = assign_demand(cells, wards, tiny_config.demand)
    cells = score_cells(cells, to_metric(stations, tiny_config.crs_metric), tiny_config.coverage)

    problem = build_problem(cells, tiny_config, budget=1, cost_model=UniformCost(1.0))
    assert problem.neighbors.shape == (len(cells), len(cells))
    assert problem.neighbors.diagonal().all()
    result = GreedySiter().solve(problem)
    assert len(result.sites) == 1
    ward_of_site = cells.loc[cells["h3"] == result.sites[0].cell_id, "ward_no"].item()
    assert ward_of_site == 4
    assert result.covered_after > result.baseline_covered

    twice = GreedySiter().solve(build_problem(cells, tiny_config, budget=1))
    assert [s.cell_id for s in twice.sites] == [s.cell_id for s in result.sites]
