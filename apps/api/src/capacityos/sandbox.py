"""Waterloo Electric sandbox orchestration.

One call = one dropped data centre in one real season/hour. It picks the real stress day of that season (2021-2025), runs the SAME agentic pipeline
(owner policy -> physical validation -> OR-Tools clearing) on the event window, and returns a PLAYBACK SCRIPT built only from the real run trace.
Nothing here computes physics; the baseline and the world are never mutated (the scenario is a throwaway overlay).
"""
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import pandas as pd

from ..agents.util import to_est, uhash
from ..data.repositories import get_load, get_pack
from ..owners.grouping import build_owners
from ..owners.runner import run_agentic
from ..projects.data_center import make_project
from ..schemas.owners import AgenticRun, OwnerAgent
from ..schemas.sandbox import (Curve, DeviceParams, DeviceTypeInfo, SandboxRunRequest, SandboxRunResponse, SandboxWorld, ScriptStep, SeasonInfo)
from ..schemas.scenario import Scenario
from ..simulation.stress_test import run_capacity_analysis, scenario_frame
from ..world.population import build_population, use_variant
from .coordinator import CoordinationError

ZONE = "waterloo-demo"
SEASON_MONTHS = {"winter": (12, 1, 2), "spring": (3, 4, 5), "summer": (6, 7, 8), "fall": (9, 10, 11)}
GROUP_OF = {"battery_operator": "battery", "ev_aggregator": "ev", "building_portfolio": "building"}
GROUP_LABEL = {"battery": "Batteries discharge", "ev": "EV charging shifted later", "building": "Buildings and homes trim heating/cooling"}
DECLINE_TEXT = {"incentive_below_minimum": "the price is below its minimum", "event_too_long": "the event is too long", "reserve_protected": "it is protecting its reserve",
                "comfort_priority": "comfort comes first", "deadline_risk": "departure deadlines are at risk", "no_capable_assets": "none of its devices can help right now",
                "event_frequency": "it has used its monthly event quota", "other": "no feasible offer"}
APPLIED_NOW = ["fleetSizeX", "ownersEnrolledPct", "minPriceScale", "batteryReservePct", "evShiftablePct", "buildingOffsetC", "buildingMaxHours", "reboundPct"]
PENDING = ["evMaxDelayH", "dcFlexPct", "dcMaxDeferH"]


@lru_cache(maxsize=8)
def reference_day(season: str) -> pd.Timestamp:
    """The real day (2021-2025) with the highest demand in that season. Fixed, deterministic."""
    df = get_load(ZONE).df
    m = df[df["timestamp"].dt.month.isin(SEASON_MONTHS[season])]
    day = m.assign(d=m["timestamp"].dt.normalize()).groupby("d")["load_mw"].max().idxmax()
    return pd.Timestamp(day)


def seasons_info() -> dict[str, SeasonInfo]:
    df = get_load(ZONE).df.set_index("timestamp")
    out = {}
    for s in SEASON_MONTHS:
        d = reference_day(s)
        vals = [round(float(df.loc[d + pd.Timedelta(hours=h), "load_mw"]), 2) for h in range(24)]
        out[s] = SeasonInfo(reference_day=d.date().isoformat(), hourly_baseline_mw=vals, peak_mw=max(vals))
    return out


