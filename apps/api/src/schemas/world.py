"""World-pack file format (snake_case, as in CLAUDE.md §9) and the API's world-state response."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .base import CamelModel
from .provenance import Provenance
from .zone import Zone


class ScaleSpec(BaseModel):
    method: Literal["scale_to_peak"]
    target_peak_mw: float = Field(gt=0)
    note: str


class HistoricalLoadSpec(BaseModel):
    dataset_id: str
    source_name: str
    source_url: str
    raw_files: list[str]
    column: str
    years: list[int]
    source_timezone: str
    source_timezone_verified: bool
    scale: ScaleSpec
    provenance: Literal["derived"]  # observed shape, scaled -> derived, never "observed Waterloo demand"


class CapacitySpec(BaseModel):
    value_mw: float = Field(gt=0)
    provenance: Literal["observed", "modeled", "user_assumption"]
    source_note: str


class FixtureSpec(BaseModel):
    file: str
    days: int
    anchor: str


class WorldPack(BaseModel):
    id: str
    name: str
    label: str
    timezone: str
    historical_load: HistoricalLoadSpec
    capacity: CapacitySpec
    der_seed: int
    der_assumptions: dict[str, float]
    fixture: FixtureSpec


class LoadSummary(CamelModel):
    hours: int
    start: str
    end: str
    peak_mw: float
    peak_timestamp: str
    mean_mw: float
    min_mw: float
    load_factor: float
    headroom_at_peak_mw: float
    hours_above_capacity: int
    interpolated_hours: int


class WorldState(CamelModel):
    """Phase 1 world state: zone + baseline summary + provenance. Projects/agents arrive later."""
    id: str
    name: str
    label: str
    mode: Literal["full", "fixture"]
    zone: Zone
    load_summary: LoadSummary
    provenance: dict[str, Provenance]
    der_assumptions: dict[str, float]


class LoadResponse(CamelModel):
    zone_id: str
    mode: Literal["full", "fixture"]
    resolution: Literal["hourly", "daily"]
    capacity_mw: float
    capacity_provenance: str
    provenance: Provenance
    points: list["HistoricalLoadPointT"]
    truncated: bool = False


from .zone import HistoricalLoadPoint as HistoricalLoadPointT  # noqa: E402

LoadResponse.model_rebuild()
