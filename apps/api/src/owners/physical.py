"""Physical layer for owner agents: the event's physics (from the deterministic DER models) and the OFFER VALIDATOR.

Nothing here is LLM-influenced. An offer is a structured per-asset MW profile over hours of the event window; it is valid only if the
asset could deliver the WHOLE profile at once under the same SOC/reserve/inverter, EV energy/deadline/charger/shiftable and building
power/duration/comfort/rebound constraints the clearing model uses (single-asset LP: maximize lambda s.t. delivered >= lambda x offer).
"""
from dataclasses import dataclass, field, replace
from typing import Optional

import pandas as pd

from ..optimization.constraints import Problem
from ..optimization.dispatcher import Exclusion, build_problem
from ..optimization.model import solve
from ..optimization.objectives import TOL
from ..schemas.owners import AssetOffer, AssetValidation, Block, OfferBody, OfferValidation, OwnerAgent
from ..schemas.scenario import Scenario
from ..simulation.stress_test import scenario_frame
from ..world.population import Population, build_population

ENVELOPE_SAFETY = 0.999
MAX_PRICE = 1000.0


@dataclass
class Physics:
    """Everything the validator/clearing needs for ONE event window. Read-only."""
    pop: Population
    df: pd.DataFrame
    capacity: float
    horizon: list[pd.Timestamp]
    in_window: list[bool]
    window_hours: int
    pb_all: Problem                       # every flexible asset available at least once in the horizon (enrolment ignored)
    exclusions: dict[str, str] = field(default_factory=dict)
    ceilings: dict[str, list[float]] = field(default_factory=dict)      # static per-hour max delivering MW per asset (window hours)

    def asset_type(self, aid: str) -> Optional[str]:
        a = self.pop.get(aid)
        return None if a is None else a.type


def build_physics(scenario: Scenario, w_start: pd.Timestamp, w_end: pd.Timestamp, tail_hours: int, *, frame: Optional[tuple] = None,
                  windows: Optional[list[tuple[pd.Timestamp, pd.Timestamp]]] = None, horizon_end: Optional[pd.Timestamp] = None,
                  init_dev: Optional[dict[str, float]] = None, prior_hours: Optional[dict[str, int]] = None, duration_period_h: Optional[int] = None) -> Physics:
    """Physics of one horizon. Single event: [w_start, w_end) + tail. Historical cluster: pass `windows` (all event windows inside the horizon),
    `frame` (df, cap) computed once, carried battery deviation `init_dev` and building `prior_hours`. `in_window` marks hours where offers/shed are allowed."""
    df, cap = (frame or scenario_frame(scenario))[:2]
    last = df["timestamp"].iloc[-1]
    h_end = horizon_end or min(w_end + pd.Timedelta(hours=tail_hours), last + pd.Timedelta(hours=1))
    horizon = [t for t in df["timestamp"] if w_start <= t < h_end]
    wins = windows or [(w_start, w_end)]
    in_window = [any(a <= t < b for a, b in wins) for t in horizon]
    pop = build_population(scenario.zone_id)
    flexible = {a.id for a in pop.agents if a.type != "solar"}
    pb, excl, _ = build_problem(pop, pop.rates(), df, cap, horizon, in_window, include=flexible)
    pb.duration_period_h = duration_period_h
    for b in pb.batteries:
        b.init_dev = (init_dev or {}).get(b.id, 0.0)
    for bl in pb.buildings:
        bl.prior_hours = (prior_hours or {}).get(bl.id, 0)
    ph = Physics(pop=pop, df=df, capacity=cap, horizon=horizon, in_window=in_window, window_hours=sum(in_window), pb_all=pb,
                 exclusions={e.agent_id: e.reason for e in excl})
    T = len(horizon)
    for b in pb.batteries:
        ph.ceilings[b.id] = [max(0.0, b.power - b.rest_dis[t]) if b.avail[t] and in_window[t] else 0.0 for t in range(T)]
    for e in pb.evs:
        ph.ceilings[e.id] = [e.shiftable * e.rest[t] if e.avail[t] and in_window[t] else 0.0 for t in range(T)]
    for bl in pb.buildings:
        ph.ceilings[bl.id] = [bl.cap[t] if bl.avail[t] and in_window[t] and bl.cap[t] > TOL else 0.0 for t in range(T)]
    return ph


def single_problem(pb: Problem, aid: str) -> Problem:
    return replace(pb, batteries=[b for b in pb.batteries if b.id == aid], evs=[e for e in pb.evs if e.id == aid],
                   buildings=[x for x in pb.buildings if x.id == aid], caps=None, prices={})


def profile_of(blocks: list[Block], horizon_len: int) -> list[float]:
    p = [0.0] * horizon_len
    for b in blocks:
        for t in range(b.start_hour, min(b.end_hour, horizon_len)):
            p[t] += b.mw
    return p


