"""Owner/operator agents, flexibility requests, offers, validation and agentic runs (CLAUDE.md §13b).

Naming: a *physical DER model* is the deterministic electrical resource (see agents/); an *owner/operator agent* is the
decision-maker controlling one or more of them. Owner behavior is Modeled; requests, validation and clearing are Derived.
"""
from typing import Literal, Optional, Union

from pydantic import Field

from .base import CamelModel
from .coordination import CoordinationResult

OwnerType = Literal["battery_operator", "ev_aggregator", "building_portfolio"]
DeclineCode = Literal["incentive_below_minimum", "event_too_long", "reserve_protected", "comfort_priority", "deadline_risk",
                      "no_capable_assets", "event_frequency", "other"]


# ---- owner agents (Modeled) -------------------------------------------------------------------------------------------
class EconomicPrefs(CamelModel):
    min_compensation_per_mwh: float        # reservation price
    target_margin: float                   # asked price = reservation x (1 + margin)
    price_sensitivity: float               # 0..1: how strongly the owner reacts to the incentive


class OperationalPrefs(CamelModel):
    reserve_preference: float              # 0..1 share of usable battery energy kept back
    comfort_priority: float                # 0..1 (buildings)
    driver_satisfaction_priority: float    # 0..1 (EV fleets)
    degradation_sensitivity: float         # 0..1 (batteries)
    max_event_hours: int                   # longest contiguous commitment
    max_events_per_month: int
    deadline_strictness: float             # 0..1


class BehavioralPrefs(CamelModel):
    risk_tolerance: float                  # 0..1
    participation_tendency: float          # 0..1


class OwnerAgent(CamelModel):
    id: str
    name: str
    owner_type: OwnerType
    controlled_asset_ids: list[str]
    economic: EconomicPrefs
    operational: OperationalPrefs
    behavioral: BehavioralPrefs
    provenance: Literal["modeled"] = "modeled"


# ---- flexibility request (Derived) ------------------------------------------------------------------------------------
class FlexibilityRequest(CamelModel):
    id: str
    scenario_id: str
    zone_id: str
    event_window_id: Optional[str] = None
    start: str
    end: str                                # exclusive
    hours: list[str]                        # window hour timestamps (EST); offer blocks index into this list
    requested_mw_by_hour: list[float]       # pre-dispatch deficit per window hour
    peak_requested_mw: float
    requested_mwh: float
    incentive_price_per_mwh: float          # price ceiling CapacityOS will pay
    capacity_mw: float
    created_at: str
    provenance: Literal["derived"] = "derived"


# ---- offers & tool calls (structured; never parsed from prose) ------------------------------------------------------------
class Block(CamelModel):
    start_hour: int = Field(ge=0)           # index into request.hours
    end_hour: int = Field(gt=0)             # exclusive
    mw: float = Field(ge=0)


class AssetOffer(CamelModel):
    asset_id: str
    blocks: list[Block]


class OfferBody(CamelModel):
    asset_offers: list[AssetOffer] = Field(min_length=1, max_length=200)
    price_per_mwh: float
    conditions: list[str] = Field(default_factory=list, max_length=6)
    explanation: str = Field(default="", max_length=600)


class SubmitOffer(OfferBody):
    tool: Literal["submit_offer"] = "submit_offer"


class ReviseOffer(OfferBody):
    tool: Literal["revise_offer"] = "revise_offer"


class DeclineOffer(CamelModel):
    tool: Literal["decline_offer"] = "decline_offer"
    reason_code: DeclineCode = "other"
    explanation: str = Field(default="", max_length=600)


class RequestInformation(CamelModel):
    tool: Literal["request_information"] = "request_information"
    asset_ids: list[str] = Field(default_factory=list, max_length=200)


OwnerAction = Union[SubmitOffer, ReviseOffer, DeclineOffer]


# ---- physical validation ---------------------------------------------------------------------------------------------
class AssetValidation(CamelModel):
    asset_id: str
    status: Literal["valid", "invalid"]
    violation: Optional[str] = None
    requested: list[Block]
    feasible_envelope: list[Block] = Field(default_factory=list)
    explanation: str = ""


class OfferValidation(CamelModel):
    status: Literal["valid", "invalid"]
    lines: list[AssetValidation]
    violation: Optional[str] = None         # first violation code
    explanation: str = ""


class OfferRecord(CamelModel):
    id: str
    owner_id: str
    revision: int                           # 0 = first offer, 1 = the single allowed revision
    body: OfferBody
    validation: OfferValidation
    status: Literal["accepted", "rejected", "revised", "priced_out"]
    counteroffer: bool = False              # asked price is above the incentive ceiling
    offered_mwh: float
    peak_mw: float
    provenance: Literal["modeled"] = "modeled"


# ---- run record -------------------------------------------------------------------------------------------------------
OwnerStatus = Literal["idle", "evaluating", "offered", "declined", "revising", "validation_failed", "accepted", "rejected", "priced_out", "fallback"]


class OwnerRecord(CamelModel):
    owner_id: str
    status: OwnerStatus
    decline_code: Optional[DeclineCode] = None
    decision_explanation: str = ""
    offers: list[OfferRecord] = Field(default_factory=list)
    provider_used: str
    fallback_reason: Optional[str] = None
    agent_calls: int = 0
    duration_ms: float = 0.0
    dispatched_mwh: float = 0.0
    cost: float = 0.0


class TraceEvent(CamelModel):
    seq: int
    type: str
    owner_id: Optional[str] = None
    payload: dict = Field(default_factory=dict)


class MarketSummary(CamelModel):
    requested_peak_mw: float
    requested_mwh: float
    offered_peak_mw: float
    offered_mwh: float
    validated_peak_mw: float
    validated_mwh: float
    priced_out_mwh: float
    dispatched_peak_mw: float
    dispatched_mwh: float
    remaining_worst_deficit_mw: float
    remaining_energy_above_capacity_mwh: float
    clearing_cost: float
    incentive_price_per_mwh: float
    owners_total: int
    owners_offered: int
    owners_declined: int
    owners_rejected: int
    owners_priced_out: int
    owners_accepted: int


class ProviderInfo(CamelModel):
    requested: str
    used: str
    model: Optional[str] = None
    fallback_reason: Optional[str] = None


class Diagnostics(CamelModel):
    agent_calls: int
    failed_calls: int
    timeouts: int
    fallbacks: int
    duration_ms: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class AgenticRunRequest(CamelModel):
    window_id: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    incentive_price_per_mwh: float = Field(default=80.0, gt=0, le=1000)
    provider: Optional[Literal["stub", "openai"]] = None
    tail_hours: int = Field(default=8, ge=0, le=12)


class AgenticRun(CamelModel):
    id: str
    replay_of: Optional[str] = None
    scenario_id: str
    mode: Literal["agentic"] = "agentic"
    provider: ProviderInfo
    request: FlexibilityRequest
    owners: list[OwnerAgent]
    records: list[OwnerRecord]
    trace: list[TraceEvent]
    market: MarketSummary
    coordination: CoordinationResult
    diagnostics: Diagnostics
    result_hash: str
    note: str
    decision_source: Literal["llm_openai", "mixed_llm_and_stub", "deterministic_stub", "replay"] = "deterministic_stub"   # who made the owner decisions
    llm_owner_count: int = 0        # owners whose decisions came from a real LLM call (0 for the stub / replay / fallbacks)
    provenance: Literal["derived"] = "derived"
    owner_behavior_provenance: Literal["modeled"] = "modeled"
