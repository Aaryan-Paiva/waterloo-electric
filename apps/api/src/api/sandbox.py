from fastapi import APIRouter, HTTPException

from ..capacityos.sandbox import run_matrix, run_sandbox, world_info
from ..schemas.sandbox import DeviceParams, MatrixRequest, MatrixResponse, SandboxRunRequest, SandboxRunResponse, SandboxWorld

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.get("/world", response_model=SandboxWorld)
def sandbox_world():
    return world_info()


@router.post("/world", response_model=SandboxWorld)
def sandbox_world_for(params: DeviceParams):
    """The world for an edited device configuration (counts, sizes), so the UI can show real totals for what the user built."""
    return world_info(params)


@router.post("/run", response_model=SandboxRunResponse)
def sandbox_run(req: SandboxRunRequest):
    """Drop a data centre in a real season/hour and rebalance. Read-only: nothing in the world or the stored scenarios changes."""
    try:
        return run_sandbox(req)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/matrix", response_model=MatrixResponse)
def sandbox_matrix(req: MatrixRequest):
    """Does this constraint set hold in every season? One run per season on the real reference day. Read-only."""
    try:
        return run_matrix(req)
    except ValueError as e:
        raise HTTPException(422, str(e))
