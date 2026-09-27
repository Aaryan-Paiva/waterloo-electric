"""Project models (CLAUDE.md §14). A project turns its parameters into an hourly load increment (MW)."""
from typing import Protocol

import numpy as np
import pandas as pd

from ..schemas.project import Project


class ProjectModel(Protocol):
    def hourly_increment_mw(self, timestamps: pd.Series) -> np.ndarray: ...


def build_model(project: Project) -> ProjectModel:
    """Phase 2 implements the data centre only; housing and EV depot arrive later."""
    from .data_center import DataCenterProject

    if project.type == "data_center":
        return DataCenterProject(project.nominal_load_mw)
    if project.type in ("housing", "ev_depot"):
        from .loads import ProfileProject

        return ProfileProject(project.hourly_profile)
    raise NotImplementedError(f"project type {project.type!r} is not implemented yet")
