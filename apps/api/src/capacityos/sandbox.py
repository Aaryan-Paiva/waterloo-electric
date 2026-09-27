"""Waterloo Electric sandbox orchestration.

One call = one dropped data centre in one real season/hour. It picks the real stress day of that season (2021-2025), runs the SAME agentic pipeline
(owner policy -> physical validation -> OR-Tools clearing) on the event window, and returns a PLAYBACK SCRIPT built only from the real run trace.
Nothing here computes physics; the baseline and the world are never mutated (the scenario is a throwaway overlay).
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache
from typing import Callable, Optional

import pandas as pd

from ..agents.util import to_est, uhash
from ..data.repositories import get_load, get_pack
from ..owners.grouping import build_owners
from ..owners.runner import run_agentic
from ..projects.loads import make_load
from ..schemas.owners import AgenticRun, OwnerAgent
from ..schemas.sandbox import (Curve, MarketLog, OwnerLog, DeviceParams, DeviceTypeInfo, LoadSpec, MatrixRequest, MatrixResponse, SeasonCell, SandboxRunRequest, SandboxRunResponse, SandboxWorld, ScriptStep, SeasonInfo)
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
APPLIED_NOW = ["fleetSizeX", "batteryCount", "evFleetCount", "buildingCount", "solarCount", "ownersEnrolledPct", "minPriceScale", "batteryReservePct", "evShiftablePct", "buildingOffsetC", "buildingMaxHours", "reboundPct"]
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


def variant_key(dp: DeviceParams) -> tuple:
    return (round(dp.fleet_size_x, 2), round(dp.battery_reserve_pct), round(dp.ev_shiftable_pct), round(dp.building_offset_c, 1), dp.building_max_hours, round(dp.rebound_pct),
            dp.battery_count, dp.ev_fleet_count, dp.building_count, dp.solar_count)


def world_info(dp: Optional[DeviceParams] = None) -> SandboxWorld:
    """The world as the sandbox sees it for a given device configuration (defaults: the visible 60/42/108/24 clusters)."""
    with use_variant(variant_key(dp or DeviceParams())):
        return _world_info()


def llm_available() -> bool:
    from ..owners.providers import provider_status
    return bool(provider_status()["openaiAvailable"])


def _world_info() -> SandboxWorld:
    pack, pop, owners = get_pack(ZONE), build_population(ZONE), build_owners(ZONE)
    dev = {t: sum(1 for a in pop.agents if a.type == t) for t in ("battery", "ev_fleet", "building", "solar")}
    return SandboxWorld(zone_id=ZONE, zone_name=pack.name, capacity_mw=pack.capacity.value_mw,
                        provenance={"demand": "derived (real IESO shape, scaled)", "devices": "modeled (synthetic)", "capacity": "modeled (assumed)", "dataCentre": "hypothetical"},
                        devices=dev, device_details=_details(pop, owners), owner_count=len(owners), seasons=seasons_info(), defaults=DeviceParams(), llm_available=llm_available(),
                        note="A planning sandbox on real demand shape with synthetic devices. Not a forecast or an engineering study.")


def _norm_loads(req: SandboxRunRequest) -> tuple[tuple[str, float], ...]:
    loads = req.loads or [LoadSpec(kind="data_centre", size=req.dc_mw)]
    return tuple(sorted((l.kind, round(float(l.size), 1)) for l in loads))


@lru_cache(maxsize=32)
def _overlay(loads: tuple[tuple[str, float], ...]):
    """Throwaway scenario: the dropped loads on the real baseline. Never stored; the world is untouched."""
    now = datetime.now(timezone.utc).isoformat()
    projects = [make_load(f"sbx-{i}", k, sz) for i, (k, sz) in enumerate(loads)]
    sc = Scenario(id="sbx-" + "-".join(f"{k}{sz:g}" for k, sz in loads), zone_id=ZONE, name="Sandbox loads", created_at=now, seed=get_pack(ZONE).der_seed, projects=projects)
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


CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "sandbox"
_mem: dict[str, SandboxRunResponse] = {}


def _cache_key(req: SandboxRunRequest, loads) -> str:
    body = {"s": req.season, "h": req.hour, "l": [list(x) for x in loads], "p": req.provider, "i": req.incentive_per_mwh, "d": req.device_params.model_dump(mode="json")}
    return hashlib.blake2b(json.dumps(body, sort_keys=True).encode(), digest_size=10).hexdigest()


def _cache_get(key: str) -> Optional[SandboxRunResponse]:
    """Decision cache: a repeated constraint set replays the same owner decisions (real LLM runs are slow and cost credits). In memory, plus disk for LLM runs."""
    if key in _mem:
        return _mem[key]
    f = CACHE_DIR / f"{key}.json"
    try:
        if f.exists():
            _mem[key] = SandboxRunResponse.model_validate_json(f.read_text())
            return _mem[key]
    except Exception:                                                                     # noqa: BLE001 — a bad cache file is just a miss
        pass
    return None


def _cache_put(key: str, r: SandboxRunResponse) -> None:
    _mem[key] = r
    if r.decision_source in ("llm_openai", "mixed_llm_and_stub"):
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            (CACHE_DIR / f"{key}.json").write_text(r.model_dump_json(by_alias=True))
        except OSError:
            pass


def owner_log(run: AgenticRun) -> list[OwnerLog]:
    by_rec = {r.owner_id: r for r in run.records}
    out = []
    for o in run.owners:
        r = by_rec.get(o.id)
        if r is None:
            continue
        last = r.offers[-1] if r.offers else None
        status = "fallback" if r.fallback_reason and not r.offers else r.status
        out.append(OwnerLog(owner_id=o.id, name=o.name, group=GROUP_OF[o.owner_type], assets=len(o.controlled_asset_ids), status=status,
                            offered_mw=round(last.peak_mw, 2) if last else 0.0, price_per_mwh=round(last.body.price_per_mwh, 1) if last else None,
                            dispatched_mwh=round(r.dispatched_mwh, 2), cost=round(r.cost, 2), explanation=(r.decision_explanation or "")[:260],
                            source="openai" if r.provider_used == "openai" else "stub"))
    return out


def market_log(run: AgenticRun) -> MarketLog:
    m, d = run.market, run.diagnostics
    return MarketLog(requested_peak_mw=m.requested_peak_mw, requested_mwh=m.requested_mwh, offered_mwh=m.offered_mwh, validated_mwh=m.validated_mwh, dispatched_mwh=m.dispatched_mwh,
                     priced_out_mwh=m.priced_out_mwh, clearing_cost=m.clearing_cost, incentive_per_mwh=m.incentive_price_per_mwh, owners_offered=m.owners_offered,
                     owners_declined=m.owners_declined, owners_rejected=m.owners_rejected, owners_priced_out=m.owners_priced_out, owners_accepted=m.owners_accepted,
                     agent_calls=d.agent_calls, duration_ms=d.duration_ms)


def run_sandbox(req: SandboxRunRequest, on_progress: Optional[Callable[[dict], None]] = None) -> SandboxRunResponse:
    loads = _norm_loads(req)
    ck = _cache_key(req, loads)
    hit = _cache_get(ck)
    if hit is not None:
        return hit.model_copy(update={"cached": True})
    r = _run_sandbox(req, loads, on_progress)
    _cache_put(ck, r)
    return r


def _run_sandbox(req: SandboxRunRequest, loads, on_progress) -> SandboxRunResponse:
    sc, df, cap, windows = _overlay(loads)
    day = reference_day(req.season)
    target = day + pd.Timedelta(hours=req.hour)
    frame = df.set_index("timestamp")
    day_rows = frame.loc[day: day + pd.Timedelta(hours=23)]
    base = float(frame.at[target, "baseline_mw"])
    before_load = float(frame.at[target, "net_mw"])
    common = dict(season=req.season, hour=req.hour, date_used=day.date().isoformat(), dc_mw=round(float(frame.at[target, "project_mw"]), 2), loads=[LoadSpec(kind=k, size=sz) for k, sz in loads], base_mw=round(base, 2), capacity_mw=cap,
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
        return calm(f"With these loads the zone stays within capacity all day ({req.season}). Try a bigger one to find where it breaks.")
    win = next((w for w in wins if to_est(w.start) <= target < to_est(w.end)), None)
    if win is None:
        return calm(f"At {target.strftime('%H:%M')} the zone is within capacity ({before_load:.1f} of {cap:g} MW). The overload is at other hours of the day.")
    w_start, w_end = max(to_est(win.start), day), min(to_est(win.end), day_end)            # a long overload is played one day at a time
    dp = req.device_params
    key = variant_key(dp)
    try:
        with use_variant(key):
            run = run_agentic(sc, w_start, w_end, None, req.incentive_per_mwh, req.provider, 8, owners_override=owners_for(dp), on_progress=on_progress)
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
                              decision_source=run.decision_source, checks_passed=run.coordination.checks_passed, run_id=run.id, owner_log=owner_log(run), market=market_log(run), **common)


def run_matrix(req: MatrixRequest) -> MatrixResponse:
    """The same constraint set against every season's real reference day (one run per season; each run covers the whole day, so every hour of it is answered)."""
    from concurrent.futures import ThreadPoolExecutor

    loads = req.loads or [LoadSpec(kind="data_centre", size=req.dc_mw)]
    key = tuple(sorted((l.kind, round(float(l.size), 1)) for l in loads))
    _, df, cap, _ = _overlay(key)
    frame = df.set_index("timestamp")

    def one(season: str) -> SeasonCell:
        day = reference_day(season)
        net = frame.loc[day: day + pd.Timedelta(hours=23), "net_mw"]
        peak_hour = int(net.reset_index(drop=True).idxmax())
        r = None
        if req.provider == "openai":                                             # the season test reuses real LLM decisions only when they are already cached; it never fans out 4x18 live calls
            sr = SandboxRunRequest(season=season, hour=peak_hour, loads=loads, provider="openai", incentive_per_mwh=req.incentive_per_mwh, device_params=req.device_params)
            r = _cache_get(_cache_key(sr, _norm_loads(sr)))
        r = r or run_sandbox(SandboxRunRequest(season=season, hour=peak_hour, loads=loads, provider="stub", incentive_per_mwh=req.incentive_per_mwh, device_params=req.device_params))
        before, after = r.curve.before, r.curve.after
        states = ["within" if b <= cap + 1e-6 else "absorbed" if a <= cap + 0.05 else "over" for b, a in zip(before, after)]
        rank = {"within": 0, "absorbed": 1, "over": 2}
        per = {name: max(states[a:b], key=lambda x: rank[x]) for name, (a, b) in {"morning": (6, 12), "afternoon": (12, 18), "evening": (18, 24)}.items()}
        overload = round(max(0.0, max(before) - cap), 1)                       # judged over the WHOLE day: the worst hour before and after
        remaining = round(max(0.0, max(after) - cap), 1) if overload > 0 else 0.0
        absorbed = round(max(0.0, overload - remaining), 1)
        outcome, text = _outcome(overload, absorbed, remaining)
        return SeasonCell(season=season, date_used=r.date_used, peak_hour=peak_hour, outcome=outcome, outcome_text=text, peak_load_mw=round(max(before), 2), peak_load_after_mw=round(max(after), 2),
                          overload_mw=overload, absorbed_mw=absorbed, remaining_mw=remaining, hours_over_before=sum(b > cap + 1e-6 for b in before),
                          hours_over_after=sum(a > cap + 0.05 for a in after), hour_states=states, periods=per, decision_source=r.decision_source, owners_accepted=r.owners_accepted, owners_total=r.owners_total)

    order = ["winter", "spring", "summer", "fall"]
    with ThreadPoolExecutor(max_workers=4) as ex:
        cells = list(ex.map(one, order))
    return MatrixResponse(capacity_mw=cap, loads=[LoadSpec(kind=k, size=sz) for k, sz in key], cells=cells, params_applied=APPLIED_NOW,
                          provenance={"demand": "derived", "devices": "modeled", "capacity": "modeled", "results": "derived"},
                          note="Each cell is the real highest-demand day of that season (2021-2025) with your loads and device settings. A stress test on history, not a forecast.")
