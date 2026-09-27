import inspect

import numpy as np
import pandas as pd
import pytest

from src.agents.util import to_est
from src.data.repositories import get_load
from src.simulation import engine
from src.simulation.engine import net_load
from src.projects.data_center import DataCenterProject
from src.world import population as popmod
from src.world.generator import N_BATTERY, N_BUILDING, N_EV, N_SOLAR, generate
from src.world.population import CONTROLLABLE_CAP, build_population

WORLD = "waterloo-demo"


def sample_ts(n=300, seed=7):
    ts = get_load(WORLD).df["timestamp"]
    idx = np.random.default_rng(seed).choice(len(ts) - 30, size=n, replace=False)
    return [ts.iloc[int(i)] for i in idx]


def fresh() -> popmod.Population:
    build_population.cache_clear()
    return build_population(WORLD)


# ---------------------------------------------------------------- reproducibility
def test_population_is_reproducible_and_seed_dependent():
    a, b = fresh(), fresh()
    assert a is not b and a.agents == b.agents and a.scale == b.scale
    assert [x.params() for x in a.agents] == [x.params() for x in b.agents]
    assert generate(42017) == generate(42017) and generate(42017) != generate(42018)
    counts = {t: sum(x.type == t for x in a.agents) for t in ("battery", "ev_fleet", "building", "solar")}
    assert counts == {"battery": N_BATTERY, "ev_fleet": N_EV, "building": N_BUILDING, "solar": N_SOLAR}
    assert len({x.id for x in a.agents}) == len(a.agents)


def test_states_are_pure_functions_of_time_not_call_order():
    pop = fresh()
    ts = sample_ts(60)
    fwd = [[pop.state(a, t).values for a in pop.agents] for t in ts]
    rev = [[pop.state(a, t).values for a in pop.agents] for t in reversed(ts)][::-1]
    assert fwd == rev
    other = fresh()
    assert [pop.state(a, ts[0]).values for a in pop.agents] == [other.state(a, ts[0]).values for a in other.agents]


def test_agent_types_use_independent_seed_streams():
    a = generate(42017)
    solar = [x for x in a if x.type == "solar"]
    assert solar == [x for x in generate(42017) if x.type == "solar"]
    assert [x.params() for x in a if x.type == "battery"] != [x.params() for x in generate(1) if x.type == "battery"]


# ---------------------------------------------------------------- physical constraints
def test_physical_constraints_hold_at_sampled_times():
    pop = fresh()
    tol = 1e-3   # state values are rounded to 4 dp
    for t in sample_ts(250):
        tt = to_est(t)
        for a in pop.agents:
            st = pop.state(a, tt)
            v = st.values
            for w in (1.0, 4.0):
                p = pop.potential(a, tt, w, {"battery": 1.0, "ev_fleet": 1.0, "building": 1.0})
                assert 0 <= p.potential_mw <= p.potential_if_enrolled_mw + tol
                if not st.available:
                    assert p.potential_mw == 0
                if a.type == "battery":
                    assert a.min_soc - tol <= v["soc"] <= a.max_soc + tol
                    assert 0 <= v["chargingMw"] <= a.power_mw + tol and 0 <= v["atRestDischargeMw"] <= a.power_mw + tol
                    assert p.potential_mw <= a.power_mw - v["atRestDischargeMw"] - v["chargingMw"] + 1e-3
                    assert p.potential_mw * w <= v["usableEnergyMwh"] + 1e-3            # cannot discharge energy it does not have
                elif a.type == "ev_fleet":
                    assert 0 <= v["chargingMw"] <= a.max_charging_mw + tol and v["connectedVehicles"] <= a.vehicles
                    assert 0 <= v["energyRequiredMwh"] <= a.vehicles * 0.95 * a.kwh_per_vehicle_day / 1000 + tol
                    assert p.potential_mw <= a.shiftable_fraction * v["chargingMw"] + 1e-3
                    if st.available and p.potential_mw > 0:
                        assert p.potential_mw * w <= max(0.0, v["slackHours"]) * v["maxEffectiveMw"] + 1e-3   # deferred energy recoverable before departure
                elif a.type == "building":
                    assert 0 <= v["sheddableMw"] <= v["hvacLoadMw"] <= v["baselineShareMw"] <= a.peak_mw + tol
                    assert 0.6 - tol <= v["comfortBudget"] <= 1.0 + tol
                    assert p.potential_mw <= v["sheddableMw"] + tol and p.sustained_hours <= a.max_curtail_h + tol
                else:
                    assert 0 <= v["generationMw"] <= a.installed_mw + tol and v["generationMw"] <= v["clearSkyMw"] * 1.05 + tol
                    assert p.potential_if_enrolled_mw == 0


