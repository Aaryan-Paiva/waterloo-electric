from typing import Optional

from .base import CamelModel


class CapacityEvent(CamelModel):
    """CLAUDE.md §12.5. Detection is Phase 2; the contract is fixed now."""
    id: str
    timestamp: str
    baseline_load_mw: float
    project_load_mw: float
    local_generation_mw: float
    pre_dispatch_net_load_mw: float
    capacity_mw: float
    deficit_mw: float
    requested_flexibility_mw: float
    resolved: bool
    post_dispatch_net_load_mw: Optional[float] = None
    remaining_deficit_mw: Optional[float] = None
