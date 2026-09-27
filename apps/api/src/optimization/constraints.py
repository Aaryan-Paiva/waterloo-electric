"""Optimization inputs/outputs and an INDEPENDENT physical-constraint validator (CLAUDE.md §19.2).

All series are hourly (1 MW for 1 h = 1 MWh) over the horizon = event window + recovery tail.
Sign convention: `reduction` > 0 lowers net load.
"""
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from .objectives import TOL


@dataclass
class BatteryIn:
    id: str; name: str
    power: float; energy: float; eta_c: float; eta_d: float; min_e: float; max_e: float
    rest_chg: list[float]; rest_dis: list[float]; soc_rest_end: list[float]; avail: list[bool]
    init_dev: float = 0.0          # carried SOC deviation from the at-rest routine (MWh, <= 0 = below routine) at the start of the horizon (historical engine)


@dataclass
class EVIn:
    id: str; name: str
    shiftable: float
    p_max: list[float]; rest: list[float]; avail: list[bool]


@dataclass
class BuildingIn:
    id: str; name: str
    cap: list[float]; max_hours: int; rebound_frac: float; rebound_h: int; avail: list[bool]
    prior_hours: int = 0           # curtailment hours already used in the 24 h before the horizon (historical engine)


@dataclass
class Problem:
    hours: list[pd.Timestamp]
    in_window: list[bool]
    pre_net: list[float]
    capacity: float
    batteries: list[BatteryIn] = field(default_factory=list)
    evs: list[EVIn] = field(default_factory=list)
    buildings: list[BuildingIn] = field(default_factory=list)
    # Agentic clearing (Phase 5-6). None = Manual mode (no offer caps). Otherwise every delivering variable
    # (battery discharge, EV deferral, building shed) of asset `id` is capped by caps[id][t] (missing => 0) and priced.
    caps: Optional[dict[str, list[float]]] = None
    prices: dict[str, float] = field(default_factory=dict)          # $/MWh delivered
    duration_period_h: Optional[int] = None                         # None: one curtailment budget per horizon (single event). N: a budget per N-hour block (historical clusters use 24)


@dataclass
class Solution:
    status: str
    objective: float
    slack: list[float]
    battery: dict[str, dict[str, list[float]]] = field(default_factory=dict)    # charge, discharge, soc (fraction, end of hour)
    ev: dict[str, dict[str, list[float]]] = field(default_factory=dict)         # defer, recover
    building: dict[str, dict[str, list[float]]] = field(default_factory=dict)   # shed, rebound
    scale: Optional[float] = None                                               # envelope mode only


@dataclass
class Check:
    name: str
    passed: bool
    max_violation: float
    detail: str = ""


def reductions(pb: Problem, sol: Solution) -> dict[str, list[list[float]]]:
    """Per-agent reduction series (MW, + lowers net load) recomputed from the raw decision values."""
    out = {"battery": [], "ev_fleet": [], "building": []}
    for b in pb.batteries:
        s = sol.battery[b.id]
        out["battery"].append([d - c for c, d in zip(s["charge"], s["discharge"])])
    for e in pb.evs:
        s = sol.ev[e.id]
        out["ev_fleet"].append([d - r for d, r in zip(s["defer"], s["recover"])])
    for bl in pb.buildings:
        s = sol.building[bl.id]
        out["building"].append([sh - rb for sh, rb in zip(s["shed"], s["rebound"])])
    return out


def optimized_net(pb: Problem, sol: Solution) -> list[float]:
    red = reductions(pb, sol)
    tot = [0.0] * len(pb.hours)
    for lst in red.values():
        for series in lst:
            for i, v in enumerate(series):
                tot[i] += v
    return [p - t for p, t in zip(pb.pre_net, tot)]


def validate(pb: Problem, sol: Solution, tol: float = 1e-5) -> list[Check]:
    """Re-derive every physical constraint from the solution; independent of the solver model."""
    T = len(pb.hours)
    worst: dict[str, float] = {}

    def note(name: str, v: float) -> None:
        worst[name] = max(worst.get(name, 0.0), v)

    for b in pb.batteries:
        s = sol.battery[b.id]
        dev = 0.0
        for t in range(T):
            c, d = s["charge"][t], s["discharge"][t]
            note("battery_nonnegative", max(0.0, -c, -d))
            if pb.caps is not None:
                note("offer_cap_respected", max(0.0, d - pb.caps.get(b.id, [0.0] * T)[t]))
            note("battery_inverter_charge", max(0.0, b.rest_chg[t] + c - b.power))
            note("battery_inverter_discharge", max(0.0, b.rest_dis[t] + d - b.power))
            if not b.avail[t]:
                note("battery_availability", max(c, d))
            dev += c * b.eta_c - d / b.eta_d
            soc_e = b.soc_rest_end[t] + dev + b.init_dev
            note("battery_soc_reserve", max(0.0, b.min_e - soc_e))
            note("battery_soc_max", max(0.0, soc_e - b.max_e))
    for e in pb.evs:
        s = sol.ev[e.id]
        for t in range(T):
            d, r = s["defer"][t], s["recover"][t]
            note("ev_nonnegative", max(0.0, -d, -r))
            if pb.caps is not None:
                note("offer_cap_respected", max(0.0, d - pb.caps.get(e.id, [0.0] * T)[t]))
            note("ev_shiftable_fraction", max(0.0, d - e.shiftable * e.rest[t]))
            note("ev_charger_limit", max(0.0, (e.rest[t] - d + r) - max(e.p_max[t], e.rest[t])))
            if not e.avail[t]:
                note("ev_plugged_in", max(d, r))
        note("ev_energy_delivered_by_deadline", abs(sum(s["defer"]) - sum(s["recover"])))
    for bl in pb.buildings:
        s = sol.building[bl.id]
        hours_on = 0
        for t in range(T):
            sh = s["shed"][t]
            note("building_nonnegative", max(0.0, -sh))
            if pb.caps is not None:
                note("offer_cap_respected", max(0.0, sh - pb.caps.get(bl.id, [0.0] * T)[t]))
            note("building_power_limit", max(0.0, sh - bl.cap[t]))
            if sh > tol:
                hours_on += 1
                if not pb.in_window[t] or not bl.avail[t]:
                    note("building_availability", sh)
            exp_rb = bl.rebound_frac / bl.rebound_h * sum(s["shed"][k] for k in range(max(0, t - bl.rebound_h), t))
            note("building_rebound_accounted", abs(s["rebound"][t] - exp_rb))
        if pb.duration_period_h is None:
            note("building_duration_budget", max(0.0, hours_on - bl.max_hours))
        else:
            P = pb.duration_period_h
            for k in range(0, T, P):
                used = sum(1 for t in range(k, min(T, k + P)) if s["shed"][t] > tol)
                note("building_duration_budget", max(0.0, used - max(0, bl.max_hours - (bl.prior_hours if k == 0 else 0))))
    net = optimized_net(pb, sol)
    note("no_hour_made_worse", max((max(0.0, max(0.0, n - pb.capacity) - max(0.0, p - pb.capacity)) for n, p in zip(net, pb.pre_net)), default=0.0))
    note("slack_accounts_for_violation", max((max(0.0, (n - pb.capacity) - s) for n, s in zip(net, sol.slack)), default=0.0))
    return [Check(n, v <= tol, round(v, 9)) for n, v in sorted(worst.items())]
