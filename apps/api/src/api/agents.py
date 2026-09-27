from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..agents.util import to_est
from ..data.repositories import get_load
from ..scenario_store import NotFound, store
from ..schemas.agents import (AgentDetail, AgentStateOut, AgentSummary, Decomposition, PopulationPotential, PopulationSummary,
                              PotentialOut, TypePotential, TypeSummary)
from ..simulation.stress_test import scenario_frame
from ..world.population import RATE_KEY, TYPES, Population, build_population
from .zones import WORLDS

router = APIRouter(prefix="/api/worlds", tags=["agents"])


def _pop(world_id: str) -> Population:
    if world_id not in WORLDS:
        raise HTTPException(404, f"unknown world {world_id!r}")
    return build_population(world_id)


def _rates(pop: Population, scenario_id: Optional[str]) -> dict:
    if not scenario_id:
        return pop.rates()
    try:
        return pop.rates(store.get(scenario_id).assumption_overrides)
    except NotFound:
        raise HTTPException(404, f"unknown scenario {scenario_id!r}")


def _ts(world_id: str, ts: str) -> pd.Timestamp:
    t = to_est(ts)
    df = get_load(world_id).df["timestamp"]
    if not (df.iloc[0] <= t <= df.iloc[-1]):
        raise HTTPException(422, f"timestamp outside the historical period {df.iloc[0].isoformat()} .. {df.iloc[-1].isoformat()}")
    return t


def _state_out(t: pd.Timestamp, st) -> AgentStateOut:
    return AgentStateOut(timestamp=t.isoformat(), available=st.available, unavailable_reason=st.reason, values=st.values)


def _summary(pop: Population, a, rates: dict) -> AgentSummary:
    return AgentSummary(id=a.id, type=a.type, name=a.name, participating=pop.participates(a, rates), participation_draw=round(a.draw, 4),
                        dispatchable=a.type != "solar", params=a.params())


def _pot_out(pop: Population, a, t, window_h: float, rates: dict) -> PotentialOut:
    p = pop.potential(a, t, window_h, rates)
    st = pop.state(a, t)
    return PotentialOut(agent_id=a.id, type=a.type, participating=pop.participates(a, rates), available=st.available, potential_mw=round(p.potential_mw, 4),
                        potential_if_enrolled_mw=round(p.potential_if_enrolled_mw, 4), sustained_hours=round(p.sustained_hours, 3),
                        limiting_factor=p.limiting_factor, decline_reason=p.decline_reason)


CAP_FIELDS = {"battery": lambda a: {"powerMw": a.power_mw, "energyMwh": a.energy_mwh},
              "ev_fleet": lambda a: {"vehicles": float(a.vehicles), "maxChargingMw": a.max_charging_mw},
              "building": lambda a: {"peakLoadMw": a.peak_mw, "maxShedMwAtPeak": a.peak_mw * a.hvac_share_max * a.shed_fraction},
              "solar": lambda a: {"installedMw": a.installed_mw}}


@router.get("/{world_id}/population", response_model=PopulationSummary)
def population_summary(world_id: str, scenario_id: Optional[str] = Query(None, alias="scenarioId")):
    pop = _pop(world_id)
    rates = _rates(pop, scenario_id)
    by_type = {}
    for ty in TYPES:
        ags = [a for a in pop.agents if a.type == ty]
        n_part = sum(pop.participates(a, rates) for a in ags)
        cap: dict[str, float] = {}
        for a in ags:
            for k, v in CAP_FIELDS[ty](a).items():
                cap[k] = round(cap.get(k, 0.0) + v, 3)
        by_type[ty] = TypeSummary(count=len(ags), participating=n_part, participation_rate_effective=round(n_part / len(ags), 3) if ags and ty in rates else 0.0, capacity=cap)
    return PopulationSummary(world_id=world_id, seed=pop.seed, calibration_scale=round(pop.scale, 4), participation_rates={k: round(v, 3) for k, v in rates.items()},
                             by_type=by_type, total_agents=len(pop.agents),
                             notes=["Synthetic agents are modeled, never known real customers.",
                                    "The population represents flexibility AROUND a baseline that already contains historical consumption and solar effects.",
                                    "Participation is a fixed per-agent draw: raising a rate only adds participants.",
                                    "Solar clusters are context/reconciliation only and offer no capacity relief."])


