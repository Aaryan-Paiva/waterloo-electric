from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.world import LoadResponse, WorldState
from ..world.state import build_world_state
from .zones import WORLDS, load_response

router = APIRouter(prefix="/api/worlds", tags=["worlds"])


@router.get("/{world_id}", response_model=WorldState)
def get_world(world_id: str):
    if world_id not in WORLDS:
        raise HTTPException(404, f"unknown world {world_id!r}")
    return build_world_state(world_id)


@router.get("/{world_id}/load", response_model=LoadResponse)
def get_world_load(world_id: str, start: Optional[str] = None, end: Optional[str] = None,
                   resolution: Literal["hourly", "daily"] = Query("hourly")):
    return load_response(world_id, start, end, resolution)
