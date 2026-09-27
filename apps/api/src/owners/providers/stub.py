"""Deterministic stub provider: no API key, no network, same inputs => same decisions. Drives tests and the default demo.

It is a small economic model of an operator, not a fit of "price -> participation %":
  reservation = min_compensation x (1 + 0.25 x the relevant priority: degradation | comfort | driver satisfaction)
  ask         = reservation x (1 + target_margin)
Incentive >= ask: full-willingness offer at the ask. reservation <= incentive < ask: offer at the incentive with quantity scaled by
how much margin is left. 0.8 x reservation <= incentive < reservation and a risk-tolerant owner: counteroffer at its own price (above
the ceiling, so CapacityOS will not clear it). Otherwise decline. Quantities use each asset's STATIC ceiling and ignore joint energy
limits on purpose, so the physical validator / one-revision path is genuinely exercised.
"""
from typing import Optional

from ...schemas.owners import AssetOffer, Block, DeclineOffer, OfferBody, ReviseOffer, SubmitOffer
from ..context import OwnerContext, Rejection
from ..physical import blocks_of
from .base import ProviderResult

MIN_MW = 0.02


def _priority(o) -> float:
    return {"battery_operator": o.operational.degradation_sensitivity, "building_portfolio": o.operational.comfort_priority,
            "ev_aggregator": o.operational.driver_satisfaction_priority}[o.owner_type]


def reservation_and_ask(o) -> tuple[float, float]:
    res = o.economic.min_compensation_per_mwh * (1 + 0.25 * _priority(o))
    return res, res * (1 + o.economic.target_margin)


def best_block(requested: list[float], length: int) -> tuple[int, int]:
    W = len(requested)
    length = max(1, min(length, W))
    best = max(range(W - length + 1), key=lambda s: (round(sum(requested[s:s + length]), 9), -s))
    return best, best + length


class StubProvider:
    name = "stub"
    model: Optional[str] = "deterministic-stub-v1"

    def decide(self, ctx: OwnerContext) -> ProviderResult:
        o, req = ctx.owner, ctx.request
        inc = req.incentive_price_per_mwh
        res, ask = reservation_and_ask(o)
        W = len(req.hours)
        capable = [a for a in ctx.assets if a.available_hours > 0 and max(a.max_mw_by_hour) > MIN_MW]
        dec = lambda code, msg: ProviderResult(DeclineOffer(reason_code=code, explanation=msg))
        if not capable:
            return dec("no_capable_assets", "None of my assets can deliver flexibility during this event.")
        if o.owner_type == "ev_aggregator" and o.operational.deadline_strictness >= 0.9 and W > 2 * o.operational.max_event_hours:
            return dec("deadline_risk", f"A {W}-hour event exceeds what my drivers' departure deadlines tolerate.")
        if inc >= ask:
            price, q = ask, 1.0
        elif inc >= res:
            price, q = inc, 0.5 + 0.5 * (inc - res) / max(ask - res, 1e-9)
        elif inc >= 0.8 * res and o.behavioral.risk_tolerance >= 0.5:
            price, q = res * (1 + o.economic.target_margin / 2), 1.0
        else:
            return dec("incentive_below_minimum", f"${inc:.0f}/MWh is below my minimum compensation (~${res:.0f}/MWh).")
        if inc < ask and o.owner_type == "battery_operator" and o.operational.reserve_preference >= 0.45:
            return dec("reserve_protected", "I protect my battery reserve unless the incentive covers my full asking price.")
        if inc < ask and o.owner_type == "building_portfolio" and o.operational.comfort_priority >= 0.8:
            return dec("comfort_priority", "Tenant comfort takes priority at this compensation.")
        value = [min(req.requested_mw_by_hour[t], sum(a.max_mw_by_hour[t] for a in capable)) * req.requested_mw_by_hour[t] for t in range(W)]   # deliverable MW per hour, weighted by how critical the hour is
        s, e = best_block(value, o.operational.max_event_hours)
        hold = {"battery_operator": o.operational.reserve_preference, "building_portfolio": o.operational.comfort_priority,
                "ev_aggregator": o.operational.driver_satisfaction_priority * o.operational.deadline_strictness}[o.owner_type]
        f = (0.55 + 0.45 * o.behavioral.participation_tendency) * q * (1 - 0.35 * hold)
        lines = []
        for a in capable:
            prof = [f * a.max_mw_by_hour[t] if s <= t < e else 0.0 for t in range(W)]
            blocks = blocks_of(prof)
            if blocks and max(prof) > MIN_MW:
                lines.append(AssetOffer(asset_id=a.asset_id, blocks=blocks))
        if not lines:
            return dec("no_capable_assets", "No asset can deliver a meaningful amount in the chosen hours.")
        tag = "counteroffer above the incentive ceiling" if price > inc else "offer"
        return ProviderResult(SubmitOffer(asset_offers=lines, price_per_mwh=round(price, 2), conditions=[f"max {o.operational.max_event_hours} contiguous hours"],
                                          explanation=f"Stub policy {tag}: reservation ${res:.0f}, ask ${ask:.0f}, incentive ${inc:.0f}; hours {s}-{e} where my assets are most useful."))

    def revise(self, ctx: OwnerContext, rejection: Rejection) -> ProviderResult:
        lines, keep = [], {ln.asset_id: ln for ln in rejection.offer.asset_offers}
        for v in rejection.validation.lines:
            if v.status == "valid":
                lines.append(keep[v.asset_id])
            elif v.feasible_envelope:
                lines.append(AssetOffer(asset_id=v.asset_id, blocks=v.feasible_envelope))
        if not lines:
            return ProviderResult(DeclineOffer(reason_code="other", explanation="After the physical check no asset can deliver the requested flexibility."))
        return ProviderResult(ReviseOffer(asset_offers=lines, price_per_mwh=rejection.offer.price_per_mwh, conditions=rejection.offer.conditions,
                                          explanation="Revised down to the physically feasible envelope reported by the validator."))
