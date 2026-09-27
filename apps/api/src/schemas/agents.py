from typing import Any, Literal, Optional

from pydantic import Field

from .base import CamelModel

AgentTypeT = Literal["battery", "ev_fleet", "building", "solar"]


class AgentSummary(CamelModel):
    id: str
    type: AgentTypeT
    name: str
    participating: bool
    participation_draw: float
    dispatchable: bool
    provenance: Literal["modeled"] = "modeled"
    params: dict[str, Any]


class AgentStateOut(CamelModel):
    timestamp: str
    available: bool
    unavailable_reason: Optional[str] = None
    values: dict[str, Any]


class AgentDetail(AgentSummary):
    state: AgentStateOut
    day_series: list[AgentStateOut]   # 24 hourly states of the selected day (at-rest behavior; no dispatch)
    potential: "PotentialOut"


class PotentialOut(CamelModel):
    agent_id: str
    type: AgentTypeT
    participating: bool
    available: bool
    potential_mw: float
    potential_if_enrolled_mw: float
    sustained_hours: float
    limiting_factor: str
    decline_reason: Optional[str] = None


class TypePotential(CamelModel):
    agents: int
    participating: int
    available: int
    potential_mw: float
    potential_if_all_enrolled_mw: float


class PopulationPotential(CamelModel):
    world_id: str
    timestamp: str
    window_hours: float
    rates: dict[str, float]
    by_type: dict[str, TypePotential]
    total_potential_mw: float
    total_if_all_enrolled_mw: float
    deficit_mw: Optional[float] = None       # populated when a scenario is given: net load above capacity at this hour
    covers_deficit_pct: Optional[float] = None
    agents: list[PotentialOut] = Field(default_factory=list)
    provenance: Literal["modeled"] = "modeled"
    note: str = "Potential flexibility only. Nothing is dispatched or optimized in this phase."


class TypeSummary(CamelModel):
    count: int
    participating: int
    participation_rate_effective: float
    capacity: dict[str, float]


class PopulationSummary(CamelModel):
    world_id: str
    seed: int
    calibration_scale: float
    participation_rates: dict[str, float]
    by_type: dict[str, TypeSummary]
    total_agents: int
    provenance: Literal["modeled"] = "modeled"
    notes: list[str]


class Decomposition(CamelModel):
    world_id: str
    timestamp: str
    baseline_mw: float
    ev_charging_mw: float
    building_flexible_load_mw: float
    battery_charging_mw: float
    solar_offset_mw: float
    controllable_mw: float
    background_residual_mw: float
    controllable_share_of_baseline: float
    reconciles: bool
    provenance: Literal["modeled"] = "modeled"
    note: str


class AssumptionsUpdate(CamelModel):
    ev_participation: Optional[float] = Field(default=None, ge=0, le=1)
    battery_participation: Optional[float] = Field(default=None, ge=0, le=1)
    building_participation: Optional[float] = Field(default=None, ge=0, le=1)


AgentDetail.model_rebuild()
