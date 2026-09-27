"""Phase 5-6: owner/operator agents, providers, physical offer validation, revision, clearing, modes, state integrity, API."""
import copy
import json
from dataclasses import replace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src import settings
from src.agents.util import to_est
from src.capacityos.coordinator import AgenticInputs, coordinate_event, resolve_window
from src.data.repositories import get_load
from src.main import app
from src.optimization.constraints import Problem, validate
from src.optimization.model import solve
from src.owners.context import OwnerContext, Rejection, build_context
from src.owners.grouping import build_owners, owner_of
from src.owners.physical import blocks_of, build_physics, profile_of, validate_offer
from src.owners.providers import OpenAIProvider, ProviderError, ProviderUnavailable, StubProvider, get_provider
from src.owners.providers.base import ProviderResult
from src.owners.runner import build_request, replay_run, run_agentic
from src.scenario_store import store
from src.schemas.owners import AssetOffer, Block, DeclineOffer, OfferBody, ReviseOffer, SubmitOffer
from src.schemas.scenario import ProjectCreate, ScenarioCreate
from src.world.population import build_population

client = TestClient(app)
WS, WE = "2025-06-24T08:00:00-05:00", "2025-06-24T22:00:00-05:00"


@pytest.fixture
def golden(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sc = store.create(ScenarioCreate(zone_id="waterloo-demo"))
    sc = store.add_project(sc.id, ProjectCreate(nominal_load_mw=20))
    s, e = resolve_window(sc, None, WS, WE)
    return sc, s, e


@pytest.fixture
def physics(golden):
    sc, s, e = golden
    return build_physics(sc, s, e, 8)


def owner(aid):
    return next(o for o in build_owners("waterloo-demo") if aid in o.controlled_asset_ids)


def offer(aid, blocks, price=50.0):
    return OfferBody(asset_offers=[AssetOffer(asset_id=aid, blocks=blocks)], price_per_mwh=price)


class ScriptedProvider:
    """Test provider: returns fixed actions per owner (first decide, then revise)."""
    name, model = "scripted", "scripted"

    def __init__(self, decide, revise=None):
        self._decide, self._revise = decide, revise

    def decide(self, ctx):
        return ProviderResult(self._decide(ctx))

    def revise(self, ctx, rj):
        return ProviderResult((self._revise or self._decide)(ctx, rj) if self._revise else self._decide(ctx))


# ---------------- owner grouping ----------------
def test_owner_grouping_is_deterministic_and_complete():
    owners = build_owners("waterloo-demo")
    assert 15 <= len(owners) <= 25
    pop = build_population("waterloo-demo")
    flexible = sorted(a.id for a in pop.agents if a.type != "solar")
    controlled = sorted(x for o in owners for x in o.controlled_asset_ids)
    assert controlled == flexible                      # every flexible asset has exactly one owner; solar has none
    assert all(o.provenance == "modeled" for o in owners)
    assert all(pop.get(x) is not None for o in owners for x in o.controlled_asset_ids)
    build_owners.cache_clear()
    again = build_owners("waterloo-demo")
    assert [o.model_dump() for o in owners] == [o.model_dump() for o in again]
    assert owner_of("waterloo-demo", "solar_001") is None


def test_owner_preferences_are_bounded_and_type_specific():
    for o in build_owners("waterloo-demo"):
        assert o.economic.min_compensation_per_mwh > 0 and 0 < o.economic.target_margin < 1
        assert 0 <= o.behavioral.risk_tolerance <= 1 and 0 <= o.behavioral.participation_tendency <= 1
        if o.owner_type == "battery_operator":
            assert o.operational.degradation_sensitivity > 0 and o.operational.comfort_priority == 0
        if o.owner_type == "building_portfolio":
            assert o.operational.comfort_priority > 0 and o.operational.degradation_sensitivity == 0
        if o.owner_type == "ev_aggregator":
            assert o.operational.driver_satisfaction_priority > 0 and o.operational.deadline_strictness > 0


def test_unauthorized_owner_cannot_offer_another_owners_asset(physics):
    a, b = build_owners("waterloo-demo")[0], build_owners("waterloo-demo")[1]
    foreign = b.controlled_asset_ids[0]
    v = validate_offer(physics, a, offer(foreign, [Block(start_hour=6, end_hour=7, mw=0.05)]), set())
    assert v.status == "invalid" and v.violation == "not_owned"


# ---------------- physical validation ----------------
def test_valid_offer_accepted(physics):
    aid = "battery_004"
    c = physics.ceilings[aid]
    t = max(range(len(c)), key=lambda i: c[i])
    v = validate_offer(physics, owner(aid), offer(aid, [Block(start_hour=t, end_hour=t + 1, mw=0.5 * c[t])]), set())
    assert v.status == "valid"


def _long_flat_battery_offer(physics):
    """A battery asset offered its lowest per-hour ceiling for the whole 14 h event: fine per hour, impossible in energy."""
    pop = physics.pop
    for aid, c in sorted(physics.ceilings.items()):
        a = pop.get(aid)
        if a.type == "battery" and min(c[:14]) > 0.05 and a.duration_h <= 2.0:
            return aid, offer(aid, [Block(start_hour=0, end_hour=14, mw=min(c[:14]))])
    pytest.skip("no suitable battery")


def test_impossible_battery_offer_rejected_with_feasible_envelope(physics):
    aid, bad = _long_flat_battery_offer(physics)
    v = validate_offer(physics, owner(aid), bad, set())
    assert v.status == "invalid" and v.lines[0].violation == "insufficient_usable_energy"
    env = v.lines[0].feasible_envelope
    assert 0 < sum(profile_of(env, 14)) < sum(profile_of(bad.asset_offers[0].blocks, 14))
    assert validate_offer(physics, owner(aid), offer(aid, env), set()).status == "valid"     # the reported envelope is itself physically valid


def test_exceeding_power_or_shiftable_limit_rejected(physics):
    aid = "battery_004"
    t = max(range(14), key=lambda i: physics.ceilings[aid][i])
    v = validate_offer(physics, owner(aid), offer(aid, [Block(start_hour=t, end_hour=t + 1, mw=physics.ceilings[aid][t] * 3)]), set())
    assert v.violation == "exceeds_power_limit"
    ev = "ev_fleet_002"
    t = max(range(14), key=lambda i: physics.ceilings[ev][i])
    v = validate_offer(physics, owner(ev), offer(ev, [Block(start_hour=t, end_hour=t + 1, mw=physics.ceilings[ev][t] * 3)]), set())
    assert v.violation == "exceeds_shiftable_fraction"


def test_ev_deadline_violation_rejected(physics):
    ev = "ev_fleet_002"
    t = max(range(14), key=lambda i: physics.ceilings[ev][i])
    pb = copy.deepcopy(physics.pb_all)
    e = next(x for x in pb.evs if x.id == ev)
    for k in range(len(e.avail)):
        if k != t:
            e.avail[k] = False                          # vehicles are only plugged in during the offered hour: deferred energy can be neither recovered nor pre-charged
    ph = replace(physics, pb_all=pb)
    v = validate_offer(ph, owner(ev), offer(ev, [Block(start_hour=t, end_hour=t + 1, mw=0.5 * physics.ceilings[ev][t])]), set())
    assert v.status == "invalid" and v.violation == "deadline_energy_violation"
    assert v.lines[0].feasible_envelope == []


def test_building_comfort_duration_violation_rejected(physics):
    b = "building_001"
    c = physics.ceilings[b]
    hrs = [t for t, x in enumerate(c[:14]) if x > 0]
    max_h = physics.pb_all.buildings[0].max_hours
    assert len(hrs) > max_h
    v = validate_offer(physics, owner(b), offer(b, [Block(start_hour=t, end_hour=t + 1, mw=c[t]) for t in hrs]), set())
    assert v.violation == "comfort_duration_violation"
    env_hours = sum(1 for x in profile_of(v.lines[0].feasible_envelope, 14) if x > 0)
    assert 0 < env_hours <= max_h


def test_unavailable_asset_and_bad_inputs_rejected(physics):
    ev = "ev_fleet_002"
    t = next(i for i in range(14) if physics.ceilings[ev][i] == 0)
    v = validate_offer(physics, owner(ev), offer(ev, [Block(start_hour=t, end_hour=t + 1, mw=0.1)]), set())
    assert v.violation == "asset_unavailable"
    o = owner("battery_004")
    assert validate_offer(physics, o, offer("battery_004", [Block(start_hour=10, end_hour=30, mw=0.1)]), set()).violation == "outside_event_window"
    assert validate_offer(physics, o, offer("solar_001", [Block(start_hour=0, end_hour=1, mw=0.1)]), set()).violation == "not_owned"
    assert validate_offer(physics, o, offer("battery_004", [Block(start_hour=6, end_hour=7, mw=0.1)], price=-1), set()).violation == "invalid_price"
    ok = offer("battery_004", [Block(start_hour=6, end_hour=7, mw=0.05)])
    assert validate_offer(physics, o, ok, {"battery_004"}).violation == "already_committed"


# ---------------- stub provider ----------------
def _ctx(golden, physics, oid, incentive=80.0):
    sc, s, e = golden
    req = build_request(sc, physics, None, incentive)
    o = next(x for x in build_owners("waterloo-demo") if x.id == oid)
    return build_context(physics, o, req)


def test_stub_is_deterministic_and_offers_or_declines(golden, physics):
    ctx = _ctx(golden, physics, "owner_battery_04")
    a1, a2 = StubProvider().decide(ctx).action, StubProvider().decide(ctx).action
    assert a1.model_dump() == a2.model_dump() and isinstance(a1, SubmitOffer)
    low = _ctx(golden, physics, "owner_battery_04", incentive=5.0)
    d = StubProvider().decide(low).action
    assert isinstance(d, DeclineOffer) and d.reason_code == "incentive_below_minimum"


def test_stub_counteroffer_is_priced_out(golden):
    sc, s, e = golden
    seen = False
    for inc in (60, 70, 85, 95, 105):
        run = run_agentic(sc, s, e, incentive=inc)
        seen |= any(r.status == "priced_out" and r.offers[-1].counteroffer for r in run.records)
    assert seen


def test_stub_revision_uses_feasible_envelope(golden):
    sc, s, e = golden
    run = run_agentic(sc, s, e, incentive=80)
    revised = [r for r in run.records if len(r.offers) == 2]
    assert revised, "expected at least one physical rejection followed by a revision"
    for r in revised:
        assert r.offers[0].status == "revised" and r.offers[0].validation.status == "invalid"
        assert r.offers[0].validation.violation
        assert r.offers[1].revision == 1 and r.offers[1].validation.status == "valid"
        assert r.offers[1].peak_mw <= r.offers[0].peak_mw + 1e-9
    assert any(t.type == "validation.failed" for t in run.trace) and any(t.type == "owner.revising" for t in run.trace)


# ---------------- revision is bounded ----------------
def test_repeated_invalid_revision_terminates_safely(golden):
    sc, s, e = golden
    aid = "battery_004"
    o = owner(aid)

    def over(ctx, *_):
        if ctx.owner.id != o.id:
            return DeclineOffer(reason_code="other", explanation="not me")
        return SubmitOffer(asset_offers=[AssetOffer(asset_id=aid, blocks=[Block(start_hour=0, end_hour=14, mw=5.0)])], price_per_mwh=50)

    calls = {"n": 0}

    def revise(ctx, rj):
        calls["n"] += 1
        return ReviseOffer(asset_offers=[AssetOffer(asset_id=aid, blocks=[Block(start_hour=0, end_hour=14, mw=4.0)])], price_per_mwh=50)

    run = run_agentic(sc, s, e, provider_override=ScriptedProvider(over, revise))
    rec = next(r for r in run.records if r.owner_id == o.id)
    assert rec.status == "rejected" and calls["n"] == 1 and len(rec.offers) == 2      # exactly one revision turn
    assert not any(a.included for a in run.coordination.agents)                        # nothing invalid reached the optimizer
    assert run.coordination.status == "unresolved" and run.coordination.checks_passed
    assert next(a for a in run.coordination.agents if a.agent_id == aid).excluded_reason.startswith("offer_rejected")


# ---------------- optimizer integration ----------------
def test_only_validated_offers_enter_and_dispatch_respects_offers(golden):
    sc, s, e = golden
    run = run_agentic(sc, s, e, incentive=100)
    c = run.coordination
    accepted = {ln.asset_id: ln for r in run.records for o in r.offers if o.status == "accepted" for ln in o.body.asset_offers}
    assert accepted
    for a in c.agents:
        if a.included:
            assert a.agent_id in accepted
            cap = profile_of(accepted[a.agent_id].blocks, 14)
            delivering = {"battery": "dischargeMw", "ev_fleet": "deferMw", "building": "shedMw"}[a.type]
            for t, x in enumerate(a.series[delivering][:14]):
                assert x <= cap[t] + 1e-6                                                # never exceeds the offer
            assert all(x <= 1e-9 for x in a.series[delivering][14:])                      # nothing delivered outside the offered hours
        else:
            assert a.dispatch_mw and all(abs(x) < 1e-9 for x in a.dispatch_mw)
    assert c.checks_passed and c.reconciled and c.mode == "agentic"
    assert any(ch.name == "offer_cap_respected" and ch.passed for ch in c.checks)      # physical checks still enforced on top
    for h in c.hourly:
        assert abs(h.optimized_net_mw - (h.pre_dispatch_net_mw - h.total_reduction_mw)) < 1e-3
        assert h.remaining_deficit_mw <= h.pre_deficit_mw + 1e-6                        # do no harm


def test_clearing_cost_reconciles_and_is_priced(golden):
    sc, s, e = golden
    run = run_agentic(sc, s, e, incentive=100)
    c = run.coordination
    assert c.clearing_cost == pytest.approx(sum(a.price_per_mwh * a.delivered_mwh for a in c.agents if a.included), abs=0.05 * len(c.agents))
    assert run.market.clearing_cost == c.clearing_cost
    m = run.market
    assert m.validated_mwh <= m.offered_mwh + m.priced_out_mwh + 1e-6 and m.dispatched_mwh <= m.validated_mwh + 1e-6


def test_cost_is_a_tiebreaker_never_traded_against_violations():
    """Two identical batteries, one expensive: the deficit needs both, so cost must not reduce the relief."""
    from src.optimization.constraints import BatteryIn
    T = 3
    mk = lambda i: BatteryIn(id=f"b{i}", name=f"b{i}", power=1.0, energy=4.0, eta_c=1.0, eta_d=1.0, min_e=0.0, max_e=4.0, rest_chg=[0.0] * T, rest_dis=[0.0] * T,
                             soc_rest_end=[4.0] * T, avail=[True] * T)
    pb = Problem(hours=[pd.Timestamp("2025-01-01", tz="Etc/GMT+5") + pd.Timedelta(hours=i) for i in range(T)], in_window=[True] * T, pre_net=[101.0] * T, capacity=99.0,
                 batteries=[mk(1), mk(2)], caps={"b1": [1.0] * T, "b2": [1.0] * T}, prices={"b1": 10.0, "b2": 900.0})
    sol = solve(pb)
    assert max(sol.slack) < 1e-6                                   # 2 MW needed, both used despite the expensive one
    assert all(c.passed for c in validate(pb, sol))
    pb.pre_net = [100.0] * T                                        # only 1 MW needed: the cheap battery is chosen
    sol = solve(pb)
    assert sum(sol.battery["b1"]["discharge"]) > sum(sol.battery["b2"]["discharge"]) + 2.5


def test_incentive_changes_owner_decisions_without_a_hardcoded_curve(golden):
    sc, s, e = golden
    disp = {inc: run_agentic(sc, s, e, incentive=inc).market.dispatched_mwh for inc in (10, 40, 80, 120)}
    assert disp[10] == 0.0 and disp[40] < disp[80] < disp[120]
    assert run_agentic(sc, s, e, incentive=10).coordination.status == "unresolved"


# ---------------- modes / providers ----------------
def test_manual_mode_unchanged_and_needs_no_llm(golden):
    sc, s, e = golden
    r = coordinate_event(sc, s, e)
    assert r.mode == "manual" and r.clearing_cost is None
    assert r.window.energy_above_capacity_before_mwh == pytest.approx(75.7, abs=0.06) and r.window.energy_above_capacity_after_mwh == pytest.approx(67.3, abs=0.06)
    assert r.status == "partially_resolved"


def test_agentic_stub_runs_without_api_key(golden, monkeypatch):
    monkeypatch.setenv("OWNER_AGENT_PROVIDER", "stub")
    sc, s, e = golden
    run = run_agentic(sc, s, e)
    assert run.provider.used == "stub" and run.diagnostics.failed_calls == 0 and run.diagnostics.agent_calls >= 18


def test_openai_absent_fails_gracefully(golden, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderUnavailable):
        get_provider("openai")
    sc, s, e = golden
    run = run_agentic(sc, s, e, provider="openai")
    assert run.provider.requested == "openai" and run.provider.used == "stub" and "OPENAI_API_KEY" in run.provider.fallback_reason
    assert any(t.type == "provider.fallback" for t in run.trace)


class _Fn:
    def __init__(self, name, args): self.name, self.arguments = name, args


class _TC:
    def __init__(self, name, args, i="call_1"): self.id, self.function = i, _Fn(name, args if isinstance(args, str) else json.dumps(args))


class _Msg:
    def __init__(self, tcs): self.tool_calls, self.content = tcs, ""


class _Resp:
    def __init__(self, tcs): self.choices = [type("C", (), {"message": _Msg(tcs)})()]; self.usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 5})()


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.chat = type("Chat", (), {"completions": self})()

    def create(self, **kw):
        nxt = self.script.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return _Resp(nxt)


