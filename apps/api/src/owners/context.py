"""What an owner agent is allowed to SEE: its own preferences, the request, and summaries of the assets it controls.
Read-only views; owners cannot see or change anything else (other owners' assets, the baseline, the scenario)."""
from typing import Optional

from pydantic import Field

from ..schemas.base import CamelModel
from ..schemas.owners import FlexibilityRequest, OfferBody, OfferValidation, OwnerAgent
from .physical import Physics


class AssetView(CamelModel):
    asset_id: str
    asset_type: str
    name: str
    kind: str
    params: dict
    max_mw_by_hour: list[float]            # static per-hour delivery ceiling over the event window (NOT a joint-feasibility guarantee)
    available_hours: int
    notes: list[str] = Field(default_factory=list)


class OwnerContext(CamelModel):
    owner: OwnerAgent
    request: FlexibilityRequest
    assets: list[AssetView]


class Rejection(CamelModel):
    offer: OfferBody
    validation: OfferValidation


def build_context(ph: Physics, owner: OwnerAgent, request: FlexibilityRequest, offset: int = 0) -> OwnerContext:
    """`offset`: index in the physics horizon where request.hours[0] sits (historical clusters build one context per event window)."""
    views = []
    W = len(request.hours)
    for aid in owner.controlled_asset_ids:
        a = ph.pop.get(aid)
        ceil = ph.ceilings.get(aid, [0.0] * (offset + W))[offset:offset + W]
        notes = []
        if aid not in ph.ceilings:
            notes.append(f"unavailable throughout the event ({ph.exclusions.get(aid, 'unavailable')})")
        if a.type == "battery":
            notes.append(f"usable energy above reserve ~{a.energy_mwh * (a.max_soc - a.min_soc):.2f} MWh at full charge; SOC evolves and is not guaranteed")
        elif a.type == "ev_fleet":
            notes.append("deferred energy must be recovered before the vehicles' departure deadline")
        else:
            notes.append(f"max {a.max_curtail_h} curtailed hour(s); rebound {a.rebound_fraction:.0%} follows the shed")
        views.append(AssetView(asset_id=aid, asset_type=a.type, name=a.name, kind=a.kind, params=a.params(), max_mw_by_hour=[round(x, 4) for x in ceil],
                               available_hours=sum(1 for x in ceil if x > 1e-9), notes=notes))
    return OwnerContext(owner=owner, request=request, assets=views)
