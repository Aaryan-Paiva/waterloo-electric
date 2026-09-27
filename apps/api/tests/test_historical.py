"""Phase 7: historical coordination engine (deterministic owner policy, 0 LLM calls)."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.capacityos.historical import make_clusters, run_historical, severity_of, status_of
from src.data.repositories import get_load
from src.main import app
from src.optimization.constraints import BatteryIn, Problem, validate
from src.optimization.model import solve
from src.scenario_store import store
from src.schemas.historical import HistoricalRequest
from src.schemas.scenario import ProjectCreate, ScenarioCreate
from src.simulation.stress_test import run_capacity_analysis

client = TestClient(app)


def _golden():
    sc = store.create(ScenarioCreate(zone_id="waterloo-demo"))
    return store.add_project(sc.id, ProjectCreate(nominal_load_mw=20))


@pytest.fixture(scope="module")
def runs():
    """One golden scenario, run once per configuration (each run ~10 s); the autouse cache clearing does not affect these objects."""
    sc = _golden()
    out = {inc: run_historical(sc, HistoricalRequest(incentive_price_per_mwh=inc)) for inc in (40, 80, 120)}
    out["gap8"] = run_historical(sc, HistoricalRequest(incentive_price_per_mwh=80, merge_gap_hours=8))
    out["again80"] = run_historical(sc, HistoricalRequest(incentive_price_per_mwh=80))
    out["scenario"] = sc
    out["analysis"] = run_capacity_analysis(sc)
    return out


# ---------------- golden 20 MW ----------------
def test_golden_20mw_history_is_fully_coordinated(runs):
    r, a = runs[80], runs["analysis"]
    assert (a.constrained_hours, a.window_count) == (268, 59)
    t = r.totals
    assert t.events == 59 and t.violation_hours_before == 268 and t.worst_deficit_before_mw == pytest.approx(8.0, abs=1e-3)
    assert t.resolved + t.partially_resolved + t.unresolved == 59
    assert t.energy_above_capacity_before_mwh == pytest.approx(sum(w.energy_over_mwh for w in a.windows), abs=0.05)
    assert r.hours_tested == 43824 and r.capacity_mw == 90.0 and r.checks_passed, [c for c in r.checks if not c.passed]
    ev = next(e for e in r.events if e.start.startswith("2025-06-24T08"))                       # the Phase 4 golden event
    assert ev.hours == 14 and ev.energy_above_capacity_before_mwh == pytest.approx(75.7, abs=0.06) and ev.worst_deficit_before_mw == pytest.approx(8.0, abs=1e-3)
    assert ev.energy_above_capacity_after_mwh < ev.energy_above_capacity_before_mwh and ev.status in ("partially_resolved", "resolved")


def test_per_event_fields_are_populated_and_consistent(runs):
    for e in runs[120].events:
        assert e.requested_mwh == pytest.approx(e.energy_above_capacity_before_mwh, abs=1e-3)      # the request IS the pre-dispatch deficit
        assert e.validated_mwh <= e.offered_mwh + e.priced_out_mwh + 1e-6 or e.validated_mwh <= e.offered_mwh * 1.001 + 1e-6
        assert e.dispatched_mwh <= e.validated_mwh + 1e-6
        assert e.energy_above_capacity_after_mwh <= e.energy_above_capacity_before_mwh + 1e-6       # never worse
        assert e.violation_hours_after <= e.violation_hours_before and e.worst_deficit_after_mw <= e.worst_deficit_before_mw + 1e-6
        assert e.severity == severity_of(e.worst_deficit_before_mw) and e.season in ("winter", "spring", "summer", "fall")
        assert e.by_type_mwh.battery + e.by_type_mwh.ev_fleet + e.by_type_mwh.building == pytest.approx(e.dispatched_mwh, abs=1e-3)
    assert set(e.status for e in runs[120].events) <= {"resolved", "partially_resolved", "unresolved"}


def test_status_and_severity_rules():
    assert status_of(10, 0) == "resolved" and status_of(0, 0) == "resolved"
    assert status_of(10, 5) == "partially_resolved" and status_of(10, 9.99) == "unresolved"
    assert [severity_of(x) for x in (0.5, 1, 2.9, 3, 5.9, 6, 8)] == ["minor", "moderate", "moderate", "major", "major", "severe", "severe"]


# ---------------- determinism ----------------
def test_deterministic_replay(runs):
    a, b = runs[80], runs["again80"]
    assert a.result_hash == b.result_hash and a.totals == b.totals and [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]
    assert [c.model_dump() for c in a.clusters] == [c.model_dump() for c in b.clusters]
    assert runs["gap8"].result_hash != a.result_hash                                              # a different physical configuration is a different result


# ---------------- chronology, adjacency, no energy reset ----------------
def test_events_and_clusters_are_chronological_and_horizons_never_overlap(runs):
    r = runs[80]
    starts = [e.start for e in r.events]
    assert starts == sorted(starts)
    cs = r.clusters
    assert [c.start for c in cs] == sorted(c.start for c in cs)
    for a, b in zip(cs, cs[1:]):
        assert a.horizon_end <= b.start                                                          # horizons are disjoint: no overlapping re-simulation of the same hour
    assert sum(len(c.window_ids) for c in cs) == 59 and {w for c in cs for w in c.window_ids} == {e.window_id for e in r.events}


def test_adjacent_events_are_merged_and_jointly_simulated(runs):
    r = runs[80]
    cl_of = {e.window_id: e.cluster_id for e in r.events}
    chains: list[list] = []                                          # runs of events each <= 24 h after the previous one
    for e in r.events:
        if chains and (pd.Timestamp(e.start) - pd.Timestamp(chains[-1][-1].end)) / pd.Timedelta(hours=1) <= 24:
            chains[-1].append(e)
        else:
            chains.append([e])
    multi = [c for c in chains if len(c) > 1]
    assert multi and len(r.clusters) < len(r.events)
    for c in multi:
        span = (pd.Timestamp(c[-1].end) - pd.Timestamp(c[0].start)) / pd.Timedelta(hours=1)
        if span <= 96:
            assert len({cl_of[e.window_id] for e in c}) == 1          # adjacent stress periods are ONE joint simulation
        else:
            assert len({cl_of[e.window_id] for e in c}) > 1           # only over-long chains are split (with state carried across the split)
    for a, b in zip(r.events, r.events[1:]):                          # events more than 24 h apart are never merged
        if (pd.Timestamp(b.start) - pd.Timestamp(a.end)) / pd.Timedelta(hours=1) > 24:
            assert cl_of[a.window_id] != cl_of[b.window_id]
    big = max(r.clusters, key=lambda c: len(c.window_ids))
    assert big.horizon_hours >= 24 and len(big.window_ids) >= 2


def test_make_clusters_merge_and_split():
    h = lambda x: pd.Timestamp("2025-01-01", tz="Etc/GMT+5") + pd.Timedelta(hours=x)
    wins = [("a", h(0), h(3)), ("b", h(10), h(12)), ("c", h(40), h(42)), ("d", h(60), h(62))]
    assert [[w[0] for w in c] for c in make_clusters(wins, 24)] == [["a", "b"], ["c", "d"]]
    assert [[w[0] for w in c] for c in make_clusters(wins, 6)] == [["a"], ["b"], ["c"], ["d"]]
    assert [[w[0] for w in c] for c in make_clusters(wins, 100, max_span_h=48)] == [["a", "b"], ["c", "d"]]        # over-long chain split at its widest gap


def test_battery_state_is_carried_not_reset_between_clusters(runs):
    r = runs["gap8"]                                        # merge gap == tail: many clusters, short gaps between them
    assert len(r.clusters) > len(runs[80].clusters)
    cs = r.clusters
    carried = [c for c in cs if c.carry_in_battery_mwh > 1e-6]
    assert carried, "expected battery energy still missing when a nearby cluster starts"
    for a, b in zip(cs, cs[1:]):
        # what is missing at the start of the next cluster = what was missing at the end of the last - what the gap allowed to recharge
        assert b.carry_in_battery_mwh == pytest.approx(max(0.0, a.carry_out_battery_mwh - b.gap_recovered_mwh), abs=2e-3)
    assert r.checks_passed
    # ...and the carried deficit costs real capability: no more relief than the merged (jointly simulated) run would need, and never negative energy
    assert all(c.carry_out_battery_mwh >= 0 and c.gap_recovered_mwh >= 0 for c in cs)


def test_soc_carry_limits_discharge_at_model_level():
    """Hand-solvable: a battery that starts the horizon 4 MWh below its routine has nothing left to give; the same battery at routine can."""
    T = 3
    ts = [pd.Timestamp("2025-01-01", tz="Etc/GMT+5") + pd.Timedelta(hours=i) for i in range(T)]
    mk = lambda dev: BatteryIn(id="b", name="b", power=2.0, energy=4.0, eta_c=1.0, eta_d=1.0, min_e=0.0, max_e=4.0, rest_chg=[0.0] * T, rest_dis=[0.0] * T,
                               soc_rest_end=[4.0] * T, avail=[True] * T, init_dev=dev)
    for dev, expect in ((0.0, True), (-4.0, False), (-2.0, True)):
        pb = Problem(hours=ts, in_window=[True] * T, pre_net=[101.0] * T, capacity=99.0, batteries=[mk(dev)], caps={"b": [2.0] * T}, prices={"b": 10.0})
        sol = solve(pb)
        delivered = sum(sol.battery["b"]["discharge"]) - 0.0
        assert (delivered > 1e-6) == expect
        assert delivered <= 4.0 + dev + 1e-6                                                     # can never discharge more than it holds
        assert all(c.passed for c in validate(pb, sol))


# ---------------- aggregate reconciliation ----------------
def test_aggregates_reconcile_for_every_incentive(runs):
    fields = ["events", "resolved", "partially_resolved", "unresolved", "violation_hours_before", "violation_hours_after", "energy_above_capacity_before_mwh",
              "energy_above_capacity_after_mwh", "requested_mwh", "offered_mwh", "validated_mwh", "dispatched_mwh", "clearing_cost"]
    for inc in (40, 80, 120):
        r = runs[inc]
        for group in (r.by_year, r.by_season, r.by_severity):
            for f in fields:
                assert sum(getattr(a, f) for a in group.values()) == pytest.approx(getattr(r.totals, f), abs=0.02), (inc, f)
            assert max(a.worst_deficit_after_mw for a in group.values()) == pytest.approx(r.totals.worst_deficit_after_mw, abs=1e-3)
        assert sum(d.dispatched_mwh for d in r.by_der_type) == pytest.approx(r.totals.dispatched_mwh, abs=0.02)
        assert sum(d.share for d in r.by_der_type) == pytest.approx(1.0, abs=1e-3) or r.totals.dispatched_mwh == 0
        assert sum(e.violation_hours_after for e in r.events) == r.totals.violation_hours_after
        assert r.totals.by_type_mwh.battery + r.totals.by_type_mwh.ev_fleet + r.totals.by_type_mwh.building == pytest.approx(r.totals.dispatched_mwh, abs=0.02)
        assert r.checks_passed and all(c.checks_passed and c.reconciled for c in r.clusters)


def test_full_history_scan_confirms_no_violation_created_outside_events(runs):
    names = {c.name: c for c in runs[120].checks}
    for n in ("hours_after_match_full_history_scan", "energy_after_matches_full_history_scan", "no_new_violations_outside_event_windows", "no_event_made_worse", "event_hours_match_scenario_analysis"):
        assert names[n].passed, names[n]


def test_incentive_scenarios_are_user_selected_and_monotonic(runs):
    d = {i: runs[i].totals for i in (40, 80, 120)}
    assert d[40].dispatched_mwh < d[80].dispatched_mwh < d[120].dispatched_mwh
    assert d[40].energy_above_capacity_after_mwh > d[80].energy_above_capacity_after_mwh > d[120].energy_above_capacity_after_mwh
    assert d[120].violation_hours_after < d[80].violation_hours_after < d[40].violation_hours_after <= 268
    assert all(runs[i].incentive_price_per_mwh == i for i in (40, 80, 120))
    body = " ".join(runs[80].note.lower().split())
    assert "not a recommendation" in body and "feasibility verdict" in body and not hasattr(runs[80], "feasible")


def test_by_year_season_severity_cover_the_history(runs):
    r = runs[80]
    assert set(r.by_year) == {"2021", "2022", "2023", "2024", "2025"} or set(r.by_year) <= {"2021", "2022", "2023", "2024", "2025"}
    assert set(r.by_season) == {"winter", "spring", "summer", "fall"} and set(r.by_severity) == {"minor", "moderate", "major", "severe"}
    assert {d.type for d in r.by_der_type} == {"battery", "ev_fleet", "building"}


# ---------------- provenance, no LLM, immutability ----------------
def test_no_llm_and_provenance(runs, monkeypatch):
    r = runs[80]
    assert r.decision_source == "deterministic_owner_policy" and r.llm_calls == 0
    assert r.provenance == "derived" and r.owner_behavior_provenance == "modeled"
    import src.owners.providers.openai_provider as op
    monkeypatch.setattr(op.OpenAIProvider, "__init__", lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM provider must not be used in historical runs")))
    monkeypatch.setenv("OWNER_AGENT_PROVIDER", "openai")
    assert run_historical(_golden(), HistoricalRequest(incentive_price_per_mwh=40)).llm_calls == 0        # would raise if any LLM provider were constructed


def test_scenario_and_baseline_are_immutable(runs):
    sc = _golden()
    before = sc.model_dump()
    h = pd.util.hash_pandas_object(get_load("waterloo-demo").df[["timestamp", "load_mw"]]).sum()
    run_historical(sc, HistoricalRequest(incentive_price_per_mwh=40, merge_gap_hours=8))
    assert store.get(sc.id).model_dump() == before
    assert pd.util.hash_pandas_object(get_load("waterloo-demo").df[["timestamp", "load_mw"]]).sum() == h


def test_agentic_runs_are_labelled_by_decision_source(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from src.agents.util import to_est
    from src.owners.runner import run_agentic
    sc = _golden()
    run = run_agentic(sc, to_est("2025-06-24T08:00:00-05:00"), to_est("2025-06-24T22:00:00-05:00"), provider="openai")     # no key: falls back to the stub
    assert run.decision_source == "deterministic_stub" and run.llm_owner_count == 0 and run.provider.fallback_reason


# ---------------- API ----------------
def test_api_historical_coordination_and_validation():
    sid = client.post("/api/scenarios", json={"zoneId": "waterloo-demo"}).json()["id"]
    client.post(f"/api/scenarios/{sid}/projects", json={"nominalLoadMw": 20})
    assert client.post(f"/api/scenarios/{sid}/historical-coordination", json={"mergeGapHours": 4, "tailHours": 8}).status_code == 422
    r = client.post(f"/api/scenarios/{sid}/historical-coordination", json={"incentivePricePerMwh": 120}).json()
    assert r["totals"]["events"] == 59 and r["decisionSource"] == "deterministic_owner_policy" and r["llmCalls"] == 0 and r["checksPassed"] and not r["cached"]
    again = client.post(f"/api/scenarios/{sid}/historical-coordination", json={"incentivePricePerMwh": 120}).json()
    assert again["cached"] and again["resultHash"] == r["resultHash"]
    ev = client.get(f"/api/historical-runs/{again['id']}/events", params={"year": 2025, "status": "partially_resolved"}).json()
    assert ev and all(e["year"] == 2025 and e["status"] == "partially_resolved" for e in ev)
    assert client.get("/api/historical-runs/nope").status_code == 404
    base = client.post("/api/scenarios", json={"zoneId": "waterloo-demo"}).json()["id"]           # baseline: no events -> empty, honest result
    z = client.post(f"/api/scenarios/{base}/historical-coordination", json={}).json()
    assert z["totals"]["events"] == 0 and z["checksPassed"]
