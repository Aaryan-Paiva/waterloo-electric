"""Historical-load repository. Serves the full parquet when present, otherwise the committed fixture,
and always says which one ('full' | 'fixture') so the UI can label demo mode (CLAUDE.md §41)."""
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

import pandas as pd

from .. import settings
from ..schemas.world import LoadSummary, WorldPack
from .ingestion import dataset_path, load_world_pack


@dataclass(frozen=True)
class LoadData:
    df: pd.DataFrame          # columns: timestamp, load_mw, observed_mw, quality_flag
    mode: str                 # "full" | "fixture"


@lru_cache(maxsize=8)
def get_pack(world_id: str) -> WorldPack:
    return load_world_pack(world_id)


@lru_cache(maxsize=8)
def get_load(world_id: str) -> LoadData:
    pack = get_pack(world_id)
    p = dataset_path(world_id)
    if p.exists():
        return LoadData(pd.read_parquet(p)[["timestamp", "load_mw", "observed_mw", "quality_flag"]], "full")
    f = settings.FIXTURES_DIR / pack.fixture.file
    body = json.loads(f.read_text())
    df = pd.DataFrame(body["points"]).rename(columns={"loadMw": "load_mw", "observedZoneMw": "observed_mw", "qualityFlag": "quality_flag"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return LoadData(df[["timestamp", "load_mw", "observed_mw", "quality_flag"]], "fixture")


def clear_caches() -> None:
    get_pack.cache_clear()
    get_load.cache_clear()


def window(df: pd.DataFrame, start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    if start:
        s = pd.Timestamp(start)
        s = s.tz_localize(df["timestamp"].dt.tz) if s.tzinfo is None else s
        df = df[df["timestamp"] >= s]
    if end:
        e = pd.Timestamp(end)
        e = e.tz_localize(df["timestamp"].dt.tz) if e.tzinfo is None else e
        df = df[df["timestamp"] < e]
    return df


def daily(df: pd.DataFrame) -> pd.DataFrame:
    g = df.assign(day=df["timestamp"].dt.normalize()).groupby("day")
    out = g.agg(load_mw=("load_mw", "max"), mean_mw=("load_mw", "mean"), min_mw=("load_mw", "min"),
                observed_mw=("observed_mw", "max")).reset_index().rename(columns={"day": "timestamp"})
    out["quality_flag"] = "ok"
    return out


def summarize(df: pd.DataFrame, capacity_mw: float) -> LoadSummary:
    i = df["load_mw"].idxmax()
    peak = float(df.loc[i, "load_mw"])
    mean = float(df["load_mw"].mean())
    return LoadSummary(hours=len(df), start=df["timestamp"].iloc[0].isoformat(), end=df["timestamp"].iloc[-1].isoformat(),
                       peak_mw=round(peak, 3), peak_timestamp=df.loc[i, "timestamp"].isoformat(), mean_mw=round(mean, 3),
                       min_mw=round(float(df["load_mw"].min()), 3), load_factor=round(mean / peak, 4),
                       headroom_at_peak_mw=round(capacity_mw - peak, 3),
                       hours_above_capacity=int((df["load_mw"] > capacity_mw).sum()),
                       interpolated_hours=int((df["quality_flag"] != "ok").sum()))
