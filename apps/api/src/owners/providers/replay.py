"""Replays recorded owner actions (deterministic audit/replay of a stored run; no model, no network)."""
from typing import Optional

from ...schemas.owners import DeclineOffer
from ..context import OwnerContext, Rejection
from .base import ProviderResult


class ReplayProvider:
    name = "replay"

    def __init__(self, decisions: dict[str, list], model: Optional[str] = None):
        self._d = {k: list(v) for k, v in decisions.items()}   # owner_id -> [first action, optional revision action]
        self.model = model

    def _next(self, owner_id: str) -> ProviderResult:
        q = self._d.get(owner_id) or []
        return ProviderResult(q.pop(0) if q else DeclineOffer(reason_code="other", explanation="no recorded action"), calls=0)

    def decide(self, ctx: OwnerContext) -> ProviderResult:
        return self._next(ctx.owner.id)

    def revise(self, ctx: OwnerContext, rejection: Rejection) -> ProviderResult:
        return self._next(ctx.owner.id)
