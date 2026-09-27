"""What would it take? Two kinds of answer, both VERIFIED by rerunning the real day:

1. Constraints: bounded, plain-language changes to the flexibility program (enrolment, incentive, prices, device counts, limits). Single levers are tried first,
   then combinations of the best ones. Every pathway shown is a full rerun that was checked, not a guess.
2. Capacity: the smallest zone limit at which the day stays within capacity with the current flexibility, and how much upgrade the flexibility avoids.

Runs use the deterministic owner policy (fast, repeatable); real-LLM owners may behave differently. Nothing here changes the world or the stored scenarios.
"""
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from typing import Optional

import hashlib
import json
from pathlib import Path

from ..schemas.sandbox import CapacityPathway, ConstraintPathway, DeviceParams, LoadSpec, RecommendResponse, SandboxRunRequest
from .sandbox import CACHE_DIR, _norm_loads, _overlay, _season_cell, reference_day

TOL = 0.05
_POOL: Optional[ThreadPoolExecutor] = None


def _pool() -> ThreadPoolExecutor:
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=4)
    return _POOL


def _job(args):
    season, loads, inc, dp, c = args
    return _season_cell(season, loads, "stub", inc, dp, c)


def _levers(dp: DeviceParams, inc: float) -> list[tuple[str, list[tuple[str, dict, float]]]]:
    """(lever name, [(plain-language change, param updates, incentive)...]) with a moderate and a strong level. Only levers with room left are offered."""
    out: list[tuple[str, list[tuple[str, dict, float]]]] = []
    add = lambda name, opts: out.append((name, [o for o in opts if o is not None]))
    if dp.owners_enrolled_pct < 100:
        add("enrol", [(f"Owners enrolled {dp.owners_enrolled_pct:g}% -> {min(100, dp.owners_enrolled_pct + 30):g}%", {"owners_enrolled_pct": min(100, dp.owners_enrolled_pct + 30)}, inc),
                      (f"Owners enrolled {dp.owners_enrolled_pct:g}% -> 100%", {"owners_enrolled_pct": 100}, inc)])
    if inc < 200:
        add("incentive", [(f"Incentive ${inc:g} -> ${min(200, inc * 1.5):g}/MWh", {}, min(200.0, round(inc * 1.5))), (f"Incentive ${inc:g} -> $200/MWh", {}, 200.0)])
    if dp.min_price_scale > 0.5:
        add("price", [(f"Owners' minimum price x{dp.min_price_scale:g} -> x{max(0.5, dp.min_price_scale * 0.75):g}", {"min_price_scale": round(max(0.5, dp.min_price_scale * 0.75), 2)}, inc),
                      (f"Owners' minimum price x{dp.min_price_scale:g} -> x0.5", {"min_price_scale": 0.5}, inc)])
    for key, label, cap_ in (("battery_count", "Batteries", 200), ("ev_fleet_count", "EV charging fleets", 150), ("building_count", "Buildings and homes", 300)):
        cur = getattr(dp, key)
        if cur < cap_:
            a, b = min(cap_, ceil(cur * 1.5)), min(cap_, cur * 2)
            add(key, [(f"{label} {cur} -> {a}", {key: a}, inc), (f"{label} {cur} -> {b}", {key: b}, inc) if b > a else None])
    if dp.battery_reserve_pct > 10:
        add("reserve", [(f"Battery reserve kept {dp.battery_reserve_pct:g}% -> 10%", {"battery_reserve_pct": 10}, inc)])
    if dp.ev_shiftable_pct < 100:
        add("evshift", [(f"EV charging that can move {dp.ev_shiftable_pct:g}% -> {min(100, dp.ev_shiftable_pct + 20):g}%", {"ev_shiftable_pct": min(100, dp.ev_shiftable_pct + 20)}, inc),
                        (f"EV charging that can move {dp.ev_shiftable_pct:g}% -> 100%", {"ev_shiftable_pct": 100}, inc)])
    if dp.building_offset_c < 3.5:
        add("offset", [(f"Building temperature offset allowed {dp.building_offset_c:g} -> 3.5 degC", {"building_offset_c": 3.5}, inc)])
    if dp.building_max_hours < 5:
        add("hours", [(f"Longest curtailment {dp.building_max_hours} h -> 5 h", {"building_max_hours": 5}, inc)])
    return [(n, o) for n, o in out if o]


_mem: dict[str, RecommendResponse] = {}


def _rec_key(req: SandboxRunRequest) -> str:
    loads = req.loads or [LoadSpec(kind="data_centre", size=req.dc_mw)]
    body = {"s": req.season, "l": sorted((x.kind, round(float(x.size), 1)) for x in loads), "i": req.incentive_per_mwh, "c": req.capacity_mw, "d": req.device_params.model_dump(mode="json")}
    return "rec_" + hashlib.blake2b(json.dumps(body, sort_keys=True).encode(), digest_size=10).hexdigest()


def recommend(req: SandboxRunRequest) -> RecommendResponse:
    """A rerun-heavy search (20-30 reruns): cached, so a rehearsed demo scenario replays instantly instead of taking up to a minute."""
    key = _rec_key(req)
    if key in _mem:
        return _mem[key]
    f = CACHE_DIR / f"{key}.json"
    try:
        if f.exists():
            r = RecommendResponse.model_validate_json(f.read_text())
            _mem[key] = r
            return r
    except Exception:                                                                     # noqa: BLE001 — a bad cache file is just a miss
        pass
    r = _recommend(req)
    _mem[key] = r
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(r.model_dump_json(by_alias=True))
    except OSError:
        pass
    return r


