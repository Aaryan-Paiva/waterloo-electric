from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from ..data.repositories import daily, get_load, get_pack, window
from ..schemas.world import LoadResponse
from ..schemas.zone import HistoricalLoadPoint, Zone
from ..world.zone import build_zone
from ..data import provenance as prov

router = APIRouter(prefix="/api/zones", tags=["zones"])
WORLDS = ["waterloo-demo"]
MAX_POINTS = 20000


def _pack(zone_id: str):
    if zone_id not in WORLDS:
        raise HTTPException(404, f"unknown zone {zone_id!r}")
    return get_pack(zone_id)


def load_response(zone_id: str, start: Optional[str], end: Optional[str], resolution: str) -> LoadResponse:
    pack = _pack(zone_id)
    data = get_load(zone_id)
    df = window(data.df, start, end)
    if resolution == "daily":
        df = daily(df)
    truncated = len(df) > MAX_POINTS
    df = df.iloc[:MAX_POINTS]
    hl = pack.historical_load
    points = [HistoricalLoadPoint(timestamp=r.timestamp.isoformat(), load_mw=round(float(r.load_mw), 3),
                                  observed_zone_mw=round(float(r.observed_mw), 1), source_id=hl.dataset_id,
                                  provenance="derived", quality_flag=r.quality_flag,
                                  mean_mw=round(float(r.mean_mw), 3) if "mean_mw" in df.columns else None,
                                  min_mw=round(float(r.min_mw), 3) if "min_mw" in df.columns else None)
              for r in df.itertuples()]
    return LoadResponse(zone_id=zone_id, mode=data.mode, resolution=resolution, capacity_mw=pack.capacity.value_mw,
                        capacity_provenance=pack.capacity.provenance,
                        provenance=prov.derived(hl.source_name, hl.scale.note), points=points, truncated=truncated)


@router.get("", response_model=list[Zone])
def list_zones():
    return [build_zone(z) for z in WORLDS]


@router.get("/{zone_id}", response_model=Zone)
def get_zone(zone_id: str):
    _pack(zone_id)
    return build_zone(zone_id)


@router.get("/{zone_id}/load", response_model=LoadResponse)
def get_zone_load(zone_id: str, start: Optional[str] = None, end: Optional[str] = None,
                  resolution: Literal["hourly", "daily"] = Query("hourly")):
    return load_response(zone_id, start, end, resolution)
