"""Single-event DER coordination (CLAUDE.md §18-19). Deterministic; never mutates the baseline or the scenario.

request -> detect violations in the window -> eligible agents (participating AND available) -> OR-Tools dispatch
-> recompute net load -> resolved / partially_resolved / unresolved. No project-level feasibility claim is made here.
"""
import pandas as pd

from dataclasses import dataclass, field
from typing import Optional

from ..agents.util import to_est
from ..optimization import objectives as obj
from ..optimization.constraints import optimized_net, reductions, validate
from ..optimization.dispatcher import build_problem
from ..optimization.model import solve
from ..schemas.coordination import AgentDispatch, Check, CoordinationResult, HourRow, WindowMetrics
from ..schemas.scenario import Scenario
from ..simulation.stress_test import scenario_frame
from ..world.population import build_population

MAX_WINDOW_HOURS = 48
TOL = obj.TOL


class CoordinationError(ValueError):
    pass


@dataclass
class AgenticInputs:
    """Agentic clearing inputs: ONLY physically validated offers. `caps[id][t]` caps the delivering variable, `prices[id]` is $/MWh."""
    include: set[str]
    caps: dict[str, list[float]]
    prices: dict[str, float]
    owner_of: dict[str, str] = field(default_factory=dict)
    reasons: dict[str, str] = field(default_factory=dict)      # asset id -> why it is not in the clearing (declined, rejected, priced_out, ...)


def _metrics(rows: list[dict], mask: list[bool]) -> WindowMetrics:
    sel = [r for r, m in zip(rows, mask) if m]
    return WindowMetrics(hours=len(sel), violation_hours_before=sum(r["pre_def"] > TOL for r in sel), violation_hours_after=sum(r["post_def"] > TOL for r in sel),
                         energy_above_capacity_before_mwh=round(sum(r["pre_def"] for r in sel), 4), energy_above_capacity_after_mwh=round(sum(r["post_def"] for r in sel), 4),
                         worst_deficit_before_mw=round(max((r["pre_def"] for r in sel), default=0.0), 4), worst_deficit_after_mw=round(max((r["post_def"] for r in sel), default=0.0), 4))


def resolve_window(scenario: Scenario, window_id: str | None, start: str | None, end: str | None) -> tuple[pd.Timestamp, pd.Timestamp]:
    if window_id:
        from ..simulation.stress_test import run_capacity_analysis
        w = next((x for x in run_capacity_analysis(scenario).windows if x.id == window_id), None)
        if w is None:
            raise CoordinationError(f"unknown event window {window_id!r} for this scenario")
        return to_est(w.start), to_est(w.end)
    if not (start and end):
        raise CoordinationError("provide windowId, or both start and end")
    return to_est(start), to_est(end)


def check_window(df: pd.DataFrame, w_start: pd.Timestamp, w_end: pd.Timestamp) -> None:
    first, last = df["timestamp"].iloc[0], df["timestamp"].iloc[-1]
    if not (first <= w_start < w_end <= last + pd.Timedelta(hours=1)):
        raise CoordinationError(f"window must lie inside the historical period {first.isoformat()} .. {last.isoformat()}")
    if (w_end - w_start) > pd.Timedelta(hours=MAX_WINDOW_HOURS):
        raise CoordinationError(f"window longer than {MAX_WINDOW_HOURS} hours")


