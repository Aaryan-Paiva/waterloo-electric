import json
import queue
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..capacityos.recommend import recommend
from ..capacityos.sandbox import run_matrix, run_sandbox, world_info
from ..schemas.sandbox import DeviceParams, MatrixRequest, MatrixResponse, RecommendResponse, SandboxRunRequest, SandboxRunResponse, SandboxWorld

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


def _clean(fn, *args):
    """Never leak a stack trace to the client: a bad input is a 422, anything else (a provider outage, a bug) is a plain 500."""
    try:
        return fn(*args)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except HTTPException:
        raise
    except Exception as e:                                                                 # noqa: BLE001
        raise HTTPException(500, f"The simulation hit an unexpected error ({type(e).__name__}). Try again, or with different loads or settings.") from e


@router.get("/world", response_model=SandboxWorld)
def sandbox_world():
    return _clean(world_info)


@router.post("/world", response_model=SandboxWorld)
def sandbox_world_for(params: DeviceParams):
    """The world for an edited device configuration (counts, sizes), so the UI can show real totals for what the user built."""
    return _clean(world_info, params)


@router.post("/run", response_model=SandboxRunResponse)
def sandbox_run(req: SandboxRunRequest):
    """Drop a data centre in a real season/hour and rebalance. Read-only: nothing in the world or the stored scenarios changes."""
    return _clean(run_sandbox, req)


@router.post("/matrix", response_model=MatrixResponse)
def sandbox_matrix(req: MatrixRequest):
    """Does this constraint set hold in every season? One run per season on the real reference day. Read-only."""
    return _clean(run_matrix, req)


@router.post("/run-stream")
def sandbox_run_stream(req: SandboxRunRequest):
    """Same run, streamed as NDJSON: one `progress` line per owner as its decision returns, then one `result` line (or `error`)."""
    q: "queue.Queue[dict]" = queue.Queue()

    def work():
        try:
            q.put({"type": "result", "data": json.loads(run_sandbox(req, on_progress=q.put).model_dump_json(by_alias=True))})
        except ValueError as e:
            q.put({"type": "error", "message": str(e)})
        except Exception as e:                                                             # noqa: BLE001
            q.put({"type": "error", "message": f"{type(e).__name__}: {e}"})
        q.put({"type": "end"})

    threading.Thread(target=work, daemon=True).start()

    def gen():
        while True:
            m = q.get()
            if m["type"] == "end":
                return
            yield json.dumps(m) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@router.post("/recommend", response_model=RecommendResponse)
def sandbox_recommend(req: SandboxRunRequest):
    """What would it take? Verified constraint changes and the zone limit that would make this season's real day hold. Read-only."""
    return _clean(recommend, req)
