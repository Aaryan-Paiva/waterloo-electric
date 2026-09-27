from typing import Any, Literal

from pydantic import Field

from .base import CamelModel

ProjectType = Literal["data_center", "housing", "ev_depot"]


class Project(CamelModel):
    """CLAUDE.md §12.3. Defined now; project insertion is Phase 2."""
    id: str
    type: ProjectType
    name: str
    provenance: Literal["hypothetical"] = "hypothetical"
    nominal_load_mw: float = Field(ge=0)
    hourly_profile: list[float] = Field(default_factory=list)
    flexibility_fraction: float = Field(default=0.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
