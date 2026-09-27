"""Owner/operator agent + agentic-run API (Phase 5-6). Runs are stored in a bounded in-memory store and never mutate the scenario."""
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..capacityos.coordinator import CoordinationError, resolve_window
from ..owners.grouping import build_owners
from ..owners.physical import build_physics
from ..owners.providers import provider_status
from ..owners.run_store import runs
from ..owners.runner import build_request, replay_run, run_agentic
from ..scenario_store import NotFound, store
from ..schemas.base import CamelModel
from ..schemas.coordination import AgentDispatch, CoordinationResult
from ..schemas.owners import AgenticRun, AgenticRunRequest, FlexibilityRequest, OfferRecord, OwnerAgent, TraceEvent
from ..schemas.scenario import Scenario
from ..world.population import build_population

router = APIRouter(prefix="/api", tags=["agentic"])


def _sc(sid: str) -> Scenario:
    try:
        return store.get(sid)
    except NotFound:
        raise HTTPException(404, f"unknown scenario {sid!r}")


def _run(rid: str) -> AgenticRun:
    s = runs.get(rid)
    if s is None:
        raise HTTPException(404, f"unknown agentic run {rid!r}")
    return s.run


class OwnerAgentsResponse(CamelModel):
    zone_id: str
    owners: list[OwnerAgent]
    flexible_assets: int
    unowned_assets: list[str]       # solar clusters: context only, no owner
    note: str


@router.get("/agentic/config")
def agentic_config():
    return provider_status()


@router.get("/scenarios/{sid}/owner-agents", response_model=OwnerAgentsResponse)
def owner_agents(sid: str):
    sc = _sc(sid)
    owners = list(build_owners(sc.zone_id))
    pop = build_population(sc.zone_id)
    return OwnerAgentsResponse(zone_id=sc.zone_id, owners=owners, flexible_assets=sum(len(o.controlled_asset_ids) for o in owners),
                               unowned_assets=sorted(a.id for a in pop.agents if a.type == "solar"),
                               note="Owner/operator agents are Modeled synthetic decision-makers, each controlling one or more deterministic physical DER models.")


def _window(sc: Scenario, window_id: Optional[str], start: Optional[str], end: Optional[str]):
    try:
        return resolve_window(sc, window_id, start, end)
    except CoordinationError as e:
        raise HTTPException(422, str(e))


@router.post("/scenarios/{sid}/events/{event_id}/flexibility-request", response_model=FlexibilityRequest)
def flexibility_request(sid: str, event_id: str, req: Optional[AgenticRunRequest] = None):
    """Preview the request CapacityOS would broadcast for this event window (Derived; nothing is stored or dispatched)."""
    sc = _sc(sid)
    req = req or AgenticRunRequest()
    s, e = _window(sc, event_id, None, None)
    try:
        return build_request(sc, build_physics(sc, s, e, req.tail_hours), event_id, req.incentive_price_per_mwh)
    except CoordinationError as ex:
        raise HTTPException(422, str(ex))


def _go(sc: Scenario, req: AgenticRunRequest, event_id: Optional[str]) -> AgenticRun:
    s, e = _window(sc, event_id or req.window_id, req.start, req.end)
    try:
        return run_agentic(sc, s, e, event_id or req.window_id, req.incentive_price_per_mwh, req.provider, req.tail_hours)
    except CoordinationError as ex:
        raise HTTPException(422, str(ex))


@router.post("/scenarios/{sid}/events/{event_id}/agentic-run", response_model=AgenticRun)
def agentic_run_for_event(sid: str, event_id: str, req: Optional[AgenticRunRequest] = None):
    return _go(_sc(sid), req or AgenticRunRequest(), event_id)


@router.post("/scenarios/{sid}/agentic-run", response_model=AgenticRun)
def agentic_run(sid: str, req: AgenticRunRequest):
    return _go(_sc(sid), req, None)


@router.get("/agentic-runs/{rid}", response_model=AgenticRun)
def get_run(rid: str):
    return _run(rid)


@router.get("/agentic-runs/{rid}/offers", response_model=list[OfferRecord])
def run_offers(rid: str):
    return [o for r in _run(rid).records for o in r.offers]


@router.get("/agentic-runs/{rid}/dispatch", response_model=CoordinationResult)
def run_dispatch(rid: str):
    return _run(rid).coordination


@router.get("/agentic-runs/{rid}/trace", response_model=list[TraceEvent])
def run_trace(rid: str):
    return _run(rid).trace


@router.post("/agentic-runs/{rid}/replay", response_model=AgenticRun)
def replay(rid: str):
    """Re-executes the recorded owner actions (no model) through validation and clearing; `resultHash` equals the original's if nothing changed."""
    _run(rid)
    try:
        return replay_run(rid)
    except NotFound:
        raise HTTPException(409, "the scenario of this run no longer exists")
    except CoordinationError as ex:
        raise HTTPException(422, str(ex))
