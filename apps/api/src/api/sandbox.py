from fastapi import APIRouter, HTTPException

from ..capacityos.sandbox import run_sandbox, world_info
from ..schemas.sandbox import SandboxRunRequest, SandboxRunResponse, SandboxWorld

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.get("/world", response_model=SandboxWorld)
def sandbox_world():
    return world_info()


@router.post("/run", response_model=SandboxRunResponse)
def sandbox_run(req: SandboxRunRequest):
    """Drop a data centre in a real season/hour and rebalance. Read-only: nothing in the world or the stored scenarios changes."""
    try:
        return run_sandbox(req)
    except ValueError as e:
        raise HTTPException(422, str(e))
