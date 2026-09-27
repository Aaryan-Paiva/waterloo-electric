import pytest
from fastapi.testclient import TestClient

from src.main import app

c = TestClient(app)


def make(mw=None, name=None):
    s = c.post("/api/scenarios", json={"name": name} if name else {}).json()
    if mw is not None:
        s = c.post(f"/api/scenarios/{s['id']}/projects", json={"type": "data_center", "nominalLoadMw": mw}).json()
    return s


def test_create_baseline_scenario_has_no_projects_and_no_violations():
    s = c.post("/api/scenarios", json={}).json()
    assert s["id"].startswith("scn-") and s["zoneId"] == "waterloo-demo" and s["projects"] == [] and s["seed"] == 42017
    a = c.get(f"/api/scenarios/{s['id']}/analysis").json()
    assert a["constrainedHours"] == 0 and a["feasibility"] == "feasible_as_is" and a["windows"] == []
    assert a["projectedPeakMw"] == a["baselinePeakMw"]


def test_add_edit_delete_project_and_hypothetical_provenance():
    s = make(20)
    p = s["projects"][0]
    assert p["provenance"] == "hypothetical" and p["type"] == "data_center" and p["hourlyProfile"] == [20.0] * 24
    s2 = c.patch(f"/api/scenarios/{s['id']}/projects/{p['id']}", json={"nominalLoadMw": 30}).json()
    assert s2["projects"][0]["nominalLoadMw"] == 30 and s2["projects"][0]["id"] == p["id"]
    s3 = c.delete(f"/api/scenarios/{s['id']}/projects/{p['id']}").json()
    assert s3["projects"] == []


@pytest.mark.parametrize("body", [
    {"type": "housing", "nominalLoadMw": 5},                       # not implemented yet
    {"type": "data_center", "nominalLoadMw": 0},
    {"type": "data_center", "nominalLoadMw": -1},
    {"type": "data_center", "nominalLoadMw": 501},
    {"type": "data_center", "nominalLoadMw": 20, "flexibilityFraction": 0.15},   # flexible compute comes later
])
def test_invalid_projects_rejected(body):
    s = make()
    assert c.post(f"/api/scenarios/{s['id']}/projects", json=body).status_code == 422


def test_unknown_ids_404():
    assert c.get("/api/scenarios/scn-nope").status_code == 404
    assert c.post("/api/scenarios", json={"zoneId": "nowhere"}).status_code == 404
    s = make()
    assert c.patch(f"/api/scenarios/{s['id']}/projects/prj-nope", json={"nominalLoadMw": 5}).status_code == 404
    assert c.delete(f"/api/scenarios/{s['id']}/projects/prj-nope").status_code == 404


def test_scenarios_never_mutate_the_baseline_world():
    w0, l0 = c.get("/api/worlds/waterloo-demo").json(), c.get("/api/zones/waterloo-demo/load", params={"resolution": "daily"}).json()
    s = make(30)
    c.get(f"/api/scenarios/{s['id']}/analysis")
    assert c.get("/api/worlds/waterloo-demo").json() == w0
    assert c.get("/api/zones/waterloo-demo/load", params={"resolution": "daily"}).json() == l0
    assert w0["loadSummary"]["hoursAboveCapacity"] == 0


def test_scenarios_are_isolated_and_clone_copies_projects():
    a, b = make(30, "A"), make(10, "B")
    assert c.get(f"/api/scenarios/{a['id']}/analysis").json()["constrainedHours"] > 0
    assert c.get(f"/api/scenarios/{b['id']}/analysis").json()["constrainedHours"] == 0
    cl = c.post(f"/api/scenarios/{a['id']}/clone").json()
    assert cl["parentScenarioId"] == a["id"] and cl["id"] != a["id"] and len(cl["projects"]) == 1
    c.delete(f"/api/scenarios/{cl['id']}/projects/{cl['projects'][0]['id']}")
    assert len(c.get(f"/api/scenarios/{a['id']}").json()["projects"]) == 1     # editing the clone leaves the original


def test_events_endpoint_pagination_and_ordering():
    s = make(20)
    e = c.get(f"/api/scenarios/{s['id']}/events", params={"limit": 5}).json()
    if e["total"] == 0:
        pytest.skip("fixture mode has no violations")
    assert e["total"] > 5 and len(e["events"]) == 5 and e["events"][0]["resolved"] is False
    ts = [x["timestamp"] for x in e["events"]]
    assert ts == sorted(ts)
    d = c.get(f"/api/scenarios/{s['id']}/events", params={"limit": 3, "order": "deficit"}).json()["events"]
    assert d[0]["deficitMw"] >= d[1]["deficitMw"] >= d[2]["deficitMw"]
    page2 = c.get(f"/api/scenarios/{s['id']}/events", params={"limit": 5, "offset": 5}).json()["events"]
    assert page2[0]["id"] != e["events"][0]["id"]


def test_scenario_load_series_carry_baseline_project_net():
    s = make(20)
    r = c.get(f"/api/scenarios/{s['id']}/load", params={"start": "2025-07-01T00:00:00-05:00", "end": "2025-07-02T00:00:00-05:00"}).json()
    assert len(r["points"]) == 24 and r["capacityMw"] == 90
    for p in r["points"]:
        assert p["projectLoadMw"] == 20 and p["netLoadMw"] == pytest.approx(p["baselineLoadMw"] + 20, abs=1e-3)
    d = c.get(f"/api/scenarios/{s['id']}/load", params={"resolution": "daily", "start": "2025-06-24", "end": "2025-06-25"}).json()["points"]
    assert len(d) == 1 and d[0]["constrainedHours"] == 14 and d[0]["deficitMw"] == 8.0   # the golden peak day


def test_phase_flag_and_no_flexibility_claims():
    a = c.get(f"/api/scenarios/{make(20)['id']}/analysis").json()
    assert a["flexibilityEvaluated"] is False and a["feasibility"] == "constraints_detected"
    assert "not a feasibility verdict" in a["note"].lower()
    assert a["provenance"]["projects"]["type"] == "hypothetical" and a["provenance"]["zoneCapacity"]["type"] == "modeled"
