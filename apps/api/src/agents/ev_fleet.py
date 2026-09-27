"""EV fleet agent (CLAUDE.md §13.2). At rest it charges unmanaged from arrival; that consumption is ALREADY in the
baseline. Potential = how much of the present charging it could defer for the whole window, without missing the
departure deadline (the deferred energy must be recovered at max charging power before departure)."""
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .base import AgentState, Context, Potential
from .util import date_key, hod, is_weekend, uhash

WINDOWS = {"depot": (18.5, 6.0), "workplace": (8.0, 17.0), "residential_managed": (18.0, 7.0)}   # arrival, departure (h, EST)


@dataclass
class EVFleetAgent:
    id: str
    name: str
    draw: float
    seed: int
    kind: str
    vehicles: int
    chargers: int
    charger_kw: float
    kwh_per_vehicle_day: float
    shiftable_fraction: float
    arrival_h: float
    departure_h: float
    type: str = "ev_fleet"

    @property
    def max_charging_mw(self) -> float:
        return self.chargers * self.charger_kw / 1000.0

    def params(self) -> dict[str, Any]:
        return {"kind": self.kind, "vehicles": self.vehicles, "chargers": self.chargers, "chargerKw": self.charger_kw,
                "maxChargingMw": round(self.max_charging_mw, 3), "kwhPerVehicleDay": round(self.kwh_per_vehicle_day, 1),
                "shiftableFraction": round(self.shiftable_fraction, 3), "arrival": f"{self.arrival_h:.1f}h", "departure": f"{self.departure_h:.1f}h"}

    def _session(self, t: pd.Timestamp):
        """Return (arrival_ts, departure_ts) of the session containing t, or None."""
        overnight = self.departure_h < self.arrival_h
        day = t.normalize()
        cands = [day - pd.Timedelta(days=1), day] if overnight else [day]
        for d0 in cands:
            jitter = (uhash(self.seed, self.id, "arr", d0.strftime("%Y-%m-%d")) - 0.5) * 1.0
            arr = d0 + pd.Timedelta(hours=self.arrival_h + jitter)
            dep = d0 + pd.Timedelta(hours=self.departure_h + (24 if overnight else 0))
            if arr <= t < dep:
                if self.kind == "workplace" and is_weekend(arr):
                    return None
                return arr, dep
        return None

    def _energy_day_mwh(self, arr: pd.Timestamp) -> float:
        cf = 0.7 + 0.25 * uhash(self.seed, self.id, "cf", arr.strftime("%Y-%m-%d"))
        return self.vehicles * cf * self.kwh_per_vehicle_day / 1000.0, cf

    def state_at(self, ts: pd.Timestamp, ctx: Context) -> AgentState:
        s = self._session(ts)
        if s is None:
            return AgentState(False, "not_plugged_in", {"connectedVehicles": 0, "chargingMw": 0.0, "energyRequiredMwh": 0.0,
                                                          "slackHours": None, "deadline": None})
        arr, dep = s
        e_day, cf = self._energy_day_mwh(arr)
        connected = int(round(self.vehicles * cf))
        p_eff = max(1e-9, min(self.max_charging_mw, connected * self.charger_kw / 1000.0))
        start = arr + pd.Timedelta(hours=0.5 * uhash(self.seed, self.id, "delay", arr.strftime("%Y-%m-%d")))
        dur = e_day / p_eff
        el = (ts - start).total_seconds() / 3600.0
        if el < 0:
            chg, rem = 0.0, e_day
        elif el < dur:
            chg, rem = p_eff, e_day - p_eff * el
        else:
            chg, rem = 0.0, 0.0
        rem = max(0.0, min(e_day, rem))
        slack = (dep - ts).total_seconds() / 3600.0 - rem / p_eff
        return AgentState(True, None, {"connectedVehicles": connected, "chargingMw": round(chg, 4), "energyRequiredMwh": round(rem, 4),
                                       "slackHours": round(slack, 3), "deadline": dep.isoformat(), "maxEffectiveMw": round(p_eff, 4)})

    def potential(self, ts: pd.Timestamp, window_h: float, ctx: Context, participating: bool) -> Potential:
        st0 = self.state_at(ts, ctx)
        if not st0.available:
            return Potential(0.0, 0.0, 0.0, "not_plugged_in", "not_plugged_in" if participating else "not_enrolled")
        n = max(1, math.ceil(window_h))
        charging = [self.state_at(ts + pd.Timedelta(hours=i), ctx).values["chargingMw"] for i in range(n)]
        sustained = min(charging)                                    # charging must be present for the whole window
        if sustained <= 0:
            return Potential(0.0, 0.0, 0.0, "not_charging", "not_charging" if participating else "not_enrolled")
        p_eff = st0.values["maxEffectiveMw"]
        cap_slack = max(0.0, st0.values["slackHours"]) * p_eff / max(window_h, 1e-9)   # deferred energy must be recoverable before departure
        by_shift = self.shiftable_fraction * sustained
        p = max(0.0, min(by_shift, cap_slack))
        lim = "deadline_slack" if cap_slack < by_shift else "shiftable_fraction"
        p = round(p, 4)
        return Potential(p if participating else 0.0, p, window_h, lim, None if participating else "not_enrolled")
