"""Typed owner tools (CLAUDE.md §13b): submit_offer / decline_offer / revise_offer / request_information.

The tool argument models live in schemas/owners.py. Every actionable decision arrives as one of these typed calls; free-form prose is
never parsed into dispatch. `execute` is the single authorization + validation choke point: a tool call can only ever produce an
OfferValidation (or read-only information); it has no path to mutate physical or world state.
"""
from typing import Union

from ..schemas.owners import DeclineOffer, OfferValidation, OwnerAgent, RequestInformation, ReviseOffer, SubmitOffer
from .context import OwnerContext
from .physical import Physics, validate_offer

TOOL_NAMES = ("submit_offer", "decline_offer", "revise_offer", "request_information")


def request_information(ctx: OwnerContext, call: RequestInformation) -> dict:
    """Read-only. An owner can only look up assets it controls."""
    mine = {v.asset_id: v.model_dump(by_alias=True) for v in ctx.assets}
    return {a: mine.get(a, {"error": "not an asset you control"}) for a in (call.asset_ids or list(mine))}


def execute(ph: Physics, owner: OwnerAgent, action: Union[SubmitOffer, ReviseOffer, DeclineOffer], committed: set[str]) -> OfferValidation | None:
    if isinstance(action, DeclineOffer):
        return None
    return validate_offer(ph, owner, action, committed)
