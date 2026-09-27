import json

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.capacityos.coordinator import coordinate_event, resolve_window
from src.data.repositories import get_load
from src.main import app
from src.optimization.constraints import validate
from src.optimization.dispatcher import build_problem
from src.optimization.model import solve
from src.scenario_store import store
from src.schemas.scenario import ProjectCreate, ScenarioCreate
from src.simulation.stress_test import run_capacity_analysis, scenario_frame
from src.world import population as popmod
from src.world.population import build_population

c = TestClient(app)
FULL = get_load("waterloo-demo").mode == "full"
full_only = pytest.mark.skipif(not FULL, reason="golden June 24 event needs the full dataset")
ALL = {"battery_participation": 1.0, "ev_participation": 1.0, "building_participation": 1.0}
NONE = {"battery_participation": 0.0, "ev_participation": 0.0, "building_participation": 0.0}


def golden_scenario(mw=20):
    return store.add_project(store.create(ScenarioCreate()).id, ProjectCreate(nominal_load_mw=mw))


def worst_window(sc):
    return max(run_capacity_analysis(sc).windows, key=lambda w: w.peak_deficit_mw)


def run(sc, w=None):
    w = w or worst_window(sc)
    return coordinate_event(sc, *resolve_window(sc, w.id, None, None))


# ------------------------------------------------------------------ golden June 24 event
@full_only
def test_golden_june_24_event():
    sc = golden_scenario()
    w = worst_window(sc)
    assert w.start.startswith("2025-06-24T08:00") and w.end.startswith("2025-06-24T22:00") and w.hours == 14 and w.peak_deficit_mw == 8.0
    r = run(sc, w)
    assert r.provenance == "derived" and r.resources_provenance == "modeled" and r.zone_id == "waterloo-demo"
    assert r.status == "partially_resolved"                                   # 22 enrolled agents cannot clear a 76 MWh event
    assert r.window.hours == 14 and r.window.violation_hours_before == 14
    assert r.window.energy_above_capacity_before_mwh == pytest.approx(75.691, abs=1e-3)
    assert r.window.energy_above_capacity_after_mwh == pytest.approx(67.28, abs=0.1)
    assert r.window.energy_above_capacity_after_mwh < r.window.energy_above_capacity_before_mwh
    assert r.window.worst_deficit_before_mw == 8.0 and 6.0 < r.window.worst_deficit_after_mw < 7.0
    assert r.tail.violation_hours_after == 0 and r.horizon.violation_hours_after == r.window.violation_hours_after
    assert r.participating_agents == r.included_agents == 22 and 3.5 < r.peak_dispatch_mw < 5.0
    assert r.checks_passed and r.reconciled and r.solver["status"] == "OPTIMAL"
    peak = next(h for h in r.hourly if h.timestamp.startswith("2025-06-24T16:00"))
    assert peak.pre_dispatch_net_mw == 98.0 and peak.remaining_deficit_mw < 8.0 and peak.total_reduction_mw > 3.0   # worst hour is reduced most
    assert "NOT a project-level feasibility claim" in r.note


@full_only
def test_golden_event_is_deterministic():
    sc = golden_scenario()
    a, b = run(sc), run(sc)
    assert json.dumps(a.model_dump(by_alias=True), sort_keys=True) == json.dumps(b.model_dump(by_alias=True), sort_keys=True)


@full_only
def test_participation_bounds_the_outcome():
    sc = golden_scenario()
    energy = {}
    for label, ov in (("none", NONE), ("default", {}), ("all", ALL)):
        s = store.update_assumptions(sc.id, ov) if ov else sc
        energy[label] = run(s, worst_window(sc)).window.energy_above_capacity_after_mwh
        if label == "none":
            r = run(s, worst_window(sc))
            assert r.status == "unresolved" and r.included_agents == 0 and r.peak_dispatch_mw == 0 and all(not a.included for a in r.agents)
    assert energy["all"] < energy["default"] < energy["none"] == pytest.approx(75.691, abs=1e-3)