def coordinate_event(scenario: Scenario, w_start: pd.Timestamp, w_end: pd.Timestamp, tail_hours: int = 8, agentic: Optional[AgenticInputs] = None) -> CoordinationResult:
    df, cap, _, _ = scenario_frame(scenario)
    first, last = df["timestamp"].iloc[0], df["timestamp"].iloc[-1]
    if not (first <= w_start < w_end <= last + pd.Timedelta(hours=1)):
        raise CoordinationError(f"window must lie inside the historical period {first.isoformat()} .. {last.isoformat()}")
    if (w_end - w_start) > pd.Timedelta(hours=MAX_WINDOW_HOURS):
        raise CoordinationError(f"window longer than {MAX_WINDOW_HOURS} hours")
    h_end = min(w_end + pd.Timedelta(hours=tail_hours), last + pd.Timedelta(hours=1))
    horizon = [t for t in df["timestamp"] if w_start <= t < h_end]
    in_window = [t < w_end for t in horizon]

    pop = build_population(scenario.zone_id)
    rates = pop.rates(scenario.assumption_overrides)
    pb, excl, solar = build_problem(pop, rates, df, cap, horizon, in_window, include=agentic.include if agentic else None)
    if agentic:
        T0 = len(horizon)
        pb.caps = {k: (list(v) + [0.0] * T0)[:T0] for k, v in agentic.caps.items()}
        pb.prices = dict(agentic.prices)
    sol = solve(pb)
    checks = validate(pb, sol)
    net = optimized_net(pb, sol)
    red = reductions(pb, sol)

    frame = df.set_index("timestamp")
    n = len(horizon)
    tot = {k: [sum(s[i] for s in v) for i in range(n)] for k, v in red.items()}
    rows, hourly = [], []
    for i, t in enumerate(horizon):
        pre = pb.pre_net[i]
        pre_def, post_def = max(0.0, pre - cap), max(0.0, net[i] - cap)
        rows.append({"pre_def": pre_def, "post_def": post_def})
        total = tot["battery"][i] + tot["ev_fleet"][i] + tot["building"][i]
        hourly.append(HourRow(timestamp=t.isoformat(), in_window=in_window[i], baseline_load_mw=round(float(frame.at[t, "baseline_mw"]), 4), project_load_mw=round(float(frame.at[t, "project_mw"]), 4),
                              pre_dispatch_net_mw=round(pre, 4), battery_reduction_mw=round(tot["battery"][i], 4), ev_reduction_mw=round(tot["ev_fleet"][i], 4),
                              building_reduction_mw=round(tot["building"][i], 4), total_reduction_mw=round(total, 4), optimized_net_mw=round(net[i], 4), capacity_mw=cap,
                              pre_deficit_mw=round(pre_def, 4), remaining_deficit_mw=round(post_def, 4), violation_before=pre_def > TOL, violation_after=post_def > TOL,
                              solar_informational_mw=round(solar[i], 4)))
    reconciled = all(abs(h.optimized_net_mw - (h.pre_dispatch_net_mw - h.total_reduction_mw)) < 1e-3 for h in hourly)

    agents: list[AgentDispatch] = []
    ex = {e.agent_id: e.reason for e in excl}
    seen = {}
    for kind, items in (("battery", pb.batteries), ("ev_fleet", pb.evs), ("building", pb.buildings)):
        for j, a in enumerate(items):
            r = red[kind][j]
            if kind == "battery":
                s = sol.battery[a.id]
                mode = ["discharging" if d > 1e-6 else "charging" if c > 1e-6 else "idle" for c, d in zip(s["charge"], s["discharge"])]
                series = {"soc": [round(x, 4) for x in s["soc"]], "chargeMw": [round(x, 4) for x in s["charge"]], "dischargeMw": [round(x, 4) for x in s["discharge"]]}
            elif kind == "ev_fleet":
                s = sol.ev[a.id]
                mode = ["deferring" if d > 1e-6 else "recovering" if c > 1e-6 else "idle" for d, c in zip(s["defer"], s["recover"])]
                cum, run = [], 0.0
                for d, c in zip(s["defer"], s["recover"]):
                    run += d - c; cum.append(round(run, 4))
                series = {"deferMw": [round(x, 4) for x in s["defer"]], "recoverMw": [round(x, 4) for x in s["recover"]], "deferredEnergyOutstandingMwh": cum}
            else:
                s = sol.building[a.id]
                mode = ["shedding" if x > 1e-6 else "rebound" if b > 1e-6 else "idle" for x, b in zip(s["shed"], s["rebound"])]
                series = {"shedMw": [round(x, 4) for x in s["shed"]], "reboundMw": [round(x, 4) for x in s["rebound"]]}
            delivered = sum(s[{"battery": "discharge", "ev_fleet": "defer", "building": "shed"}[kind]])
            price = agentic.prices.get(a.id) if agentic else None
            agents.append(AgentDispatch(agent_id=a.id, type=kind, name=a.name, participating=True, included=True, dispatch_mw=[round(x, 4) for x in r],
                                        mode=mode, peak_mw=round(max(r, default=0.0), 4), energy_mwh=round(sum(x for x in r if x > 0), 4), series=series,
                                        owner_id=agentic.owner_of.get(a.id) if agentic else None, price_per_mwh=price,
                                        delivered_mwh=round(delivered, 4), cost=None if price is None else round(price * delivered, 2)))
            seen[a.id] = True
    for a in sorted((x for x in pop.agents if x.type != "solar"), key=lambda x: x.id):
        if a.id in seen:
            continue
        agents.append(AgentDispatch(agent_id=a.id, type=a.type, name=a.name, participating=False if agentic else pop.participates(a, rates), included=False,
                                    excluded_reason=(agentic.reasons.get(a.id) if agentic else None) or ex.get(a.id, "not_enrolled"), owner_id=agentic.owner_of.get(a.id) if agentic else None,
                                    dispatch_mw=[0.0] * n, mode=["idle"] * n, peak_mw=0.0, energy_mwh=0.0, series={}))
    agents.sort(key=lambda a: (not a.included, a.type, a.agent_id))

    win, tail, hor = _metrics(rows, in_window), _metrics(rows, [not m for m in in_window]), _metrics(rows, [True] * n)
    pre_e, post_e = hor.energy_above_capacity_before_mwh, hor.energy_above_capacity_after_mwh
    if pre_e <= TOL:
        status, why = "resolved", "No capacity violation in this window; nothing to coordinate."
    elif post_e <= TOL and hor.violation_hours_after == 0:
        status, why = "resolved", "Every violation hour in the window and recovery tail is within capacity after dispatch."
    elif post_e < pre_e * 0.995:
        status, why = "partially_resolved", f"Energy above capacity reduced from {pre_e:.2f} to {post_e:.2f} MWh; {hor.violation_hours_after} violation hour(s) remain."
    else:
        status, why = "unresolved", "Eligible flexibility cannot meaningfully reduce the violation in this window."
    energy = {k: round(sum(x for s in v for x in s if x > 0), 4) for k, v in red.items()}
    clearing_cost = round(sum(a.cost or 0.0 for a in agents), 2) if agentic else None
    return CoordinationResult(
        scenario_id=scenario.id, zone_id=scenario.zone_id, status=status, status_reason=why, window_start=w_start.isoformat(), window_end=w_end.isoformat(),
        horizon_end=h_end.isoformat(), tail_hours=int((h_end - w_end) / pd.Timedelta(hours=1)), capacity_mw=cap, window=win, tail=tail, horizon=hor,
        peak_dispatch_mw=round(max((h.total_reduction_mw for h in hourly), default=0.0), 4), dispatched_energy_mwh=energy,
        participating_agents=sum(a.participating for a in agents), included_agents=sum(a.included for a in agents), hourly=hourly, agents=agents,
        checks=[Check(name=c.name, passed=c.passed, max_violation=c.max_violation) for c in checks], checks_passed=all(c.passed for c in checks), reconciled=reconciled,
        solver={"name": "SCIP (OR-Tools)", "status": sol.status, "objective": round(sol.objective, 6), "threads": 1, "deterministic": True},
        participation_rates={k: round(v, 3) for k, v in rates.items()},
        objective_weights={"unresolvedViolationPerMwh": obj.W_SLACK, "batteryThroughputPerMwh": obj.W_BATTERY, "evShiftPerMwh": obj.W_EV, "buildingShedPerMwh": obj.W_BUILDING,
                           **({"offerPricePerDollar": obj.W_PRICE} if agentic else {})},
        mode="agentic" if agentic else "manual", clearing_cost=clearing_cost,
        note=("Agentic clearing over physically validated owner offers only. " if agentic else "") + "Single-event coordination result. Synthetic resources are Modeled; this result is Derived. It is NOT a project-level feasibility claim: it covers one event window only.")
