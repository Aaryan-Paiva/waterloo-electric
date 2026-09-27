"""DER agent contract (CLAUDE.md §12.4, §13). Phase 3: agents EXPOSE state and potential flexibility.
They never dispatch, never change the baseline, and are always `modeled` (never known real customers)."""
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

import pandas as pd


@dataclass
class Context:
    """Read-only world context. `heat_index(ts)` in [0,1] is derived from the (already-observed) baseline shape."""
    heat_index: Any                 # callable: pd.Timestamp -> float
    seed: int


@dataclass
class AgentState:
    available: bool
    reason: Optional[str]
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class Potential:
    potential_mw: float                 # 0 unless the agent participates
    potential_if_enrolled_mw: float     # what it could offer if it participated
    sustained_hours: float
    limiting_factor: str
    decline_reason: Optional[str] = None


class Agent(Protocol):
    id: str
    type: str
    name: str
    draw: float
    def params(self) -> dict[str, Any]: ...
    def state_at(self, ts: pd.Timestamp, ctx: Context) -> AgentState: ...
    def potential(self, ts: pd.Timestamp, window_h: float, ctx: Context, participating: bool) -> Potential: ...