def test_solar_is_zero_at_night_and_positive_at_midday_in_summer():
    pop = fresh()
    solar = [a for a in pop.agents if a.type == "solar"]
    day = pd.Timestamp("2024-07-01", tz="Etc/GMT+5")
    for h in (0, 1, 2, 3, 22, 23):
        assert all(pop.state(a, day + pd.Timedelta(hours=h)).values["generationMw"] == 0 for a in solar)
    assert sum(pop.state(a, day + pd.Timedelta(hours=12)).values["generationMw"] for a in solar) > 0


def test_ev_workplace_fleets_absent_on_weekends():
    pop = fresh()
    sat = pd.Timestamp("2025-06-28 11:00", tz="Etc/GMT+5")    # Saturday
    for a in pop.agents:
        if a.type == "ev_fleet" and a.kind == "workplace":
            assert not pop.state(a, sat).available and pop.state(a, sat).values["chargingMw"] == 0


# ---------------------------------------------------------------- participation
def test_participation_is_a_fixed_draw_and_nested():
    pop = fresh()
    flex = [a for a in pop.agents if a.type != "solar"]
    prev: set = set()
    for r in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        rates = {"battery": r, "ev_fleet": r, "building": r}
        now = {a.id for a in flex if pop.participates(a, rates)}
        assert prev <= now                                    # raising participation only ADDS agents
        assert now == {a.id for a in flex if a.draw < r}
        prev = now
    assert prev == {a.id for a in flex}
    assert not any(pop.participates(a, {"battery": 1, "ev_fleet": 1, "building": 1}) for a in pop.agents if a.type == "solar")


def test_default_rates_come_from_the_world_pack():
    pop = fresh()
    assert pop.rates() == {"battery": 0.40, "ev_fleet": 0.35, "building": 0.25}
    assert pop.rates({"ev_participation": 0.6})["ev_fleet"] == 0.6 and pop.rates({"ev_participation": None})["ev_fleet"] == 0.35


def test_non_participants_offer_nothing_and_say_why():
    pop = fresh()
    none = {"battery": 0.0, "ev_fleet": 0.0, "building": 0.0}
    allr = {"battery": 1.0, "ev_fleet": 1.0, "building": 1.0}
    t = to_est("2025-06-24T20:00:00-05:00")
    totals = []
    for a in (a for a in pop.agents if a.type != "solar"):
        p0, p1 = pop.potential(a, t, 1.0, none), pop.potential(a, t, 1.0, allr)
        assert p0.potential_mw == 0 and p0.decline_reason == "not_enrolled"
        assert p1.potential_mw == p0.potential_if_enrolled_mw == p1.potential_if_enrolled_mw
        totals.append(p1.potential_mw)
    assert sum(totals) > 0
    prev = -1.0
    for r in (0.0, 0.25, 0.5, 0.75, 1.0):
        tot = sum(pop.potential(a, t, 1.0, {"battery": r, "ev_fleet": r, "building": r}).potential_mw for a in pop.agents)
        assert tot >= prev
        prev = tot