def _details(pop, owners) -> dict[str, DeviceTypeInfo]:
    of = lambda ot: sum(1 for o in owners if o.owner_type == ot)
    by = lambda t: [a for a in pop.agents if a.type == t]
    b, e, bl, so = by("battery"), by("ev_fleet"), by("building"), by("solar")
    return {
        "battery": DeviceTypeInfo(label="Batteries", clusters=len(b), total_mw=round(sum(a.power_mw for a in b), 1), total_mwh=round(sum(a.energy_mwh for a in b), 1), owners=of("battery_operator"),
                                  does="Discharge at the peak and charge off-peak, on top of their normal routine.", limits="Charge level, a reserve kept back, inverter power, round-trip losses."),
        "ev": DeviceTypeInfo(label="EV charging fleets", clusters=len(e), total_mw=round(sum(a.max_charging_mw for a in e), 1), vehicles=sum(a.vehicles for a in e), owners=of("ev_aggregator"),
                             does="Delay charging to later, then catch up before departure.", limits="Vehicles must be charged by their departure time; a shiftable share and charger power cap."),
        "building": DeviceTypeInfo(label="Buildings and homes", clusters=len(bl), total_mw=round(sum(a.peak_mw for a in bl), 1), owners=of("building_portfolio"),
                                   does="Trim heating and cooling for a few hours, then rebound.", limits="Comfort budget, longest curtailment, rebound load afterwards."),
        "solar": DeviceTypeInfo(label="Solar", clusters=len(so), total_mw=round(sum(a.installed_mw for a in so), 1), owners=0,
                                does="Generates only. Already part of the baseline demand, so it never dispatches.", limits="Sun and weather."),
    }


def world_info() -> SandboxWorld:
    pack, pop, owners = get_pack(ZONE), build_population(ZONE), build_owners(ZONE)
    dev = {t: sum(1 for a in pop.agents if a.type == t) for t in ("battery", "ev_fleet", "building", "solar")}
    return SandboxWorld(zone_id=ZONE, zone_name=pack.name, capacity_mw=pack.capacity.value_mw,
                        provenance={"demand": "derived (real IESO shape, scaled)", "devices": "modeled (synthetic)", "capacity": "modeled (assumed)", "dataCentre": "hypothetical"},
                        devices=dev, device_details=_details(pop, owners), owner_count=len(owners), seasons=seasons_info(), defaults=DeviceParams(),
                        note="A planning sandbox on real demand shape with synthetic devices. Not a forecast or an engineering study.")


@lru_cache(maxsize=16)
def _overlay(dc_mw: float):
    now = datetime.now(timezone.utc).isoformat()
    sc = Scenario(id=f"sbx-{dc_mw:g}", zone_id=ZONE, name=f"Sandbox {dc_mw:g} MW data centre", created_at=now, seed=get_pack(ZONE).der_seed, projects=[make_project("sbx-dc", dc_mw)])
    df, cap, _, _ = scenario_frame(sc)
    windows = run_capacity_analysis(sc).windows
    return sc, df, cap, windows


def owners_for(params: DeviceParams) -> list[OwnerAgent]:
    """Owner-level parameters: a deterministic enrolled subset (seeded draw per owner) and a price scale."""
    out = []
    for o in build_owners(ZONE):
        if uhash(get_pack(ZONE).der_seed, o.id, "enrol") * 100 >= params.owners_enrolled_pct:
            continue
        e = o.economic.model_copy(update={"min_compensation_per_mwh": round(o.economic.min_compensation_per_mwh * params.min_price_scale, 2)})
        out.append(o.model_copy(update={"economic": e}))
    return out


def _outcome(overload: float, absorbed: float, remaining: float) -> tuple[str, str]:
    if overload <= 1e-6:
        return "no_overload", "The zone stays within capacity at this hour."
    if remaining <= 0.05:
        return "holds", f"The flexible grid absorbed the whole {overload:.1f} MW overload."
    if absorbed / overload >= 0.25:
        return "partly_holds", f"The flexible grid absorbed {absorbed:.1f} of {overload:.1f} MW ({round(absorbed / overload * 100)}%). {remaining:.1f} MW stays over capacity."
    return "breaks", f"Flexibility ran out: only {absorbed:.1f} of {overload:.1f} MW absorbed, {remaining:.1f} MW stays over capacity."


