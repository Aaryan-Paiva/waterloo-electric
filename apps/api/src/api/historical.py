"""Phase 7 API: coordinate every historical capacity-event window (deterministic owner policy, 0 LLM calls). Read-only; results are cached."""
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..capacityos.coordinator import CoordinationError
from ..capacityos.historical import get_or_run, get_result
from ..scenario_store import NotFound, store
from ..schemas.historical import EventResult, HistoricalRequest, HistoricalResult
from ..schemas.scenario import Scenario

router = APIRouter(prefix="/api", tags=["historical"])


def _sc(sid: str) -> Scenario:
    try:
        return store.get(sid)
    except NotFound:
        raise HTTPException(404, f"unknown scenario {sid!r}")


@router.post("/scenarios/{sid}/historical-coordination", response_model=HistoricalResult)
def historical_coordination(sid: str, req: Optional[HistoricalRequest] = None):
    """Runs (or returns the cached) chronological coordination of ALL capacity-event windows at the chosen incentive. Takes ~10 s uncached."""
    sc = _sc(sid)
    try:
        return get_or_run(sc, req or HistoricalRequest())
    except CoordinationError as e:
        raise HTTPException(422, str(e))


def _run(rid: str) -> HistoricalResult:
    r = get_result(rid)
    if r is None:
        raise HTTPException(404, f"unknown historical run {rid!r}")
    return r


@router.get("/historical-runs/{rid}", response_model=HistoricalResult)
def get_historical(rid: str):
    return _run(rid)


@router.get("/historical-runs/{rid}/events", response_model=list[EventResult])
def historical_events(rid: str, year: Optional[int] = None, season: Optional[str] = None, status: Optional[str] = None, severity: Optional[str] = None):
    return [e for e in _run(rid).events if (year is None or e.year == year) and (season is None or e.season == season)
            and (status is None or e.status == status) and (severity is None or e.severity == severity)]
