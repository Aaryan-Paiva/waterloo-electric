"""Agentic run orchestration: an explicit, bounded, deterministic state machine (no agent framework; see ARCHITECTURE.md).

  receive_request -> inspect_assets -> owner_decision -> [decline] | submit_offer -> physical_validation
       -> valid: price check -> accepted | priced_out
       -> invalid: ONE revision -> physical_validation -> accepted | priced_out | rejected
  then: OR-Tools clearing over the accepted offers only -> validated physical dispatch.

LLM/provider output only ever becomes a typed action; deterministic code owns validation, clearing and all world state.
"""
import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable, Optional

import pandas as pd

from ..capacityos.coordinator import AgenticInputs, CoordinationError, check_window, coordinate_event
from ..schemas.coordination import CoordinationResult
from ..schemas.owners import (AgenticRun, DeclineOffer, Diagnostics, FlexibilityRequest, MarketSummary, OfferBody, OfferRecord, OwnerAgent, OwnerRecord,
                              ProviderInfo, TraceEvent)
from ..schemas.scenario import Scenario
from .context import OwnerContext, Rejection, build_context
from .grouping import build_owners
from .physical import Physics, build_physics, profile_of
from .providers import OwnerAgentProvider, ProviderError, ProviderResult, ProviderUnavailable, StubProvider, get_provider
from .run_store import StoredRun, runs
from .tools import execute

MAX_WORKERS = 8


def build_request(scenario: Scenario, ph: Physics, window_id: Optional[str], incentive: float) -> FlexibilityRequest:
    W = ph.window_hours
    net = {t: float(v) for t, v in zip(ph.df["timestamp"], ph.df["net_mw"])}
    hours = ph.horizon[:W]
    req_mw = [round(max(0.0, net[t] - ph.capacity), 4) for t in hours]
    if sum(req_mw) <= 1e-9:
        raise CoordinationError("no capacity violation in this window: nothing to request")
    start, end = hours[0], hours[-1] + pd.Timedelta(hours=1)
    rid = "req_" + hashlib.blake2b(f"{scenario.id}|{start.isoformat()}|{end.isoformat()}|{incentive}".encode(), digest_size=5).hexdigest()
    return FlexibilityRequest(id=rid, scenario_id=scenario.id, zone_id=scenario.zone_id, event_window_id=window_id, start=start.isoformat(), end=end.isoformat(),
                              hours=[t.isoformat() for t in hours], requested_mw_by_hour=req_mw, peak_requested_mw=max(req_mw), requested_mwh=round(sum(req_mw), 4),
                              incentive_price_per_mwh=incentive, capacity_mw=ph.capacity, created_at=datetime.now(timezone.utc).isoformat())


def _peak_mwh(profiles: list[list[float]], W: int) -> tuple[float, float]:
    tot = [sum(p[t] for p in profiles) for t in range(W)]
    return round(max(tot, default=0.0), 4), round(sum(tot), 4)


def _resolve_provider(requested: str, override: Optional[OwnerAgentProvider]) -> tuple[OwnerAgentProvider, ProviderInfo]:
    if override is not None:
        return override, ProviderInfo(requested=override.name, used=override.name, model=override.model)
    try:
        p = get_provider(requested)
        return p, ProviderInfo(requested=requested, used=p.name, model=p.model)
    except ProviderUnavailable as e:
        s = StubProvider()
        return s, ProviderInfo(requested=requested, used="stub", model=s.model, fallback_reason=str(e))