def build_script(run: AgenticRun, focus_ts: str, inc: float) -> tuple[list[ScriptStep], dict[str, float], float, float]:
    owners = {o.id: o for o in run.owners}
    steps: list[ScriptStep] = []
    add = lambda kind, text, **kw: steps.append(ScriptStep(i=len(steps), kind=kind, text=text, **kw))
    hm = lambda iso: pd.Timestamp(iso).strftime("%H:%M")
    r = run.request
    add("request", f"Need {r.peak_requested_mw:.1f} MW between {hm(r.start)} and {hm(r.end)}. Offering up to ${inc:.0f}/MWh.", mw=r.peak_requested_mw)
    for e in run.trace:
        o = owners.get(e.owner_id) if e.owner_id else None
        if not o:
            continue
        g, p = GROUP_OF[o.owner_type], e.payload
        kw = dict(owner_id=o.id, owner_name=o.name, group=g)
        if e.type == "owner.offer_submitted" and p.get("revision") != 1:
            add("owner_offer", f"{o.name}: offering {float(p.get('peakMw', 0)):.1f} MW at ${float(p.get('pricePerMwh', 0)):.0f}/MWh.", mw=float(p.get("peakMw", 0)), price=float(p.get("pricePerMwh", 0)), **kw)
        elif e.type == "owner.declined":
            add("owner_decline", f"{o.name}: declined, {DECLINE_TEXT.get(str(p.get('reasonCode')), 'no feasible offer')}.", **kw)
        elif e.type == "offer.priced_out":
            add("owner_decline", f"{o.name}: asked ${float(p.get('pricePerMwh', 0)):.0f}/MWh, above the ceiling, so it was not cleared.", price=float(p.get("pricePerMwh", 0)), **kw)
        elif e.type == "validation.failed":
            lines = p.get("lines") or []
            rq, fs = sum(float(x.get("requestedPeakMw", 0)) for x in lines), sum(float(x.get("feasiblePeakMw", 0)) for x in lines)
            add("validation_fail", f"Physical check: {o.name} offered {rq:.1f} MW but its devices can only deliver {fs:.1f} MW ({str(p.get('violation', '')).replace('_', ' ')}).", mw=fs, **kw)
        elif e.type == "owner.revising":
            add("revision", f"{o.name}: revising the offer to what its devices can do.", **kw)
        elif e.type == "offer.accepted":
            add("accepted", f"{o.name}: accepted ({float(p.get('mwh', 0)):.1f} MWh).", mw=float(p.get("peakMw", 0)), price=float(p.get("pricePerMwh", 0)), **kw)
    add("clearing", "The optimizer is choosing who does what within every device's physical limits.")
    row = next((h for h in run.coordination.hourly if h.timestamp == focus_ts), None) or max(run.coordination.hourly, key=lambda h: h.pre_deficit_mw)
    by = {"battery": row.battery_reduction_mw, "ev": row.ev_reduction_mw, "building": row.building_reduction_mw}
    load = row.pre_dispatch_net_mw
    for g in ("battery", "ev", "building"):
        load -= by[g]
        txt = f"{GROUP_LABEL[g]}: -{by[g]:.1f} MW." if by[g] > 0.005 else (f"{GROUP_LABEL[g].split(':')[0]}: recovering earlier relief (+{-by[g]:.1f} MW)." if by[g] < -0.005 else f"{GROUP_LABEL[g]}: no relief this hour.")
        add("dispatch", txt, group=g, mw=round(by[g], 2), load_after_mw=round(load, 2))
    return steps, {k: round(v, 3) for k, v in by.items()}, row.pre_dispatch_net_mw, row.optimized_net_mw


