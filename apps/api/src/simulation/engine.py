"""Net-load accounting (CLAUDE.md §15).

  net_load[t] = baseline[t] + project_increment[t] + modeled_incremental_charging[t]
                - dispatched_battery_discharge[t] - local_generation_offset[t] - demand_reduction_or_shift[t]

Phase 2 uses only the first two terms (+ a zero local-generation column reserved for later). The baseline
frame is never mutated: a new frame is returned.
"""
from typing import Sequence

import numpy as np
import pandas as pd

from ..projects.base import ProjectModel


def net_load(baseline: pd.DataFrame, projects: Sequence[ProjectModel]) -> pd.DataFrame:
    out = baseline[["timestamp", "load_mw", "quality_flag"]].rename(columns={"load_mw": "baseline_mw"}).copy()
    project = np.zeros(len(out))
    for p in projects:
        project += p.hourly_increment_mw(out["timestamp"])
    out["project_mw"] = project
    out["local_generation_mw"] = 0.0
    out["net_mw"] = out["baseline_mw"] + out["project_mw"] - out["local_generation_mw"]
    return out.reset_index(drop=True)
