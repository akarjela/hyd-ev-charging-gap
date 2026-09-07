"""Optional ward population from the Census 2011 CSV on data.opencity.in.

The file covers Hyderabad district only, so many GHMC wards have no row. A
ward without population keeps NaN; nothing is estimated or filled.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

GHMC_MARK = "GHMC"


def load_population(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    needed = {"Ward", "VName", "TOT_P"}
    if not needed.issubset(df.columns):
        raise ValueError(f"population csv needs columns {sorted(needed)}")
    if "Level1" in df.columns:
        df = df[df["Level1"].str.upper() == "WARD"]
    df = df[df["VName"].str.contains(GHMC_MARK, na=False)]
    out = pd.DataFrame(
        {
            "ward_no": pd.to_numeric(df["Ward"], errors="coerce").astype("Int64"),
            "population": pd.to_numeric(df["TOT_P"], errors="coerce"),
            "census_name": df["VName"].str.strip(),
        }
    ).dropna(subset=["ward_no", "population"])
    return out.drop_duplicates("ward_no").reset_index(drop=True)


def join_population(wards: gpd.GeoDataFrame, pop: pd.DataFrame) -> tuple[gpd.GeoDataFrame, list[int]]:
    joined = wards.merge(pop[["ward_no", "population"]], on="ward_no", how="left")
    joined = gpd.GeoDataFrame(joined, geometry="geometry", crs=wards.crs)
    unmatched = joined.loc[joined["population"].isna() & joined["ward_no"].notna(), "ward_no"].astype(int).tolist()
    return joined, sorted(unmatched)
