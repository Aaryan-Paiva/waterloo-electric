"""Phase 7 — Historical Coordination Engine (deterministic; NO LLM calls).

Every capacity-event window of the scenario's full history is coordinated, chronologically, with the SAME Modeled owner preferences as Agentic Mode
(the deterministic stub policy is the cached "owner policy"), the SAME physical offer validator and the SAME OR-Tools clearing.

Physical continuity (nothing resets magically between events):
  * Windows separated by <= merge_gap_hours (default 24 h, always >= the recovery tail) are merged into a CLUSTER and simulated JOINTLY: one battery
    SOC trajectory, one EV energy balance, one building comfort budget (per 24 h block) over the whole cluster, with the gap hours in between.
  * A cluster's battery SOC deviation from its routine is CARRIED to the next cluster. In the gap between clusters a battery recharges only as its
    inverter allows AND only in the zone's headroom below capacity (recharging can never create a violation). Whatever is still missing is carried in.
  * Building curtailment hours used in the previous 24 h are carried (relevant when a very long cluster is split). EV deferral must be recovered
    before departure inside the horizon, so nothing is carried for EVs.
  * Owner behavior has state too: an owner offers at most `max_events_per_month` event windows per calendar month (decline code event_frequency).
"""
import hashlib
import json
import time
import uuid
from dataclasses import replace
from typing import Optional

import pandas as pd

from ..agents.util import to_est
from ..optimization import objectives as obj
from ..optimization.constraints import optimized_net, reductions, validate
from ..optimization.dispatcher import _avg
from ..optimization.model import solve
from ..owners.context import Rejection, build_context
from ..owners.grouping import build_owners
from ..owners.physical import build_physics, profile_of
from ..owners.providers.stub import StubProvider
from ..owners.tools import execute
from ..schemas.historical import (Agg, ByType, ClusterResult, DerContribution, EventResult, HistCheck, HistoricalResult, HistoricalRequest, HourlyRow)
from ..schemas.owners import AssetOffer, Block, DeclineOffer, FlexibilityRequest, OfferBody, SubmitOffer
from ..schemas.scenario import Scenario
from ..simulation.stress_test import run_capacity_analysis, scenario_frame
from ..world.population import build_population
from .coordinator import CoordinationError

POLICY_VERSION = "owner-policy-v1 (deterministic stub economics)"
MAX_SPAN_H = 96                 # a cluster longer than this is split at its widest internal gap (state is carried across the split)
DURATION_BLOCK_H = 24
TOL = obj.TOL
SEASON = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring", 6: "summer", 7: "summer", 8: "summer", 9: "fall", 10: "fall", 11: "fall"}
SEVERITY_BOUNDS = ((1.0, "minor"), (3.0, "moderate"), (6.0, "major"))     # by the event's worst pre-dispatch deficit (MW); >= 6 => severe
_cache: "dict[tuple, HistoricalResult]" = {}
_by_id: "dict[str, HistoricalResult]" = {}
MAX_CACHED = 12


def severity_of(peak_mw: float) -> str:
    return next((name for hi, name in SEVERITY_BOUNDS if peak_mw < hi), "severe")


def status_of(pre: float, post: float) -> str:
    if pre <= TOL or post <= TOL:
        return "resolved"
    return "partially_resolved" if post < pre * 0.995 else "unresolved"


def make_clusters(wins: list[tuple], merge_gap_h: int, max_span_h: int = MAX_SPAN_H) -> list[list[tuple]]:
    """wins: [(id, start, end)] sorted. Merge when the gap is <= merge_gap_h; split over-long clusters at their widest gap."""
    gap = pd.Timedelta(hours=merge_gap_h)
    groups: list[list[tuple]] = []
    for w in wins:
        if groups and w[1] - groups[-1][-1][2] <= gap:
            groups[-1].append(w)
        else:
            groups.append([w])

    def split(g: list[tuple]) -> list[list[tuple]]:
        if len(g) < 2 or g[-1][2] - g[0][1] <= pd.Timedelta(hours=max_span_h):
            return [g]
        i = max(range(1, len(g)), key=lambda k: (g[k][1] - g[k - 1][2], -k))
        return split(g[:i]) + split(g[i:])
    return [c for g in groups for c in split(g)]


