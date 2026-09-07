"""Charging stations from OpenChargeMap.

`fetch_stations` needs an API key and network; it writes the raw response to
disk once. `load_stations` reads that cached file, so every later step is
offline and reproducible.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import httpx
from shapely.geometry import Point

from hydgap.config import BBox
from hydgap.spatial.crs import WGS84

OCM_URL = "https://api.openchargemap.io/v3/poi/"


@dataclass
class StationReport:
    total: int
    kept: int
    dropped_no_coords: int
    unknown_status: int
    unknown_power: int
    fetched_at: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def fetch_stations(bbox: BBox, api_key: str, out_path: Path | str, max_results: int = 2000, url: str = OCM_URL) -> int:
    if not api_key:
        raise ValueError("OpenChargeMap requires an API key (set OCM_API_KEY)")
    params = {
        "output": "json",
        "boundingbox": bbox.as_ocm(),
        "maxresults": max_results,
        "compact": "true",
        "verbose": "false",
    }
    resp = httpx.get(url, params=params, headers={"X-API-Key": api_key, "User-Agent": "hydgap/0.1"}, timeout=60)
    resp.raise_for_status()
    pois = resp.json()
    payload = {
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": url,
        "bbox": bbox.model_dump(),
        "count": len(pois),
        "pois": pois,
    }
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return len(pois)


def _operational(poi: dict) -> bool | None:
    status = poi.get("StatusType") or {}
    if "IsOperational" in status and status["IsOperational"] is not None:
        return bool(status["IsOperational"])
    return None


def _max_power(poi: dict) -> float | None:
    powers = [c.get("PowerKW") for c in poi.get("Connections") or [] if c.get("PowerKW") is not None]
    return max(powers) if powers else None


def load_stations(path: Path | str) -> tuple[gpd.GeoDataFrame, StationReport]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    fetched_at = None
    pois = data
    if isinstance(data, dict):
        pois = data.get("pois", [])
        fetched_at = data.get("fetched_at")

    rows, dropped = [], 0
    for poi in pois:
        addr = poi.get("AddressInfo") or {}
        lat, lon = addr.get("Latitude"), addr.get("Longitude")
        if lat is None or lon is None:
            dropped += 1
            continue
        rows.append(
            {
                "ocm_id": poi.get("ID"),
                "title": addr.get("Title"),
                "operator": (poi.get("OperatorInfo") or {}).get("Title"),
                "n_connections": len(poi.get("Connections") or []),
                "max_power_kw": _max_power(poi),
                "is_operational": _operational(poi),
                "geometry": Point(float(lon), float(lat)),
            }
        )
    stations = gpd.GeoDataFrame(rows, geometry="geometry", crs=WGS84) if rows else gpd.GeoDataFrame(
        columns=["ocm_id", "title", "operator", "n_connections", "max_power_kw", "is_operational", "geometry"],
        geometry="geometry",
        crs=WGS84,
    )
    report = StationReport(
        total=len(pois),
        kept=len(stations),
        dropped_no_coords=dropped,
        unknown_status=int(stations["is_operational"].isna().sum()) if len(stations) else 0,
        unknown_power=int(stations["max_power_kw"].isna().sum()) if len(stations) else 0,
        fetched_at=fetched_at,
    )
    return stations, report
