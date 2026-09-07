"""An H3 hexagon grid over the ward union, in the metric CRS."""

from __future__ import annotations

import geopandas as gpd
import h3
from shapely.geometry import Polygon

from hydgap.spatial.crs import WGS84, to_metric


def cell_polygon(cell: str) -> Polygon:
    boundary = h3.cell_to_boundary(cell)
    return Polygon([(lng, lat) for lat, lng in boundary])


def build_hex_grid(wards: gpd.GeoDataFrame, resolution: int, crs_metric: str) -> gpd.GeoDataFrame:
    """Cells whose centre lies inside any ward, tagged with that ward by centroid.

    Returns a GeoDataFrame in `crs_metric` with columns h3, ward_no, area_m2, geometry.
    """
    wards_wgs = wards if wards.crs is not None and wards.crs.is_geographic else wards.to_crs(WGS84)
    union = wards_wgs.geometry.union_all()
    cells = sorted(h3.geo_to_cells(union, resolution))
    grid = gpd.GeoDataFrame({"h3": cells}, geometry=[cell_polygon(c) for c in cells], crs=WGS84)
    grid_m = to_metric(grid, crs_metric)
    wards_m = to_metric(wards_wgs[["ward_no", "geometry"]], crs_metric)

    centroids = gpd.GeoDataFrame({"h3": grid_m["h3"]}, geometry=grid_m.geometry.centroid, crs=crs_metric)
    tagged = gpd.sjoin(centroids, wards_m, how="inner", predicate="within")
    tagged = tagged.drop_duplicates("h3")[["h3", "ward_no"]]

    grid_m = grid_m.merge(tagged, on="h3", how="inner")
    grid_m["area_m2"] = grid_m.geometry.area
    return grid_m[["h3", "ward_no", "area_m2", "geometry"]].reset_index(drop=True)
