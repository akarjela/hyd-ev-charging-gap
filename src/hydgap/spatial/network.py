"""Who can reach whom within a radius.

`StraightLineReachability` is the v1 model: Euclidean distance in the metric
CRS. The extension point for a road network is the `Reachability` protocol:
an OSMnx-backed implementation would build a drive/ride graph for the bbox,
snap origins and targets to nodes, and answer `within` with network distance
(an isochrone), leaving every caller unchanged.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree


class Reachability(Protocol):
    def within(self, origins_xy: np.ndarray, targets_xy: np.ndarray, radius_m: float) -> csr_matrix:
        """Sparse (n_origins x n_targets) boolean matrix: origin i reaches target j within radius."""

    def nearest(self, origins_xy: np.ndarray, targets_xy: np.ndarray) -> np.ndarray:
        """Distance in metres from each origin to its nearest target (inf if there are none)."""


class StraightLineReachability:
    def within(self, origins_xy: np.ndarray, targets_xy: np.ndarray, radius_m: float) -> csr_matrix:
        n, m = len(origins_xy), len(targets_xy)
        if n == 0 or m == 0:
            return csr_matrix((n, m), dtype=bool)
        tree = cKDTree(targets_xy)
        hits = tree.query_ball_point(origins_xy, r=radius_m)
        rows = np.repeat(np.arange(n), [len(h) for h in hits])
        cols = np.concatenate([np.asarray(h, dtype=int) for h in hits]) if len(rows) else np.array([], dtype=int)
        return csr_matrix((np.ones(len(rows), dtype=bool), (rows, cols)), shape=(n, m))

    def nearest(self, origins_xy: np.ndarray, targets_xy: np.ndarray) -> np.ndarray:
        if len(targets_xy) == 0:
            return np.full(len(origins_xy), np.inf)
        dist, _ = cKDTree(targets_xy).query(origins_xy, k=1)
        return np.asarray(dist, dtype=float)


def xy(gdf) -> np.ndarray:
    """Centroid coordinates of a metric GeoDataFrame as an (n, 2) array."""
    c = gdf.geometry.centroid
    return np.column_stack([c.x.to_numpy(), c.y.to_numpy()]) if len(gdf) else np.empty((0, 2))