def test_openai_provider_parses_structured_tool_calls(golden, physics):
    ctx = _ctx(golden, physics, "owner_battery_04")
    args = {"assetOffers": [{"assetId": "battery_004", "blocks": [{"startHour": 6, "endHour": 8, "mw": 0.1}]}], "pricePerMwh": 70, "conditions": [], "explanation": "ok"}
    p = OpenAIProvider(client=FakeClient([[_TC("submit_offer", args)]]), model="x")
    r = p.decide(ctx)
    assert isinstance(r.action, SubmitOffer) and r.action.price_per_mwh == 70 and r.input_tokens == 10
    # request_information is answered from the owner's OWN assets only, then the model decides
    ri = _TC("request_information", {"assetIds": ["battery_004", "building_001"]}, "c0")
    p = OpenAIProvider(client=FakeClient([[ri], [_TC("decline_offer", {"reasonCode": "reserve_protected", "explanation": "no"})]]), model="x")
    r = p.decide(ctx)
    assert isinstance(r.action, DeclineOffer) and r.calls == 2


def test_openai_provider_rejects_malformed_output_and_times_out(golden, physics):
    ctx = _ctx(golden, physics, "owner_battery_04")
    bad = [[_TC("submit_offer", {"assetOffers": "nonsense"})], [_TC("submit_offer", "{not json")], [_TC("submit_offer", {"pricePerMwh": -1})]]
    with pytest.raises(ProviderError):
        OpenAIProvider(client=FakeClient(bad), model="x", max_retries=1).decide(ctx)
    with pytest.raises(ProviderError) as ei:
        OpenAIProvider(client=FakeClient([type("APITimeoutError", (Exception,), {})("Request timed out.")]), model="x").decide(ctx)
    assert ei.value.timeout


