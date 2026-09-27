"""New-load projects for the sandbox (all Hypothetical). A load is an hourly MW increment on the baseline, never a replacement for it.

  data centre : size = MW, constant 24/7.
  housing     : size = homes, evening-shaped (about 1.8 kW per home at the evening peak, including some EV and heat-pump use).
  EV depot    : size = chargers (19.2 kW each), charging mostly between 6 pm and 6 am at about 75% utilization at its peak.
Shapes are illustrative modeling assumptions (fractions of the peak, by hour of day, EST).
"""
import numpy as np
import pandas as pd

from ..schemas.project import Project
from .data_center import make_project as make_dc

KW_PER_HOME_PEAK = 1.8
CHARGER_KW, CHARGER_PEAK_UTIL = 19.2, 0.75
HOUSING_SHAPE = [0.42, 0.38, 0.36, 0.35, 0.37, 0.45, 0.58, 0.66, 0.60, 0.52, 0.48, 0.47, 0.46, 0.46, 0.48, 0.55, 0.68, 0.85, 0.98, 1.00, 0.95, 0.82, 0.62, 0.50]
EV_DEPOT_SHAPE = [0.85, 0.85, 0.80, 0.75, 0.70, 0.45, 0.10, 0.03, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.03, 0.05, 0.08, 0.25, 0.70, 1.00, 1.00, 0.98, 0.95, 0.90]
KINDS = ("data_centre", "housing", "ev_depot")


class ProfileProject:
    def __init__(self, hourly_mw: list[float]):
        if len(hourly_mw) != 24:
            raise ValueError("hourly profile must have 24 values")
        self.profile = np.asarray(hourly_mw, dtype=float)

    def hourly_increment_mw(self, timestamps: pd.Series) -> np.ndarray:
        return self.profile[timestamps.dt.hour.to_numpy()]


def make_load(pid: str, kind: str, size: float, name: str | None = None) -> Project:
    if kind == "data_centre":
        return make_dc(pid, size, name)
    if kind == "housing":
        if not 1 <= size <= 100_000:
            raise ValueError("homes must be between 1 and 100,000")
        peak = size * KW_PER_HOME_PEAK / 1000.0
        return Project(id=pid, type="housing", name=name or f"{int(size):,} homes", nominal_load_mw=round(peak, 3), hourly_profile=[round(peak * f, 4) for f in HOUSING_SHAPE],
                       flexibility_fraction=0.0, metadata={"homes": int(size), "profile": "residential_evening"})
    if kind == "ev_depot":
        if not 1 <= size <= 2000:
            raise ValueError("chargers must be between 1 and 2,000")
        peak = size * CHARGER_KW * CHARGER_PEAK_UTIL / 1000.0
        return Project(id=pid, type="ev_depot", name=name or f"{int(size)}-charger EV depot", nominal_load_mw=round(peak, 3), hourly_profile=[round(peak * f, 4) for f in EV_DEPOT_SHAPE],
                       flexibility_fraction=0.0, metadata={"chargers": int(size), "profile": "depot_overnight"})
    raise ValueError(f"unknown load kind {kind!r}")
