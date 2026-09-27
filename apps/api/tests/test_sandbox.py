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
    assert w.capacity_mw == 90.0 and w.devices["battery"] == 20 and w.owner_count == 18 and set(w.seasons) == {"winter", "spring", "summer", "fall"}
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
    assert all(a <= b + 1e-6 for a, b in zip(r.curve.after, r.curve.before))          # never worse
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
    base = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(fleet_size_x=3)))
    bigger = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(fleet_size_x=4)))
    smaller = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(fleet_size_x=1)))
    assert smaller.absorbed_mw < base.absorbed_mw < bigger.absorbed_mw + 1e-9
    reserve = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(fleet_size_x=3, battery_reserve_pct=60)))
    assert reserve.absorbed_mw < base.absorbed_mw                                       # a bigger reserve leaves less to give
    few = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(owners_enrolled_pct=30)))
    assert few.owners_total < base.owners_total and few.absorbed_mw <= base.absorbed_mw + 1e-9
    pricey = run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(min_price_scale=2.0)))
    assert pricey.absorbed_mw <= base.absorbed_mw + 1e-9


def test_world_and_baseline_are_not_mutated():
    df = get_load("waterloo-demo").df
    h = pd.util.hash_pandas_object(df[["timestamp", "load_mw"]]).sum()
    run_sandbox(SandboxRunRequest(**GOLDEN, device_params=DeviceParams(fleet_size_x=4, battery_reserve_pct=50)))
    assert pd.util.hash_pandas_object(get_load("waterloo-demo").df[["timestamp", "load_mw"]]).sum() == h
    from src.world.population import build_population
    pop = build_population("waterloo-demo")
    assert len(pop.agents) == 78 and pop.scale == 1.0 and pop.agents[0].power_mw == build_population("waterloo-demo").agents[0].power_mw      # base population untouched by variants


def test_api():
    w = client.get("/api/sandbox/world").json()
    assert w["capacityMw"] == 90 and w["defaults"]["fleetSizeX"] == 3.0
    r = client.post("/api/sandbox/run", json={"season": "summer", "hour": 16, "dcMw": 20, "deviceParams": {"fleetSizeX": 4}}).json()
    assert r["hasOverload"] and r["script"][0]["kind"] == "request" and r["outcome"] in ("holds", "partlyHolds", "partly_holds", "breaks")
    assert client.post("/api/sandbox/run", json={"season": "monsoon"}).status_code == 422
    assert client.post("/api/sandbox/run", json={"dcMw": -1}).status_code == 422
