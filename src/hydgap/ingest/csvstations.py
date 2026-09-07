"""Charging stations from a plain CSV you supply.

Columns are matched case-insensitively by any of these names:

    name       name, title, station
    latitude   latitude, lat
    longitude  longitude, lon, lng, long
    operator   operator, network            (optional)
    status     status, is_operational       (optional: yes/no, true/false, operational/closed, 1/0)
    power_kw   power_kw, max_power_kw, kw   (optional)
    connections connections, n_connections, ports (optional)

Rows without a usable latitude and longitude are dropped and counted.
Nothing else is inferred.
"""

from __future__ import annotations

import csv
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from hydgap.ingest.ocm import StationReport
from hydgap.spatial.crs import WGS84

ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "title", "station"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lon", "lng", "long"),
    "operator": ("operator", "network"),
    "status": ("status", "is_operational", "operational"),
    "power_kw": ("power_kw", "max_power_kw", "kw"),
    "connections": ("connections", "n_connections", "ports"),
}

TRUE = {"yes", "true", "1", "operational", "open", "active", "y"}
FALSE = {"no", "false", "0", "closed", "inactive", "not operational", "n"}


def _columns(header: list[str]) -> dict[str, str]:
    lower = {h.strip().lower(): h for h in header}
    found: dict[str, str] = {}
    for field, names in ALIASES.items():
        for n in names:
            if n in lower:
                found[field] = lower[n]
                break
    missing = [f for f in ("latitude", "longitude") if f not in found]
    if missing:
        raise ValueError(f"stations csv needs latitude and longitude columns; missing {missing}. Header: {header}")
    return found


def _float(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _status(v: str | None) -> bool | None:
    if v is None:
        return None
    s = v.strip().lower()
    if s in TRUE:
        return True
    if s in FALSE:
        return False
    return None


def load_stations_csv(path: Path | str) -> tuple[gpd.GeoDataFrame, StationReport]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = _columns(reader.fieldnames or [])
        rows, total, dropped = [], 0, 0
        for i, r in enumerate(reader, start=1):
            total += 1
            lat, lon = _float(r.get(cols["latitude"])), _float(r.get(cols["longitude"]))
            if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                dropped += 1
                continue
            def get(k: str, row: dict = r) -> str | None:
                return row.get(cols[k]) if k in cols else None

            conns = _float(get("connections"))
            rows.append(
                {
                    "ocm_id": None,
                    "source_row": i,
                    "title": (get("name") or "").strip() or None,
                    "operator": (get("operator") or "").strip() or None,
                    "n_connections": int(conns) if conns is not None else 0,
                    "max_power_kw": _float(get("power_kw")),
                    "is_operational": _status(get("status")),
                    "geometry": Point(lon, lat),
                }
            )
    columns = ["ocm_id", "source_row", "title", "operator", "n_connections", "max_power_kw", "is_operational", "geometry"]
    stations = gpd.GeoDataFrame(rows, columns=columns, geometry="geometry", crs=WGS84)
    report = StationReport(
        total=total,
        kept=len(stations),
        dropped_no_coords=dropped,
        unknown_status=int(stations["is_operational"].isna().sum()) if len(stations) else 0,
        unknown_power=int(stations["max_power_kw"].isna().sum()) if len(stations) else 0,
        fetched_at=None,
    )
    return stations, report
