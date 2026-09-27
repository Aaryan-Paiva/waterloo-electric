"""Phase 2 orchestration: scenario -> full-history net load -> capacity analysis / events / load views."""
import numpy as np
import pandas as pd

from ..data.repositories import get_load, get_pack
from ..projects.base import build_model
from ..schemas.analysis import CapacityAnalysis, EventsResponse, ScenarioLoadPoint, ScenarioLoadResponse
from ..schemas.scenario import Scenario
from .engine import net_load
from .events import to_events, violations
from .metrics import capacity_metrics


def scenario_frame(scenario: Scenario) -> tuple[pd.DataFrame, float, str, str]:
    """Net-load frame over the full history. The stored baseline is never mutated."""
    data, pack = get_load(scenario.zone_id), get_pack(scenario.zone_id)
    df = net_load(data.df, [build_model(p) for p in scenario.projects])
    return df, pack.capacity.value_mw, pack.capacity.provenance, data.mode


def run_capacity_analysis(scenario: Scenario) -> CapacityAnalysis:
    df, cap, cap_prov, mode = scenario_frame(scenario)
    return capacity_metrics(scenario, df, cap, cap_prov, mode)


def list_events(scenario: Scenario, limit: int, offset: int, order: str) -> EventsResponse:
    df, cap, _, _ = scenario_frame(scenario)
    v = violations(df, cap)
    if order == "deficit":
        v = v.sort_values(["deficit_mw", "timestamp"], ascending=[False, True])
    page = v.iloc[offset: offset + limit]
    return EventsResponse(scenario_id=scenario.id, total=len(v), offset=offset, limit=limit, order=order,  # type: ignore[arg-type]
                          events=to_events(page, cap))


def scenario_load(scenario: Scenario, start: str | None, end: str | None, resolution: str, max_points: int = 20000) -> ScenarioLoadResponse:
    from ..data.repositories import window

    df, cap, cap_prov, mode = scenario_frame(scenario)
    df = window(df.rename(columns={}), start, end)
    df = df.assign(deficit_mw=np.maximum(0.0, df["net_mw"] - cap), over=(df["net_mw"] > cap).astype(int))
    if resolution == "daily":
        g = df.assign(day=df["timestamp"].dt.normalize()).groupby("day")
        d = g.agg(baseline_mw=("baseline_mw", "max"), project_mw=("project_mw", "mean"), net_mw=("net_mw", "max"),
                  deficit_mw=("deficit_mw", "max"), over=("over", "sum")).reset_index().rename(columns={"day": "timestamp"})
        d["quality_flag"] = "ok"
        df = d
    truncated = len(df) > max_points
    df = df.iloc[:max_points]
    is_daily = resolution == "daily"
    pts = [ScenarioLoadPoint(timestamp=r.timestamp.isoformat(), baseline_load_mw=round(float(r.baseline_mw), 3),
                             project_load_mw=round(float(r.project_mw), 3), net_load_mw=round(float(r.net_mw), 3),
                             deficit_mw=round(float(r.deficit_mw), 3), constrained_hours=int(r.over) if is_daily else None,
                             quality_flag=r.quality_flag) for r in df.itertuples()]
    return ScenarioLoadResponse(scenario_id=scenario.id, zone_id=scenario.zone_id, mode=mode, resolution=resolution,  # type: ignore[arg-type]
                                capacity_mw=cap, capacity_provenance=cap_prov, points=pts, truncated=truncated)
