"""Waterloo Electric sandbox API (thin layer over the agentic pipeline). Results are Derived; devices/owners Modeled; the data centre Hypothetical."""
from typing import Literal, Optional

from pydantic import Field

from .base import CamelModel

Season = Literal["winter", "spring", "summer", "fall"]
Group = Literal["battery", "ev", "building"]
Outcome = Literal["holds", "partly_holds", "breaks", "no_overload"]


class DeviceParams(CamelModel):
    """Concrete, editable device behavior. Owner-level knobs apply from Stage 1; device-level knobs from Stage 2 (see `paramsApplied`)."""
    fleet_size_x: float = Field(default=3.0, ge=0.5, le=5.0)      # modeled assumption: size of the flexible fleet (1 = calibrated to <= 25% of load)
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
    dc_mw: float = Field(default=20, gt=0, le=200)
    provider: Literal["stub", "openai"] = "stub"
    incentive_per_mwh: float = Field(default=100, gt=0, le=1000)
    device_params: DeviceParams = Field(default_factory=DeviceParams)


class SeasonInfo(CamelModel):
    reference_day: str
    hourly_baseline_mw: list[float]
    peak_mw: float


class SandboxWorld(CamelModel):
    zone_id: str
    zone_name: str
    capacity_mw: float
    provenance: dict[str, str]
    devices: dict[str, int]
    owner_count: int
    seasons: dict[str, SeasonInfo]
    defaults: DeviceParams
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
    dc_mw: float
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
    provenance: dict[str, str]
    note: str
