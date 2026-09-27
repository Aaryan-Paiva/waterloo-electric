"""Waterloo Electric sandbox API (thin layer over the agentic pipeline). Results are Derived; devices/owners Modeled; the data centre Hypothetical."""
from typing import Literal, Optional

from pydantic import Field

from .base import CamelModel

Season = Literal["winter", "spring", "summer", "fall"]
Group = Literal["battery", "ev", "building"]
Outcome = Literal["holds", "partly_holds", "breaks", "no_overload"]


LoadKind = Literal["data_centre", "housing", "ev_depot"]


class LoadSpec(CamelModel):
    kind: LoadKind = "data_centre"
    size: float = Field(default=20, gt=0, le=100000)        # MW (data centre), homes (housing), chargers (EV depot)
    lot: Optional[int] = None                                 # where it stands on the map (UI only)


class DeviceParams(CamelModel):
    """Concrete, editable device behavior. Owner-level knobs apply from Stage 1; device-level knobs from Stage 2 (see `paramsApplied`)."""
    fleet_size_x: float = Field(default=1.0, ge=0.5, le=5.0)      # advanced: scales every device's size (1 = as generated); prefer the visible counts below
    battery_count: int = Field(default=60, ge=0, le=300)          # modeled clusters; defaults = 3x the original 20/14/36/8 world, now VISIBLE
    ev_fleet_count: int = Field(default=42, ge=0, le=200)
    building_count: int = Field(default=108, ge=0, le=400)
    solar_count: int = Field(default=24, ge=0, le=100)
    battery_reserve_pct: float = Field(default=25, ge=0, le=80)
    owners_enrolled_pct: float = Field(default=100, ge=0, le=100)
    min_price_scale: float = Field(default=1.0, ge=0.2, le=3.0)
    ev_shiftable_pct: float = Field(default=60, ge=0, le=100)
    ev_max_delay_h: float = Field(default=4, ge=0, le=12)
    building_offset_c: float = Field(default=2, ge=0, le=4)
    building_max_hours: int = Field(default=3, ge=0, le=6)
    rebound_pct: float = Field(default=70, ge=0, le=100)
    dc_flex_pct: float = Field(default=0, ge=0, le=50)
    dc_max_defer_h: float = Field(default=3, ge=0, le=8)


class SandboxRunRequest(CamelModel):
    season: Season = "summer"
    hour: int = Field(default=16, ge=0, le=23)
    loads: list[LoadSpec] = Field(default_factory=list)          # new loads to drop in; empty = one 20 MW data centre (dcMw)
    dc_mw: float = Field(default=20, gt=0, le=200)
    provider: Literal["stub", "openai"] = "stub"
    incentive_per_mwh: float = Field(default=100, gt=0, le=1000)
    device_params: DeviceParams = Field(default_factory=DeviceParams)
    capacity_mw: Optional[float] = Field(default=None, ge=40, le=250)      # what-if zone limit; None = the modeled 90 MW


class OwnerLog(CamelModel):
    """One owner/operator's decision in the run: the asset log."""
    owner_id: str
    name: str
    group: Group
    assets: int
    status: str                      # accepted | declined | rejected | priced_out | fallback
    offered_mw: float = 0.0
    price_per_mwh: Optional[float] = None
    dispatched_mwh: float = 0.0
    cost: float = 0.0
    explanation: str = ""
    source: str                      # openai | stub


class MarketLog(CamelModel):
    requested_peak_mw: float
    requested_mwh: float
    offered_mwh: float
    validated_mwh: float
    dispatched_mwh: float
    priced_out_mwh: float
    clearing_cost: float
    incentive_per_mwh: float
    owners_offered: int
    owners_declined: int
    owners_rejected: int
    owners_priced_out: int
    owners_accepted: int
    agent_calls: int
    duration_ms: float


class SeasonInfo(CamelModel):
    reference_day: str
    hourly_baseline_mw: list[float]
    peak_mw: float


class DeviceTypeInfo(CamelModel):
    label: str
    clusters: int
    total_mw: float                  # at fleet size 1x: power (batteries), charger capacity (EV), controllable peak load (buildings), installed (solar)
    total_mwh: Optional[float] = None
    vehicles: Optional[int] = None
    owners: int
    does: str
    limits: str


