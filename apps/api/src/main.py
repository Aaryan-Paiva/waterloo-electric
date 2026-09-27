from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import settings
from .api import agents, historical, owners, sandbox, scenarios, worlds, zones

app = FastAPI(title="CapacityOS API", version="0.1.0",
              description="Capacity-planning and flexibility sandbox. Not a utility engineering study.")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["*"])
app.include_router(zones.router)
app.include_router(worlds.router)
app.include_router(scenarios.router)
app.include_router(agents.router)
app.include_router(owners.router)
app.include_router(historical.router)
app.include_router(sandbox.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "capacityos-api", "phase": "7"}