def run_agentic(scenario: Scenario, w_start: pd.Timestamp, w_end: pd.Timestamp, window_id: Optional[str] = None, incentive: float = 80.0,
                provider: Optional[str] = None, tail_hours: int = 8, provider_override: Optional[OwnerAgentProvider] = None,
                replay_of: Optional[str] = None, owners_override: Optional[list[OwnerAgent]] = None,
                on_progress: Optional[Callable[[dict], None]] = None) -> AgenticRun:
    from .. import settings
    t_run = time.perf_counter()
    ph = build_physics(scenario, w_start, w_end, tail_hours)
    check_window(ph.df, w_start, w_end)
    request = build_request(scenario, ph, window_id, incentive)
    owners = list(owners_override) if owners_override is not None else list(build_owners(scenario.zone_id))
    prov, pinfo = _resolve_provider(provider or settings.owner_agent_config()["provider"], provider_override)
    stub = StubProvider()
    W = ph.window_hours

    trace: list[TraceEvent] = []
    emit = lambda typ, owner=None, **payload: trace.append(TraceEvent(seq=len(trace), type=typ, owner_id=owner, payload=payload))
    emit("request.created", requestId=request.id, peakRequestedMw=request.peak_requested_mw, requestedMwh=request.requested_mwh,
         incentivePricePerMwh=incentive, start=request.start, end=request.end, provider=pinfo.used)
    if pinfo.fallback_reason:
        emit("provider.fallback", reason=pinfo.fallback_reason, requested=pinfo.requested, used=pinfo.used)

    contexts: dict[str, OwnerContext] = {o.id: build_context(ph, o, request) for o in owners}
    stats = {"calls": 0, "failed": 0, "timeouts": 0, "fallbacks": 0, "in": 0, "out": 0}
    actions: dict[str, list] = {}

    def call(fn, *args):
        t0 = time.perf_counter()
        try:
            return fn(*args), None, (time.perf_counter() - t0) * 1000
        except ProviderError as e:
            return None, e, (time.perf_counter() - t0) * 1000
        except Exception as e:                                        # noqa: BLE001 — never let a provider bug break the run
            return None, ProviderError(f"{type(e).__name__}: {e}"), (time.perf_counter() - t0) * 1000

    # phase 1: owner decisions (parallel only for network providers; the stub / replay are instant and stay sequential)
    if prov.name in ("stub", "replay"):
        first = {o.id: call(prov.decide, contexts[o.id]) for o in owners}
    else:
        names = {o.id: o.name for o in owners}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(call, prov.decide, contexts[o.id]): o.id for o in owners}
            first = {}
            for n, f in enumerate(as_completed(futs), 1):                # stream each owner's decision as soon as it returns
                oid = futs[f]
                first[oid] = f.result()
                if on_progress:
                    res_, err_, ms_ = first[oid]
                    kind = "fallback" if err_ else "declined" if isinstance(res_.action, DeclineOffer) else "offered"
                    on_progress({"type": "owner", "ownerId": oid, "ownerName": names[oid], "status": kind, "done": n, "total": len(owners), "ms": round(ms_)})

    def account(res: Optional[ProviderResult], err: Optional[ProviderError]) -> None:
        if res:
            stats["calls"] += res.calls
            stats["in"] += res.input_tokens or 0
            stats["out"] += res.output_tokens or 0
        if err:
            stats["calls"] += 1
            stats["failed"] += 1
            stats["timeouts"] += 1 if err.timeout else 0

    committed: set[str] = set()
    records: list[OwnerRecord] = []
    accepted: dict[str, tuple[OfferBody, str]] = {}            # owner_id -> (body, offer id)
    asset_reason: dict[str, str] = {}
    first_offers: list[list[float]] = []                        # profiles of first submissions (=> "offered")

    for o in owners:
        ctx = contexts[o.id]
        emit("owner.evaluating", o.id, assets=len(o.controlled_asset_ids))
        res, err, ms = first[o.id]
        account(res, err)
        used, fb = prov.name, None
        if err:
            stats["fallbacks"] += 1
            fb = f"{prov.name} failed ({err}); deterministic stub used for this owner"
            emit("provider.fallback", o.id, reason=fb)
            res, _, ms2 = call(stub.decide, ctx)
            ms += ms2
            used = "stub"
        acts = [res.action]
        rec = OwnerRecord(owner_id=o.id, status="evaluating", provider_used=used, fallback_reason=fb, agent_calls=res.calls if not err else 1, duration_ms=round(ms, 1))
        action = res.action

        if isinstance(action, DeclineOffer):
            rec.status, rec.decline_code, rec.decision_explanation = "declined", action.reason_code, action.explanation
            emit("owner.declined", o.id, reasonCode=action.reason_code, explanation=action.explanation)
            for a in o.controlled_asset_ids:
                asset_reason[a] = "owner_declined"
            actions[o.id] = acts
            records.append(rec)
            continue

        rec.decision_explanation = action.explanation
        body: OfferBody = action
        prof0 = [sum(profile_of(ln.blocks, W)[t] for ln in body.asset_offers) for t in range(W)]
        first_offers.append(prof0)
        emit("owner.offer_submitted", o.id, pricePerMwh=body.price_per_mwh, assets=len(body.asset_offers), peakMw=round(max(prof0), 4), mwh=round(sum(prof0), 4),
             explanation=body.explanation)
        final: Optional[OfferBody] = None
        revision = 0
        while True:
            v = execute(ph, o, body, committed)
            peak = round(max(sum(profile_of(ln.blocks, W)[t] for ln in body.asset_offers) for t in range(W)), 4)
            mwh = round(sum(sum(profile_of(ln.blocks, W)) for ln in body.asset_offers), 4)
            oid = f"offer_{o.id}_{revision}"
            if v.status == "valid":
                emit("validation.passed", o.id, revision=revision, mwh=mwh)
                if body.price_per_mwh > incentive + 1e-9:
                    rec.offers.append(OfferRecord(id=oid, owner_id=o.id, revision=revision, body=body, validation=v, status="priced_out", counteroffer=True, offered_mwh=mwh, peak_mw=peak))
                    rec.status = "priced_out"
                    emit("offer.priced_out", o.id, pricePerMwh=body.price_per_mwh, incentive=incentive)
                    for ln in body.asset_offers:
                        asset_reason[ln.asset_id] = "priced_out"
                else:
                    rec.offers.append(OfferRecord(id=oid, owner_id=o.id, revision=revision, body=body, validation=v, status="accepted", offered_mwh=mwh, peak_mw=peak))
                    rec.status = "accepted"
                    final = body
                    accepted[o.id] = (body, oid)
                    committed.update(ln.asset_id for ln in body.asset_offers)
                    emit("offer.accepted", o.id, mwh=mwh, peakMw=peak, pricePerMwh=body.price_per_mwh)
                break
            emit("validation.failed", o.id, revision=revision, violation=v.violation, explanation=v.explanation,
                 lines=[{"assetId": x.asset_id, "violation": x.violation, "requestedPeakMw": max((b.mw for b in x.requested), default=0.0),
                         "feasiblePeakMw": max((b.mw for b in x.feasible_envelope), default=0.0)} for x in v.lines if x.status == "invalid"])
            if revision == 1:                                                    # bounded: exactly one revision turn
                rec.offers.append(OfferRecord(id=oid, owner_id=o.id, revision=revision, body=body, validation=v, status="rejected", offered_mwh=mwh, peak_mw=peak))
                rec.status = "rejected"
                emit("offer.rejected", o.id, violation=v.violation)
                for a in o.controlled_asset_ids:
                    asset_reason[a] = f"offer_rejected: {v.violation}"
                break
            rec.offers.append(OfferRecord(id=oid, owner_id=o.id, revision=revision, body=body, validation=v, status="revised", offered_mwh=mwh, peak_mw=peak))
            rec.status = "revising"
            emit("owner.revising", o.id, violation=v.violation)
            rj = Rejection(offer=body, validation=v)
            r2, e2, ms3 = call(prov.revise, ctx, rj)
            account(r2, e2)
            rec.duration_ms = round(rec.duration_ms + ms3, 1)
            if e2:
                stats["fallbacks"] += 1
                emit("provider.fallback", o.id, reason=f"{prov.name} revise failed ({e2}); stub used")
                r2, _, _ = call(stub.revise, ctx, rj)
                rec.fallback_reason = (rec.fallback_reason or "") + f" revise: {e2}"
            else:
                rec.agent_calls += r2.calls
            acts.append(r2.action)
            if isinstance(r2.action, DeclineOffer):
                rec.status, rec.decline_code, rec.decision_explanation = "rejected", r2.action.reason_code, r2.action.explanation
                emit("owner.declined", o.id, reasonCode=r2.action.reason_code, explanation=r2.action.explanation, afterRejection=True)
                for a in o.controlled_asset_ids:
                    asset_reason[a] = f"offer_rejected: {v.violation}"
                break
            body, revision = r2.action, 1
            rec.decision_explanation = body.explanation or rec.decision_explanation
            emit("owner.offer_submitted", o.id, revision=1, pricePerMwh=body.price_per_mwh, assets=len(body.asset_offers), explanation=body.explanation)
        actions[o.id] = acts
        records.append(rec)

    # clearing: ONLY physically validated, priced-in offers reach OR-Tools
    include, caps, prices, owner_of = set(), {}, {}, {}
    for o in owners:
        for a in o.controlled_asset_ids:
            owner_of[a] = o.id
    for oid, (body, _) in accepted.items():
        for ln in body.asset_offers:
            include.add(ln.asset_id)
            caps[ln.asset_id] = profile_of(ln.blocks, W)
            prices[ln.asset_id] = body.price_per_mwh
    for o in owners:
        for a in o.controlled_asset_ids:
            asset_reason.setdefault(a, "not_offered_by_owner" if a not in include else "")
    emit("optimizer.started", assets=len(include), owners=len(accepted))
    coord = coordinate_event(scenario, w_start, w_end, tail_hours, AgenticInputs(include, caps, prices, owner_of, {k: v for k, v in asset_reason.items() if v}))
    emit("optimizer.completed", status=coord.status, remainingWorstDeficitMw=coord.window.worst_deficit_after_mw, clearingCost=coord.clearing_cost, checksPassed=coord.checks_passed)
    by_agent = {a.agent_id: a for a in coord.agents}
    for rec in records:
        mine = [by_agent[a] for a in next(x.controlled_asset_ids for x in owners if x.id == rec.owner_id) if a in by_agent and by_agent[a].included]
        rec.dispatched_mwh = round(sum(a.delivered_mwh or 0.0 for a in mine), 4)
        rec.cost = round(sum(a.cost or 0.0 for a in mine), 2)
        if rec.dispatched_mwh > 1e-6:
            emit("agent.dispatched", rec.owner_id, mwh=rec.dispatched_mwh, cost=rec.cost)
    emit("market.cleared", status=coord.status, dispatchedPeakMw=coord.peak_dispatch_mw, clearingCost=coord.clearing_cost)

    market = _market(request, records, first_offers, accepted, coord, W, incentive)
    ident = json.dumps({"accepted": {k: [b.model_dump(by_alias=True, mode="json"), ] for k, (b, _) in sorted(accepted.items())},
                        "net": [h.optimized_net_mw for h in coord.hourly]}, sort_keys=True)
    diag = Diagnostics(agent_calls=stats["calls"], failed_calls=stats["failed"], timeouts=stats["timeouts"], fallbacks=stats["fallbacks"],
                       duration_ms=round((time.perf_counter() - t_run) * 1000, 1), input_tokens=stats["in"] or None, output_tokens=stats["out"] or None)
    n_llm = sum(1 for r_ in records if r_.provider_used == "openai")
    if pinfo.used == "openai" and n_llm < len(records):                  # never claim an LLM run when owners actually fell back to the stub
        first_fb = next((r_.fallback_reason for r_ in records if r_.fallback_reason), None)
        pinfo = ProviderInfo(requested=pinfo.requested, used="stub" if n_llm == 0 else "openai (partial)", model=pinfo.model if n_llm else stub.model,
                             fallback_reason=(first_fb or "")[:300] or None)
    src_label = "replay" if pinfo.used == "replay" else "llm_openai" if n_llm == len(records) and n_llm else "mixed_llm_and_stub" if n_llm else "deterministic_stub"
    run = AgenticRun(id="run_" + uuid.uuid4().hex[:10], replay_of=replay_of, scenario_id=scenario.id, provider=pinfo, request=request, owners=owners, records=records, trace=trace,
                     market=market, coordination=coord, diagnostics=diag,
                     decision_source=src_label, llm_owner_count=n_llm, result_hash=hashlib.blake2b(ident.encode(), digest_size=8).hexdigest(),
                     note="Owner/operator decisions are Modeled synthetic behavior (not predictions of real customers); requests, validation and clearing are Derived. "
                          "Only physically validated offers reached the optimizer; the optimizer's own physical constraints were enforced on top.")
    runs.put(StoredRun(run, actions, w_start.isoformat(), w_end.isoformat(), window_id, incentive, tail_hours))
    return run


