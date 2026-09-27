from typing import Literal

from .base import CamelModel

AgentType = Literal["battery", "ev_fleet", "building", "solar", "industrial_dr"]


class DERAgentBase(CamelModel):
    """CLAUDE.md §12.4 / §13. Common fields only; per-type state/dispatch arrives in Phase 3-4.
    Synthetic agents are always `modeled`, never known real customers."""
    id: str
    type: AgentType
    participating: bool
    provenance: Literal["modeled"] = "modeled"