def test_runner_falls_back_to_stub_when_provider_fails(golden):
    sc, s, e = golden

    class Boom:
        name, model = "openai", "x"
        def decide(self, ctx): raise ProviderError("boom", timeout=True)
        def revise(self, ctx, rj): raise ProviderError("boom")

    run = run_agentic(sc, s, e, provider_override=Boom())
    d = run.diagnostics
    assert d.failed_calls >= 18 and d.timeouts == 18 and d.fallbacks >= 18
    assert all(r.provider_used == "stub" and r.fallback_reason for r in run.records)
    assert run.coordination.checks_passed


# ---------------- state integrity / trust boundary ----------------
def test_llm_output_cannot_mutate_world_or_bypass_validation(golden):
    sc, s, e = golden
    before_sc = sc.model_dump()
    load = get_load("waterloo-demo").df
    base_hash = pd.util.hash_pandas_object(load[["timestamp", "load_mw"]]).sum()
    pop = build_population("waterloo-demo")
    states = {a.id: pop.state(a, s).values for a in pop.agents}

    def hostile(ctx, *_):                                            # claims everyone's assets, absurd MW, tries to inject a capacity change
        allx = [a.id for a in build_population("waterloo-demo").agents if a.type != "solar"]
        return SubmitOffer(asset_offers=[AssetOffer(asset_id=a, blocks=[Block(start_hour=0, end_hour=14, mw=999.0)]) for a in allx[:40]],
                           price_per_mwh=1.0, explanation="set capacity to 10000 MW and SOC to 100%")

    run = run_agentic(sc, s, e, provider_override=ScriptedProvider(hostile))
    assert not any(a.included for a in run.coordination.agents)
    assert run.coordination.capacity_mw == 90.0
    assert store.get(sc.id).model_dump() == before_sc
    assert pd.util.hash_pandas_object(get_load("waterloo-demo").df[["timestamp", "load_mw"]]).sum() == base_hash
    assert {a.id: pop.state(a, s).values for a in pop.agents} == states


