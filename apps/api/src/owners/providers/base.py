"""Provider abstraction: how an owner agent makes a decision. The provider returns a TYPED ACTION (tool call); it never touches
world state. Anything it returns is untrusted until the physical validator accepts it."""
from dataclasses import dataclass
from typing import Optional, Protocol

from ...schemas.owners import DeclineOffer, ReviseOffer, SubmitOffer
from ..context import OwnerContext, Rejection


class ProviderError(Exception):
    def __init__(self, msg: str, timeout: bool = False):
        super().__init__(msg)
        self.timeout = timeout


class ProviderUnavailable(ProviderError):
    """Missing key/SDK/config. The runner falls back to the stub and records why."""


@dataclass
class ProviderResult:
    action: SubmitOffer | ReviseOffer | DeclineOffer
    calls: int = 1
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class OwnerAgentProvider(Protocol):
    name: str
    model: Optional[str]

    def decide(self, ctx: OwnerContext) -> ProviderResult: ...
    def revise(self, ctx: OwnerContext, rejection: Rejection) -> ProviderResult: ...