def _agg(events: list[EventResult]) -> Agg:
    a = Agg(events=len(events))
    for e in events:
        setattr(a, e.status, getattr(a, e.status) + 1)
        a.violation_hours_before += e.violation_hours_before
        a.violation_hours_after += e.violation_hours_after
        a.energy_above_capacity_before_mwh += e.energy_above_capacity_before_mwh
        a.energy_above_capacity_after_mwh += e.energy_above_capacity_after_mwh
        a.worst_deficit_before_mw = max(a.worst_deficit_before_mw, e.worst_deficit_before_mw)
        a.worst_deficit_after_mw = max(a.worst_deficit_after_mw, e.worst_deficit_after_mw)
        a.requested_mwh += e.requested_mwh
        a.offered_mwh += e.offered_mwh
        a.validated_mwh += e.validated_mwh
        a.dispatched_mwh += e.dispatched_mwh
        a.clearing_cost += e.clearing_cost
        for k in ("battery", "ev_fleet", "building"):
            setattr(a.by_type_mwh, k, getattr(a.by_type_mwh, k) + getattr(e.by_type_mwh, k))
    for f in ("energy_above_capacity_before_mwh", "energy_above_capacity_after_mwh", "requested_mwh", "offered_mwh", "validated_mwh", "dispatched_mwh", "clearing_cost"):
        setattr(a, f, round(getattr(a, f), 4))
    a.worst_deficit_before_mw, a.worst_deficit_after_mw = round(a.worst_deficit_before_mw, 4), round(a.worst_deficit_after_mw, 4)
    for k in ("battery", "ev_fleet", "building"):
        setattr(a.by_type_mwh, k, round(getattr(a.by_type_mwh, k), 4))
    return a


def _recover_gap(dev: dict, batteries: dict, pop, ts: list, net: list, cap: float, from_pos: int, to_pos: int, extra_load: dict) -> float:
    """Recharge batteries that are still below their routine, hour by hour, within inverter spare power AND zone headroom (<= capacity)."""
    recovered = 0.0
    need = sorted(k for k, v in dev.items() if v < -1e-9)
    pos = from_pos
    while need and pos < to_pos:
        t = ts[pos]
        head = max(0.0, cap - net[pos] - extra_load.get(pos, 0.0))
        for bid in list(need):
            if head <= 1e-12:
                break
            a = batteries[bid]
            st = pop.state(a, t)
            if not st.available:
                continue
            spare = max(0.0, a.power_mw - _avg(pop, a, t, "chargingMw"))
            e_in = min(spare, head, -dev[bid] / a.charge_eff)
            if e_in <= 0:
                continue
            gain = e_in * a.charge_eff
            dev[bid] += gain
            recovered += gain
            head -= e_in
            extra_load[pos] = extra_load.get(pos, 0.0) + e_in
            if dev[bid] > -1e-9:
                dev[bid] = 0.0
                need.remove(bid)
        pos += 1
    return recovered