def blocks_of(profile: list[float]) -> list[Block]:
    out, t = [], 0
    while t < len(profile):
        if profile[t] > 1e-6:
            e = t + 1
            while e < len(profile) and abs(profile[e] - profile[t]) < 1e-9:
                e += 1
            out.append(Block(start_hour=t, end_hour=e, mw=round(profile[t], 4)))
            t = e
        else:
            t += 1
    return out


def _fmt(profile: list[float]) -> str:
    hrs = sum(1 for x in profile if x > 1e-6)
    return f"{max(profile, default=0.0):.2f} MW peak over {hrs} h"


def validate_line(ph: Physics, owner: OwnerAgent, line: AssetOffer, committed: set[str]) -> AssetValidation:
    T = len(ph.horizon)
    bad = lambda code, msg, env=None: AssetValidation(asset_id=line.asset_id, status="invalid", violation=code, requested=line.blocks,
                                                       feasible_envelope=env or [], explanation=msg)
    aid = line.asset_id
    if aid not in owner.controlled_asset_ids:
        return bad("not_owned", f"{owner.id} does not control {aid}")
    atype = ph.asset_type(aid)
    if atype is None or atype == "solar":
        return bad("not_a_flexible_asset", f"{aid} is not a dispatchable flexible asset")
    if aid in committed:
        return bad("already_committed", f"{aid} is already committed in another accepted offer")
    for b in line.blocks:
        if b.end_hour <= b.start_hour or b.end_hour > T or not all(ph.in_window[t] for t in range(b.start_hour, b.end_hour)):
            return bad("outside_event_window", f"block [{b.start_hour},{b.end_hour}) is outside the event window")
    prof = profile_of(line.blocks, T)
    if max(prof, default=0.0) <= 0:
        return bad("empty_offer", "offer has no positive MW")
    if sum(b.end_hour - b.start_hour for b in line.blocks) != sum(1 for x in prof if x > 0):
        return bad("overlapping_blocks", "offered blocks overlap")
    if aid not in ph.ceilings:
        return bad("asset_unavailable", f"asset unavailable throughout the event ({ph.exclusions.get(aid, 'unavailable')})")
    ceil = ph.ceilings[aid]
    pb1 = single_problem(ph.pb_all, aid)
    prof_full = prof

    code: Optional[str] = None
    if any(p > 1e-9 and c <= 1e-9 for p, c in zip(prof, ceil)):
        code = "asset_unavailable"
    elif any(p > c + 1e-6 for p, c in zip(prof, ceil)):
        code = {"battery": "exceeds_power_limit", "ev_fleet": "exceeds_shiftable_fraction", "building": "exceeds_comfort_power_limit"}[atype]
    trunc = prof_full
    if atype == "building":
        bl1 = pb1.buildings[0]
        P = ph.pb_all.duration_period_h or T
        keep: set[int] = set()
        over = False
        for k in range(0, T, P):
            on = [t for t in range(k, min(T, k + P)) if prof[t] > 1e-9]
            budget = max(0, bl1.max_hours - (bl1.prior_hours if k == 0 and ph.pb_all.duration_period_h else 0))
            over |= len(on) > budget
            keep.update(sorted(on, key=lambda t: (-prof[t], t))[:budget])
        if over:
            code = code or "comfort_duration_violation"
            trunc = [prof_full[t] if t in keep else 0.0 for t in range(T)]
    sol = solve(pb1, scale_target={aid: trunc})
    lam = sol.scale or 0.0
    if code is None and lam >= 1.0 - 1e-6:
        return AssetValidation(asset_id=aid, status="valid", requested=line.blocks, feasible_envelope=line.blocks, explanation="within all physical limits")
    code = code or {"battery": "insufficient_usable_energy", "ev_fleet": "deadline_energy_violation", "building": "comfort_duration_violation"}[atype]
    env_prof = [ENVELOPE_SAFETY * min(lam, 1.0) * x for x in trunc]
    env = blocks_of(env_prof)
    return bad(code, f"requested {_fmt(prof)}; feasible envelope {_fmt(env_prof)} ({code.replace('_', ' ')})", env)


def validate_offer(ph: Physics, owner: OwnerAgent, body: OfferBody, committed: set[str]) -> OfferValidation:
    if not (0 < body.price_per_mwh <= MAX_PRICE):
        return OfferValidation(status="invalid", lines=[], violation="invalid_price", explanation=f"price must be in (0, {MAX_PRICE:.0f}] $/MWh")
    seen: set[str] = set()
    lines = []
    for ln in body.asset_offers:
        v = validate_line(ph, owner, ln, committed | seen)
        if v.status == "valid":
            seen.add(ln.asset_id)
        lines.append(v)
    bad = [x for x in lines if x.status == "invalid"]
    if bad:
        return OfferValidation(status="invalid", lines=lines, violation=bad[0].violation, explanation="; ".join(f"{x.asset_id}: {x.explanation}" for x in bad))
    return OfferValidation(status="valid", lines=lines, explanation="all assets within physical limits")
