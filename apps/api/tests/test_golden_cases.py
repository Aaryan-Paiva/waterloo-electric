"""The measured Phase-2 cases on the full 2021-2025 Waterloo Demo Zone dataset (43,824 hours, 90 MW modeled capacity).

Numbers were measured independently (pandas: load_mw + MW > 90) before the engine existed, then confirmed through the API.
The 20 MW case is the golden demo.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.data.repositories import get_load
from src.main import app

c = TestClient(app)
FULL = get_load("waterloo-demo").mode == "full"
pytestmark = pytest.mark.skipif(not FULL, reason="measured cases require the full parquet dataset")

CASES = {  # MW: (constrained hours, affected days, worst deficit MW, projected peak MW, % within capacity, windows)
    10: (0, 0, 0.0, 88.0, 100.0, 0),
    20: (268, 51, 8.0, 98.0, 99.3885, 59),
    30: (2912, 401, 18.0, 108.0, 93.3552, 421),
}


def analysis(mw: int) -> dict:
    s = c.post("/api/scenarios", json={"name": f"DC-{mw}"}).json()
    c.post(f"/api/scenarios/{s['id']}/projects", json={"type": "data_center", "nominalLoadMw": mw})
    return c.get(f"/api/scenarios/{s['id']}/analysis").json()


@pytest.mark.parametrize("mw", [10, 20, 30])
def test_measured_case(mw):
    hours, days, worst, peak, pct, windows = CASES[mw]
    a = analysis(mw)
    assert a["hoursTested"] == 43824 and a["capacityMw"] == 90 and a["mode"] == "full"
    assert a["constrainedHours"] == hours
    assert a["affectedDays"] == days
    assert a["worstDeficitMw"] == pytest.approx(worst, abs=1e-3)
    assert a["projectedPeakMw"] == pytest.approx(peak, abs=1e-3)
    assert a["percentWithinCapacity"] == pytest.approx(pct, abs=1e-3)
    assert a["windowCount"] == windows == len(a["windows"])
    assert a["minHeadroomMw"] == pytest.approx(90 - peak, abs=1e-3)
    assert a["feasibility"] == ("feasible_as_is" if hours == 0 else "constraints_detected")


@pytest.mark.parametrize("mw", [10, 20, 30])
def test_independent_recomputation_agrees(mw):
    """A from-scratch pandas count on the parquet must agree with the API (guards against engine bugs)."""
    d = get_load("waterloo-demo").df
    over = d[d["load_mw"] + mw > 90]
    a = analysis(mw)
    assert a["constrainedHours"] == len(over)
    assert a["affectedDays"] == over["timestamp"].dt.date.nunique()
    assert a["worstDeficitMw"] == pytest.approx(max(0.0, (d["load_mw"] + mw - 90).max()), abs=1e-3)


def test_golden_20mw_story():
    a = analysis(20)
    world = c.get("/api/worlds/waterloo-demo").json()
    assert world["loadSummary"]["hoursAboveCapacity"] == 0          # baseline alone is fine...
    assert a["constrainedHours"] == 268 and a["affectedDays"] == 51   # ...+20 MW creates clear violations
    assert a["worstDeficitTimestamp"] == a["baselinePeakTimestamp"] == world["loadSummary"]["peakTimestamp"]   # worst hour = baseline peak hour
    assert a["worstDeficitTimestamp"].startswith("2025-06-24")
    worst = max(a["windows"], key=lambda w: w["peakDeficitMw"])
    assert worst["hours"] == 14 and worst["peakDeficitMw"] == 8.0 and worst["start"].startswith("2025-06-24T08:00")
    assert a["byYear"]["2025"]["constrainedHours"] == 154 and a["byYear"]["2021"]["constrainedHours"] == 39
    assert sum(y["constrainedHours"] for y in a["byYear"].values()) == 268
    assert a["flexibilityEvaluated"] is False                       # Phase 2: no DER, no optimizer


def test_constrained_hours_grow_monotonically_with_size():
    hours = [analysis(mw)["constrainedHours"] for mw in (10, 15, 20, 25, 30)]
    assert hours == sorted(hours) and hours[0] == 0 and hours[-1] == 2912
