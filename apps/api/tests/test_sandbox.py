"""Waterloo Electric sandbox API: real reference days, playback script from the real trace, parameters change outcomes, immutability."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.capacityos.sandbox import reference_day, run_sandbox, world_info
from src.data.repositories import get_load
from src.main import app
from src.schemas.sandbox import DeviceParams, SandboxRunRequest

client = TestClient(app)
GOLDEN = dict(season="summer", hour=16, dc_mw=20)


def test_reference_days_are_real_and_fixed():
    d = {s: reference_day(s) for s in ("winter", "spring", "summer", "fall")}
    assert d["summer"].date().isoformat() == "2025-06-24"                   # the Phase 4 golden day
    df = get_load("waterloo-demo").df
    for s, day in d.items():
        assert day in set(df["timestamp"].dt.normalize())
    w = world_info()
    assert w.capacity_mw == 90.0 and w.devices == {"battery": 60, "ev_fleet": 42, "building": 108, "solar": 24} and w.owner_count == 18 and set(w.seasons) == {"winter", "spring", "summer", "fall"}
    assert all(len(v.hourly_baseline_mw) == 24 for v in w.seasons.values())
    assert w.provenance["demand"].startswith("derived") and w.provenance["devices"].startswith("modeled")


def test_golden_run_has_a_script_built_from_the_real_trace():
    r = run_sandbox(SandboxRunRequest(**GOLDEN))
    assert r.has_overload and r.base_mw == 78.0 and r.load_before_mw == 98.0 and r.overload_mw == 8.0 and r.capacity_mw == 90.0
    kinds = [s.kind for s in r.script]
    assert kinds[0] == "request" and kinds[-1] == "done" and "clearing" in kinds and kinds.count("dispatch") == 3
    assert [s.i for s in r.script] == list(range(len(r.script)))
    assert r.checks_passed and r.decision_source in ("deterministic_stub", "mixed_llm_and_stub") and r.decision_source != "llm_openai"
    assert 0 <= r.absorbed_mw <= r.overload_mw and r.load_after_mw == pytest.approx(r.load_before_mw - r.absorbed_mw, abs=0.05) or r.remaining_mw == 0
    assert len(r.curve.hours) == 24 == len(r.curve.before) == len(r.curve.after)
    assert all(a <= max(b, r.capacity_mw) + 1e-6 for a, b in zip(r.curve.after, r.curve.before))          # never pushed over capacity (recharging may add load below it)
    assert any(s.kind == "validation_fail" for s in r.script)                          # the physical check is visible in the story
    assert r.outcome in ("holds", "partly_holds", "breaks") and r.provenance["results"] == "derived"


def test_deterministic():
    a, b = run_sandbox(SandboxRunRequest(**GOLDEN)), run_sandbox(SandboxRunRequest(**GOLDEN))
    assert [s.text for s in a.script] == [s.text for s in b.script] and a.load_after_mw == b.load_after_mw


def test_no_overload_paths():
    r = run_sandbox(SandboxRunRequest(season="winter", hour=18, dc_mw=20))
    assert r.outcome == "no_overload" and not r.has_overload and r.script[-1].kind == "done" and r.owners_total == 0
    night = run_sandbox(SandboxRunRequest(season="summer", hour=4, dc_mw=20))
    assert night.outcome == "no_overload" and night.load_before_mw < 90


def test_bigger_data_centre_in_winter_creates_stress_and_long_events_play_one_day():
    r = run_sandbox(SandboxRunRequest(season="winter", hour=18, dc_mw=45))
    assert r.has_overload and r.load_before_mw > 100 and r.outcome in ("breaks", "partly_holds")


def test_device_parameters_change_the_outcome():
    base = run_sandbox(SandboxRunRequest(**GOLDEN))
    bigger = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(battery_count=120, ev_fleet_count=84, building_count=216, solar_count=48)))
    smaller = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(battery_count=20, ev_fleet_count=14, building_count=36, solar_count=8)))
    assert smaller.absorbed_mw < base.absorbed_mw < bigger.absorbed_mw + 1e-9
    reserve = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(battery_reserve_pct=60)))
    assert reserve.absorbed_mw < base.absorbed_mw                                       # a bigger reserve leaves less to give
    few = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(owners_enrolled_pct=30)))
    assert few.owners_total < base.owners_total and few.absorbed_mw <= base.absorbed_mw + 1e-9
    pricey = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(min_price_scale=2.0)))
    assert pricey.absorbed_mw <= base.absorbed_mw + 1e-9


def test_world_and_baseline_are_not_mutated():
    df = get_load("waterloo-demo").df
    h = pd.util.hash_pandas_object(df[["timestamp", "load_mw"]]).sum()
    run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(battery_count=90, battery_reserve_pct=50)))
    assert pd.util.hash_pandas_object(get_load("waterloo-demo").df[["timestamp", "load_mw"]]).sum() == h
    from src.world.population import build_population
    pop = build_population("waterloo-demo")
    assert len(pop.agents) == 78 and pop.scale == 1.0 and pop.agents[0].power_mw == build_population("waterloo-demo").agents[0].power_mw      # base population untouched by variants


def test_api():
    w = client.get("/api/sandbox/world").json()
    assert w["capacityMw"] == 90 and w["defaults"]["fleetSizeX"] == 1.0 and w["defaults"]["batteryCount"] == 60
    r = client.post("/api/sandbox/run", json={"season": "summer", "hour": 16, "dcMw": 20, "deviceParams": {"batteryCount": 90}}).json()
    assert r["hasOverload"] and r["script"][0]["kind"] == "request" and r["outcome"] in ("holds", "partlyHolds", "partly_holds", "breaks")
    assert client.post("/api/sandbox/run", json={"season": "monsoon"}).status_code == 422
    assert client.post("/api/sandbox/run", json={"dcMw": -1}).status_code == 422


def test_device_details_are_real_and_summary_matches_counts():
    w = world_info()
    assert set(w.device_details) == {"battery", "ev", "building", "solar"}
    assert w.device_details["battery"].clusters == 60 and w.device_details["ev"].clusters == 42 and w.device_details["building"].clusters == 108
    assert w.device_details["battery"].total_mw > 0 and w.device_details["battery"].total_mwh > w.device_details["battery"].total_mw
    assert w.device_details["ev"].vehicles and w.device_details["solar"].owners == 0
    assert sum(d.owners for d in w.device_details.values()) == w.owner_count


def test_default_demo_scenario_is_pinned():
    """The scenario the demo opens on: summer 2 pm, 20 MW data centre, default fleet (3x). A change here must be deliberate."""
    r = run_sandbox(SandboxRunRequest(season="summer", hour=14, dc_mw=20))
    assert r.date_used == "2025-06-24" and r.base_mw == pytest.approx(76.4, abs=0.1) and r.load_before_mw == pytest.approx(96.4, abs=0.1)
    assert r.outcome == "holds" and r.remaining_mw == 0.0 and r.absorbed_mw == pytest.approx(6.4, abs=0.1)
    assert r.dispatch_by_group["battery"] > 2 and r.dispatch_by_group["building"] > 1
    assert r.checks_passed and r.decision_source == "deterministic_stub"


# ---------------- Stage A: editable device counts and multiple loads ----------------
def test_generator_counts_are_prefix_stable_and_defaults_reproduce_the_original_world():
    from src.world.generator import generate
    orig = generate(42017, 1.0)
    assert orig == generate(42017, 1.0, {"battery": 20, "ev_fleet": 14, "building": 36, "solar": 8})
    big = generate(42017, 1.0, {"battery": 60, "ev_fleet": 42, "building": 108, "solar": 24})
    assert len(big) == 234 and [a.id for a in big][:3] == ["battery_001", "battery_002", "battery_003"]
    b_small = [a for a in orig if a.type == "battery"]
    b_big = [a for a in big if a.type == "battery"]
    assert b_small[0].power_mw == b_big[0].power_mw and b_small[5].draw == b_big[5].draw       # same seeded draws for the first clusters
    fewer = generate(42017, 1.0, {"battery": 5})
    assert sum(a.type == "battery" for a in fewer) == 5 and sum(a.type == "solar" for a in fewer) == 8


def test_owners_regroup_with_the_device_counts_and_cover_every_flexible_asset():
    from src.capacityos.sandbox import variant_key
    from src.owners.grouping import build_owners
    from src.world.population import build_population, use_variant
    for dp in (DeviceParams(), DeviceParams(battery_count=10, ev_fleet_count=6, building_count=12, solar_count=2)):
        with use_variant(variant_key(dp)):
            pop, owners = build_population("waterloo-demo"), build_owners("waterloo-demo")
            flexible = sorted(a.id for a in pop.agents if a.type != "solar")
            assert sorted(x for o in owners for x in o.controlled_asset_ids) == flexible and 1 <= len(owners) <= 18
    assert len(build_population("waterloo-demo").agents) == 78                                  # base world untouched


def test_housing_and_ev_depot_loads_add_to_the_baseline_by_hour():
    from src.projects.base import build_model
    from src.projects.loads import make_load
    df = get_load("waterloo-demo").df.iloc[:48]
    homes, depot = make_load("h", "housing", 1000), make_load("d", "ev_depot", 100)
    assert homes.type == "housing" and homes.provenance == "hypothetical" and homes.nominal_load_mw == pytest.approx(1.8, abs=0.01)
    inc = build_model(homes).hourly_increment_mw(df["timestamp"])
    hrs = df["timestamp"].dt.hour.to_numpy()
    assert inc[hrs == 19].max() == pytest.approx(1.8, abs=0.01) and inc[hrs == 4].max() < inc[hrs == 19].max()          # evening-shaped
    assert build_model(depot).hourly_increment_mw(df["timestamp"])[hrs == 20].max() > build_model(depot).hourly_increment_mw(df["timestamp"])[hrs == 12].max()
    with pytest.raises(ValueError):
        make_load("x", "housing", 0)


def test_multiple_loads_add_up_and_are_reported():
    from src.schemas.sandbox import LoadSpec
    one = run_sandbox(SandboxRunRequest(season="summer", hour=19, loads=[LoadSpec(kind="data_centre", size=20)]))
    two = run_sandbox(SandboxRunRequest(season="summer", hour=19, loads=[LoadSpec(kind="data_centre", size=20), LoadSpec(kind="housing", size=1000)]))
    assert two.load_before_mw == pytest.approx(one.load_before_mw + 1.8 * 0.99, abs=0.15) and two.dc_mw > one.dc_mw
    assert [(l.kind, l.size) for l in two.loads] == [("data_centre", 20.0), ("housing", 1000.0)]
    three = run_sandbox(SandboxRunRequest(season="summer", hour=19, loads=[LoadSpec(kind="data_centre", size=20), LoadSpec(kind="data_centre", size=15)]))
    assert three.load_before_mw == pytest.approx(one.load_before_mw + 15, abs=0.1)


def test_acceptance_sentence_runs_end_to_end():
    """40% batteries enrolled-ish, EV flexible, $75/MWh, add 1,000 homes + a 20 MW data centre."""
    from src.schemas.sandbox import LoadSpec
    r = run_sandbox(SandboxRunRequest(season="summer", hour=19, incentive_per_mwh=75, loads=[LoadSpec(kind="data_centre", size=20), LoadSpec(kind="housing", size=1000)],
                                      device_params=DeviceParams(owners_enrolled_pct=40, ev_shiftable_pct=90)))
    assert r.has_overload and r.script[-1].kind == "done" and r.checks_passed and r.owners_total < 18


# ---------------- Stage B: season matrix ----------------
def test_matrix_covers_every_season_and_hours_are_consistent():
    from src.capacityos.sandbox import run_matrix
    from src.schemas.sandbox import MatrixRequest
    m = run_matrix(MatrixRequest(dc_mw=20))
    assert [c.season for c in m.cells] == ["winter", "spring", "summer", "fall"] and m.capacity_mw == 90.0
    by = {c.season: c for c in m.cells}
    assert by["summer"].outcome in ("holds", "partly_holds", "breaks") and by["summer"].hours_over_before > 0
    assert by["winter"].outcome == "no_overload" and by["winter"].hours_over_before == 0
    for c in m.cells:
        assert len(c.hour_states) == 24 and set(c.periods) == {"morning", "afternoon", "evening"}
        assert c.hours_over_after <= c.hours_over_before and c.peak_load_after_mw <= c.peak_load_mw + 1e-6
        assert (c.hours_over_before > 0) == any(s != "within" for s in c.hour_states)
        assert (c.outcome == "holds") == (c.hours_over_before > 0 and c.remaining_mw <= 0.05) and (c.outcome == "no_overload") == (c.overload_mw == 0)
    # the same constraint set is deterministic
    assert [c.model_dump() for c in run_matrix(MatrixRequest(dc_mw=20)).cells] == [c.model_dump() for c in m.cells]


def test_matrix_responds_to_constraints_and_bigger_loads_stress_more_seasons():
    from src.capacityos.sandbox import run_matrix
    from src.schemas.sandbox import LoadSpec, MatrixRequest
    small = run_matrix(MatrixRequest(loads=[LoadSpec(kind="data_centre", size=20)]))
    big = run_matrix(MatrixRequest(loads=[LoadSpec(kind="data_centre", size=45)]))
    assert sum(c.hours_over_before for c in big.cells) > sum(c.hours_over_before for c in small.cells)
    assert next(c for c in big.cells if c.season == "winter").hours_over_before > 0
    strong = run_matrix(MatrixRequest(loads=[LoadSpec(kind="data_centre", size=30)], device_params=DeviceParams(battery_count=120, ev_fleet_count=84, building_count=216)))
    weak = run_matrix(MatrixRequest(loads=[LoadSpec(kind="data_centre", size=30)], device_params=DeviceParams(battery_count=10, ev_fleet_count=6, building_count=12)))
    assert sum(c.hours_over_after for c in strong.cells) < sum(c.hours_over_after for c in weak.cells)


def test_matrix_api():
    r = client.post("/api/sandbox/matrix", json={"loads": [{"kind": "data_centre", "size": 20}, {"kind": "housing", "size": 1000}]}).json()
    assert len(r["cells"]) == 4 and r["capacityMw"] == 90 and r["cells"][0]["season"] == "winter" and r["cells"][2]["hourStates"]
    assert client.post("/api/sandbox/matrix", json={"dcMw": -5}).status_code == 422