# ------------------------------------------------------------------ reconciliation & only eligible agents
@full_only
def test_reconciliation_and_no_hour_made_worse():
    sc = golden_scenario()
    r = run(sc)
    df, cap, _, _ = scenario_frame(sc)
    frame = df.set_index("timestamp")
    for h in r.hourly:
        t = pd.Timestamp(h.timestamp)
        assert h.baseline_load_mw + h.project_load_mw == pytest.approx(h.pre_dispatch_net_mw, abs=2e-3)
        assert h.pre_dispatch_net_mw == pytest.approx(float(frame.at[t, "net_mw"]), abs=1e-3)              # same numbers the analysis used
        assert h.optimized_net_mw == pytest.approx(h.pre_dispatch_net_mw - h.total_reduction_mw, abs=1e-3)
        assert h.total_reduction_mw == pytest.approx(h.battery_reduction_mw + h.ev_reduction_mw + h.building_reduction_mw, abs=1e-3)
        assert h.remaining_deficit_mw == pytest.approx(max(0.0, h.optimized_net_mw - cap), abs=1e-3)
        assert h.pre_deficit_mw == pytest.approx(max(0.0, h.pre_dispatch_net_mw - cap), abs=1e-3)
        assert h.remaining_deficit_mw <= h.pre_deficit_mw + 1e-6                                           # never worse
        assert h.violation_after == (h.remaining_deficit_mw > 1e-6) and h.violation_before == (h.pre_deficit_mw > 1e-6)
    per_agent = np.sum([a.dispatch_mw for a in r.agents if a.included], axis=0)
    assert np.allclose(per_agent, [h.total_reduction_mw for h in r.hourly], atol=2e-3)                    # per-agent dispatch sums to the curve
    assert r.window.violation_hours_after == sum(h.violation_after for h in r.hourly if h.in_window)


@full_only
def test_only_participating_and_available_agents_dispatch():
    sc = golden_scenario()
    pop = build_population("waterloo-demo")
    rates = pop.rates(sc.assumption_overrides)
    r = run(sc)
    for a in r.agents:
        agent = pop.get(a.agent_id)
        assert a.provenance == "modeled" and a.type != "solar"
        if any(abs(x) > 1e-9 for x in a.dispatch_mw):
            assert a.included and a.participating and pop.participates(agent, rates)
        if not a.participating:
            assert not a.included and a.excluded_reason == "not_enrolled" and a.energy_mwh == 0
    assert {a.agent_id for a in r.agents if a.type != "solar"} == {a.id for a in pop.agents if a.type != "solar"}


@full_only
def test_solar_is_informational_and_does_not_change_the_result():
    sc = golden_scenario()
    base = run(sc)
    assert any(h.solar_informational_mw > 0 for h in base.hourly)
    pop = build_population("waterloo-demo")
    no_solar = popmod.Population(pop.seed, [a for a in pop.agents if a.type != "solar"], pop.scale, pop.ctx, pop.baseline_index, pop.default_rates)
    popmod.build_population.cache_clear()
    import src.capacityos.coordinator as coord
    orig = coord.build_population
    coord.build_population = lambda _w: no_solar
    try:
        other = run(sc)
    finally:
        coord.build_population = orig
    dump = lambda r: [(h.pre_dispatch_net_mw, h.optimized_net_mw, h.total_reduction_mw) for h in r.hourly]
    assert dump(base) == dump(other) and [a.dispatch_mw for a in base.agents] == [a.dispatch_mw for a in other.agents]


# ------------------------------------------------------------------ immutability
@full_only
def test_coordination_never_mutates_baseline_or_scenario():
    sc = golden_scenario()
    before_df = get_load("waterloo-demo").df.copy()
    before_sc = sc.model_dump_json()
    a0 = run_capacity_analysis(sc).model_dump_json()
    run(sc)
    run(sc)
    pd.testing.assert_frame_equal(get_load("waterloo-demo").df, before_df)
    assert store.get(sc.id).model_dump_json() == before_sc and run_capacity_analysis(sc).model_dump_json() == a0
    a = run_capacity_analysis(sc)
    assert (a.constrained_hours, a.affected_days, a.worst_deficit_mw, a.projected_peak_mw) == (268, 51, 8.0, 98.0)


