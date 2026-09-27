from typing import Any, Literal, Optional

from .base import CamelModel

CapacityProvenance = Literal["observed", "modeled", "user_assumption"]


class Zone(CamelModel):
    """CLAUDE.md §12.1."""
    id: str
    name: str
    timezone: str
    geometry: Optional[dict[str, Any]] = None
    capacity_mw: float
    capacity_provenance: CapacityProvenance
    historical_start: str
    historical_end: str
    world_seed: int


class HistoricalLoadPoint(CamelModel):
    """CLAUDE.md §10.2 (+ the unscaled source value so the scaling is never hidden)."""
    timestamp: str
    load_mw: float
    observed_zone_mw: Optional[float] = None   # unscaled IESO zone value
    source_id: str
    provenance: Literal["observed", "derived"]
    quality_flag: Optional[str] = None         # "ok" | "interpolated"
    mean_mw: Optional[float] = None            # daily resolution only
    min_mw: Optional[float] = None             # daily resolution only
