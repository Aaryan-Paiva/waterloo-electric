"""Solar cluster (CLAUDE.md §13.4). Solar is a generation OFFSET that is already embedded in the observed baseline.
It is exposed for context and reconciliation only: it is NEVER subtracted from the baseline again and offers no
capacity relief (`potential` is always 0). This is the no-double-counting rule (CLAUDE.md §11.2)."""
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .base import AgentState, Context, Potential
from .util import clear_sky_fraction, date_key, uhash


@dataclass
class SolarAgent:
    id: str
    name: str
    draw: float
    seed: int
    installed_mw: float
    derate: float
    type: str = "solar"

    def params(self) -> dict[str, Any]:
        return {"installedMw": round(self.installed_mw, 3), "derate": round(self.derate, 3), "dispatchable": False}

    def state_at(self, ts: pd.Timestamp, ctx: Context) -> AgentState:
        clear = clear_sky_fraction(ts) * self.installed_mw * self.derate
        cloud = 0.3 + 0.7 * uhash(self.seed, "cloud", date_key(ts))                  # shared per-day sky for all clusters
        var = 0.95 + 0.1 * uhash(self.seed, self.id, "var", ts.isoformat())
        gen = max(0.0, min(self.installed_mw, clear * cloud * var))
        return AgentState(True, None, {"generationMw": round(gen, 4), "clearSkyMw": round(clear, 4), "cloudFactor": round(cloud, 3),
                                       "alreadyInBaseline": True})

    def potential(self, ts: pd.Timestamp, window_h: float, ctx: Context, participating: bool) -> Potential:
        return Potential(0.0, 0.0, 0.0, "already_in_baseline", None)