# ------------------------------------------------------------------ physical constraints on real windows
@full_only
@pytest.mark.parametrize("overrides", [{}, ALL, {"battery_participation": 0.8, "ev_participation": 0.1, "building_participation": 0.6}])
def test_physical_constraints_hold_across_many_windows(overrides):
    sc = golden_scenario()
    if overrides:
        sc = store.update_assumptions(sc.id, overrides)
    pop = build_population("waterloo-demo")
    rates = pop.rates(sc.assumption_overrides)
    df, cap, _, _ = scenario_frame(sc)
    windows = sorted(run_capacity_analysis(sc).windows, key=lambda w: -w.peak_deficit_mw)[:6]
    for w in windows:
        start, end = pd.Timestamp(w.start), pd.Timestamp(w.end)
        h_end = min(end + pd.Timedelta(hours=8), df["timestamp"].iloc[-1] + pd.Timedelta(hours=1))
        horizon = [t for t in df["timestamp"] if start <= t < h_end]
        pb, excl, _ = build_problem(pop, rates, df, cap, horizon, [t < end for t in horizon])
        sol = solve(pb)
        assert sol.status in ("OPTIMAL", "FEASIBLE")
        bad = [x for x in validate(pb, sol) if not x.passed]
        assert not bad, (w.id, bad)
        for b in pb.batteries:                                                     # independent SOC / inverter recomputation
            s = sol.battery[b.id]
            assert min(s["soc"]) >= b.min_e / b.energy - 1e-6 and max(s["soc"]) <= b.max_e / b.energy + 1e-6
            assert all(d + rd <= b.power + 1e-6 for d, rd in zip(s["discharge"], b.rest_dis))
        for e in pb.evs:
            s = sol.ev[e.id]
            assert sum(s["defer"]) == pytest.approx(sum(s["recover"]), abs=1e-6)
            assert all(d <= e.shiftable * r + 1e-6 for d, r in zip(s["defer"], e.rest))
        for k in pb.buildings:
            s = sol.building[k.id]
            assert sum(1 for x in s["shed"] if x > 1e-6) <= k.max_hours
            assert all(x <= cap_t + 1e-6 for x, cap_t in zip(s["shed"], k.cap))
        assert all(x.reason for x in excl)


# ------------------------------------------------------------------ API
def test_api_simulate_event_by_window_id_and_alias():
    s = c.post("/api/scenarios", json={}).json()
    c.post(f"/api/scenarios/{s['id']}/projects", json={"type": "data_center", "nominalLoadMw": 20})
    a = c.get(f"/api/scenarios/{s['id']}/analysis").json()
    w = max(a["windows"], key=lambda x: x["peakDeficitMw"])
    r1 = c.post(f"/api/scenarios/{s['id']}/simulate/event", json={"windowId": w["id"]})
    r2 = c.post(f"/api/scenarios/{s['id']}/coordinate", json={"windowId": w["id"]})
    assert r1.status_code == r2.status_code == 200 and r1.json() == r2.json()
    body = r1.json()
    assert body["provenance"] == "derived" and body["resourcesProvenance"] == "modeled" and body["checksPassed"] and body["reconciled"]
    assert body["status"] in ("partially_resolved", "resolved") and len(body["hourly"]) == body["window"]["hours"] + body["tailHours"]
    assert c.get(f"/api/scenarios/{s['id']}/analysis").json() == a                # read-only


def test_api_explicit_window_and_validation_errors():
    s = c.post("/api/scenarios", json={}).json()
    sid = s["id"]
    ok = c.post(f"/api/scenarios/{sid}/coordinate", json={"start": "2025-06-24T08:00:00-05:00", "end": "2025-06-24T12:00:00-05:00", "tailHours": 4})
    assert ok.status_code == 200 and ok.json()["status"] == "resolved" and ok.json()["window"]["violationHoursBefore"] == 0     # baseline alone: nothing to coordinate
    assert ok.json()["includedAgents"] >= 0 and ok.json()["peakDispatchMw"] == 0
    assert c.post(f"/api/scenarios/{sid}/coordinate", json={}).status_code == 422
    assert c.post(f"/api/scenarios/{sid}/coordinate", json={"windowId": "win_nope"}).status_code == 422
    assert c.post(f"/api/scenarios/{sid}/coordinate", json={"start": "2025-06-01T00:00:00-05:00", "end": "2025-06-10T00:00:00-05:00"}).status_code == 422   # > 48 h
    assert c.post(f"/api/scenarios/{sid}/coordinate", json={"start": "1999-01-01T00:00:00-05:00", "end": "1999-01-01T05:00:00-05:00"}).status_code == 422
    assert c.post("/api/scenarios/scn-nope/coordinate", json={"windowId": "x"}).status_code == 404
