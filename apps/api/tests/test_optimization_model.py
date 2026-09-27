"""Unit tests of the OR-Tools model on tiny hand-solvable problems (physics, not data)."""
import pandas as pd
import pytest

from src.optimization.constraints import BatteryIn, BuildingIn, EVIn, Problem, optimized_net, validate
from src.optimization.model import solve


def hours(n):
    return list(pd.date_range("2025-06-24 12:00", periods=n, freq="h", tz="Etc/GMT+5"))


def problem(pre, cap=10.0, window=None, **kw):
    n = len(pre)
    return Problem(hours=hours(n), in_window=window or [True] * n, pre_net=list(pre), capacity=cap, **kw)


def battery(n, power=2.0, energy=2.0, soc=None, avail=None, eta=1.0, rest_chg=0.0, rest_dis=0.0, min_e=0.0):
    return BatteryIn(id="b1", name="b", power=power, energy=energy, eta_c=eta, eta_d=eta, min_e=min_e, max_e=energy,
                     rest_chg=[rest_chg] * n, rest_dis=[rest_dis] * n, soc_rest_end=[energy if soc is None else soc] * n, avail=avail or [True] * n)


def total_over(pb, sol):
    return sum(max(0.0, x - pb.capacity) for x in optimized_net(pb, sol))


def passed(pb, sol):
    bad = [c for c in validate(pb, sol) if not c.passed]
    assert not bad, bad


def test_no_resources_means_no_change():
    pb = problem([13, 13, 8])
    sol = solve(pb)
    assert sol.status == "OPTIMAL" and optimized_net(pb, sol) == pb.pre_net


def test_battery_is_limited_by_stored_energy_and_inverter_power():
    pb = problem([13, 13, 8], batteries=[battery(3, power=2.0, energy=2.0)])
    sol = solve(pb)
    passed(pb, sol)
    d = sol.battery["b1"]["discharge"]
    assert sum(d) == pytest.approx(2.0, abs=1e-6)                 # only 2 MWh in the tank
    assert max(d) <= 2.0 + 1e-9                                   # inverter limit
    assert total_over(pb, sol) == pytest.approx(6.0 - 2.0, abs=1e-6)


def test_battery_respects_reserve_and_efficiency():
    pb = problem([13, 13], batteries=[battery(2, power=5, energy=4.0, soc=3.0, eta=0.9, min_e=1.0)])
    sol = solve(pb)
    passed(pb, sol)
    d = sol.battery["b1"]["discharge"]
    assert sum(d) / 0.9 <= (3.0 - 1.0) + 1e-6                     # usable energy above reserve, after discharge losses
    assert min(sol.battery["b1"]["soc"]) >= 1.0 / 4.0 - 1e-9


def test_battery_at_reserve_or_unavailable_gives_nothing():
    pb = problem([13, 13], batteries=[battery(2, soc=0.0, energy=2.0)])
    assert sum(solve(pb).battery["b1"]["discharge"]) == 0
    pb = problem([13, 13], batteries=[battery(2, avail=[False, False])])
    assert sum(solve(pb).battery["b1"]["discharge"]) == 0


def test_battery_can_precharge_before_the_peak_using_time_coupling():
    n = 3   # hour 0 has headroom, hours 1-2 do not; battery starts half empty so it must charge in hour 0 first
    pb = problem([6, 13, 13], batteries=[battery(n, power=3, energy=4.0, soc=1.0)])
    sol = solve(pb)
    passed(pb, sol)
    s = sol.battery["b1"]
    assert sum(s["charge"]) > 0 and s["charge"][0] > 0            # charged where capacity was free
    assert total_over(pb, sol) < 6.0 - 1e-6                       # and used it when the grid was tight


