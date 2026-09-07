import pytest
from fastapi.testclient import TestClient

from hydgap.api.app import create_app
from hydgap.pipeline import build_artifacts
from tests.test_pipeline import stage_raw


@pytest.fixture
def client(fixtures, tiny_config, tmp_path):
    raw = stage_raw(fixtures, tmp_path)
    processed = tmp_path / "processed"
    build_artifacts(tiny_config, raw, processed)
    app = create_app(processed, fixtures / "model_tiny.yaml")
    with TestClient(app) as c:
        yield c


def _is_fc(body):
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 0
    return body["features"]


def test_layers_are_geojson(client):
    cells = _is_fc(client.get("/api/cells").json())
    assert {"h3", "score", "ward_no", "demand"} <= set(cells[0]["properties"])
    wards = _is_fc(client.get("/api/wards").json())
    assert len(wards) == 3
    props = {w["properties"]["ward_no"]: w["properties"] for w in wards}
    assert props[4]["population"] is None
    assert props[4]["rank"] == 1
    stations = _is_fc(client.get("/api/stations").json())
    assert len(stations) == 3
    assert stations[0]["geometry"]["type"] == "Point"


def test_ranking_and_meta(client):
    rows = client.get("/api/wards/ranking?limit=2").json()
    assert [r["rank"] for r in rows] == [1, 2]
    meta = client.get("/api/meta").json()
    assert meta["wards"]["missing"] == [3]
    assert meta["population"]["unmatched"] == [4]


def test_optimize_returns_sites_and_curve(client):
    r = client.get("/api/optimize?budget=3&site_cost=1").json()
    assert len(r["sites"]) == 3
    gains = [s["marginal_gain"] for s in r["sites"]]
    assert gains == sorted(gains, reverse=True)
    assert r["sites"][0]["ward_no"] == 4
    assert r["covered_after"] > r["baseline_covered"]
    assert len(r["sites_geojson"]["features"]) == 3
    assert r["sites"][-1]["cumulative_gain"] == pytest.approx(sum(gains))
    again = client.get("/api/optimize?budget=3&site_cost=1").json()
    assert again == r


def test_index_served(client):
    html = client.get("/").text
    assert "<title>" in html and "leaflet" in html.lower()
