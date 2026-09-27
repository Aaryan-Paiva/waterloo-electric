"""Deterministic, seeded grouping of the physical DER models under owner/operator agents (CLAUDE.md §13b).

70 flexible assets (20 batteries, 14 EV fleets, 36 buildings) -> 18 owners (5 battery operators, 5 EV aggregators, 8 building
portfolios). Solar (8 clusters) is context only and has no owner. Every flexible asset belongs to exactly one owner.
Same seed => same grouping and same preferences (pure functions of (seed, ids); no global RNG, no call-order dependence).
"""
from functools import lru_cache

import numpy as np

from ..agents.util import uhash
from ..schemas.owners import BehavioralPrefs, EconomicPrefs, OperationalPrefs, OwnerAgent
from ..world.population import build_population

GROUPS = {"battery": ("battery_operator", 5, 2), "ev_fleet": ("ev_aggregator", 5, 2), "building": ("building_portfolio", 8, 3)}   # (type, owners, min size)
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# (lo, hi) ranges per owner type; a field that does not apply to a type is 0
RANGES = {
    "battery_operator": dict(min_comp=(45, 115), margin=(0.05, 0.25), sens=(0.3, 0.9), reserve=(0.1, 0.5), comfort=(0, 0), driver=(0, 0), degr=(0.3, 0.9), hours=(3, 8), events=(4, 20), deadline=(0, 0), risk=(0.2, 0.8), tend=(0.3, 0.9)),
    "ev_aggregator": dict(min_comp=(25, 75), margin=(0.05, 0.2), sens=(0.3, 0.9), reserve=(0, 0), comfort=(0, 0), driver=(0.4, 0.9), degr=(0, 0), hours=(2, 6), events=(4, 16), deadline=(0.5, 0.95), risk=(0.2, 0.8), tend=(0.3, 0.9)),
    "building_portfolio": dict(min_comp=(30, 95), margin=(0.05, 0.25), sens=(0.3, 0.9), reserve=(0, 0), comfort=(0.3, 0.9), driver=(0, 0), degr=(0, 0), hours=(2, 5), events=(3, 12), deadline=(0, 0), risk=(0.2, 0.8), tend=(0.3, 0.9)),
}


def _partition(ids: list[str], k: int, min_size: int, seed: int, key: str) -> list[list[str]]:
    rng = np.random.default_rng(np.random.SeedSequence([seed, int(uhash(key) * 2**31)]))
    perm = [ids[i] for i in rng.permutation(len(ids))]
    extra = len(ids) - k * min_size
    sizes = np.full(k, min_size) + rng.multinomial(extra, rng.dirichlet(np.full(k, 4.0)))
    out, i = [], 0
    for s in sizes:
        out.append(sorted(perm[i:i + int(s)]))
        i += int(s)
    return out


def _u(seed: int, oid: str, name: str, lo: float, hi: float) -> float:
    return lo + (hi - lo) * uhash(seed, oid, "pref", name)


def _prefs(seed: int, oid: str, otype: str):
    r = RANGES[otype]
    g = lambda n: _u(seed, oid, n, *r[n if n != "min_comp" else "min_comp"])
    econ = EconomicPrefs(min_compensation_per_mwh=round(g("min_comp"), 1), target_margin=round(g("margin"), 3), price_sensitivity=round(g("sens"), 3))
    op = OperationalPrefs(reserve_preference=round(g("reserve"), 3), comfort_priority=round(g("comfort"), 3), driver_satisfaction_priority=round(g("driver"), 3),
                          degradation_sensitivity=round(g("degr"), 3), max_event_hours=int(round(g("hours"))), max_events_per_month=int(round(g("events"))),
                          deadline_strictness=round(g("deadline"), 3))
    beh = BehavioralPrefs(risk_tolerance=round(g("risk"), 3), participation_tendency=round(g("tend"), 3))
    return econ, op, beh


def _label(agents: dict, ids: list[str]) -> str:
    kinds = [agents[i].kind for i in ids]
    top = max(sorted(set(kinds)), key=kinds.count)
    return top.replace("_", " ").title()


@lru_cache(maxsize=4)
def build_owners(world_id: str) -> tuple[OwnerAgent, ...]:
    pop = build_population(world_id)
    by_id = {a.id: a for a in pop.agents}
    owners: list[OwnerAgent] = []
    for atype, (otype, k, min_size) in GROUPS.items():
        ids = sorted(a.id for a in pop.agents if a.type == atype)
        for n, group in enumerate(_partition(ids, k, min_size, pop.seed, f"{world_id}|{atype}")):
            oid = f"owner_{otype.split('_')[0]}_{n + 1:02d}"
            econ, op, beh = _prefs(pop.seed, oid, otype)
            noun = {"battery_operator": "Battery Operator", "ev_aggregator": "EV Aggregator", "building_portfolio": "Building Portfolio"}[otype]
            owners.append(OwnerAgent(id=oid, name=f"{_label(by_id, group)} {noun} {LETTERS[n]}", owner_type=otype, controlled_asset_ids=group,
                                     economic=econ, operational=op, behavioral=beh))
    return tuple(owners)


def owner_of(world_id: str, asset_id: str) -> str | None:
    return next((o.id for o in build_owners(world_id) if asset_id in o.controlled_asset_ids), None)
