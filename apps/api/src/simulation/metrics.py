"""Reportable metrics computed once, centrally, so UI and reports agree (CLAUDE.md §38)."""
import pandas as pd

from ..data import provenance as prov
from ..schemas.analysis import CapacityAnalysis, YearCount
from ..schemas.scenario import Scenario
from .events import group_windows, violations


def capacity_metrics(scenario: Scenario, df: pd.DataFrame, capacity_mw: float, capacity_provenance: str, mode: str,
                     max_windows: int | None = None) -> CapacityAnalysis:
    v = violations(df, capacity_mw)
    n = len(df)
    ib, ip = df["baseline_mw"].idxmax(), df["net_mw"].idxmax()
    windows = group_windows(v)
    by_year = {str(y): YearCount(constrained_hours=len(g), affected_days=int(g["timestamp"].dt.date.nunique()))
               for y, g in v.groupby(v["timestamp"].dt.year)}
    worst = v.loc[v["deficit_mw"].idxmax()] if len(v) else None
    projects = ", ".join(f"{p.name}" for p in scenario.projects) or "none"
    return CapacityAnalysis(
        scenario_id=scenario.id, zone_id=scenario.zone_id, mode=mode,  # type: ignore[arg-type]
        historical_start=df["timestamp"].iloc[0].isoformat(), historical_end=df["timestamp"].iloc[-1].isoformat(),
        hours_tested=n, capacity_mw=capacity_mw, capacity_provenance=capacity_provenance,
        baseline_peak_mw=round(float(df.loc[ib, "baseline_mw"]), 3), baseline_peak_timestamp=df.loc[ib, "timestamp"].isoformat(),
        projected_peak_mw=round(float(df.loc[ip, "net_mw"]), 3), projected_peak_timestamp=df.loc[ip, "timestamp"].isoformat(),
        min_headroom_mw=round(capacity_mw - float(df.loc[ip, "net_mw"]), 3),
        constrained_hours=len(v), percent_within_capacity=round(100.0 * (n - len(v)) / n, 4),
        affected_days=int(v["timestamp"].dt.date.nunique()) if len(v) else 0,
        worst_deficit_mw=round(float(worst["deficit_mw"]), 3) if worst is not None else 0.0,
        worst_deficit_timestamp=worst["timestamp"].isoformat() if worst is not None else None,
        window_count=len(windows), windows=windows[:max_windows] if max_windows else windows, by_year=by_year,
        feasibility="constraints_detected" if len(v) else "feasible_as_is", flexibility_evaluated=False,
        provenance={"historicalDemand": prov.derived("IESO Southwest-zone observed shape, scaled", "Derived baseline."),
                    "zoneCapacity": prov.modeled("Hackathon assumption", "Modeled capacity."),
                    "projects": prov.hypothetical(f"Projects in this scenario: {projects}."),
                    "result": prov.derived("CapacityOS capacity screening", "Model output: baseline + project vs modeled capacity, before any flexibility.")},
        note="Pre-flexibility screening. No DER dispatch or optimization has been applied; this is not a feasibility verdict with flexibility.")