def _market(request, records, first_offers, accepted, coord: CoordinationResult, W: int, incentive: float) -> MarketSummary:
    off_peak, off_mwh = _peak_mwh(first_offers, W)
    val = [profile_of(ln.blocks, W) for body, _ in accepted.values() for ln in body.asset_offers]
    val_peak, val_mwh = _peak_mwh(val, W)
    po = sum(r.offers[-1].offered_mwh for r in records if r.status == "priced_out")
    disp = round(sum(a.delivered_mwh or 0.0 for a in coord.agents), 4)
    st = lambda s: sum(1 for r in records if r.status == s)
    return MarketSummary(requested_peak_mw=request.peak_requested_mw, requested_mwh=request.requested_mwh, offered_peak_mw=off_peak, offered_mwh=off_mwh,
                         validated_peak_mw=val_peak, validated_mwh=val_mwh, priced_out_mwh=round(po, 4), dispatched_peak_mw=coord.peak_dispatch_mw, dispatched_mwh=disp,
                         remaining_worst_deficit_mw=coord.window.worst_deficit_after_mw, remaining_energy_above_capacity_mwh=coord.window.energy_above_capacity_after_mwh,
                         clearing_cost=coord.clearing_cost or 0.0, incentive_price_per_mwh=incentive, owners_total=len(records),
                         owners_offered=sum(1 for r in records if r.offers), owners_declined=st("declined"), owners_rejected=st("rejected"),
                         owners_priced_out=st("priced_out"), owners_accepted=st("accepted"))


def replay_run(run_id: str) -> AgenticRun:
    """Re-executes a stored run from its RECORDED owner actions (no model). Physical validation and clearing run again from scratch."""
    from ..scenario_store import store
    from .providers.replay import ReplayProvider
    s = runs.get(run_id)
    if s is None:
        raise KeyError(run_id)
    sc = store.get(s.run.scenario_id)
    from ..agents.util import to_est
    return run_agentic(sc, to_est(s.window_start), to_est(s.window_end), s.window_id, s.incentive, None, s.tail_hours,
                       provider_override=ReplayProvider(s.actions, s.run.provider.model), replay_of=run_id)
