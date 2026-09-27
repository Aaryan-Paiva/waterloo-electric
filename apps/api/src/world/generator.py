"""Deterministic synthetic DER population (CLAUDE.md §11, §13). Same seed + assumptions => same population.

Each agent TYPE draws from its own SeedSequence child, so changing one type never reshuffles another.
Participation is a fixed uniform `draw` per agent: participating = draw < rate. Raising a rate therefore only ADDS
participants (nested populations), which keeps what-ifs and later recommendations coherent.
"""
import math

import numpy as np

from ..agents.battery import BatteryAgent
from ..agents.building import KINDS, BuildingAgent
from ..agents.ev_fleet import WINDOWS, EVFleetAgent
from ..agents.solar import SolarAgent

N_BATTERY, N_EV, N_BUILDING, N_SOLAR = 20, 14, 36, 8


def _rngs(seed: int) -> dict[str, np.random.Generator]:
    kids = np.random.SeedSequence(seed).spawn(4)
    return {k: np.random.default_rng(c) for k, c in zip(("battery", "ev_fleet", "building", "solar"), kids)}


def generate(seed: int, scale: float = 1.0):
    r = _rngs(seed)
    agents = []

    g = r["battery"]
    for i in range(N_BATTERY):
        kind = "commercial" if i < 12 else ("community" if i < 18 else "industrial")
        p = {"commercial": g.uniform(0.15, 0.6), "community": g.uniform(0.6, 1.2), "industrial": g.uniform(1.0, 1.6)}[kind]
        dur = {"commercial": g.choice([2.0, 4.0]), "community": 4.0, "industrial": 2.0}[kind]
        agents.append(BatteryAgent(id=f"battery_{i + 1:03d}", name=f"{kind.title()} battery {i + 1}", draw=float(g.random()), seed=seed, kind=kind,
                                   power_mw=float(p * scale), duration_h=float(dur), charge_eff=float(g.uniform(0.93, 0.97)),
                                   discharge_eff=float(g.uniform(0.93, 0.97)), min_soc=float(g.uniform(0.10, 0.25)), max_soc=float(g.uniform(0.92, 1.0)),
                                   charge_start_h=int(g.integers(0, 4)), charge_len_h=int(g.integers(3, 6)), self_supply_fraction=float(g.uniform(0.2, 0.5))))

    g = r["ev_fleet"]
    kinds = ["depot"] * 5 + ["workplace"] * 5 + ["residential_managed"] * 4
    for i, kind in enumerate(kinds[:N_EV]):
        n = int(max(4, round(g.integers(20, 160) * scale)))
        ratio = g.uniform(0.5, 1.0)
        arr, dep = WINDOWS[kind]
        kwh = {"depot": g.uniform(70, 160), "workplace": g.uniform(15, 35), "residential_managed": g.uniform(10, 25)}[kind]
        agents.append(EVFleetAgent(id=f"ev_fleet_{i + 1:03d}", name=f"{kind.replace('_', ' ').title()} EV fleet {i + 1}", draw=float(g.random()), seed=seed,
                                   kind=kind, vehicles=n, chargers=int(max(2, math.ceil(n * ratio))), charger_kw=float(g.choice([7.2, 11.0, 19.2])),
                                   kwh_per_vehicle_day=float(kwh), shiftable_fraction=float(g.uniform(0.5, 0.9)), arrival_h=arr, departure_h=dep))

    g = r["building"]
    order = ["office"] * 12 + ["school"] * 6 + ["retail"] * 8 + ["apartment"] * 6 + ["municipal"] * 4
    for i, kind in enumerate(order[:N_BUILDING]):
        peak = {"office": g.uniform(0.3, 1.2), "school": g.uniform(0.3, 0.9), "retail": g.uniform(0.2, 0.8), "apartment": g.uniform(0.4, 1.4), "municipal": g.uniform(0.3, 1.0)}[kind]
        agents.append(BuildingAgent(id=f"building_{i + 1:03d}", name=f"{kind.title()} building {i + 1}", draw=float(g.random()), seed=seed, kind=kind,
                                    peak_mw=float(peak * scale), hvac_share_max=float(g.uniform(0.35, 0.55)), shed_fraction=float(g.uniform(0.2, 0.4)),
                                    max_curtail_h=int(g.integers(2, 5)), rebound_fraction=float(g.uniform(0.6, 0.9)), rebound_h=int(g.integers(2, 4))))

    g = r["solar"]
    for i in range(N_SOLAR):
        agents.append(SolarAgent(id=f"solar_{i + 1:03d}", name=f"Solar cluster {i + 1}", draw=float(g.random()), seed=seed,
                                 installed_mw=float(g.uniform(0.3, 1.2) * scale), derate=float(g.uniform(0.85, 1.0))))
    return agents