@router.get("/{world_id}/agents", response_model=list[AgentSummary])
def list_agents(world_id: str, type: Optional[Literal["battery", "ev_fleet", "building", "solar"]] = None, participating: Optional[bool] = None,
                scenario_id: Optional[str] = Query(None, alias="scenarioId"), limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)):
    pop = _pop(world_id)
    rates = _rates(pop, scenario_id)
    out = [_summary(pop, a, rates) for a in pop.agents if (type is None or a.type == type)]
    if participating is not None:
        out = [a for a in out if a.participating == participating]
    return out[offset: offset + limit]


@router.get("/{world_id}/agents/{agent_id}", response_model=AgentDetail)
def agent_detail(world_id: str, agent_id: str, timestamp: Optional[str] = None, window_hours: float = Query(1.0, alias="windowHours", gt=0, le=12),
                 scenario_id: Optional[str] = Query(None, alias="scenarioId")):
    pop = _pop(world_id)
    a = pop.get(agent_id)
    if a is None:
        raise HTTPException(404, f"unknown agent {agent_id!r}")
    rates = _rates(pop, scenario_id)
    t = _ts(world_id, timestamp) if timestamp else get_load(world_id).df["timestamp"].iloc[0] + pd.Timedelta(days=180, hours=16)
    day0 = t.normalize()
    series = [_state_out(day0 + pd.Timedelta(hours=h), pop.state(a, day0 + pd.Timedelta(hours=h))) for h in range(24)]
    base = _summary(pop, a, rates)
    return AgentDetail(**base.model_dump(), state=_state_out(t, pop.state(a, t)), day_series=series, potential=_pot_out(pop, a, t, window_hours, rates))


@router.get("/{world_id}/population/potential", response_model=PopulationPotential)
def population_potential(world_id: str, timestamp: str, window_hours: float = Query(1.0, alias="windowHours", gt=0, le=12),
                         scenario_id: Optional[str] = Query(None, alias="scenarioId"), include_agents: bool = Query(False, alias="includeAgents")):
    pop = _pop(world_id)
    t = _ts(world_id, timestamp)
    rates = _rates(pop, scenario_id)
    rows = [_pot_out(pop, a, t, window_hours, rates) for a in pop.agents]
    by_type = {}
    for ty in TYPES:
        r = [x for x in rows if x.type == ty]
        by_type[ty] = TypePotential(agents=len(r), participating=sum(x.participating for x in r), available=sum(x.available for x in r),
                                    potential_mw=round(sum(x.potential_mw for x in r), 4), potential_if_all_enrolled_mw=round(sum(x.potential_if_enrolled_mw for x in r), 4))
    total = round(sum(v.potential_mw for v in by_type.values()), 4)
    deficit = covers = None
    if scenario_id:
        df, cap, _, _ = scenario_frame(store.get(scenario_id))
        row = df[df["timestamp"] == t]
        if len(row):
            deficit = round(max(0.0, float(row["net_mw"].iloc[0]) - cap), 4)
            covers = round(min(100.0, 100.0 * total / deficit), 1) if deficit > 0 else None
    return PopulationPotential(world_id=world_id, timestamp=t.isoformat(), window_hours=window_hours, rates={k: round(v, 3) for k, v in rates.items()},
                               by_type=by_type, total_potential_mw=total, total_if_all_enrolled_mw=round(sum(v.potential_if_all_enrolled_mw for v in by_type.values()), 4),
                               deficit_mw=deficit, covers_deficit_pct=covers, agents=rows if include_agents else [])


@router.get("/{world_id}/population/decomposition", response_model=Decomposition)
def population_decomposition(world_id: str, timestamp: str):
    pop = _pop(world_id)
    t = _ts(world_id, timestamp)
    d = pop.decomposition(t)
    recon = abs((d["backgroundResidualMw"] + d["controllableMw"] - d["solarOffsetMw"]) - d["baselineMw"]) < 1e-3 and d["backgroundResidualMw"] >= 0
    return Decomposition(world_id=world_id, timestamp=d["timestamp"], baseline_mw=d["baselineMw"], ev_charging_mw=d["evChargingMw"],
                         building_flexible_load_mw=d["buildingFlexibleLoadMw"], battery_charging_mw=d["batteryChargingMw"], solar_offset_mw=d["solarOffsetMw"],
                         controllable_mw=d["controllableMw"], background_residual_mw=d["backgroundResidualMw"],
                         controllable_share_of_baseline=d["controllableShareOfBaseline"], reconciles=bool(recon),
                         note="baseline = background residual + EV + building HVAC + battery charging - solar offset. Solar is already in the observed baseline and is never subtracted again.")
