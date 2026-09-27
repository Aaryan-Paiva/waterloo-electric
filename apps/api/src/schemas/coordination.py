from typing import Literal, Optional

from pydantic import Field

from .base import CamelModel

Status = Literal["resolved", "partially_resolved", "unresolved"]


class CoordinationRequest(CamelModel):
    window_id: Optional[str] = None       # an EventWindow id from the scenario analysis
    start: Optional[str] = None           # or an explicit window [start, end)
    end: Optional[str] = None
    tail_hours: int = Field(default=8, ge=0, le=12)   # recovery horizon after the window (EV deadlines, building rebound, battery recharge)


class HourRow(CamelModel):
    timestamp: str
    in_window: bool
    baseline_load_mw: float
    project_load_mw: float
    pre_dispatch_net_mw: float
    battery_reduction_mw: float
    ev_reduction_mw: float
    building_reduction_mw: float
    total_reduction_mw: float
    optimized_net_mw: float
    capacity_mw: float
    pre_deficit_mw: float
    remaining_deficit_mw: float
    violation_before: bool
    violation_after: bool
    solar_informational_mw: float         # already inside the baseline; never used by the optimizer


class AgentDispatch(CamelModel):
    agent_id: str
    type: Literal["battery", "ev_fleet", "building"]
    name: str
    participating: bool
    included: bool
    excluded_reason: Optional[str] = None
    dispatch_mw: list[float]              # reduction of net load per horizon hour (+ lowers load)
    mode: list[str]                       # discharging | charging | deferring | recovering | shedding | rebound | idle
    peak_mw: float
    energy_mwh: float
    series: dict[str, list[float]]
    provenance: Literal["modeled"] = "modeled"
    owner_id: Optional[str] = None         # agentic mode: the owner/operator agent whose validated offer covers this asset
    price_per_mwh: Optional[float] = None
    delivered_mwh: Optional[float] = None  # delivering energy (discharge / deferral / shed)
    cost: Optional[float] = None


class Check(CamelModel):
    name: str
    passed: bool
    max_violation: float


class WindowMetrics(CamelModel):
    hours: int
    violation_hours_before: int
    violation_hours_after: int
    energy_above_capacity_before_mwh: float
    energy_above_capacity_after_mwh: float
    worst_deficit_before_mw: float
    worst_deficit_after_mw: float


class CoordinationResult(CamelModel):
    scenario_id: str
    zone_id: str
    provenance: Literal["derived"] = "derived"
    status: Status
    status_reason: str
    window_start: str
    window_end: str                        # exclusive
    horizon_end: str                       # exclusive: window + recovery tail
    tail_hours: int
    capacity_mw: float
    window: WindowMetrics                  # inside the event window
    tail: WindowMetrics                    # recovery tail after the window (rebound/recharge must not create new violations)
    horizon: WindowMetrics
    peak_dispatch_mw: float
    dispatched_energy_mwh: dict[str, float]
    participating_agents: int
    included_agents: int
    hourly: list[HourRow]
    agents: list[AgentDispatch]
    checks: list[Check]
    checks_passed: bool
    reconciled: bool
    solver: dict[str, object]
    participation_rates: dict[str, float]
    objective_weights: dict[str, float]
    note: str
    resources_provenance: Literal["modeled"] = "modeled"
    mode: Literal["manual", "agentic"] = "manual"
    clearing_cost: Optional[float] = None  # agentic mode: sum(price x delivered MWh) [modeled $]