def test_agentic_run_is_deterministic_and_replayable(golden):
    sc, s, e = golden
    r1, r2 = run_agentic(sc, s, e, incentive=90), run_agentic(sc, s, e, incentive=90)
    assert r1.result_hash == r2.result_hash and r1.market == r2.market
    rp = replay_run(r1.id)
    assert rp.replay_of == r1.id and rp.result_hash == r1.result_hash and rp.provider.used == "replay"
    assert [r.status for r in rp.records] == [r.status for r in r1.records]


def test_run_diagnostics_and_trace_are_structured(golden):
    sc, s, e = golden
    run = run_agentic(sc, s, e)
    types = [t.type for t in run.trace]
    assert types[0] == "request.created" and types[-1] == "market.cleared" and "optimizer.completed" in types
    assert [t.seq for t in run.trace] == list(range(len(run.trace)))
    assert run.diagnostics.duration_ms > 0 and run.request.provenance == "derived" and run.owner_behavior_provenance == "modeled"
    assert "sk-" not in json.dumps(run.model_dump(by_alias=True, mode="json"))


# ---------------- API ----------------
def _api_scenario():
    sid = client.post("/api/scenarios", json={"zoneId": "waterloo-demo"}).json()["id"]
    client.post(f"/api/scenarios/{sid}/projects", json={"nominalLoadMw": 20})
    return sid


