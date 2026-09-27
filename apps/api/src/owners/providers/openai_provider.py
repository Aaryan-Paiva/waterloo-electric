"""OpenAI owner-agent provider: structured tool calling, schema-validated output, explicit timeout, bounded retries.

Trust boundary: the model's output is UNTRUSTED. It is parsed into a typed action (pydantic); anything malformed is retried a bounded
number of times and then raised as ProviderError (the runner falls back to the stub for that owner and records it). The action is then
physically validated by deterministic code; nothing the model says can change SOC, load, limits, the scenario or capacity.
`request_information` lets the model look up its OWN assets' data (read-only) inside a bounded turn budget.
"""
import json
import threading
import time
from typing import Any, Optional

from pydantic import ValidationError

from ...schemas.owners import DeclineOffer, OfferBody, RequestInformation, ReviseOffer, SubmitOffer
from ..context import OwnerContext, Rejection
from ..tools import request_information
from .base import ProviderError, ProviderResult, ProviderUnavailable

MAX_TURNS = 3
RATE_RETRIES = 3            # extra attempts after a 429, with backoff (separate from the malformed-output retries)
_gate = threading.Lock()
_last_call = [0.0]


def _pace(min_interval: float) -> None:
    """Global pacing between model calls (thread-safe) so a run stays under the account's requests-per-minute limit."""
    if min_interval <= 0:
        return
    with _gate:
        wait = _last_call[0] + min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()

SYSTEM = """You are the decision-making agent of a synthetic owner/operator of distributed energy resources in a grid-planning SANDBOX \
(all owners and assets are modeled, not real customers). CapacityOS sends a flexibility request for a capacity-constrained event window. \
Decide whether to participate, how much, and at what price, according to YOUR preferences (minimum compensation, margin, reserve \
preference, comfort / driver priorities, degradation sensitivity, max event hours, risk tolerance, participation tendency).
Rules: act ONLY by calling exactly one tool. Offer blocks are hour indexes into request.hours (end exclusive) with MW per asset; only offer assets you \
control. A physical validator will reject offers the assets cannot physically deliver; you may not override it. Asking above the \
incentive ceiling makes a counteroffer that will not be cleared. Be realistic and consistent with your preferences; keep explanations short.
Practical guidance: offer ONLY in hours where request.requestedMwByHour is above 0 (the event window peak is what matters); size the offer to the request, not to your assets' maximum. Each asset's deliverableMwhTotal is the energy it can really deliver over the window: keep the sum of (MW x hours) per asset at or below it and put it in the highest-need hours. maxMwByHour is a static ceiling, not a joint guarantee: a battery cannot run at its ceiling for every hour (energy is finite, so keep MW x hours within its usable energy and use the highest-need hours), an EV fleet must recover deferred energy before departure, a building can only curtail for its max hours. When revising after a physical rejection, COPY the blocks from physicalRejection.validation.lines[].feasibleEnvelope for each asset (you may lower them, never raise them)."""


def _schema(model) -> dict:
    s = model.model_json_schema(by_alias=True)
    s.get("properties", {}).pop("tool", None)
    s["required"] = [r for r in s.get("required", []) if r != "tool"]
    return s


def _tool(name: str, desc: str, model) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": _schema(model)}}