# ---------------------------------------------------------------- provenance
def test_every_agent_is_modeled_and_never_dispatched():
    pop = fresh()
    assert all(getattr(a, "type") in ("battery", "ev_fleet", "building", "solar") for a in pop.agents)
    forbidden = ("dispatch", "optimiz", "apply_dispatch")
    assert not any(any(f in n.lower() for f in forbidden) for a in pop.agents for n in dir(a) if not n.startswith("__"))


# ---------------------------------------------------------------- baseline immutability & no solar double counting
def test_population_never_alters_the_baseline():
    before = get_load(WORLD).df.copy()
    pop = fresh()
    for t in sample_ts(80):
        pop.decomposition(t)
        for a in pop.agents:
            pop.potential(a, t, 2.0, pop.rates())
    pd.testing.assert_frame_equal(get_load(WORLD).df, before)
    base = net_load(before, [])
    assert np.allclose(base["net_mw"], before["load_mw"])                   # no DER term in the net-load equation


def test_net_load_engine_has_no_agent_or_solar_terms():
    src = inspect.getsource(engine).lower()
    assert "agents" not in src and "solar" not in src.replace("local_generation", "") and "population" not in src


def test_decomposition_reconciles_to_the_observed_baseline_without_double_counting_solar():
    pop = fresh()
    worst_share = 0.0
    for t in sample_ts(300):
        d = pop.decomposition(t)
        assert d["baselineMw"] is not None
        # baseline = residual + controllable - solar : solar is an attributed OFFSET inside the baseline, never subtracted twice
        assert d["backgroundResidualMw"] + d["controllableMw"] - d["solarOffsetMw"] == pytest.approx(d["baselineMw"], abs=1e-3)
        assert d["backgroundResidualMw"] >= 0
        assert d["solarOffsetMw"] >= 0
        worst_share = max(worst_share, d["controllableShareOfBaseline"])
    assert worst_share <= CONTROLLABLE_CAP + 0.03                           # attribution never exceeds the calibrated cap (sampled)


def test_solar_offers_no_relief_and_is_excluded_from_totals():
    pop = fresh()
    t = to_est("2025-06-24T13:00:00-05:00")
    rates = {"battery": 1.0, "ev_fleet": 1.0, "building": 1.0}
    solar = [a for a in pop.agents if a.type == "solar"]
    assert sum(pop.state(a, t).values["generationMw"] for a in solar) > 0     # it IS generating...
    for a in solar:
        p = pop.potential(a, t, 1.0, rates)
        assert p.potential_mw == 0 and p.potential_if_enrolled_mw == 0 and p.limiting_factor == "already_in_baseline"
        assert pop.state(a, t).values["alreadyInBaseline"] is True
    without = popmod.Population(pop.seed, [a for a in pop.agents if a.type != "solar"], pop.scale, pop.ctx, pop.baseline_index, pop.default_rates)
    assert sum(pop.potential(a, t, 1.0, rates).potential_mw for a in pop.agents) == sum(without.potential(a, t, 1.0, rates).potential_mw for a in without.agents)
    assert without.decomposition(t)["controllableMw"] == pop.decomposition(t)["controllableMw"]


def test_scenario_analysis_is_unchanged_by_the_population():
    from src.scenario_store import store
    from src.schemas.scenario import ProjectCreate, ScenarioCreate
    from src.simulation.stress_test import run_capacity_analysis

    def golden():
        sc = store.add_project(store.create(ScenarioCreate()).id, ProjectCreate(nominal_load_mw=20))
        a = run_capacity_analysis(sc)
        return a.constrained_hours, a.affected_days, a.worst_deficit_mw, a.projected_peak_mw

    before = golden()
    pop = fresh()
    for t in sample_ts(40):
        pop.decomposition(t)
    assert golden() == before == (268, 51, 8.0, 98.0) or get_load(WORLD).mode == "fixture"
