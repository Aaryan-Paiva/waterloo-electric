"""Normalise IESO hourly zonal demand into a clean hourly series (CLAUDE.md §10.3).

IESO reports use hour-ending 1..24. We map HE h on date D to the hour STARTING at D + (h-1) h.
IESO publishes in EST year-round (fixed UTC-5, no daylight saving) — recorded as unverified in the world pack.
Missing hours are linearly interpolated and flagged; large gaps are refused (never silently invented).
"""
from pathlib import Path

import pandas as pd

SOURCE_TZ = "Etc/GMT+5"  # fixed UTC-5 (note the POSIX sign inversion)
MAX_GAP_HOURS = 6


def read_ieso_zonal(path: Path, column: str) -> pd.DataFrame:
    """Return columns [timestamp (tz-aware UTC-5), observed_mw, quality_flag] for one yearly file."""
    raw = pd.read_csv(path, skiprows=3)
    if column not in raw.columns:
        raise ValueError(f"{path.name}: column {column!r} not found; have {list(raw.columns)}")
    raw["Date"] = pd.to_datetime(raw["Date"])
    raw = raw.drop_duplicates(subset=["Date", "Hour"], keep="last")
    if not raw["Hour"].between(1, 24).all():
        raise ValueError(f"{path.name}: hour-ending outside 1..24")
    raw["timestamp"] = (raw["Date"] + pd.to_timedelta(raw["Hour"] - 1, unit="h")).dt.tz_localize(SOURCE_TZ)
    s = raw.set_index("timestamp")[column].astype(float).sort_index()
    return normalize_series(s)


def normalize_series(s: pd.Series) -> pd.DataFrame:
    """Reindex to a complete hourly grid; interpolate short gaps and flag them; refuse long gaps."""
    full = pd.date_range(s.index.min(), s.index.max(), freq="h", tz=s.index.tz)
    s = s.reindex(full)
    missing = s.isna()
    if missing.any():
        run = missing.astype(int).groupby((~missing).cumsum()).cumsum()
        if int(run.max()) > MAX_GAP_HOURS:
            raise ValueError(f"gap of {int(run.max())} consecutive missing hours exceeds {MAX_GAP_HOURS}")
        s = s.interpolate(limit_direction="both")
    if (s <= 0).any():
        raise ValueError("non-positive demand value found; refusing to ingest")
    out = pd.DataFrame({"observed_mw": s})
    out["quality_flag"] = ["interpolated" if m else "ok" for m in missing]
    out.index.name = "timestamp"
    return out.reset_index()
