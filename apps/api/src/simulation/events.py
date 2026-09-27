"""Capacity-event detection and windowing (CLAUDE.md §12.5, §15, §21).

A violation is net_load > capacity (strict). Equal to capacity is NOT a violation.
"""
import pandas as pd

from ..schemas.events import CapacityEvent
from ..schemas.analysis import EventWindow


def violations(df: pd.DataFrame, capacity_mw: float) -> pd.DataFrame:
    v = df[df["net_mw"] > capacity_mw].copy()
    v["deficit_mw"] = v["net_mw"] - capacity_mw
    return v


def event_id(ts: pd.Timestamp) -> str:
    return "evt_" + ts.strftime("%Y%m%dT%H%M%S%z")


def to_events(v: pd.DataFrame, capacity_mw: float) -> list[CapacityEvent]:
    return [CapacityEvent(id=event_id(r.timestamp), timestamp=r.timestamp.isoformat(),
                          baseline_load_mw=round(float(r.baseline_mw), 3), project_load_mw=round(float(r.project_mw), 3),
                          local_generation_mw=round(float(r.local_generation_mw), 3),
                          pre_dispatch_net_load_mw=round(float(r.net_mw), 3), capacity_mw=capacity_mw,
                          deficit_mw=round(float(r.deficit_mw), 3), requested_flexibility_mw=round(float(r.deficit_mw), 3),
                          resolved=False)
            for r in v.itertuples()]


def group_windows(v: pd.DataFrame) -> list[EventWindow]:
    """Consecutive constrained hours -> one window. `end` is exclusive (the hour after the last constrained hour)."""
    if v.empty:
        return []
    v = v.sort_values("timestamp")
    gap = v["timestamp"].diff() != pd.Timedelta(hours=1)
    gid = gap.cumsum()
    out: list[EventWindow] = []
    for _, g in v.groupby(gid, sort=True):
        i = g["deficit_mw"].idxmax()
        start, last = g["timestamp"].iloc[0], g["timestamp"].iloc[-1]
        out.append(EventWindow(
            id="win_" + start.strftime("%Y%m%dT%H%M%S%z"), start=start.isoformat(), end=(last + pd.Timedelta(hours=1)).isoformat(),
            hours=len(g), peak_deficit_mw=round(float(g.loc[i, "deficit_mw"]), 3), peak_timestamp=g.loc[i, "timestamp"].isoformat(),
            mean_deficit_mw=round(float(g["deficit_mw"].mean()), 3), energy_over_mwh=round(float(g["deficit_mw"].sum()), 3),
            days=int(g["timestamp"].dt.date.nunique())))
    return out
