"""Flagship data-centre project (CLAUDE.md §14.1).

Phase 2 model: constant 24/7 load at the nominal size, no flexible compute (flexibility is 0 until the
optimizer exists), hypothetical provenance. It is an INCREMENT on the observed/derived baseline, never a
replacement for it.
"""
import numpy as np
import pandas as pd

from ..schemas.project import Project

PROFILE_ID = "constant_24_7"
MAX_NOMINAL_MW = 500.0


class DataCenterProject:
    def __init__(self, nominal_mw: float):
        if not 0 < nominal_mw <= MAX_NOMINAL_MW:
            raise ValueError(f"nominal_mw must be in (0, {MAX_NOMINAL_MW}]")
        self.nominal_mw = float(nominal_mw)

    def hourly_increment_mw(self, timestamps: pd.Series) -> np.ndarray:
        return np.full(len(timestamps), self.nominal_mw, dtype=float)


def make_project(project_id: str, nominal_mw: float, name: str | None = None) -> Project:
    DataCenterProject(nominal_mw)  # validates
    return Project(id=project_id, type="data_center", name=name or f"{nominal_mw:g} MW data centre",
                   nominal_load_mw=float(nominal_mw), hourly_profile=[float(nominal_mw)] * 24,
                   flexibility_fraction=0.0, metadata={"profile": PROFILE_ID, "operating_hours": "24/7"})
