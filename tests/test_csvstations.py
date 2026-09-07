import shutil

import pytest

from hydgap.config import StationsConfig
from hydgap.ingest.csvstations import load_stations_csv
from hydgap.ingest.stations import load_station_layer, merge_stations
from hydgap.pipeline import STATIONS_CSV, build_artifacts
from tests.test_pipeline import stage_raw


def test_csv_loader_matches_aliases_and_drops_bad_rows(fixtures):
    stations, report = load_stations_csv(fixtures / "stations_tiny.csv")
    assert report.total == 5
    assert report.kept == 3
    assert report.dropped_no_coords == 2
    assert report.unknown_status == 1
    assert stations.crs.to_epsg() == 4326
    row = stations[stations["title"] == "CSV in ward 4"].iloc[0]
    assert row["operator"] == "Alt Op"
    assert row["is_operational"] is False or row["is_operational"] == False
    assert stations["max_power_kw"].isna().sum() == 1


def test_csv_loader_requires_coordinates(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("name,operator\nA,B\n")
    with pytest.raises(ValueError, match="latitude"):
        load_stations_csv(bad)


def test_merge_dedupes_within_radius(fixtures, tiny_config):
    raw = fixtures
    cfg = StationsConfig(source="both", ocm_file="stations_tiny.json", csv_file="stations_tiny.csv", dedupe_m=50)
    stations, meta = load_station_layer(cfg, raw, tiny_config.crs_metric)
    assert meta["source"] == "both"
    assert meta["ocm"]["kept"] == 3
    assert meta["csv"]["kept"] == 3
    assert meta["duplicates_dropped"] == 1
    assert len(stations) == 5
    assert set(stations["source"]) == {"ocm", "csv"}

    far = StationsConfig(source="both", ocm_file="stations_tiny.json", csv_file="stations_tiny.csv", dedupe_m=0)
    stations2, meta2 = load_station_layer(far, raw, tiny_config.crs_metric)
    assert meta2["duplicates_dropped"] == 0 and len(stations2) == 6


def test_merge_handles_empty_sides(fixtures, tiny_config):
    ocm, _ = load_station_layer(StationsConfig(source="ocm", ocm_file="stations_tiny.json"), fixtures, tiny_config.crs_metric)
    merged, dups = merge_stations(ocm, ocm.iloc[0:0], 50, tiny_config.crs_metric)
    assert len(merged) == 3 and dups == 0


def test_pipeline_runs_on_csv_source(fixtures, tiny_config, tmp_path):
    raw = stage_raw(fixtures, tmp_path)
    shutil.copy(fixtures / "stations_tiny.csv", raw / STATIONS_CSV)
    cfg = tiny_config.model_copy(update={"stations": StationsConfig(source="csv")})
    meta = build_artifacts(cfg, raw, tmp_path / "processed")
    assert meta["stations"]["source"] == "csv"
    assert meta["stations"]["kept"] == 3
    assert meta["stations"]["csv"]["dropped_no_coords"] == 2

    both = tiny_config.model_copy(update={"stations": StationsConfig(source="both")})
    meta2 = build_artifacts(both, raw, tmp_path / "processed2")
    assert meta2["stations"]["kept"] == 5


def test_missing_csv_is_a_clear_error(fixtures, tiny_config, tmp_path):
    raw = stage_raw(fixtures, tmp_path)
    cfg = tiny_config.model_copy(update={"stations": StationsConfig(source="csv")})
    with pytest.raises(FileNotFoundError, match="stations.csv"):
        build_artifacts(cfg, raw, tmp_path / "processed")
