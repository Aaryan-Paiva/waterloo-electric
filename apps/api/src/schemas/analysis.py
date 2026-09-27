from typing import Literal, Optional

from .base import CamelModel
from .provenance import Provenance


class EventWindow(CamelModel):
    """A run of consecutive constrained hours. `end` is exclusive."""
    id: str
    start: str
    end: str
    hours: int
    peak_deficit_mw: float
    peak_timestamp: str
    mean_deficit_mw: float
    energy_over_mwh: float
    days: int


class YearCount(CamelModel):
    constrained_hours: int
    affected_days: int


class CapacityAnalysis(CamelModel):
    """Pre-flexibility capacity screening of a scenario over the whole historical series (CLAUDE.md §17, §20.1, §38).
    Phase 2 has no DER dispatch, so these are the 'before flexibility' numbers."""
    scenario_id: str
    zone_id: str
    mode: Literal["full", "fixture"]
    historical_start: str
    historical_end: str
    hours_tested: int
    capacity_mw: float
    capacity_provenance: str
    baseline_peak_mw: float
    baseline_peak_timestamp: str
    projected_peak_mw: float
    projected_peak_timestamp: str
    min_headroom_mw: float
    constrained_hours: int          # = violationsBefore
    percent_within_capacity: float  # never "reliability"
    affected_days: int
    worst_deficit_mw: float
    worst_deficit_timestamp: Optional[str] = None
    window_count: int
    windows: list[EventWindow]
    by_year: dict[str, YearCount]
    feasibility: Literal["feasible_as_is", "constraints_detected"]
    flexibility_evaluated: bool = False
    provenance: dict[str, Provenance]
    note: str


class EventsResponse(CamelModel):
    scenario_id: str
    total: int
    offset: int
    limit: int
    order: Literal["chronological", "deficit"]
    events: list["CapacityEventT"]


class ScenarioLoadPoint(CamelModel):
    timestamp: str
    baseline_load_mw: float      # hourly: baseline; daily: daily peak of baseline
    project_load_mw: float       # hourly: project increment; daily: daily mean
    net_load_mw: float           # hourly: net; daily: daily peak of net
    deficit_mw: float
    constrained_hours: Optional[int] = None  # daily only
    quality_flag: Optional[str] = None


class ScenarioLoadResponse(CamelModel):
    scenario_id: str
    zone_id: str
    mode: Literal["full", "fixture"]
    resolution: Literal["hourly", "daily"]
    capacity_mw: float
    capacity_provenance: str
    points: list[ScenarioLoadPoint]
    truncated: bool = False


from .events import CapacityEvent as CapacityEventT  # noqa: E402

EventsResponse.model_rebuild()