def _recommend(req: SandboxRunRequest) -> RecommendResponse:
    loads = req.loads or [LoadSpec(kind="data_centre", size=req.dc_mw)]
    key = _norm_loads(SandboxRunRequest(loads=loads, dc_mw=req.dc_mw))
    dp0, inc0, cap_o = req.device_params, req.incentive_per_mwh, req.capacity_mw
    _, _, cap, _ = _overlay(key, cap_o)
    counter = {"n": 0}

    def cell(dp: DeviceParams, inc: float, c: Optional[float] = cap_o):
        counter["n"] += 1
        return _season_cell(req.season, loads, "stub", inc, dp, c)

    def cells(specs):
        """Evaluate several (dp, inc) candidates in parallel; returns SeasonCells in order."""
        counter["n"] += len(specs)
        return list(_pool().map(_job, [(req.season, loads, inc, d, cap_o) for d, inc in specs]))

    base = cell(dp0, inc0)
    peak_before = base.peak_load_mw
    resp = dict(season=req.season, date_used=reference_day(req.season).date().isoformat(), peak_hour=base.peak_hour, capacity_mw=cap, overload_mw=base.overload_mw,
                remaining_mw=base.remaining_mw, already_holds=base.remaining_mw <= TOL)
    if base.overload_mw <= 0:
        return RecommendResponse(**resp, runs_tested=counter["n"], constraint_pathways=[], capacity_pathway=None,
                                 note="Nothing to fix: with these loads the zone stays within capacity for this season's real day.")

    def apply(dp: DeviceParams, upd: dict) -> DeviceParams:
        return dp.model_copy(update=upd)

    levers = _levers(dp0, inc0)
    mk = lambda title, changes, d, inc, c: ConstraintPathway(title=title, changes=changes, device_params=d, incentive_per_mwh=inc, outcome=c.outcome, absorbed_mw=c.absorbed_mw,
                                                            remaining_mw=c.remaining_mw, holds=c.remaining_mw <= TOL)

    def apply_all(opts) -> tuple[DeviceParams, float, list[str]]:
        d, inc, labels = dp0, inc0, []
        for label, upd, i in opts:
            labels.append(label)
            d = d.model_copy(update=upd)
            inc = max(inc, i) if i != inc0 else inc
        return d, inc, labels

    def run_many(optlists):
        prepared = [apply_all(o) for o in optlists]
        outs = cells([(d, inc) for d, inc, _ in prepared])
        return [(o, d, inc, labels, c) for o, (d, inc, labels), c in zip(optlists, prepared, outs)]

    def run(opts):
        return run_many([opts])[0]

    # round 1: the strong level of every lever on its own (in parallel)
    strong = {name: opts[-1] for name, opts in levers}
    singles = run_many([[strong[n]] for n in strong])
    pathways: list[ConstraintPathway] = []
    holding = [r for r in singles if r[4].remaining_mw <= TOL]
    if holding:
        for opts, d, inc, labels, c in sorted(holding, key=lambda r: r[4].remaining_mw)[:3]:
            name = next(n for n, o in strong.items() if o == opts[0])
            for mild in dict(levers)[name][:-1]:                                # prefer the gentlest level that still works
                m = run([mild])
                if m[4].remaining_mw <= TOL:
                    opts, d, inc, labels, c = m
                    break
            pathways.append(mk("One change is enough", labels, d, inc, c))
    else:
        # round 2: pairs among the five strongest levers (enrolment and incentive only help together, so single-lever gains understate them)
        ranked = sorted(singles, key=lambda r: r[4].remaining_mw)[:4]
        names = [next(n for n, o in strong.items() if o == r[0][0]) for r in ranked]
        pair_runs = run_many([[strong[names[i]], strong[names[j]]] for i in range(len(names)) for j in range(i + 1, len(names))])
        ranked_names = [next(n for n, o in strong.items() if o == r[0][0]) for r in sorted(singles, key=lambda r: r[4].remaining_mw)]
        best = min(pair_runs + ranked, key=lambda r: r[4].remaining_mw)
        # round 3: add each remaining lever to the best pair/single
        used = {next(n for n, o in strong.items() if o == x) for x in best[0]}
        trip = run_many([list(best[0]) + [strong[n]] for n in [n for n in ranked_names if n not in used][:3]])
        allr = pair_runs + trip + singles
        full = sorted((r for r in allr if r[4].remaining_mw <= TOL), key=lambda r: (len(r[0]), r[4].remaining_mw))
        if full:
            for opts, d, inc, labels, c in full[:2]:
                pathways.append(mk("Several changes together", labels, d, inc, c))
        else:
            opts, d, inc, labels, c = min(allr, key=lambda r: r[4].remaining_mw)
            pathways.append(mk("Best within limits (still not enough)", labels, d, inc, c))

    # capacity: smallest limit at which the day stays within capacity WITH the current flexibility, verified by a rerun at that limit
    needed = ceil(base.peak_load_after_mw * 2 - 1e-9) / 2
    needed_nf = ceil(peak_before * 2 - 1e-9) / 2
    ver = cell(dp0, inc0, float(max(40.0, needed)))
    capp = CapacityPathway(current_mw=cap, needed_mw=needed, increase_mw=round(max(0.0, needed - cap), 1), needed_without_flex_mw=needed_nf,
                           flex_defers_mw=round(max(0.0, needed_nf - needed), 1), verified=ver.remaining_mw <= TOL and ver.peak_load_after_mw <= needed + TOL)
    return RecommendResponse(**resp, runs_tested=counter["n"], constraint_pathways=pathways, capacity_pathway=capp,
                             note="Each option was verified by rerunning this season's real highest-demand day with the deterministic owner policy. Real LLM owners may behave differently. A what-if on history, not a forecast or an engineering study.")