TOOLS = {
    "submit_offer": _tool("submit_offer", "Offer flexibility from assets you control: per-asset MW blocks and one price ($/MWh).", SubmitOffer),
    "decline_offer": _tool("decline_offer", "Decline to participate in this event.", DeclineOffer),
    "revise_offer": _tool("revise_offer", "Submit ONE revised offer after a physical-validation rejection (use the feasible envelope).", ReviseOffer),
    "request_information": _tool("request_information", "Look up read-only details of assets you control.", RequestInformation),
}
ACTIONS = {"submit_offer": SubmitOffer, "revise_offer": ReviseOffer, "decline_offer": DeclineOffer}


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str = "", model: str = "gpt-4o-mini", timeout_s: float = 20.0, max_retries: int = 1, client: Any = None, min_interval_s: float = 0.0):
        self.model = model
        self.min_interval = min_interval_s
        self.max_retries = max(0, max_retries)
        if client is not None:
            self._client = client
            return
        if not api_key:
            raise ProviderUnavailable("OPENAI_API_KEY is not set")
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ProviderUnavailable("the `openai` package is not installed (pip install -e '.[openai]')") from e
        self._client = OpenAI(api_key=api_key, timeout=timeout_s, max_retries=0)

    # -- public --------------------------------------------------------------------------------------------------------
    def decide(self, ctx: OwnerContext) -> ProviderResult:
        req = ctx.request.requested_mw_by_hour
        top = sorted(range(len(req)), key=lambda t: -req[t])[:5]
        return self._run(ctx, ["submit_offer", "decline_offer", "request_information"], {"task": "decide", "highestNeedHourIndexes": sorted(top), "context": ctx.model_dump(by_alias=True)})

    def revise(self, ctx: OwnerContext, rejection: Rejection) -> ProviderResult:
        return self._run(ctx, ["revise_offer", "decline_offer"], {"task": "revise_once", "context": ctx.model_dump(by_alias=True),
                                                                   "physicalRejection": rejection.model_dump(by_alias=True)})

    # -- internals -----------------------------------------------------------------------------------------------------
    def _run(self, ctx: OwnerContext, allowed: list[str], payload: dict) -> ProviderResult:
        msgs: list[dict] = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(payload)}]
        tools = [TOOLS[n] for n in allowed]
        calls = in_tok = out_tok = 0
        errors = 0
        for _ in range(MAX_TURNS + self.max_retries):
            try:
                resp = None
                for attempt in range(RATE_RETRIES + 1):
                    _pace(self.min_interval)
                    try:
                        resp = self._client.chat.completions.create(model=self.model, messages=msgs, tools=tools, tool_choice="required")
                        break
                    except Exception as e:                                # noqa: BLE001
                        if attempt < RATE_RETRIES and "ratelimit" in type(e).__name__.lower() and "insufficient_quota" not in str(e) and "no credits" not in str(e):
                            time.sleep(max(self.min_interval, 6.5) * (attempt + 1))      # back off and retry a requests-per-minute 429
                            continue
                        raise
            except Exception as e:                                        # noqa: BLE001 — timeouts/network/API errors all become ProviderError
                timeout = "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower()
                raise ProviderError(f"{type(e).__name__}: {str(e)[:160]}", timeout=timeout) from e
            calls += 1
            u = getattr(resp, "usage", None)
            in_tok += int(getattr(u, "prompt_tokens", 0) or 0)
            out_tok += int(getattr(u, "completion_tokens", 0) or 0)
            msg = resp.choices[0].message
            tcs = getattr(msg, "tool_calls", None) or []
            if not tcs:
                errors += 1
                msgs += [{"role": "assistant", "content": getattr(msg, "content", "") or ""}, {"role": "user", "content": "Respond by calling exactly one tool."}]
            else:
                tc = tcs[0]
                name = tc.function.name
                msgs.append({"role": "assistant", "content": None, "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": name, "arguments": tc.function.arguments}}]})
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    if name not in allowed:
                        raise ValueError(f"tool {name} not allowed here")
                    if name == "request_information":
                        info = RequestInformation.model_validate(args)
                        result = request_information(ctx, info)
                        msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
                        continue
                    action = ACTIONS[name].model_validate(args)
                    return ProviderResult(action, calls=calls, input_tokens=in_tok, output_tokens=out_tok)
                except (ValidationError, ValueError, json.JSONDecodeError) as e:
                    errors += 1
                    msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps({"error": str(e)[:300]})})
            if errors > self.max_retries:
                break
        raise ProviderError(f"no valid tool call after {calls} call(s)")
