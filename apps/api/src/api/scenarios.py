from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from ..scenario_store import NotFound, store
from ..schemas.agents import AssumptionsUpdate
from ..capacityos.coordinator import CoordinationError, coordinate_event, resolve_window
from ..schemas.coordination import CoordinationRequest, CoordinationResult
from ..schemas.analysis import CapacityAnalysis, EventsResponse, ScenarioLoadResponse
from ..schemas.scenario import ProjectCreate, ProjectUpdate, Scenario, ScenarioCreate
from ..simulation.stress_test import list_events, run_capacity_analysis, scenario_load
from .zones import WORLDS

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _get(sid: str) -> Scenario:
    try:
        return store.get(sid)
    except NotFound:
        raise HTTPException(404, f"unknown scenario {sid!r}")


@router.post("", response_model=Scenario, status_code=201)
def create_scenario(req: ScenarioCreate):
    if req.zone_id not in WORLDS:
        raise HTTPException(404, f"unknown zone {req.zone_id!r}")
    return store.create(req)


@router.get("/{sid}", response_model=Scenario)
def get_scenario(sid: str):
    return _get(sid)


@router.post("/{sid}/clone", response_model=Scenario, status_code=201)
def clone_scenario(sid: str, name: Optional[str] = None):
    _get(sid)
    return store.clone(sid, name)


@router.post("/{sid}/projects", response_model=Scenario, status_code=201)
def add_project(sid: str, req: ProjectCreate):
    _get(sid)
    return store.add_project(sid, req)


@router.patch("/{sid}/projects/{pid}", response_model=Scenario)
def update_project(sid: str, pid: str, req: ProjectUpdate):
    _get(sid)
    try:
        return store.update_project(sid, pid, req)
    except NotFound:
        raise HTTPException(404, f"unknown project {pid!r}")


@router.delete("/{sid}/projects/{pid}", response_model=Scenario)
def delete_project(sid: str, pid: str):
    _get(sid)
    try:
        return store.delete_project(sid, pid)
    except NotFound:
        raise HTTPException(404, f"unknown project {pid!r}")


@router.get("/{sid}/analysis", response_model=CapacityAnalysis)
def get_analysis(sid: str):
    return run_capacity_analysis(_get(sid))


@router.get("/{sid}/events", response_model=EventsResponse)
def get_events(sid: str, limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0),
               order: Literal["chronological", "deficit"] = "chronological"):
    return list_events(_get(sid), limit, offset, order)


@router.get("/{sid}/load", response_model=ScenarioLoadResponse)
def get_scenario_load(sid: str, start: Optional[str] = None, end: Optional[str] = None,
                      resolution: Literal["hourly", "daily"] = Query("hourly")):
    return scenario_load(_get(sid), start, end, resolution)


@router.patch("/{sid}/assumptions", response_model=Scenario)
def update_assumptions(sid: str, req: AssumptionsUpdate):
    """Scenario-level DER participation overrides. The world (and its seeded population) is never changed."""
    _get(sid)
    return store.update_assumptions(sid, req.model_dump(exclude_none=True))


@router.post("/{sid}/simulate/event", response_model=CoordinationResult)
@router.post("/{sid}/coordinate", response_model=CoordinationResult)
def coordinate(sid: str, req: CoordinationRequest):
    """Optimize DER dispatch for ONE event window. Read-only: the scenario and baseline are never modified."""
    sc = _get(sid)
    try:
        start, end = resolve_window(sc, req.window_id, req.start, req.end)
        return coordinate_event(sc, start, end, req.tail_hours)
    except CoordinationError as e:
        raise HTTPException(422, str(e))
