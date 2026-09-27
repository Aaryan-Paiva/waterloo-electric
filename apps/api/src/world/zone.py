from ..data.repositories import get_load, get_pack
from ..schemas.zone import Zone


def build_zone(world_id: str) -> Zone:
    pack, data = get_pack(world_id), get_load(world_id)
    return Zone(id=pack.id, name=pack.name, timezone=pack.timezone, capacity_mw=pack.capacity.value_mw,
                capacity_provenance=pack.capacity.provenance, historical_start=data.df["timestamp"].iloc[0].isoformat(),
                historical_end=data.df["timestamp"].iloc[-1].isoformat(), world_seed=pack.der_seed)
