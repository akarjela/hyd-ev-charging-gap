"""Model configuration: one YAML file holds every threshold and weight."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "model.yaml"


class BBox(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def as_ocm(self) -> str:
        return f"({self.min_lat},{self.min_lon}),({self.max_lat},{self.max_lon})"


class CoverageConfig(BaseModel):
    service_radius_m: float = Field(2000, gt=0)
    target_chargers: int = Field(2, ge=1)
    distance_decay_m: float = Field(1500, gt=0)
    w_count: float = Field(0.6, ge=0)
    w_distance: float = Field(0.4, ge=0)
    require_operational: bool = False

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> CoverageConfig:
        if abs(self.w_count + self.w_distance - 1.0) > 1e-9:
            raise ValueError("coverage weights must sum to 1")
        return self


class DemandConfig(BaseModel):
    mode: Literal["uniform", "population"] = "uniform"


class OptimizerConfig(BaseModel):
    method: Literal["greedy"] = "greedy"
    site_cost: float = Field(1.0, gt=0)
    default_budget: float = Field(10, gt=0)
    candidate_pool: Literal["all", "uncovered"] = "all"
    coverage_threshold: float = Field(0.5, ge=0, le=1)


class StationsConfig(BaseModel):
    source: Literal["ocm", "csv", "both"] = "ocm"
    ocm_file: str = "ocm_stations.json"
    csv_file: str = "stations.csv"
    dedupe_m: float = Field(50, ge=0)


class Sources(BaseModel):
    wards_url: str = ""
    ocm_url: str = ""
    population_url: str = ""


class ModelConfig(BaseModel):
    crs_metric: str = "EPSG:32644"
    h3_resolution: int = Field(8, ge=5, le=11)
    bbox: BBox
    coverage: CoverageConfig = CoverageConfig()
    demand: DemandConfig = DemandConfig()
    optimizer: OptimizerConfig = OptimizerConfig()
    stations: StationsConfig = StationsConfig()
    expected_wards: int = Field(150, ge=1)
    sources: Sources = Sources()


def load_config(path: Path | str | None = None) -> ModelConfig:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        return ModelConfig.model_validate(yaml.safe_load(f))


def config_hash(cfg: ModelConfig) -> str:
    payload = json.dumps(cfg.model_dump(), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:12]
