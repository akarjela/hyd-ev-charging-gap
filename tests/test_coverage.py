import math

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from hydgap.config import CoverageConfig
from hydgap.ingest.ocm import load_stations
from hydgap.ingest.wards import load_wards
from hydgap.spatial.coverage import coverage_score, score_cells
from hydgap.spatial.crs import to_metric
from hydgap.spatial.grid import build_hex_grid
from hydgap.spatial.network import StraightLineReachability

CFG = CoverageConfig(service_radius_m=2000, target_chargers=2, distance_decay_m=1500, w_count=0.6, w_distance=0.4)


def test_score_formula_and_bounds():
    s = coverage_score(np.array([0, 1, 2, 5]), np.array([5000.0, 1500.0, 0.0, 0.0]), CFG)
    assert math.isclose(s[0], 0.4 * math.exp(-5000 / 1500))
    assert math.isclose(s[1], 0.3 + 0.4 * math.exp(-1))
    assert math.isclose(s[2], 1.0)
    assert math.isclose(s[3], 1.0)
    assert (s >= 0).all() and (s <= 1).all()
    assert s[0] < s[1] < s[2]


def test_hand_computed_distance_in_metres():
    a = gpd.GeoDataFrame(geometry=[Point(78.40, 17.40)], crs="EPSG:4326")
    b = gpd.GeoDataFrame(geometry=[Point(78.40, 17.40 + 0.0271)], crs="EPSG:4326")
    d = StraightLineReachability().nearest(
        np.array([[a.to_crs("EPSG:32644").geometry.x[0], a.to_crs("EPSG:32644").geometry.y[0]]]),
        np.array([[b.to_crs("EPSG:32644").geometry.x[0], b.to_crs("EPSG:32644").geometry.y[0]]]),
    )[0]
    assert abs(d - 2997) < 5


def test_cells_scored_against_fixture_stations(fixtures, tiny_config):
    wards = load_wards(fixtures / "wards_tiny.geojson")
    stations, _ = load_stations(fixtures / "stations_tiny.json")
    cells = build_hex_grid(wards, tiny_config.h3_resolution, tiny_config.crs_metric)
    cells["demand"] = 1.0
    scored = score_cells(cells, to_metric(stations, tiny_config.crs_metric), tiny_config.coverage)

    station_1 = to_metric(stations[stations["ocm_id"] == 1], tiny_config.crs_metric).geometry.iloc[0]
    host = scored[scored.geometry.contains(station_1)]
    assert len(host) == 1
    assert host["nearest_m"].item() < 300
    assert host["n_within"].item() >= 1
    assert host["score"].item() > 0.5

    far = scored[scored["ward_no"] == 4]
    assert (far["n_within"] == 0).all()
    assert (far["nearest_m"] > 2000).all()
    assert (far["score"] < 0.5).all()


def test_require_operational_drops_unknown_status(fixtures, tiny_config):
    wards = load_wards(fixtures / "wards_tiny.geojson")
    stations, _ = load_stations(fixtures / "stations_tiny.json")
    cells = build_hex_grid(wards, tiny_config.h3_resolution, tiny_config.crs_metric)
    strict = CFG.model_copy(update={"require_operational": True})
    lax = score_cells(cells, to_metric(stations, tiny_config.crs_metric), CFG)
    tight = score_cells(cells, to_metric(stations, tiny_config.crs_metric), strict)
    assert tight["n_within"].sum() < lax["n_within"].sum()
