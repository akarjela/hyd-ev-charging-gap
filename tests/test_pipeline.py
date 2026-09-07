import shutil

from hydgap.pipeline import POPULATION_FILE, STATIONS_FILE, WARDS_FILE, build_artifacts, load_artifacts


def stage_raw(fixtures, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(fixtures / "wards_tiny.geojson", raw / WARDS_FILE)
    shutil.copy(fixtures / "stations_tiny.json", raw / STATIONS_FILE)
    shutil.copy(fixtures / "population_tiny.csv", raw / POPULATION_FILE)
    return raw


def test_build_writes_artifacts_and_gap_meta(fixtures, tiny_config, tmp_path):
    raw = stage_raw(fixtures, tmp_path)
    meta = build_artifacts(tiny_config, raw, tmp_path / "processed")
    assert meta["wards"]["missing"] == [3]
    assert meta["population"]["unmatched"] == [4]
    assert meta["stations"]["dropped_no_coords"] == 1
    assert meta["grid"]["n_cells"] > 50
    assert 0 < meta["coverage"]["share_cells_covered"] < 1

    art = load_artifacts(tmp_path / "processed")
    assert len(art.cells) == meta["grid"]["n_cells"]
    assert art.wards["rank"].tolist() == [1, 2, 3]
    assert art.cells.crs.to_epsg() == 32644
    assert art.meta["config_hash"] == meta["config_hash"]
