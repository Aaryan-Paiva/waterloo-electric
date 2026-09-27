"""Deterministic OR-Tools model for ONE event window (CLAUDE.md §19). SCIP MILP (buildings need a binary duration budget).

Decision variables per hour over horizon = event window + recovery tail:
  battery  c_t, d_t          extra charge / discharge beyond its at-rest routine (SOC deviation is cumulative, carried forward)
  EV fleet def_t, rec_t      energy deferred / recovered; total deferred == total recovered before departure
  building shed_t, u_t       HVAC shed inside the window; u_t binary; sum(u) <= max curtailment hours; rebound follows
  slack_t                    capacity violation left after dispatch (minimized)
Solar never appears: it is already in the baseline.
"""
from ortools.linear_solver import pywraplp

from .constraints import Problem, Solution
from .objectives import EPS_AGENT, TOL, W_BATTERY, W_BUILDING, W_EV, W_PRICE, W_SEVERITY, W_SLACK


def solve(pb: Problem, scale_target: dict[str, list[float]] | None = None) -> Solution:
    """Clearing mode (default) minimizes residual violation. Envelope mode (`scale_target`): maximize lambda in [0,1] such that each asset
    can deliver lambda x target[t] MW in every hour at once (used by the physical offer validator); capacity/net-load is ignored."""
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise RuntimeError("SCIP solver unavailable")
    solver.SetNumThreads(1)
    solver.SetTimeLimit(30_000)
    inf = solver.infinity()
    T = len(pb.hours)
    red: list[list[tuple]] = [[] for _ in range(T)]      # per hour: (variable, coefficient) contributions to REDUCTION
    obj = solver.Objective()
    obj.SetMinimization()

    # "Do no harm": no hour may end up worse than before dispatch, and hours that were within capacity must stay within capacity
    # (so rebound / recovery / recharge can never create new violations).
    pre_def = [max(0.0, x - pb.capacity) for x in pb.pre_net]
    slack = [solver.NumVar(0.0, pre_def[t], f"slack_{t}") for t in range(T)]
    for t in range(T):
        obj.SetCoefficient(slack[t], W_SLACK * (1.0 + W_SEVERITY * pre_def[t]))

    envelope = scale_target is not None
    caps = pb.caps
    cap_of = lambda aid, t, hi: hi if caps is None else min(hi, caps.get(aid, [0.0] * T)[t])
    price = lambda aid: W_PRICE * pb.prices.get(aid, 0.0)
    lam = solver.NumVar(0.0, 1.0, "lambda") if envelope else None
    deliver: dict[str, list] = {}          # per asset: per hour list of (variable, coefficient) whose sum is the NET reduction the asset delivers
    bvars, evars, kvars = {}, {}, {}
    for i, b in enumerate(pb.batteries):
        c = [solver.NumVar(0.0, max(0.0, b.power - b.rest_chg[t]) if b.avail[t] else 0.0, f"c_{b.id}_{t}") for t in range(T)]
        d = [solver.NumVar(0.0, cap_of(b.id, t, max(0.0, b.power - b.rest_dis[t]) if b.avail[t] else 0.0), f"d_{b.id}_{t}") for t in range(T)]
        bvars[b.id] = (c, d)
        deliver[b.id] = [[(d[t], 1.0), (c[t], -1.0)] for t in range(T)]
        for t in range(T):
            red[t] += [(d[t], 1.0), (c[t], -1.0)]
            eps = EPS_AGENT * (i + 1)
            obj.SetCoefficient(c[t], W_BATTERY + eps)
            obj.SetCoefficient(d[t], W_BATTERY + eps + price(b.id))
            row = solver.Constraint(b.min_e - b.soc_rest_end[t] - b.init_dev, b.max_e - b.soc_rest_end[t] - b.init_dev)      # SOC/reserve, cumulative deviation
            for k in range(t + 1):
                row.SetCoefficient(c[k], b.eta_c)
                row.SetCoefficient(d[k], -1.0 / b.eta_d)

    for i, e in enumerate(pb.evs):
        de = [solver.NumVar(0.0, cap_of(e.id, t, e.shiftable * e.rest[t] if e.avail[t] else 0.0), f"def_{e.id}_{t}") for t in range(T)]
        rc = [solver.NumVar(0.0, max(0.0, e.p_max[t] - 0.0) if e.avail[t] else 0.0, f"rec_{e.id}_{t}") for t in range(T)]
        evars[e.id] = (de, rc)
        deliver[e.id] = [[(de[t], 1.0), (rc[t], -1.0)] for t in range(T)]
        bal = solver.Constraint(0.0, 0.0)                               # energy requirement met by departure
        for t in range(T):
            red[t] += [(de[t], 1.0), (rc[t], -1.0)]
            cap = solver.Constraint(-inf, max(e.p_max[t], e.rest[t]) - e.rest[t])   # rest - def + rec <= charger limit
            cap.SetCoefficient(rc[t], 1.0)
            cap.SetCoefficient(de[t], -1.0)
            bal.SetCoefficient(de[t], 1.0)
            bal.SetCoefficient(rc[t], -1.0)
            eps = EPS_AGENT * (i + 1)
            obj.SetCoefficient(de[t], W_EV + eps + price(e.id))
            obj.SetCoefficient(rc[t], W_EV + eps)

    for i, bl in enumerate(pb.buildings):
        ok = [pb.in_window[t] and bl.avail[t] and bl.cap[t] > TOL for t in range(T)]
        sh = [solver.NumVar(0.0, cap_of(bl.id, t, bl.cap[t] if ok[t] else 0.0), f"shed_{bl.id}_{t}") for t in range(T)]
        deliver[bl.id] = [[(sh[t], 1.0)] for t in range(T)]
        u = [solver.BoolVar(f"u_{bl.id}_{t}") for t in range(T)]
        kvars[bl.id] = sh
        P = pb.duration_period_h or T                                    # duration budget: one per horizon, or one per P-hour block (historical clusters)
        durs = {}
        for k in range(0, T, P):
            durs[k // P] = solver.Constraint(0.0, float(max(0, bl.max_hours - (bl.prior_hours if k == 0 and pb.duration_period_h else 0))))
        for t in range(T):
            link = solver.Constraint(-inf, 0.0)
            link.SetCoefficient(sh[t], 1.0)
            link.SetCoefficient(u[t], -(bl.cap[t] if ok[t] else 0.0))
            durs[t // P].SetCoefficient(u[t], 1.0)
            red[t].append((sh[t], 1.0))
            share = bl.rebound_frac / bl.rebound_h                       # rebound load in the following hours
            for k in range(1, bl.rebound_h + 1):
                if t + k < T:
                    red[t + k].append((sh[t], -share))
            obj.SetCoefficient(sh[t], W_BUILDING + EPS_AGENT * (i + 1) + price(bl.id))

    if envelope:
        for aid, target in scale_target.items():
            for t in range(T):
                if target[t] > TOL and aid in deliver:
                    row = solver.Constraint(0.0, inf)                    # delivered_t - lambda * target_t >= 0
                    for var, coef in deliver[aid][t]:                    # NET reduction (discharge - charge, defer - recover), so charge/recover
                        row.SetCoefficient(var, coef)                    # in the same hour cannot fake a delivery
                    row.SetCoefficient(lam, -target[t])
        for t in range(T):
            obj.SetCoefficient(slack[t], 0.0)
        obj.SetCoefficient(lam, -1e6)                                    # maximize lambda (dominates the tiny dispatch-cost tie-breaks)
    else:
        for t in range(T):
            row = solver.Constraint(pb.pre_net[t] - pb.capacity, inf)    # pre - reductions - slack <= capacity
            row.SetCoefficient(slack[t], 1.0)
            for var, coef in red[t]:
                row.SetCoefficient(var, coef)

    status = solver.Solve()
    name = {pywraplp.Solver.OPTIMAL: "OPTIMAL", pywraplp.Solver.FEASIBLE: "FEASIBLE", pywraplp.Solver.INFEASIBLE: "INFEASIBLE"}.get(status, f"STATUS_{status}")
    clean = lambda v: 0.0 if abs(v) < 1e-9 else float(v)
    val = lambda vs: [clean(v.solution_value()) for v in vs]
    sol = Solution(status=name, objective=float(obj.Value()) if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else float("nan"), slack=val(slack))
    if envelope:
        sol.scale = clean(lam.solution_value()) if name in ("OPTIMAL", "FEASIBLE") else 0.0
    if name in ("OPTIMAL", "FEASIBLE"):
        for b in pb.batteries:
            c, d = (val(x) for x in bvars[b.id])
            dev, soc = b.init_dev, []
            for t in range(T):
                dev += c[t] * b.eta_c - d[t] / b.eta_d
                soc.append((b.soc_rest_end[t] + dev) / b.energy)
            sol.battery[b.id] = {"charge": c, "discharge": d, "soc": soc}
        for e in pb.evs:
            de, rc = (val(x) for x in evars[e.id])
            sol.ev[e.id] = {"defer": de, "recover": rc}
        for bl in pb.buildings:
            shed = val(kvars[bl.id])
            rb = [bl.rebound_frac / bl.rebound_h * sum(shed[k] for k in range(max(0, t - bl.rebound_h), t)) for t in range(T)]
            sol.building[bl.id] = {"shed": shed, "rebound": rb}
    else:                                                                # nothing feasible: report zero dispatch honestly
        for b in pb.batteries:
            sol.battery[b.id] = {"charge": [0.0] * T, "discharge": [0.0] * T, "soc": [b.soc_rest_end[t] / b.energy for t in range(T)]}
        for e in pb.evs:
            sol.ev[e.id] = {"defer": [0.0] * T, "recover": [0.0] * T}
        for bl in pb.buildings:
            sol.building[bl.id] = {"shed": [0.0] * T, "rebound": [0.0] * T}
    return sol
