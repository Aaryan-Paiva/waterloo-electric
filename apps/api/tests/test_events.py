import pandas as pd
import pytest

from src.simulation.events import event_id, group_windows, to_events, violations

CAP = 90.0


def frame(nets, start="2025-07-01 00:00"):
    ts = pd.date_range(start, periods=len(nets), freq="h", tz="Etc/GMT+5")
    return pd.DataFrame({"timestamp": ts, "baseline_mw": [n - 20 for n in nets], "project_mw": 20.0,
                         "local_generation_mw": 0.0, "net_mw": nets, "quality_flag": "ok"})


def test_violation_is_strictly_above_capacity():
    df = frame([89.9, 90.0, 90.1, 95.0])
    v = violations(df, CAP)
    assert list(v["net_mw"]) == [90.1, 95.0]                     # exactly-at-capacity is NOT a violation
    assert list(v["deficit_mw"].round(3)) == [0.1, 5.0]


def test_events_have_full_contract_and_are_unresolved():
    df = frame([80, 92, 96, 80])
    evs = to_events(violations(df, CAP), CAP)
    assert [e.deficit_mw for e in evs] == [2.0, 6.0]
    e = evs[1]
    assert e.pre_dispatch_net_load_mw == 96 and e.baseline_load_mw == 76 and e.project_load_mw == 20
    assert e.capacity_mw == CAP and e.requested_flexibility_mw == 6.0 and e.resolved is False
    assert e.post_dispatch_net_load_mw is None and e.remaining_deficit_mw is None
    assert len({x.id for x in evs}) == 2 and evs[0].id == event_id(pd.Timestamp("2025-07-01 01:00", tz="Etc/GMT+5"))


def test_windows_group_consecutive_hours_only():
    df = frame([80, 92, 96, 91, 80, 80, 93, 80, 91, 92, 80])   # windows: h1-3, h6, h8-9
    ws = group_windows(violations(df, CAP))
    assert [w.hours for w in ws] == [3, 1, 2]
    w = ws[0]
    assert w.peak_deficit_mw == 6.0 and w.peak_timestamp.startswith("2025-07-01T02:00")
    assert w.start.startswith("2025-07-01T01:00") and w.end.startswith("2025-07-01T04:00")   # end exclusive
    assert w.energy_over_mwh == pytest.approx(2 + 6 + 1) and w.mean_deficit_mw == pytest.approx(3.0)


def test_window_spanning_midnight_counts_two_days():
    df = frame([80] * 22 + [95, 95, 95, 95, 80], start="2025-07-01 00:00")   # hours 22..25 -> spans Jul 1 & Jul 2
    ws = group_windows(violations(df, CAP))
    assert len(ws) == 1 and ws[0].hours == 4 and ws[0].days == 2


def test_no_violations_means_no_windows():
    assert group_windows(violations(frame([70, 80, 90]), CAP)) == []
