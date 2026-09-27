import pytest
from pydantic import ValidationError

from src import settings
from src.schemas import CapacityEvent, Project, Provenance, WorldPack, Zone


def test_world_pack_validates_and_labels_are_honest():
    pack = WorldPack.model_validate_json((settings.WORLD_PACKS_DIR / "waterloo_demo.json").read_text())
    assert pack.id == "waterloo-demo"
    assert pack.capacity.provenance == "modeled"              # capacity is an assumption
    assert pack.historical_load.provenance == "derived"       # scaled observed shape, never "observed Waterloo"
    assert pack.historical_load.source_timezone_verified is False
    assert pack.der_seed == 42017


def test_world_pack_rejects_observed_label_for_scaled_series():
    raw = (settings.WORLD_PACKS_DIR / "waterloo_demo.json").read_text().replace('"provenance": "derived"', '"provenance": "observed"')
    with pytest.raises(ValidationError):
        WorldPack.model_validate_json(raw)


def test_camel_case_serialisation():
    z = Zone(id="z", name="Z", timezone="America/Toronto", capacity_mw=90, capacity_provenance="modeled",
             historical_start="a", historical_end="b", world_seed=1)
    d = z.model_dump(by_alias=True)
    assert "capacityMw" in d and "capacityProvenance" in d and "worldSeed" in d


def test_projects_are_always_hypothetical():
    assert Project(id="p", type="data_center", name="DC", nominal_load_mw=20).provenance == "hypothetical"
    with pytest.raises(ValidationError):
        Project(id="p", type="data_center", name="DC", nominal_load_mw=20, provenance="observed")


def test_provenance_types_and_event_contract():
    with pytest.raises(ValidationError):
        Provenance(type="real")
    e = CapacityEvent(id="e", timestamp="t", baseline_load_mw=78, project_load_mw=20, local_generation_mw=0,
                      pre_dispatch_net_load_mw=98, capacity_mw=90, deficit_mw=8, requested_flexibility_mw=8, resolved=False)
    assert e.deficit_mw == 8 and e.post_dispatch_net_load_mw is None
