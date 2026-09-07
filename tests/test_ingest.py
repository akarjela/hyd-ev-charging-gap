import math

from hydgap.config import config_hash, load_config
from hydgap.ingest.ocm import load_stations
from hydgap.ingest.population import join_population, load_population
from hydgap.ingest.wards import load_wards, parse_ward_name, report_ward_gaps


def test_config_loads_and_hashes(tiny_config):
    assert tiny_config.coverage.service_radius_m == 2000
    assert len(config_hash(tiny_config)) == 12
    assert config_hash(tiny_config) == config_hash(load_config(__import__("tests.conftest", fromlist=["FIXTURES"]).FIXTURES / "model_tiny.yaml"))


def test_ward_name_parses():
    assert parse_ward_name("Ward 91 Khairatabad") == (91, "Khairatabad")
    assert parse_ward_name("Ward 7") == (7, "")
    assert parse_ward_name("Somewhere") == (None, "Somewhere")


def test_wards_load_sorted_with_gap_report(fixtures):
    wards = load_wards(fixtures / "wards_tiny.geojson")
    assert wards["ward_no"].tolist() == [1, 2, 4]
    assert wards.crs.to_epsg() == 4326
    report = report_ward_gaps(wards, expected=4)
    assert report.found == 3
    assert report.missing == [3]
    assert report.duplicates == []
    assert report.unparsed == []


def test_population_join_reports_unmatched(fixtures):
    wards = load_wards(fixtures / "wards_tiny.geojson")
    pop = load_population(fixtures / "population_tiny.csv")
    assert pop["ward_no"].tolist() == [1, 2]
    joined, unmatched = join_population(wards, pop)
    assert unmatched == [4]
    assert joined.loc[joined["ward_no"] == 1, "population"].item() == 30000
    assert math.isnan(joined.loc[joined["ward_no"] == 4, "population"].item())


def test_stations_drop_missing_coords_and_count_unknowns(fixtures):
    stations, report = load_stations(fixtures / "stations_tiny.json")
    assert report.total == 4
    assert report.kept == 3
    assert report.dropped_no_coords == 1
    assert report.unknown_status == 1
    assert report.unknown_power == 1
    assert report.fetched_at.startswith("2026")
    assert stations.crs.to_epsg() == 4326
    assert stations.loc[stations["ocm_id"] == 1, "max_power_kw"].item() == 7.4