def run_sandbox(req: SandboxRunRequest) -> SandboxRunResponse:
    sc, df, cap, windows = _overlay(round(req.dc_mw, 1))
    day = reference_day(req.season)
    target = day + pd.Timedelta(hours=req.hour)
    frame = df.set_index("timestamp")
    day_rows = frame.loc[day: day + pd.Timedelta(hours=23)]
    base = float(frame.at[target, "baseline_mw"])
    before_load = float(frame.at[target, "net_mw"])
    common = dict(season=req.season, hour=req.hour, date_used=day.date().isoformat(), dc_mw=req.dc_mw, base_mw=round(base, 2), capacity_mw=cap,
                  params_applied=APPLIED_NOW, params_pending=PENDING,
                  provenance={"demand": "derived", "devices": "modeled", "capacity": "modeled", "dataCentre": "hypothetical", "results": "derived"},
                  note="Simulation on the real demand shape with synthetic devices. Not a forecast, recommendation or engineering study.")
    curve = Curve(hours=list(range(24)), before=[round(float(v), 2) for v in day_rows["net_mw"]], after=[round(float(v), 2) for v in day_rows["net_mw"]])

    def calm(text: str) -> SandboxRunResponse:
        return SandboxRunResponse(focus_timestamp=target.isoformat(), load_before_mw=round(before_load, 2), load_after_mw=round(before_load, 2), overload_mw=0.0, has_overload=False,
                                  absorbed_mw=0.0, remaining_mw=0.0, outcome="no_overload", outcome_text=text, dispatch_by_group={"battery": 0.0, "ev": 0.0, "building": 0.0},
                                  script=[ScriptStep(i=0, kind="done", text=text)], curve=curve, owners_total=0, owners_accepted=0, event_energy_before_mwh=0.0,
                                  event_energy_after_mwh=0.0, decision_source="none", checks_passed=True, **common)

    day_end = day + pd.Timedelta(hours=24)
    wins = [w for w in windows if to_est(w.start) < day_end and to_est(w.end) > day]
    if not wins:
        return calm(f"With a {req.dc_mw:g} MW data centre the zone stays within capacity all day ({req.season}). Try a bigger one to find where it breaks.")
    win = next((w for w in wins if to_est(w.start) <= target < to_est(w.end)), None)
    if win is None:
        return calm(f"At {target.strftime('%H:%M')} the zone is within capacity ({before_load:.1f} of {cap:g} MW). The overload is at other hours of the day.")
    w_start, w_end = max(to_est(win.start), day), min(to_est(win.end), day_end)            # a long overload is played one day at a time
    dp = req.device_params
    key = (round(dp.fleet_size_x, 2), round(dp.battery_reserve_pct), round(dp.ev_shiftable_pct), round(dp.building_offset_c, 1), dp.building_max_hours, round(dp.rebound_pct))
    try:
        with use_variant(key):
            run = run_agentic(sc, w_start, w_end, None, req.incentive_per_mwh, req.provider, 8, owners_override=owners_for(dp))
    except CoordinationError as e:
        raise ValueError(str(e))
    script, by, pre, post = build_script(run, target.isoformat(), req.incentive_per_mwh)
    overload = round(max(0.0, pre - cap), 1)                 # one decimal everywhere, so the numbers on screen add up
    remaining = round(max(0.0, post - cap), 1)
    absorbed = round(max(0.0, overload - remaining), 1)
    outcome, text = _outcome(overload, absorbed, remaining)
    opt = {pd.Timestamp(h.timestamp): h.optimized_net_mw for h in run.coordination.hourly}
    after = [round(opt.get(t, float(v)), 2) for t, v in zip(day_rows.index, day_rows["net_mw"])]
    script.append(ScriptStep(i=len(script), kind="done", text=text, load_after_mw=round(post, 2)))
    w = run.coordination.window
    return SandboxRunResponse(focus_timestamp=target.isoformat(), load_before_mw=round(pre, 2), load_after_mw=round(post, 2), overload_mw=round(overload, 2), has_overload=True,
                              absorbed_mw=round(absorbed, 2), remaining_mw=round(remaining, 2), outcome=outcome, outcome_text=text, dispatch_by_group=by, script=script,
                              curve=Curve(hours=list(range(24)), before=curve.before, after=after), owners_total=run.market.owners_total, owners_accepted=run.market.owners_accepted,
                              event_energy_before_mwh=w.energy_above_capacity_before_mwh, event_energy_after_mwh=w.energy_above_capacity_after_mwh,
                              decision_source=run.decision_source, checks_passed=run.coordination.checks_passed, run_id=run.id, **common)
