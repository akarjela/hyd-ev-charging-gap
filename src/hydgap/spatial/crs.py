"""Reprojection helpers. All distance and area maths happens in a metric CRS."""

from __future__ import annotations

import geopandas as gpd

WGS84 = "EPSG:4326"
METRIC_CRS = "EPSG:32644"


def to_metric(gdf: gpd.GeoDataFrame, crs: str = METRIC_CRS) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs(WGS84)
    return gdf.to_crs(crs)


def to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.to_crs(WGS84)


def assert_metric(gdf: gpd.GeoDataFrame) -> None:
    if gdf.crs is None or gdf.crs.is_geographic:
        raise ValueError("expected a projected (metric) CRS; reproject with to_metric() first")
