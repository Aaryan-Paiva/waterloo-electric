"""Battery agent (CLAUDE.md §13.1).

At rest a battery follows a deterministic daily routine that is ALREADY reflected in the historical baseline:
charge overnight, hold, partially self-supply 16-20h, hold. Potential flexibility is the EXTRA discharge it could give
above what it already does: limited by inverter headroom and by usable energy above the reserve.
"""
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .base import AgentState, Context, Potential
from .util import date_key, hod, prev_date_key, uhash


@dataclass
class BatteryAgent:
    id: str
    name: str
    draw: float
    seed: int
    kind: str
    power_mw: float
    duration_h: float
    charge_eff: float
    discharge_eff: float
    min_soc: float
    max_soc: float
    charge_start_h: int
    charge_len_h: int
    self_supply_fraction: float
    type: str = "battery"

    @property
    def energy_mwh(self) -> float:
        return self.power_mw * self.duration_h

    def params(self) -> dict[str, Any]:
        return {"kind": self.kind, "powerMw": round(self.power_mw, 3), "energyMwh": round(self.energy_mwh, 3),
                "chargeEfficiency": round(self.charge_eff, 3), "dischargeEfficiency": round(self.discharge_eff, 3),
                "minSoc": round(self.min_soc, 3), "maxSoc": round(self.max_soc, 3),
                "chargeWindow": f"{self.charge_start_h:02d}:00-{(self.charge_start_h + self.charge_len_h) % 24:02d}:00",
                "selfSupplyFraction": round(self.self_supply_fraction, 3)}

    # --- at-rest routine -------------------------------------------------------------------------------------
    def _full(self, d: str) -> float:
        return self.max_soc - 0.03 * uhash(self.seed, self.id, "full", d)

    def _low(self, d: str) -> float:
        drop = self.self_supply_fraction * (self._full(d) - self.min_soc) * (0.8 + 0.4 * uhash(self.seed, self.id, "low", d))
        return max(self.min_soc, self._full(d) - drop)

    def _maintenance(self, d: str) -> bool:
        return uhash(self.seed, self.id, "maint", d) < 0.02

    def _soc_and_flows(self, t: pd.Timestamp) -> tuple[float, float, float, str]:
        d, h = date_key(t), hod(t)
        c0, c1 = self.charge_start_h, self.charge_start_h + self.charge_len_h
        low_prev, low_today, full = self._low(prev_date_key(t)), self._low(d), self._full(d)
        if h < c0:
            return low_prev, 0.0, 0.0, "idle"
        if h < c1:
            f = (h - c0) / (c1 - c0)
            soc = low_prev + (full - low_prev) * f
            chg = (full - low_prev) * self.energy_mwh / (self.charge_eff * (c1 - c0))
            return soc, min(chg, self.power_mw), 0.0, "charging"
        hold = full * (1 - 0.0005 * (h - c1))
        if h < 16:
            return hold, 0.0, 0.0, "idle"
        hold16 = full * (1 - 0.0005 * (16 - c1))
        if h < 20:
            f = (h - 16) / 4.0
            soc = hold16 + (low_today - hold16) * f
            dis = max(0.0, (hold16 - low_today)) * self.energy_mwh * self.discharge_eff / 4.0
            return soc, 0.0, min(dis, self.power_mw), "self_supply"
        return low_today, 0.0, 0.0, "idle"

    def state_at(self, ts: pd.Timestamp, ctx: Context) -> AgentState:
        soc, chg, dis, mode = self._soc_and_flows(ts)
        soc = min(self.max_soc, max(self.min_soc, soc))
        maint = self._maintenance(date_key(ts))
        reason = "maintenance_day" if maint else ("at_reserve_soc" if soc <= self.min_soc + 0.02 else None)
        return AgentState(available=reason is None, reason=reason, values={
            "soc": round(soc, 4), "mode": mode, "chargingMw": round(chg, 4), "atRestDischargeMw": round(dis, 4),
            "usableEnergyMwh": round(max(0.0, soc - self.min_soc) * self.energy_mwh * self.discharge_eff, 4)})

    def potential(self, ts: pd.Timestamp, window_h: float, ctx: Context, participating: bool) -> Potential:
        st = self.state_at(ts, ctx)
        if not st.available:
            return Potential(0.0, 0.0, 0.0, st.reason or "unavailable", st.reason if participating else "not_enrolled")
        v = st.values
        headroom = max(0.0, self.power_mw - v["atRestDischargeMw"] - v["chargingMw"])   # cannot exceed inverter power
        by_energy = v["usableEnergyMwh"] / max(window_h, 1e-9)
        p = max(0.0, min(headroom, by_energy))
        lim = "energy" if by_energy < headroom else "inverter_power"
        enrolled = round(p, 4)
        return Potential(enrolled if participating else 0.0, enrolled, window_h, lim, None if participating else "not_enrolled")
