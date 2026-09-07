import math

from hydgap.config import DemandConfig
from hydgap.ingest.population import join_population, load_population
from hydgap.ingest.wards import load_wards
from hydgap.spatial.demand import assign_demand
from hydgap.spatial.grid import build_hex_grid


def _cells(fixtures, cfg):
    wards = load_wards(fixtures / "wards_tiny.geojson")
    wards, _ = join_population(wards, load_population(fixtures / "population_tiny.csv"))
    return wards, build_hex_grid(wards, cfg.h3_resolution, cfg.crs_metric)


def test_uniform_demand_is_area_in_km2(fixtures, tiny_config):
    _, cells = _cells(fixtures, tiny_config)
    out, report = assign_demand(cells, None, DemandConfig(mode="uniform"))
    assert math.isclose(out["demand"].sum(), cells["area_m2"].sum() / 1e6)
    assert report.mode == "uniform"
    assert report.excluded_wards == []


def test_population_demand_splits_by_area_and_excludes_unmatched(fixtures, tiny_config):
    wards, cells = _cells(fixtures, tiny_config)
    out, report = assign_demand(cells, wards, DemandConfig(mode="population"))
    by_ward = out.groupby("ward_no")["demand"].sum()
    assert math.isclose(by_ward[1], 30000)
    assert math.isclose(by_ward[2], 20000)
    assert out.loc[out["ward_no"] == 4, "demand"].isna().all()
    assert report.excluded_wards == [4]
    assert report.excluded_cells == int((out["ward_no"] == 4).sum())
    assert math.isclose(report.total_demand, 50000)
