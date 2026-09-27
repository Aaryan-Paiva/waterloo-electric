"""Build the optimization Problem from the scenario + the participating, available agents (CLAUDE.md §18).

Only agents that are enrolled (participation draw < rate) can appear; per-hour availability comes from each agent's own
time-varying state. Non-participants and never-available agents are excluded WITH a reason. Solar is informational only.
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ..world.population import Population
from .constraints import BatteryIn, BuildingIn, EVIn, Problem

SUB = (0, 15, 30, 45)   # minutes sampled per hour for hour-averages


@dataclass
class Exclusion:
    agent_id: str
    reason: str


def _avg(pop: Population, a, t: pd.Timestamp, key: str) -> float:
    return sum(float(pop.state(a, t + pd.Timedelta(minutes=m)).values.get(key, 0.0) or 0.0) for m in SUB) / len(SUB)


def build_problem(pop: Population, rates: dict, df: pd.DataFrame, capacity: float, horizon: list[pd.Timestamp], in_window: list[bool],
                  include: Optional[set[str]] = None) -> tuple[Problem, list[Exclusion], list[float]]:
    """Manual mode: enrolment = participation draw < rate. Agentic mode (`include` given): exactly those asset ids (owner offers that
    passed physical validation) enter; the participation draw is ignored. Physical availability is applied identically in both."""
    pre = {t: float(v) for t, v in zip(df["timestamp"], df["net_mw"])}
    pb = Problem(hours=horizon, in_window=in_window, pre_net=[pre[t] for t in horizon], capacity=capacity)
    excl: list[Exclusion] = []
    for a in sorted((x for x in pop.agents if x.type != "solar"), key=lambda x: x.id):
        if (a.id not in include) if include is not None else (not pop.participates(a, rates)):
            excl.append(Exclusion(a.id, "no_validated_offer" if include is not None else "not_enrolled"))
            continue
        states = [pop.state(a, t) for t in horizon]
        avail = [s.available for s in states]
        if not any(avail):
            excl.append(Exclusion(a.id, "unavailable: " + next((s.reason for s in states if s.reason), "unavailable")))
            continue
        if a.type == "battery":
            pb.batteries.append(BatteryIn(
                id=a.id, name=a.name, power=a.power_mw, energy=a.energy_mwh, eta_c=a.charge_eff, eta_d=a.discharge_eff,
                min_e=a.min_soc * a.energy_mwh, max_e=a.max_soc * a.energy_mwh,
                rest_chg=[_avg(pop, a, t, "chargingMw") for t in horizon], rest_dis=[_avg(pop, a, t, "atRestDischargeMw") for t in horizon],
                soc_rest_end=[pop.state(a, t + pd.Timedelta(hours=1)).values["soc"] * a.energy_mwh for t in horizon], avail=avail))
        elif a.type == "ev_fleet":
            rest, pmax, av = [], [], []
            for t in horizon:
                sub = [pop.state(a, t + pd.Timedelta(minutes=m)) for m in SUB]
                frac = sum(s.available for s in sub) / len(sub)
                peff = max((float(s.values.get("maxEffectiveMw", 0.0) or 0.0) for s in sub if s.available), default=0.0)
                r = sum(float(s.values.get("chargingMw", 0.0) or 0.0) for s in sub) / len(sub)
                rest.append(r); pmax.append(max(peff * frac, r)); av.append(frac > 0)
            pb.evs.append(EVIn(id=a.id, name=a.name, shiftable=a.shiftable_fraction, p_max=pmax, rest=rest, avail=av))
        else:
            pb.buildings.append(BuildingIn(id=a.id, name=a.name, cap=[float(s.values["sheddableMw"]) if s.available else 0.0 for s in states],
                                           max_hours=a.max_curtail_h, rebound_frac=a.rebound_fraction, rebound_h=a.rebound_h, avail=avail))
    solar = [a for a in pop.agents if a.type == "solar"]
    solar_mw = [sum(float(pop.state(a, t).values["generationMw"]) for a in solar) for t in horizon]   # informational only
    return pb, excl, solar_mw
