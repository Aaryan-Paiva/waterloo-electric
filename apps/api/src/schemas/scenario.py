from typing import Any, Literal, Optional

from pydantic import Field, field_validator

from .base import CamelModel
from .project import Project


class Scenario(CamelModel):
    """CLAUDE.md §12.2."""
    id: str
    zone_id: str
    name: str
    created_at: str
    seed: int
    projects: list[Project] = Field(default_factory=list)
    assumption_overrides: dict[str, Any] = Field(default_factory=dict)
    parent_scenario_id: Optional[str] = None


class ScenarioCreate(CamelModel):
    zone_id: str = "waterloo-demo"
    name: Optional[str] = None
    seed: Optional[int] = None


class ProjectCreate(CamelModel):
    """Phase 2 accepts the data centre only, with a constant 24/7 profile and no flexible compute."""
    type: Literal["data_center"] = "data_center"
    name: Optional[str] = None
    nominal_load_mw: float = Field(gt=0, le=500)
    flexibility_fraction: float = 0.0

    @field_validator("flexibility_fraction")
    @classmethod
    def _no_flex_yet(cls, v: float) -> float:
        if v != 0:
            raise ValueError("flexible compute is not available until a later phase")
        return v


class ProjectUpdate(CamelModel):
    name: Optional[str] = None
    nominal_load_mw: Optional[float] = Field(default=None, gt=0, le=500)
