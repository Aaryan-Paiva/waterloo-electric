import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_zones_list_and_detail():
    zs = client.get("/api/zones").json()
    assert [z["id"] for z in zs] == ["waterloo-demo"]
    z = client.get("/api/zones/waterloo-demo").json()
    assert z["capacityMw"] == 90 and z["capacityProvenance"] == "modeled" and z["worldSeed"] == 42017
    assert client.get("/api/zones/nowhere").status_code == 404


def test_hourly_window():
    r = client.get("/api/zones/waterloo-demo/load", params={"start": "2025-07-01T00:00:00-05:00", "end": "2025-07-02T00:00:00-05:00"}).json()
    assert r["resolution"] == "hourly" and len(r["points"]) == 24
    assert r["capacityMw"] == 90 and r["provenance"]["type"] == "derived"
    p = r["points"][0]
    assert p["provenance"] == "derived" and 0 < p["loadMw"] <= 78 and p["observedZoneMw"] > 1000


def test_daily_resolution_reports_peak_mean_min():
    r = client.get("/api/zones/waterloo-demo/load", params={"resolution": "daily", "start": "2025-07-01", "end": "2025-07-08"}).json()
    assert r["resolution"] == "daily" and len(r["points"]) == 7
    for p in r["points"]:
        assert p["minMw"] <= p["meanMw"] <= p["loadMw"]


def test_world_state_has_provenance_and_summary():
    w = client.get("/api/worlds/waterloo-demo").json()
    assert w["mode"] in ("full", "fixture")
    assert set(w["provenance"]) == {"historicalDemand", "derPopulation", "zoneCapacity", "newProject"}
    assert w["provenance"]["historicalDemand"]["type"] == "derived"
    assert w["provenance"]["derPopulation"]["type"] == "modeled"
    assert w["provenance"]["newProject"]["type"] == "hypothetical"
    ls = w["loadSummary"]
    assert ls["peakMw"] == pytest.approx(78.0, abs=1e-3) or w["mode"] == "fixture"
    assert ls["hoursAboveCapacity"] == 0 and w["derAssumptions"]["ev_participation"] == 0.35


def test_falls_back_to_fixture_and_says_so(monkeypatch, tmp_path):
    from src import settings
    from src.data import repositories

    monkeypatch.setattr(settings, "PROCESSED_DIR", tmp_path)          # no parquet available
    monkeypatch.setattr("src.data.ingestion.settings.PROCESSED_DIR", tmp_path)
    repositories.clear_caches()
    w = client.get("/api/worlds/waterloo-demo").json()
    assert w["mode"] == "fixture" and w["loadSummary"]["hours"] == 720
    assert "fixture" in w["provenance"]["historicalDemand"]["notes"].lower()


def test_playback_clock():
    from src.world.clock import SimulationClock

    c = SimulationClock(n_hours=100)
    assert c.advance(2, "10x") == 20 and c.advance(1000, "1000x") == 99 and c.seek(-5) == 0
