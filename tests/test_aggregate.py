from hydgap.ingest.ocm import load_stations
from hydgap.ingest.wards import load_wards
from hydgap.spatial.aggregate import aggregate_wards
from hydgap.spatial.coverage import score_cells
from hydgap.spatial.crs import to_metric
from hydgap.spatial.demand import assign_demand
from hydgap.spatial.grid import build_hex_grid


def test_ward_without_chargers_ranks_worst(fixtures, tiny_config):
    wards = load_wards(fixtures / "wards_tiny.geojson")
    stations, _ = load_stations(fixtures / "stations_tiny.json")
    cells = build_hex_grid(wards, tiny_config.h3_resolution, tiny_config.crs_metric)
    cells, _ = assign_demand(cells, wards, tiny_config.demand)
    cells = score_cells(cells, to_metric(stations, tiny_config.crs_metric), tiny_config.coverage)
    summary = aggregate_wards(cells, to_metric(wards, tiny_config.crs_metric), tiny_config)

    assert summary["rank"].tolist() == [1, 2, 3]
    assert summary.iloc[0]["ward_no"] == 4
    assert summary.iloc[0]["share_uncovered"] == 1.0
    assert summary.iloc[-1]["ward_no"] == 1
    assert summary["n_cells"].sum() == len(cells)
