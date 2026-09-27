from ..data import provenance as prov
from ..data.repositories import get_load, get_pack, summarize
from ..schemas.world import WorldState
from .zone import build_zone


def build_world_state(world_id: str) -> WorldState:
    pack, data = get_pack(world_id), get_load(world_id)
    hl = pack.historical_load
    mode_note = "Committed 30-day fixture (demo mode)." if data.mode == "fixture" else "Full 2021-2025 hourly dataset."
    return WorldState(
        id=pack.id, name=pack.name, label=pack.label, mode=data.mode, zone=build_zone(world_id),
        load_summary=summarize(data.df, pack.capacity.value_mw),
        provenance={
            "historicalDemand": prov.derived(hl.source_name, f"{hl.scale.note} {mode_note}"),
            "derPopulation": prov.modeled("CapacityOS synthetic DER population", "Seeded synthetic batteries, EV fleets, flexible buildings and solar clusters (seed = world pack der_seed). Modeled flexibility AROUND the baseline, never added to it; not known real customers."),
            "zoneCapacity": prov.modeled("Hackathon assumption", pack.capacity.source_note),
            "newProject": prov.hypothetical("Projects are added by the user (Phase 2)."),
        },
        der_assumptions=pack.der_assumptions,
    )
