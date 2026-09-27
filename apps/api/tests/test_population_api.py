import pytest
from fastapi.testclient import TestClient

from src.main import app

c = TestClient(app)
W = "/api/worlds/waterloo-demo"
PEAK = "2025-06-24T16:00:00-05:00"


def scenario(mw=None):
    s = c.post("/api/scenarios", json={}).json()
    if mw:
        c.post(f"/api/scenarios/{s['id']}/projects", json={"type": "data_center", "nominalLoadMw": mw})
    return s["id"]


def test_population_summary():
    s = c.get(f"{W}/population").json()
    assert s["seed"] == 42017 and s["provenance"] == "modeled" and s["totalAgents"] == 78
    assert {k: v["count"] for k, v in s["byType"].items()} == {"battery": 20, "ev_fleet": 14, "building": 36, "solar": 8}
    assert s["participationRates"] == {"battery": 0.4, "ev_fleet": 0.35, "building": 0.25}
    assert s["byType"]["solar"]["participating"] == 0 and s["byType"]["battery"]["capacity"]["powerMw"] > 0
    assert any("never known real customers" in n for n in s["notes"])


def test_agents_list_filter_and_detail():
    bat = c.get(f"{W}/agents", params={"type": "battery"}).json()
    assert len(bat) == 20 and all(a["type"] == "battery" and a["provenance"] == "modeled" for a in bat)
    part = c.get(f"{W}/agents", params={"type": "battery", "participating": True}).json()
    assert 0 < len(part) < 20 and all(a["participating"] for a in part)
    d = c.get(f"{W}/agents/battery_001", params={"timestamp": PEAK}).json()
    assert d["provenance"] == "modeled" and len(d["daySeries"]) == 24 and d["state"]["values"]["soc"] > 0
    assert d["potential"]["agentId"] == "battery_001" and d["params"]["powerMw"] > 0
    assert c.get(f"{W}/agents/nope").status_code == 404
    assert c.get(f"{W}/agents/battery_001", params={"timestamp": "1999-01-01T00:00:00-05:00"}).status_code == 422


def test_potential_at_golden_peak_and_deficit_link():
    sid = scenario(20)
    r = c.get(f"{W}/population/potential", params={"timestamp": PEAK, "windowHours": 1, "scenarioId": sid, "includeAgents": True}).json()
    assert r["provenance"] == "modeled" and "Nothing is dispatched" in r["note"]
    assert r["deficitMw"] == pytest.approx(8.0, abs=1e-3)                   # the golden worst hour
    assert 3.5 < r["totalPotentialMw"] < 5.5 and r["totalPotentialMw"] < r["deficitMw"]           # current DERs cannot cover it alone
    assert r["totalIfAllEnrolledMw"] > r["deficitMw"]                        # but broader participation could (a later recommendation)
    assert 0 < r["coversDeficitPct"] < 100 and r["byType"]["solar"]["potentialMw"] == 0
    assert len(r["agents"]) == 78
    assert r["totalPotentialMw"] == pytest.approx(sum(t["potentialMw"] for t in r["byType"].values()), abs=1e-3)


def test_longer_windows_never_increase_sustained_potential_for_batteries():
    a = c.get(f"{W}/population/potential", params={"timestamp": PEAK, "windowHours": 1}).json()["byType"]["battery"]["potentialIfAllEnrolledMw"]
    b = c.get(f"{W}/population/potential", params={"timestamp": PEAK, "windowHours": 4}).json()["byType"]["battery"]["potentialIfAllEnrolledMw"]
    assert b <= a + 1e-6


def test_scenario_participation_overrides_are_isolated_and_monotone():
    s1, s2 = scenario(20), scenario(20)
    base = c.get(f"{W}/population/potential", params={"timestamp": PEAK, "scenarioId": s1}).json()
    r = c.patch(f"/api/scenarios/{s1}/assumptions", json={"batteryParticipation": 1.0, "evParticipation": 0.8}).json()
    assert r["assumptionOverrides"] == {"battery_participation": 1.0, "ev_participation": 0.8}
    up = c.get(f"{W}/population/potential", params={"timestamp": PEAK, "scenarioId": s1}).json()
    assert up["totalPotentialMw"] >= base["totalPotentialMw"]
    assert up["byType"]["battery"]["potentialMw"] == pytest.approx(up["byType"]["battery"]["potentialIfAllEnrolledMw"], abs=1e-3)
    assert c.get(f"{W}/population", params={"scenarioId": s1}).json()["participationRates"]["battery"] == 1.0
    other = c.get(f"{W}/population/potential", params={"timestamp": PEAK, "scenarioId": s2}).json()
    assert other["totalPotentialMw"] == base["totalPotentialMw"]              # another scenario is untouched
    assert c.get(f"{W}/population").json()["participationRates"]["battery"] == 0.4      # the world's defaults never change


@pytest.mark.parametrize("body", [{"evParticipation": 1.5}, {"batteryParticipation": -0.1}])
def test_invalid_participation_rejected(body):
    assert c.patch(f"/api/scenarios/{scenario()}/assumptions", json=body).status_code == 422


def test_decomposition_endpoint_reconciles():
    d = c.get(f"{W}/population/decomposition", params={"timestamp": PEAK}).json()
    assert d["provenance"] == "modeled" and d["reconciles"] is True and d["baselineMw"] == 78.0
    assert d["backgroundResidualMw"] + d["controllableMw"] - d["solarOffsetMw"] == pytest.approx(78.0, abs=1e-3)
    assert "never subtracted again" in d["note"]


def test_agent_apis_never_change_the_baseline_or_analysis():
    w0 = c.get(W).json()
    sid = scenario(20)
    a0 = c.get(f"/api/scenarios/{sid}/analysis").json()
    for ts in (PEAK, "2025-08-11T15:00:00-05:00"):
        c.get(f"{W}/population/potential", params={"timestamp": ts, "scenarioId": sid, "includeAgents": True})
        c.get(f"{W}/population/decomposition", params={"timestamp": ts})
    assert c.get(W).json() == w0 and c.get(f"/api/scenarios/{sid}/analysis").json() == a0
    assert a0["constrainedHours"] == 268
