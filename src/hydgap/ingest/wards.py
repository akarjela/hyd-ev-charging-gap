"""GHMC ward boundaries from the datameet / OpenStreetMap GeoJSON."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import geopandas as gpd

from hydgap.spatial.crs import WGS84

WARD_NAME = re.compile(r"^\s*Ward\s+(\d+)\s*(.*?)\s*$", re.IGNORECASE)


@dataclass
class WardGapReport:
    expected: int
    found: int
    missing: list[int] = field(default_factory=list)
    duplicates: list[int] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def parse_ward_name(name: str | None) -> tuple[int | None, str]:
    if not name:
        return None, ""
    m = WARD_NAME.match(name)
    if not m:
        return None, name.strip()
    return int(m.group(1)), m.group(2)


def load_wards(path: Path | str) -> gpd.GeoDataFrame:
    raw = gpd.read_file(path)
    if raw.crs is None:
        raw = raw.set_crs(WGS84)
    parsed = [parse_ward_name(n) for n in raw.get("name", [None] * len(raw))]
    wards = gpd.GeoDataFrame(
        {
            "ward_no": [p[0] for p in parsed],
            "ward_name": [p[1] for p in parsed],
            "source_name": list(raw.get("name", [""] * len(raw))),
        },
        geometry=raw.geometry.values,
        crs=raw.crs,
    )
    wards["ward_no"] = wards["ward_no"].astype("Int64")
    return wards.sort_values("ward_no", na_position="last").reset_index(drop=True)


def report_ward_gaps(wards: gpd.GeoDataFrame, expected: int) -> WardGapReport:
    numbers = wards["ward_no"].dropna().astype(int).tolist()
    present = set(numbers)
    missing = [n for n in range(1, expected + 1) if n not in present]
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    unparsed = wards.loc[wards["ward_no"].isna(), "source_name"].astype(str).tolist()
    return WardGapReport(expected=expected, found=len(present), missing=missing, duplicates=duplicates, unparsed=unparsed)