def test_api_owner_agents_and_config():
    sid = _api_scenario()
    j = client.get(f"/api/scenarios/{sid}/owner-agents").json()
    assert 15 <= len(j["owners"]) <= 25 and j["flexibleAssets"] == 70 and len(j["unownedAssets"]) == 8
    assert j["owners"][0]["provenance"] == "modeled"
    cfg = client.get("/api/agentic/config").json()
    assert cfg["stubAvailable"] is True and "openaiAvailable" in cfg and "apiKey" not in json.dumps(cfg).lower()


def test_api_agentic_run_flow():
    sid = _api_scenario()
    win = client.get(f"/api/scenarios/{sid}/analysis").json()["windows"]
    w = next(x for x in win if x["start"].startswith("2025-06-24T08"))
    req = client.post(f"/api/scenarios/{sid}/events/{w['id']}/flexibility-request", json={"incentivePricePerMwh": 85}).json()
    assert req["peakRequestedMw"] == pytest.approx(8.0, abs=0.01) and req["incentivePricePerMwh"] == 85 and req["provenance"] == "derived"
    run = client.post(f"/api/scenarios/{sid}/events/{w['id']}/agentic-run", json={"incentivePricePerMwh": 85}).json()
    assert run["mode"] == "agentic" and run["coordination"]["checksPassed"] and run["market"]["requestedPeakMw"] == pytest.approx(8.0, abs=0.01)
    rid = run["id"]
    assert client.get(f"/api/agentic-runs/{rid}").json()["resultHash"] == run["resultHash"]
    assert len(client.get(f"/api/agentic-runs/{rid}/offers").json()) >= 1
    assert client.get(f"/api/agentic-runs/{rid}/dispatch").json()["mode"] == "agentic"
    assert client.get(f"/api/agentic-runs/{rid}/trace").json()[0]["type"] == "request.created"
    rp = client.post(f"/api/agentic-runs/{rid}/replay").json()
    assert rp["resultHash"] == run["resultHash"] and rp["replayOf"] == rid
    # the baseline scenario is untouched by agentic runs
    assert client.get(f"/api/scenarios/{sid}").json()["projects"][0]["nominalLoadMw"] == 20


def test_api_errors():
    sid = client.post("/api/scenarios", json={"zoneId": "waterloo-demo"}).json()["id"]          # baseline: no violations anywhere
    r = client.post(f"/api/scenarios/{sid}/agentic-run", json={"start": WS, "end": WE})
    assert r.status_code == 422 and "no capacity violation" in r.text
    assert client.get("/api/agentic-runs/run_nope").status_code == 404
    assert client.get("/api/scenarios/scn-nope/owner-agents").status_code == 404
    assert client.post(f"/api/scenarios/{sid}/events/nope/agentic-run", json={}).status_code == 422
