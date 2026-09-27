"""Flexible building agent (CLAUDE.md §13.3). Its load is an ATTRIBUTED SHARE of the observed baseline, never an
addition. Potential = temporary HVAC shed, limited by max curtailment duration and remaining comfort budget."""
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .base import AgentState, Context, Potential
from .util import date_key, hod, is_weekend, uhash

# occupancy profile by kind: (open_h, close_h, weekday_only)
KINDS = {"office": (7, 18, True), "school": (7, 16, True), "retail": (9, 21, False), "apartment": (0, 24, False), "municipal": (6, 22, False)}


@dataclass
class BuildingAgent:
    id: str
    name: str
    draw: float
    seed: int
    kind: str
    peak_mw: float
    hvac_share_max: float
    shed_fraction: float
    max_curtail_h: int
    rebound_fraction: float
    rebound_h: int
    type: str = "building"

    def params(self) -> dict[str, Any]:
        return {"kind": self.kind, "peakLoadMw": round(self.peak_mw, 3), "hvacShareMax": round(self.hvac_share_max, 3),
                "shedFraction": round(self.shed_fraction, 3), "maxCurtailmentHours": self.max_curtail_h,
                "reboundFraction": round(self.rebound_fraction, 3), "reboundHours": self.rebound_h}

    def _occupancy(self, t: pd.Timestamp) -> float:
        open_h, close_h, weekday_only = KINDS[self.kind]
        h = hod(t)
        if weekday_only and is_weekend(t):
            return 0.3
        if self.kind == "apartment":
            return 0.55 + 0.45 * (1.0 if (h >= 17 or h < 8) else 0.6)
        return 1.0 if open_h <= h < close_h else 0.4

    def _load_parts(self, t: pd.Timestamp, ctx: Context) -> tuple[float, float]:
        heat = ctx.heat_index(t)
        base = self.peak_mw * self._occupancy(t) * (0.85 + 0.15 * heat)
        hvac = base * self.hvac_share_max * (0.4 + 0.6 * heat)
        return base, hvac

    def state_at(self, ts: pd.Timestamp, ctx: Context) -> AgentState:
        base, hvac = self._load_parts(ts, ctx)
        occ = self._occupancy(ts)
        comfort = 0.6 + 0.4 * uhash(self.seed, self.id, "comfort", date_key(ts))
        avail = occ >= 0.9 or self.kind == "apartment"
        return AgentState(avail, None if avail else "low_occupancy", {
            "baselineShareMw": round(base, 4), "hvacLoadMw": round(hvac, 4), "occupancy": round(occ, 3),
            "comfortBudget": round(comfort, 3), "sheddableMw": round(hvac * self.shed_fraction * comfort, 4)})

    def potential(self, ts: pd.Timestamp, window_h: float, ctx: Context, participating: bool) -> Potential:
        st = self.state_at(ts, ctx)
        if not st.available:
            return Potential(0.0, 0.0, 0.0, st.reason or "unavailable", st.reason if participating else "not_enrolled")
        shed = st.values["sheddableMw"]
        sustain = min(window_h, float(self.max_curtail_h))
        avg = shed * (sustain / max(window_h, 1e-9))                    # average over the window if it exceeds max curtailment
        lim = "max_curtailment_duration" if window_h > self.max_curtail_h else "comfort_and_hvac_share"
        p = round(avg, 4)
        return Potential(p if participating else 0.0, p, sustain, lim, None if participating else "not_enrolled")