def run_historical(scenario: Scenario, req: HistoricalRequest) -> HistoricalResult:
    if req.merge_gap_hours < req.tail_hours:
        raise CoordinationError("mergeGapHours must be >= tailHours (a recovery tail may not run into the next cluster)")
    t_run = time.perf_counter()
    inc = req.incentive_price_per_mwh
    frame = scenario_frame(scenario)
    df, cap = frame[0], frame[1]
    analysis = run_capacity_analysis(scenario)
    ts = list(df["timestamp"])
    net = [float(v) for v in df["net_mw"]]
    pos = {t: i for i, t in enumerate(ts)}
    N = len(ts)
    wins = sorted(((w.id, to_est(w.start), to_est(w.end)) for w in analysis.windows), key=lambda w: w[1])
    clusters = make_clusters(wins, req.merge_gap_hours)
    pop = build_population(scenario.zone_id)
    owners = list(build_owners(scenario.zone_id))
    batteries = {a.id: a for a in pop.agents if a.type == "battery"}
    stub = StubProvider()

    dev: dict[str, float] = {}                 # battery id -> carried deviation from routine (MWh, <= 0)
    shed_pos: dict[str, list[int]] = {}        # building id -> absolute hour positions curtailed so far
    monthly: dict[tuple, int] = {}             # (owner id, YYYY-MM) -> event windows offered
    extra_load: dict[int, float] = {}          # gap recharge load by absolute hour
    reduc: dict[int, list[float]] = {}         # absolute hour -> [battery, ev, building] net reduction
    events: list[EventResult] = []
    clus: list[ClusterResult] = []
    hourly: list[HourlyRow] = []
    delivered_by_owner_type = {"battery": 0.0, "ev_fleet": 0.0, "building": 0.0}
    cluster_ok = True
    prev_h_end: Optional[int] = None

    for ci, cl in enumerate(clusters):
        cid = f"cl-{ci + 1:03d}"
        s_pos, e_pos = pos[cl[0][1]], pos[cl[-1][2]] if cl[-1][2] in pos else N
        h_end = min(e_pos + req.tail_hours, N)
        if ci + 1 < len(clusters):
            h_end = min(h_end, pos[clusters[ci + 1][0][1]])
        gap_rec = 0.0
        if prev_h_end is not None and dev:
            gap_rec = _recover_gap(dev, batteries, pop, ts, net, cap, prev_h_end, s_pos, extra_load)
        carry_in = abs(sum(dev.values()))
        prior = {bid: sum(1 for p in v if s_pos - DURATION_BLOCK_H <= p < s_pos) for bid, v in shed_pos.items()}
        ph = build_physics(scenario, ts[s_pos], ts[e_pos - 1] + pd.Timedelta(hours=1), req.tail_hours, frame=frame, windows=[(w[1], w[2]) for w in cl],
                           horizon_end=ts[h_end] if h_end < N else ts[-1] + pd.Timedelta(hours=1), init_dev=dict(dev), prior_hours=prior, duration_period_h=DURATION_BLOCK_H)
        T = len(ph.horizon)
        pre_def = [max(0.0, net[s_pos + i] - cap) for i in range(T)]

        # --- per-window requests and per-owner decisions (deterministic policy), then ONE joint validation per owner ---
        wmeta = []
        for wid, ws, we in cl:
            o = pos[ws] - s_pos
            L = (pos[we] if we in pos else N) - pos[ws]
            hrs = [ts[pos[ws] + k].isoformat() for k in range(L)]
            reqmw = [round(pre_def[o + k], 4) for k in range(L)]
            r = FlexibilityRequest(id=f"req-{wid}", scenario_id=scenario.id, zone_id=scenario.zone_id, event_window_id=wid, start=hrs[0], end=(ts[pos[ws] + L].isoformat() if pos[ws] + L < N else hrs[-1]),
                                   hours=hrs, requested_mw_by_hour=reqmw, peak_requested_mw=max(reqmw), requested_mwh=round(sum(reqmw), 4), incentive_price_per_mwh=inc,
                                   capacity_mw=cap, created_at="")
            wmeta.append((wid, ws, o, L, r))
        committed: set[str] = set()
        accepted: dict[str, OfferBody] = {}
        offered = [0.0] * len(cl)
        offering = [0] * len(cl)
        priced_out_prof: dict[str, list[float]] = {}
        outcome = {"accepted": 0, "declined": 0, "rejected": 0, "priced_out": 0}
        for ow in owners:
            lines: dict[str, list[Block]] = {}
            prices: list[float] = []
            last_ctx = None
            for k, (wid, ws, o, L, r) in enumerate(wmeta):
                ym = (ow.id, ws.strftime("%Y-%m"))
                if monthly.get(ym, 0) >= ow.operational.max_events_per_month:
                    continue                                                                    # event_frequency: this owner has used its monthly quota
                ctx = build_context(ph, ow, r, offset=o)
                last_ctx = ctx
                act = stub.decide(ctx).action
                if isinstance(act, DeclineOffer):
                    continue
                monthly[ym] = monthly.get(ym, 0) + 1
                prices.append(act.price_per_mwh)
                offering[k] += 1
                for ln in act.asset_offers:
                    for b in ln.blocks:
                        lines.setdefault(ln.asset_id, []).append(Block(start_hour=b.start_hour + o, end_hour=b.end_hour + o, mw=b.mw))
                        offered[k] += b.mw * (b.end_hour - b.start_hour)
            if not lines:
                outcome["declined"] += 1
                continue
            body = OfferBody(asset_offers=[AssetOffer(asset_id=a, blocks=sorted(bs, key=lambda b: b.start_hour)) for a, bs in sorted(lines.items())], price_per_mwh=max(prices))
            v = execute(ph, ow, body, committed)
            if v.status == "invalid":
                r2 = stub.revise(last_ctx, Rejection(offer=body, validation=v)).action
                if isinstance(r2, DeclineOffer):
                    outcome["rejected"] += 1
                    continue
                body = OfferBody(asset_offers=r2.asset_offers, price_per_mwh=r2.price_per_mwh)
                v = execute(ph, ow, body, committed)
                if v.status == "invalid":
                    outcome["rejected"] += 1
                    continue
            if body.price_per_mwh > inc + 1e-9:
                outcome["priced_out"] += 1
                for ln in body.asset_offers:
                    priced_out_prof[ln.asset_id] = profile_of(ln.blocks, T)
                continue
            outcome["accepted"] += 1
            accepted[ow.id] = body
            committed.update(ln.asset_id for ln in body.asset_offers)

        # --- OR-Tools clearing of validated offers only ---
        caps, prices_by_asset = {}, {}
        for body in accepted.values():
            for ln in body.asset_offers:
                caps[ln.asset_id] = profile_of(ln.blocks, T)
                prices_by_asset[ln.asset_id] = body.price_per_mwh
        inc_ids = set(caps)
        pb = replace(ph.pb_all, batteries=[b for b in ph.pb_all.batteries if b.id in inc_ids], evs=[e for e in ph.pb_all.evs if e.id in inc_ids],
                     buildings=[x for x in ph.pb_all.buildings if x.id in inc_ids], caps=caps, prices=prices_by_asset)
        sol = solve(pb)
        checks = validate(pb, sol)
        ok = all(c.passed for c in checks)
        opt = optimized_net(pb, sol)
        red = reductions(pb, sol)
        cluster_ok &= ok
        post_def = [max(0.0, opt[i] - cap) for i in range(T)]
        tot = {k: [sum(x[i] for x in v) for i in range(T)] for k, v in red.items()}
        reconciled = all(abs(opt[i] - (pb.pre_net[i] - tot["battery"][i] - tot["ev_fleet"][i] - tot["building"][i])) < 1e-3 for i in range(T))
        deliver = {"battery": {b.id: sol.battery[b.id]["discharge"] for b in pb.batteries}, "ev_fleet": {e.id: sol.ev[e.id]["defer"] for e in pb.evs},
                   "building": {x.id: sol.building[x.id]["shed"] for x in pb.buildings}}
        for i in range(T):
            reduc[s_pos + i] = [tot["battery"][i], tot["ev_fleet"][i], tot["building"][i]]
            hourly.append(HourlyRow(timestamp=ph.horizon[i].isoformat(), in_window=ph.in_window[i], pre_net_mw=round(pb.pre_net[i], 4), optimized_net_mw=round(opt[i], 4),
                                    battery_mw=round(tot["battery"][i], 4), ev_mw=round(tot["ev_fleet"][i], 4), building_mw=round(tot["building"][i], 4)))
        for x in pb.buildings:
            shed_pos.setdefault(x.id, []).extend(s_pos + i for i, v in enumerate(sol.building[x.id]["shed"]) if v > 1e-6)

        # --- per-event results (window slices of the joint solution) ---
        for k, (wid, ws, o, L, r) in enumerate(wmeta):
            sl = range(o, o + L)
            pre_e, post_e = sum(pre_def[i] for i in sl), sum(post_def[i] for i in sl)
            bt = {t: sum(sum(deliver[t][a][i] for i in sl) for a in deliver[t]) for t in deliver}
            cost = sum(prices_by_asset[a] * sum(deliver[t][a][i] for i in sl) for t in deliver for a in deliver[t])
            for t, v in bt.items():
                delivered_by_owner_type[t] += v
            val_mwh = sum(sum(caps[a][i] for i in sl) for a in caps)
            po_mwh = sum(sum(p[i] for i in sl) for p in priced_out_prof.values())
            events.append(EventResult(
                window_id=wid, cluster_id=cid, start=ts[pos[ws]].isoformat(), end=(ts[pos[ws] + L].isoformat() if pos[ws] + L < N else ts[-1].isoformat()), hours=L, year=ws.year,
                season=SEASON[ws.month], severity=severity_of(max(pre_def[i] for i in sl)), status=status_of(pre_e, post_e), requested_peak_mw=r.peak_requested_mw, requested_mwh=r.requested_mwh,
                owners_offering=offering[k], offered_mwh=round(offered[k], 4), validated_mwh=round(val_mwh, 4), priced_out_mwh=round(po_mwh, 4), dispatched_mwh=round(sum(bt.values()), 4),
                dispatched_peak_mw=round(max(tot["battery"][i] + tot["ev_fleet"][i] + tot["building"][i] for i in sl), 4), clearing_cost=round(cost, 2),
                by_type_mwh=ByType(**{k2: round(v, 4) for k2, v in bt.items()}),
                violation_hours_before=sum(pre_def[i] > TOL for i in sl), violation_hours_after=sum(post_def[i] > TOL for i in sl),
                energy_above_capacity_before_mwh=round(pre_e, 4), energy_above_capacity_after_mwh=round(post_e, 4),
                worst_deficit_before_mw=round(max(pre_def[i] for i in sl), 4), worst_deficit_after_mw=round(max(post_def[i] for i in sl), 4)))

        # --- carry battery state out (never carry a surplus) ---
        for b in pb.batteries:
            d_end = sol.battery[b.id]["soc"][-1] * b.energy - b.soc_rest_end[-1]
            dev[b.id] = min(0.0, d_end)
        dev = {k: v for k, v in dev.items() if v < -1e-9}
        clus.append(ClusterResult(id=cid, window_ids=[w[0] for w in cl], start=ts[s_pos].isoformat(), end=ts[e_pos - 1].isoformat(), horizon_end=(ts[h_end].isoformat() if h_end < N else ts[-1].isoformat()),
                                  horizon_hours=T, carry_in_battery_mwh=round(carry_in, 4) + 0.0, carry_out_battery_mwh=round(-sum(dev.values()), 4) + 0.0,
                                  gap_recovered_mwh=round(gap_rec, 4), owners_accepted=outcome["accepted"], owners_declined=outcome["declined"], owners_rejected=outcome["rejected"],
                                  owners_priced_out=outcome["priced_out"], solver_status=sol.status, checks_passed=ok, reconciled=reconciled))
        prev_h_end = h_end

    # ---------------- aggregation ----------------
    totals = _agg(events)
    by_year = {str(y): _agg([e for e in events if e.year == y]) for y in sorted({e.year for e in events})}
    by_season = {s: _agg([e for e in events if e.season == s]) for s in ("winter", "spring", "summer", "fall")}
    by_sev = {s: _agg([e for e in events if e.severity == s]) for s in ("minor", "moderate", "major", "severe")}
    tot_disp = sum(delivered_by_owner_type.values())
    cost_by_type = {t: 0.0 for t in delivered_by_owner_type}
    served = {t: 0 for t in delivered_by_owner_type}
    for e in events:
        for t in delivered_by_owner_type:
            v = getattr(e.by_type_mwh, t)
            served[t] += v > 1e-6
    der = [DerContribution(type=t, dispatched_mwh=round(v, 4), share=round(v / tot_disp, 4) if tot_disp else 0.0, events_served=int(served[t]), clearing_cost=0.0) for t, v in delivered_by_owner_type.items()]

    # ---------------- independent full-history verification ----------------
    post_all = [net[i] - sum(reduc.get(i, [0, 0, 0])) + extra_load.get(i, 0.0) for i in range(N)]
    viol_after_all = sum(1 for i in range(N) if post_all[i] - cap > TOL)
    viol_before_all = sum(1 for i in range(N) if net[i] - cap > TOL)
    inside = set()
    for _, ws, we in wins:
        inside.update(range(pos[ws], pos[we] if we in pos else N))
    outside_viol = sum(1 for i in range(N) if i not in inside and post_all[i] - cap > TOL)
    energy_before_all = sum(max(0.0, net[i] - cap) for i in range(N))
    energy_after_all = sum(max(0.0, post_all[i] - cap) for i in range(N))
    fc = lambda name, ok, d="": HistCheck(name=name, passed=bool(ok), detail=d)
    close = lambda a, b: abs(a - b) < 1e-2
    checks = [
        fc("event_hours_match_scenario_analysis", totals.violation_hours_before == analysis.constrained_hours == viol_before_all, f"{totals.violation_hours_before} vs {analysis.constrained_hours}"),
        fc("event_count_matches_scenario_analysis", totals.events == analysis.window_count, f"{totals.events} vs {analysis.window_count}"),
        fc("hours_after_match_full_history_scan", totals.violation_hours_after == viol_after_all, f"{totals.violation_hours_after} vs {viol_after_all}"),
        fc("energy_after_matches_full_history_scan", close(totals.energy_above_capacity_after_mwh, energy_after_all), f"{totals.energy_above_capacity_after_mwh:.2f} vs {energy_after_all:.2f}"),
        fc("energy_before_matches_full_history_scan", close(totals.energy_above_capacity_before_mwh, energy_before_all), f"{totals.energy_above_capacity_before_mwh:.2f} vs {energy_before_all:.2f}"),
        fc("no_new_violations_outside_event_windows", outside_viol == 0, f"{outside_viol} hours"),
        fc("no_event_made_worse", all(e.energy_above_capacity_after_mwh <= e.energy_above_capacity_before_mwh + 1e-6 for e in events)),
        fc("aggregates_reconcile", all(sum(getattr(a, "dispatched_mwh") for a in g.values()) - totals.dispatched_mwh < 1e-2 and sum(a.violation_hours_after for a in g.values()) == totals.violation_hours_after
                                        and sum(a.events for a in g.values()) == totals.events for g in (by_year, by_season, by_sev))),
        fc("der_contribution_reconciles", close(sum(d.dispatched_mwh for d in der), totals.dispatched_mwh)),
        fc("all_cluster_physical_checks_passed", cluster_ok),
        fc("all_clusters_reconciled", all(c.reconciled for c in clus)),
    ]
    core = {"inc": inc, "tail": req.tail_hours, "gap": req.merge_gap_hours, "policy": POLICY_VERSION,
            "events": [(e.window_id, e.status, round(e.energy_above_capacity_after_mwh, 3), round(e.dispatched_mwh, 3), e.violation_hours_after) for e in events],
            "clusters": [(c.id, round(c.carry_in_battery_mwh, 3), round(c.carry_out_battery_mwh, 3)) for c in clus]}
    res = HistoricalResult(
        id="hist_" + uuid.uuid4().hex[:10], scenario_id=scenario.id, zone_id=scenario.zone_id, policy_version=POLICY_VERSION, incentive_price_per_mwh=inc, tail_hours=req.tail_hours,
        merge_gap_hours=req.merge_gap_hours, capacity_mw=cap, hours_tested=N, period_start=ts[0].isoformat(), period_end=(ts[-1] + pd.Timedelta(hours=1)).isoformat(), totals=totals,
        by_year=by_year, by_season=by_season, by_severity=by_sev, by_der_type=der, events=events, clusters=clus, hourly=hourly, checks=checks, checks_passed=all(c.passed for c in checks),
        result_hash=hashlib.blake2b(json.dumps(core, sort_keys=True).encode(), digest_size=8).hexdigest(), duration_ms=round((time.perf_counter() - t_run) * 1000, 1),
        note="Deterministic modeled owner policy (0 LLM calls) applied to every historical capacity-event window, chronologically, with carried battery state. "
             "Owner behavior is Modeled; results are Derived. This is a user-selected incentive scenario, NOT a recommendation and NOT a project-level feasibility verdict.")
    return res


def _key(scenario: Scenario, req: HistoricalRequest) -> tuple:
    return (json.dumps([p.model_dump(mode="json") for p in scenario.projects], sort_keys=True), scenario.zone_id, req.incentive_price_per_mwh, req.tail_hours, req.merge_gap_hours, POLICY_VERSION)


def get_or_run(scenario: Scenario, req: HistoricalRequest) -> HistoricalResult:
    k = _key(scenario, req)
    if k in _cache:
        hit = _cache[k].model_copy(update={"cached": True, "scenario_id": scenario.id})
        _by_id[hit.id] = hit
        return hit
    res = run_historical(scenario, req)
    _cache[k] = res
    _by_id[res.id] = res
    while len(_cache) > MAX_CACHED:
        _cache.pop(next(iter(_cache)))
    return res


def get_result(rid: str) -> Optional[HistoricalResult]:
    return _by_id.get(rid)


def clear_cache() -> None:
    _cache.clear()
    _by_id.clear()