class SandboxWorld(CamelModel):
    zone_id: str
    zone_name: str
    capacity_mw: float
    provenance: dict[str, str]
    devices: dict[str, int]
    device_details: dict[str, DeviceTypeInfo]
    owner_count: int
    seasons: dict[str, SeasonInfo]
    defaults: DeviceParams
    llm_available: bool = False      # a live OpenAI key is configured, so owners can be real LLM agents
    note: str


class ScriptStep(CamelModel):
    i: int
    kind: Literal["request", "owner_offer", "owner_decline", "validation_fail", "revision", "accepted", "clearing", "dispatch", "done"]
    text: str
    owner_id: Optional[str] = None
    owner_name: Optional[str] = None
    group: Optional[Group] = None
    mw: Optional[float] = None
    price: Optional[float] = None
    load_after_mw: Optional[float] = None


class Curve(CamelModel):
    hours: list[int]
    before: list[float]
    after: list[float]


class SandboxRunResponse(CamelModel):
    season: Season
    hour: int
    date_used: str
    focus_timestamp: str
    dc_mw: float                     # total added load at the chosen hour (MW), all loads
    loads: list[LoadSpec] = Field(default_factory=list)
    base_mw: float
    load_before_mw: float
    load_after_mw: float
    capacity_mw: float
    overload_mw: float
    has_overload: bool
    absorbed_mw: float
    remaining_mw: float
    outcome: Outcome
    outcome_text: str
    dispatch_by_group: dict[str, float]
    script: list[ScriptStep]
    curve: Curve
    owners_total: int
    owners_accepted: int
    event_energy_before_mwh: float
    event_energy_after_mwh: float
    decision_source: str
    checks_passed: bool
    params_applied: list[str]
    params_pending: list[str]
    run_id: Optional[str] = None
    owner_log: list[OwnerLog] = Field(default_factory=list)
    market: Optional[MarketLog] = None
    cached: bool = False
    provenance: dict[str, str]
    note: str


CellState = Literal["within", "absorbed", "over"]


class MatrixRequest(CamelModel):
    """One constraint set (loads + device parameters + owner provider) tested against every season's real reference day."""
    loads: list[LoadSpec] = Field(default_factory=list)
    dc_mw: float = Field(default=20, gt=0, le=200)
    provider: Literal["stub", "openai"] = "stub"
    incentive_per_mwh: float = Field(default=100, gt=0, le=1000)
    device_params: DeviceParams = Field(default_factory=DeviceParams)
    capacity_mw: Optional[float] = Field(default=None, ge=40, le=250)


class SeasonCell(CamelModel):
    season: Season
    date_used: str
    peak_hour: int                     # hour of the day's highest load with these loads
    outcome: Outcome
    outcome_text: str
    peak_load_mw: float                # before the flexible grid acts
    peak_load_after_mw: float
    overload_mw: float                 # at the peak hour
    absorbed_mw: float
    remaining_mw: float
    hours_over_before: int
    hours_over_after: int
    hour_states: list[CellState]       # 24 hours: within capacity / overload absorbed / still over capacity
    periods: dict[str, CellState]      # morning (6-11), afternoon (12-17), evening (18-23): the worst state in the period
    decision_source: str
    owners_accepted: int
    owners_total: int


class MatrixResponse(CamelModel):
    capacity_mw: float
    loads: list[LoadSpec]
    cells: list[SeasonCell]
    params_applied: list[str]
    note: str
    provenance: dict[str, str]


class ConstraintPathway(CamelModel):
    title: str
    changes: list[str]                   # plain-language, e.g. "Owners enrolled 60% -> 100%"
    device_params: DeviceParams          # the full parameter set with the changes applied
    incentive_per_mwh: float
    outcome: Outcome
    absorbed_mw: float
    remaining_mw: float
    holds: bool                          # verified by a full rerun of that day


class CapacityPathway(CamelModel):
    current_mw: float
    needed_mw: float                     # smallest zone limit (to 0.5 MW) at which the day stays within capacity, WITH the current flexibility
    increase_mw: float
    needed_without_flex_mw: float        # the same, if nothing flexible acted
    flex_defers_mw: float                # upgrade avoided by the flexibility
    verified: bool


class RecommendResponse(CamelModel):
    season: Season
    date_used: str
    peak_hour: int
    capacity_mw: float
    overload_mw: float
    remaining_mw: float
    already_holds: bool
    runs_tested: int
    constraint_pathways: list[ConstraintPathway]
    capacity_pathway: Optional[CapacityPathway] = None
    note: str
