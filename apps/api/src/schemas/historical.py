"""Phase 7: historical coordination of every capacity-event window over the full history (deterministic owner policy, 0 LLM calls).
Owner behavior is Modeled; all results are Derived. No project-level feasibility verdict is made here."""
from typing import Literal, Optional

from pydantic import Field

from .base import CamelModel

Status = Literal["resolved", "partially_resolved", "unresolved"]
Severity = Literal["minor", "moderate", "major", "severe"]
Season = Literal["winter", "spring", "summer", "fall"]


class HistoricalRequest(CamelModel):
    incentive_price_per_mwh: float = Field(default=80.0, gt=0, le=1000)
    tail_hours: int = Field(default=8, ge=0, le=12)
    merge_gap_hours: int = Field(default=24, ge=1, le=72)     # windows separated by <= this many hours are simulated jointly (must be >= tail_hours)


class ByType(CamelModel):
    battery: float = 0.0
    ev_fleet: float = 0.0
    building: float = 0.0


class EventResult(CamelModel):
    window_id: str
    cluster_id: str
    start: str
    end: str                               # exclusive
    hours: int
    year: int
    season: Season
    severity: Severity
    status: Status
    requested_peak_mw: float
    requested_mwh: float
    owners_offering: int
    offered_mwh: float                     # owner offers before physical validation (this window's hours)
    validated_mwh: float                   # accepted (physically valid, priced in) offers
    priced_out_mwh: float
    dispatched_mwh: float                  # OR-Tools delivering energy inside the window
    dispatched_peak_mw: float
    clearing_cost: float                   # modeled $
    by_type_mwh: ByType
    violation_hours_before: int
    violation_hours_after: int
    energy_above_capacity_before_mwh: float
    energy_above_capacity_after_mwh: float
    worst_deficit_before_mw: float
    worst_deficit_after_mw: float


class ClusterResult(CamelModel):
    id: str
    window_ids: list[str]
    start: str
    end: str                               # last window end
    horizon_end: str                       # + recovery tail (truncated at the next cluster)
    horizon_hours: int
    carry_in_battery_mwh: float            # battery energy still missing vs. its routine when this cluster starts (carried, NOT reset)
    carry_out_battery_mwh: float
    gap_recovered_mwh: float               # battery energy recovered in the gap before this cluster (limited by inverter and zone headroom)
    owners_accepted: int
    owners_declined: int
    owners_rejected: int
    owners_priced_out: int
    solver_status: str
    checks_passed: bool
    reconciled: bool


class Agg(CamelModel):
    """One aggregation bucket (total, a year, a season, a severity class). Every field is a sum/max of EventResult fields."""
    events: int = 0
    resolved: int = 0
    partially_resolved: int = 0
    unresolved: int = 0
    violation_hours_before: int = 0
    violation_hours_after: int = 0
    energy_above_capacity_before_mwh: float = 0.0
    energy_above_capacity_after_mwh: float = 0.0
    worst_deficit_before_mw: float = 0.0
    worst_deficit_after_mw: float = 0.0
    requested_mwh: float = 0.0
    offered_mwh: float = 0.0
    validated_mwh: float = 0.0
    dispatched_mwh: float = 0.0
    clearing_cost: float = 0.0
    by_type_mwh: ByType = Field(default_factory=ByType)


class DerContribution(CamelModel):
    type: Literal["battery", "ev_fleet", "building"]
    dispatched_mwh: float
    share: float
    events_served: int
    clearing_cost: float


class HourlyRow(CamelModel):
    timestamp: str
    in_window: bool
    pre_net_mw: float
    optimized_net_mw: float
    battery_mw: float
    ev_mw: float
    building_mw: float


class HistCheck(CamelModel):
    name: str
    passed: bool
    detail: str = ""


class HistoricalResult(CamelModel):
    id: str
    scenario_id: str
    zone_id: str
    provenance: Literal["derived"] = "derived"
    owner_behavior_provenance: Literal["modeled"] = "modeled"
    decision_source: Literal["deterministic_owner_policy"] = "deterministic_owner_policy"
    llm_calls: int = 0
    policy_version: str
    incentive_price_per_mwh: float
    tail_hours: int
    merge_gap_hours: int
    capacity_mw: float
    hours_tested: int
    period_start: str
    period_end: str
    totals: Agg
    by_year: dict[str, Agg]
    by_season: dict[str, Agg]
    by_severity: dict[str, Agg]
    by_der_type: list[DerContribution]
    events: list[EventResult]
    clusters: list[ClusterResult]
    hourly: list[HourlyRow]
    checks: list[HistCheck]
    checks_passed: bool
    result_hash: str
    duration_ms: float
    cached: bool = False
    note: str