def test_ev_deferral_is_recovered_before_departure():
    n = 4
    ev = EVIn(id="e1", name="e", shiftable=1.0, p_max=[1.5] * n, rest=[1.0, 1.0, 0.0, 0.0], avail=[True] * n)
    pb = problem([11, 11, 5, 5], evs=[ev])
    sol = solve(pb)
    passed(pb, sol)
    s = sol.ev["e1"]
    assert sum(s["defer"]) == pytest.approx(sum(s["recover"]), abs=1e-6)     # energy requirement met
    assert total_over(pb, sol) == pytest.approx(0.0, abs=1e-6)               # both violation hours cleared
    rest = [1.0, 1.0, 0.0, 0.0]
    assert all(r - d + rc <= 1.5 + 1e-9 for r, d, rc in zip(rest, s["defer"], s["recover"]))          # charger limit respected


def test_ev_cannot_defer_beyond_its_shiftable_fraction_or_without_recovery_time():
    ev = EVIn(id="e1", name="e", shiftable=0.5, p_max=[1.0, 1.0], rest=[1.0, 0.0], avail=[True, True])
    pb = problem([12, 5], evs=[ev])
    sol = solve(pb)
    passed(pb, sol)
    assert sol.ev["e1"]["defer"][0] <= 0.5 + 1e-9
    tight = EVIn(id="e2", name="e", shiftable=1.0, p_max=[1.0, 1.0], rest=[1.0, 1.0], avail=[True, True])   # charger already maxed: no room to recover
    pb2 = problem([12, 12], evs=[tight])
    assert sum(solve(pb2).ev["e2"]["defer"]) == pytest.approx(0.0, abs=1e-9)


def test_building_duration_budget_and_power_limit():
    b = BuildingIn(id="k1", name="k", cap=[1.0] * 4, max_hours=2, rebound_frac=0.0, rebound_h=1, avail=[True] * 4)
    pb = problem([12, 12, 12, 12], buildings=[b])
    sol = solve(pb)
    passed(pb, sol)
    shed = sol.building["k1"]["shed"]
    assert sum(1 for x in shed if x > 1e-9) <= 2 and max(shed) <= 1.0 + 1e-9
    assert total_over(pb, sol) == pytest.approx(8.0 - 2.0, abs=1e-6)         # 2 hours x 1 MW


def test_rebound_can_never_create_a_new_violation():
    b = BuildingIn(id="k1", name="k", cap=[1.0] * 3, max_hours=1, rebound_frac=0.5, rebound_h=1, avail=[True] * 3)
    pb = problem([12, 10, 10], buildings=[b])                                # hours 1-2 sit exactly at capacity
    sol = solve(pb)
    passed(pb, sol)
    assert max(0.0, *[x - pb.capacity for x in optimized_net(pb, sol)[1:]]) == pytest.approx(0.0, abs=1e-9)
    assert sum(sol.building["k1"]["shed"]) == pytest.approx(0.0, abs=1e-9)   # shedding is refused: its rebound would breach capacity


def test_building_only_sheds_inside_the_event_window():
    b = BuildingIn(id="k1", name="k", cap=[1.0] * 4, max_hours=4, rebound_frac=0.0, rebound_h=1, avail=[True] * 4)
    pb = problem([12, 12, 12, 12], window=[True, True, False, False], buildings=[b])
    shed = solve(pb).building["k1"]["shed"]
    assert shed[2] == shed[3] == 0.0


def test_no_hour_is_made_worse_and_results_are_deterministic():
    b = BuildingIn(id="k1", name="k", cap=[1.0] * 4, max_hours=3, rebound_frac=0.8, rebound_h=2, avail=[True] * 4)
    pb = problem([12, 11, 9, 8], buildings=[b], batteries=[battery(4, power=1, energy=1)])
    a, c = solve(pb), solve(pb)
    passed(pb, a)
    assert a.battery == c.battery and a.building == c.building and a.slack == c.slack
    for n, p in zip(optimized_net(pb, a), pb.pre_net):
        assert max(0.0, n - pb.capacity) <= max(0.0, p - pb.capacity) + 1e-6


def test_validator_detects_a_broken_solution():
    pb = problem([13, 13], batteries=[battery(2, power=2, energy=2)])
    sol = solve(pb)
    sol.battery["b1"]["discharge"] = [5.0, 5.0]                    # violates inverter and energy limits
    names = {c.name for c in validate(pb, sol) if not c.passed}
    assert {"battery_inverter_discharge", "battery_soc_reserve"} <= names
