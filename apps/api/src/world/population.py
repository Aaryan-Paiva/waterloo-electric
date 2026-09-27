"""Population: the synthetic DER agents of a world + read-only queries (state, potential flexibility, decomposition).

Nothing here dispatches or optimizes, and nothing here touches the baseline (CLAUDE.md §11.2, ADR-003).
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Any, Optional

import numpy as np
import pandas as pd

from ..agents.base import Agent, AgentState, Context, Potential
from ..agents.util import to_est
from ..data.repositories import get_load, get_pack
from .generator import generate

TYPES = ["battery", "ev_fleet", "building", "solar"]
RATE_KEY = {"battery": "battery_participation", "ev_fleet": "ev_participation", "building": "building_participation"}
CONTROLLABLE_CAP = 0.25          # attributed controllable load must stay <= 25% of the observed baseline at every hour


@dataclass
class Population:
    seed: int
    agents: list
    scale: float
    ctx: Context
    baseline_index: dict = field(default_factory=dict)      # ns timestamp -> baseline MW (read-only view)
    default_rates: dict = field(default_factory=dict)

    # ---- participation ----------------------------------------------------------------------------------
    def rates(self, overrides: Optional[dict] = None) -> dict:
        r = {**self.default_rates, **{k: v for k, v in (overrides or {}).items() if v is not None}}
        return {t: float(r.get(k, 0.0)) for t, k in RATE_KEY.items()}

    def participates(self, a, rates: dict) -> bool:
        return a.type in rates and a.draw < rates[a.type]          # solar is never a flexibility participant

    def get(self, agent_id: str):
        return next((a for a in self.agents if a.id == agent_id), None)

    # ---- queries ------------------------------------------------------------------------------------------
    def baseline_mw(self, ts: pd.Timestamp) -> Optional[float]:
        return self.baseline_index.get(pd.Timestamp(ts).value)

    def state(self, a, ts) -> AgentState:
        return a.state_at(to_est(ts), self.ctx)

    def potential(self, a, ts, window_h: float, rates: dict) -> Potential:
        return a.potential(to_est(ts), window_h, self.ctx, self.participates(a, rates))

    def decomposition(self, ts) -> dict[str, Any]:
        """Modeled attribution of the OBSERVED baseline (CLAUDE.md §11.3). baseline = residual + EV + HVAC + battery charging - solar."""
        t = to_est(ts)
        b = self.baseline_mw(t)
        sums = {"evChargingMw": 0.0, "buildingFlexibleLoadMw": 0.0, "batteryChargingMw": 0.0, "solarOffsetMw": 0.0}
        for a in self.agents:
            v = a.state_at(t, self.ctx).values
            if a.type == "ev_fleet":
                sums["evChargingMw"] += v["chargingMw"]
            elif a.type == "building":
                sums["buildingFlexibleLoadMw"] += v["hvacLoadMw"]
            elif a.type == "battery":
                sums["batteryChargingMw"] += v["chargingMw"]
            else:
                sums["solarOffsetMw"] += v["generationMw"]
        controllable = sums["evChargingMw"] + sums["buildingFlexibleLoadMw"] + sums["batteryChargingMw"]
        residual = (b - controllable + sums["solarOffsetMw"]) if b is not None else None
        return {"timestamp": t.isoformat(), "baselineMw": b, **{k: round(v, 4) for k, v in sums.items()},
                "controllableMw": round(controllable, 4),
                "backgroundResidualMw": None if residual is None else round(residual, 4),
                "controllableShareOfBaseline": None if not b else round(controllable / b, 4)}


def _heat_index_fn(df: pd.DataFrame):
    p10, p95 = df["load_mw"].quantile(0.10), df["load_mw"].quantile(0.95)
    idx = {int(t.value): float(np.clip((v - p10) / (p95 - p10), 0, 1)) for t, v in zip(df["timestamp"], df["load_mw"])}
    hod_med = df.groupby(df["timestamp"].dt.hour)["load_mw"].median()
    fallback = {h: float(np.clip((v - p10) / (p95 - p10), 0, 1)) for h, v in hod_med.items()}

    def heat(t: pd.Timestamp) -> float:
        return idx.get(int(pd.Timestamp(t).value), fallback[pd.Timestamp(t).hour])
    return heat


def _max_controllable_share(pop: Population, df: pd.DataFrame) -> float:
    """Worst attributed-controllable / baseline over a seasonal x hourly grid."""
    worst = 0.0
    lo = df["timestamp"].min().normalize()
    days = [lo + pd.Timedelta(days=int(d)) for d in (10, 100, 190, 280, 330, 750, 1200, 1600)]
    for d in days:
        for h in range(24):
            t = d + pd.Timedelta(hours=h)
            b = pop.baseline_mw(t)
            if b:
                worst = max(worst, pop.decomposition(t)["controllableMw"] / b)
    return worst


_variant: ContextVar[Optional[tuple]] = ContextVar("population_variant", default=None)


@contextmanager
def use_variant(key: Optional[tuple]):
    """Sandbox only: make build_population() return a parameter variant of the same seeded population inside this context (thread-local)."""
    tok = _variant.set(key)
    try:
        yield
    finally:
        _variant.reset(tok)


@lru_cache(maxsize=4)
def _base(world_id: str) -> Population:
    pack, data = get_pack(world_id), get_load(world_id)
    df = data.df
    base_index = {int(t.value): float(v) for t, v in zip(df["timestamp"], df["load_mw"])}
    ctx = Context(heat_index=_heat_index_fn(df), seed=pack.der_seed)
    pop = Population(pack.der_seed, generate(pack.der_seed, 1.0), 1.0, ctx, base_index, dict(pack.der_assumptions))
    worst = _max_controllable_share(pop, df)
    if worst > CONTROLLABLE_CAP:                                   # calibrate: shrink sizes so attribution never exceeds the cap
        scale = CONTROLLABLE_CAP / worst
        pop = Population(pack.der_seed, generate(pack.der_seed, scale), scale, ctx, base_index, dict(pack.der_assumptions))
    return pop


@lru_cache(maxsize=16)
def _variant_population(world_id: str, key: tuple) -> Population:
    """key = (fleetSize, batteryReservePct, evShiftablePct, buildingOffsetC, buildingMaxHours, reboundPct). Same seeded population, sizes scaled by
    `fleetSize` (a modeled assumption: how large the flexible fleet is, 1 = calibrated to <= 25% of load) and behavior fields overridden when changed."""
    fleet, reserve, ev_shift, offset, max_h, rebound = key
    base = _base(world_id)
    agents = generate(base.seed, base.scale * fleet)
    out = []
    for a in agents:
        if a.type == "battery" and reserve != 25:
            a = replace(a, min_soc=min(reserve / 100.0, a.max_soc - 0.05))
        elif a.type == "ev_fleet" and ev_shift != 60:
            a = replace(a, shiftable_fraction=ev_shift / 100.0)
        elif a.type == "building":
            ch = {}
            if offset != 2:
                ch["shed_fraction"] = min(0.9, a.shed_fraction * offset / 2.0)
            if max_h != 3:
                ch["max_curtail_h"] = int(max_h)
            if rebound != 70:
                ch["rebound_fraction"] = rebound / 100.0
            if ch:
                a = replace(a, **ch)
        out.append(a)
    return Population(base.seed, out, base.scale * fleet, base.ctx, base.baseline_index, dict(base.default_rates))


def build_population(world_id: str) -> Population:
    key = _variant.get()
    return _base(world_id) if key is None else _variant_population(world_id, key)


build_population.cache_clear = lambda: (_base.cache_clear(), _variant_population.cache_clear())   # type: ignore[attr-defined]
