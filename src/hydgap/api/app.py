"""FastAPI: the built layers as GeoJSON, ward ranking, and the optimizer on demand."""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from hydgap.api.schemas import OptimizeOut, SiteOut
from hydgap.config import DEFAULT_CONFIG, PROJECT_ROOT, ModelConfig, load_config
from hydgap.optimize import SOLVERS, UniformCost, build_problem
from hydgap.pipeline import Artifacts, load_artifacts
from hydgap.spatial.crs import to_wgs84

STATIC = Path(__file__).parent / "static"


def feature_collection(gdf: gpd.GeoDataFrame, columns: list[str]) -> dict:
    keep = [c for c in columns if c in gdf.columns]
    wgs = to_wgs84(gdf[keep + ["geometry"]])
    props = wgs[keep].astype(object).where(pd.notna(wgs[keep]), None)
    wgs = gpd.GeoDataFrame(props, geometry=wgs.geometry, crs=wgs.crs)
    return json.loads(wgs.to_json(drop_id=True))


def create_app(processed: Path | str | None = None, config: Path | str | None = None) -> FastAPI:
    processed_dir = Path(processed or os.environ.get("HYDGAP_PROCESSED") or PROJECT_ROOT / "data" / "processed")
    config_path = Path(config or os.environ.get("HYDGAP_CONFIG") or DEFAULT_CONFIG)
    state: dict = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state["cfg"] = load_config(config_path)
        state["art"] = load_artifacts(processed_dir)
        state["cells_geojson"] = feature_collection(
            state["art"].cells, ["h3", "ward_no", "score", "nearest_m", "n_within", "demand", "area_m2"]
        )
        state["wards_geojson"] = feature_collection(
            state["art"].wards,
            ["ward_no", "ward_name", "population", "rank", "mean_score", "share_uncovered", "share_zero_chargers",
             "uncovered_demand", "demand", "n_cells", "nearest_m_median"],
        )
        state["stations_geojson"] = feature_collection(
            state["art"].stations, ["ocm_id", "title", "operator", "n_connections", "max_power_kw", "is_operational"]
        )
        state["optimize"] = _make_optimizer(state["art"], state["cfg"])
        yield
        state.clear()

    app = FastAPI(title="hydgap", lifespan=lifespan)

    def art() -> Artifacts:
        if "art" not in state:
            raise HTTPException(503, "artifacts not loaded")
        return state["art"]

    @app.get("/api/meta")
    def meta() -> dict:
        return art().meta

    @app.get("/api/cells")
    def cells() -> dict:
        art()
        return state["cells_geojson"]

    @app.get("/api/wards")
    def wards() -> dict:
        art()
        return state["wards_geojson"]

    @app.get("/api/wards/ranking")
    def ranking(limit: int = Query(20, ge=1, le=500)) -> list[dict]:
        w = art().wards.drop(columns="geometry").head(limit)
        return json.loads(w.to_json(orient="records"))

    @app.get("/api/stations")
    def stations() -> dict:
        art()
        return state["stations_geojson"]

    @app.get("/api/optimize", response_model=OptimizeOut)
    def optimize(
        budget: float = Query(None, gt=0),
        site_cost: float = Query(None, gt=0),
        radius_m: float = Query(None, gt=0),
    ) -> OptimizeOut:
        art()
        cfg: ModelConfig = state["cfg"]
        b = budget if budget is not None else cfg.optimizer.default_budget
        c = site_cost if site_cost is not None else cfg.optimizer.site_cost
        r = radius_m if radius_m is not None else cfg.coverage.service_radius_m
        return state["optimize"](b, c, r)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def _make_optimizer(art: Artifacts, cfg: ModelConfig):
    centroids = to_wgs84(gpd.GeoDataFrame(geometry=art.cells.geometry.centroid, crs=art.cells.crs))
    lat = dict(zip(art.cells["h3"], centroids.geometry.y))
    lon = dict(zip(art.cells["h3"], centroids.geometry.x))
    ward = dict(zip(art.cells["h3"], art.cells["ward_no"]))

    @lru_cache(maxsize=256)
    def run(budget: float, site_cost: float, radius_m: float) -> OptimizeOut:
        problem = build_problem(art.cells, cfg, budget, UniformCost(site_cost), radius_m=radius_m)
        result = SOLVERS[cfg.optimizer.method]().solve(problem)
        sites = [
            SiteOut(
                order=s.order,
                cell_id=s.cell_id,
                ward_no=None if pd.isna(ward[s.cell_id]) else int(ward[s.cell_id]),
                marginal_gain=s.marginal_gain,
                cumulative_gain=s.cumulative_gain,
                cost=s.cost,
                spent=s.spent,
                lat=float(lat[s.cell_id]),
                lon=float(lon[s.cell_id]),
            )
            for s in result.sites
        ]
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                    "properties": s.model_dump(exclude={"lat", "lon"}),
                }
                for s in sites
            ],
        }
        return OptimizeOut(
            budget=budget,
            site_cost=site_cost,
            radius_m=radius_m,
            total_demand=result.total_demand,
            baseline_covered=result.baseline_covered,
            covered_after=result.covered_after,
            spent=result.spent,
            sites=sites,
            sites_geojson=geojson,
        )

    return run


app = create_app()
