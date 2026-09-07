from hydgap.ingest.wards import load_wards
from hydgap.spatial.crs import to_metric
from hydgap.spatial.grid import build_hex_grid


def test_grid_covers_wards_and_tags_each_cell(fixtures, tiny_config):
    wards = load_wards(fixtures / "wards_tiny.geojson")
    cells = build_hex_grid(wards, tiny_config.h3_resolution, tiny_config.crs_metric)
    assert len(cells) > 50
    assert cells["ward_no"].notna().all()
    assert set(cells["ward_no"].astype(int)) == {1, 2, 4}
    assert cells["h3"].is_unique

    wards_m = to_metric(wards, tiny_config.crs_metric)
    union = wards_m.geometry.union_all()
    assert cells.geometry.centroid.within(union).all()
    assert abs(cells["area_m2"].sum() - union.area) / union.area < 0.10
