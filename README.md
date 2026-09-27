# CapacityOS

**A living sandbox for local-grid capacity planning.** Drop a hypothetical data centre, housing development, or EV depot onto a modeled electrical zone, watch it strain against the zone's capacity, then watch batteries, EV charging, and flexible buildings negotiate to absorb the overload — every offer checked against real device physics, every dispatch decided by a deterministic optimizer.

Built for **AF Hacks: Growing Canada** (Sep 26–27, 2026). The zone modeled is the **Ontario Southwest Zone Sandbox**.

> A planning simulation, **not** a forecast, a recommendation engine, a feasibility verdict, or a utility-grade engineering study.

## Why

Connecting big new loads (AI data centres, EV depots, housing) to the grid takes years, and planners can't easily see how much local flexibility (virtual power plants, batteries, smart charging, flexible buildings) could absorb before that infrastructure needs to be built. Flexibility programs are real in Canada today (Ontario's Peak Perks VPP has 100,000+ homes enrolled), but there was no fast way to test a specific flexibility program against a specific new load before committing to it. CapacityOS is that testing ground.

**Users:** utility and municipal planners, VPP/flexibility-program designers, developers evaluating a site's electrical capacity.
**Next step after the hackathon:** a calibrated pilot with a real distribution utility — replacing the synthetic device population, assumed capacity, and derived demand with real meter data, real device ratings, and a real enrolled fleet, benchmarked against a planning case the utility has already worked through. A location is a "world pack" (a demand dataset plus a config), so the simulation, agent, and optimization engine itself does not change.

## What you can do

- **Drag a new load** (data centre, housing development, or EV depot) onto an empty lot. The zone strains against a 90 MW modeled capacity.
- **Watch it negotiate:** 18 owner agents (real LLM-backed agents when an OpenAI key is configured, a labelled deterministic policy otherwise) independently offer or decline flexibility as their decisions stream in. A physical validator rejects offers that violate battery state-of-charge, EV departure deadlines, or building comfort limits — an invalid offer gets exactly one bounded revision attempt. An OR-Tools optimizer then picks dispatch from the validated offers: first minimizing the remaining overload, then minimizing modeled dispatch cost among what's left. The **Log** tab shows every owner's decision, its status (accepted / declined / rejected by physics / priced out), and the optimizer's summary.
- **Read the honest result:** how much of the overload was absorbed, broken down by device type, a before/after chart of the real reference day, and a plain outcome label — holds / partly holds / breaks. It states what happened in this simulation, not a real-world verdict.
- **Fix it:** when a result doesn't fully hold, CapacityOS runs 20–30 real reruns of the simulation testing bounded changes — enrollment, incentive, owners' minimum price, device counts, battery reserve, EV shiftable share, building comfort offset, curtailment duration — alone and combined, plus a capacity-increase fallback. Every pathway shown is a verified rerun, never a guess.
- **Change the conditions:** four seasons and a time-of-day slider. Each season replays the real highest-demand day of 2021–2025 for that season, so a program can be tested against more than one lucky day.
- **Edit the devices:** device counts, incentive ($/MWh), a zone-capacity what-if, owners enrolled, owners' minimum price, battery reserve, EV shiftable share, allowed temperature offset, longest curtailment. A "what changed" line compares against the previous run.
- **Inspect anything:** click a device-type legend row or a cluster to see what it does, its size, its owner, its limits, and its contribution in the current run. Click a run in **History** to restore its exact setup.

## Data honesty (labelled on screen)

| Item | Label |
|---|---|
| Hourly demand shape: IESO Southwest zone, 2021–2025, scaled to a 78 MW peak | **Derived** (never "observed Waterloo demand" — no observed Waterloo-only series exists) |
| 90 MW zone capacity | **Modeled** (assumption) |
| 234 device clusters (60 batteries, 42 EV fleets, 108 buildings, 24 solar) grouped into 18 owners | **Modeled** (synthetic, seeded; a cluster stands for many real units) |
| New data centre / housing / EV depot | **Hypothetical** |
| Runs and results | **Derived** |
| A capacity what-if you set (Fix It → Try this limit, or the editor slider) | **User assumption** |

IESO timestamps are treated as fixed EST (an unverified convention, stated explicitly rather than silently assumed).

## Architecture

```
┌─────────────────────────────┐        ┌──────────────────────────────────────────────────────────┐
│  apps/web (Next.js/React)   │        │  apps/api (FastAPI, Python 3.12)                          │
│                             │        │                                                            │
│  isometric world canvas ────┼───────►│  /api/sandbox/world   → world pack + seeded population     │
│  drag-and-drop new loads    │  HTTP  │  /api/sandbox/run     → one scenario, one reference hour   │
│  device editor (sliders)    │◄───────┤  /api/sandbox/recommend → Fix It: bounded rerun search      │
│  Result / Log / Fix it /    │  JSON  │  /api/sandbox/seasons → same config, 4 real reference days │
│  Seasons / Runs tabs        │        │                                                            │
│  script player (replays     │        │  The UI computes nothing — it plays a script the backend  │
│  the backend's real trace)  │        │  built from the real optimizer trace.                     │
└─────────────────────────────┘        └──────────────────────────────────────────────────────────┘
```

### The decision pipeline (what actually happens on one overload)

```
1. Historical demand (IESO Southwest shape, derived)
        +
   Hypothetical new load (data centre / housing / EV depot)
        ↓
2. Net load vs. modeled 90 MW capacity  →  deficit_MW = max(0, net_load − capacity)
        ↓  (if deficit > 0)
3. FlexibilityRequest broadcast to every owner — same request, no quotas
        ↓
4. Owner agents decide independently
   • deterministic policy (default, offline, reproducible), or
   • OpenAI-backed reasoning (18 parallel calls, ~35s cold, cached after)
   → each owner returns: offer(MW, price, duration) | decline(reason)
        ↓
5. Physical offer validator (deterministic, unconditional)
   • battery: power / energy / state-of-charge / reserve bounds
   • EV fleet: charging deadline must still be met
   • building: comfort-offset and max-curtailment-hours bounds
   → invalid offer → exactly ONE bounded revision attempt → then accept-as-is or reject
        ↓
6. OR-Tools optimizer clears ONLY validated offers
   objective: first minimize remaining overload, then minimize modeled dispatch cost
        ↓
7. Dispatch applied → net load recomputed → outcome labelled:
   holds | partly holds | breaks  (never a bare pass/fail)
        ↓
8. If not fully resolved → Fix It searches 20-30 bounded parameter changes,
   reruns the simulation for each, and returns only VERIFIED pathways
```

**The rule that never bends:** an LLM can *propose* an offer. It can never *decide* a dispatch. Every number that reaches the optimizer has already passed a deterministic physical check — LLM output is treated as untrusted input and is structurally incapable of touching state of charge, load, capacity, or the optimizer's constraints. This is why the product can show `decisionSource: llm_openai` vs. `deterministic_owner_policy` side by side without the result ever becoming less trustworthy — the physics layer and the optimizer don't care which one proposed the offer.

### Two kinds of "agent" (kept structurally separate)

| | Physical device model | Owner agent |
|---|---|---|
| Represents | the battery / EV fleet / building itself | the economic decision-maker behind it |
| Owns | state of charge, deadlines, power/energy/comfort limits | willingness, price, timing, decline/revise |
| Implementation | deterministic Python (`apps/api/src/agents/`) | deterministic stub or OpenAI (`apps/api/src/owners/`) |
| Can it invent a number? | no — it's a physics model | yes — but every offer it makes is checked before it counts |

### Seasons, Fix It, and provenance are backend-computed, frontend-played

The frontend never runs the simulation itself. Every screen — the Result tab, the Log, Fix It's tested pathways, the Seasons comparison — is a JSON response from a real backend computation, and the UI just animates a script built from that real trace. This is a deliberate design choice: it means the demo you see is never faked, only ever replayed.

## Run it

```bash
# API (Python 3.12)
cd apps/api && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/uvicorn src.main:app --port 8000

# Web (another terminal)
cd apps/web && cp .env.example .env.local && npm install && npm run dev      # http://localhost:3000
```

No API key is needed — owners then use the deterministic policy, clearly labelled as such. For real LLM owners: `cp .env.example .env`, set `OWNER_AGENT_PROVIDER=openai` and `OPENAI_API_KEY`, `uv pip install -e ".[openai]"`, and start the API from a shell that has loaded `.env` (never commit it). A first real-LLM run takes about 35s (18 parallel calls); identical reruns replay instantly from a local decision cache (`apps/api/.cache`, gitignored). `scripts/warm_cache.py` pre-runs the demo scenarios. LLM decisions vary run to run; the cache pins one, and the physical validator and optimizer never trust them regardless.

## Tests

```bash
cd apps/api && .venv/bin/python -m pytest -q          # engine, owners, validator, historical coordination, sandbox
cd apps/web && npm test && npm run lint && npx tsc --noEmit && npm run build
```

## Also in the repo

The engine's earlier analysis screens live at `/world/waterloo-demo` (scenario events, agents, single-event and historical coordination). Demo-video production tooling (Runway generation, title overlays, walkthrough recording, final assembly) lives in `apps/web/scripts/` — see `demo_video_script.md` and `demo_video_storyboard.md` there for the shot-by-shot breakdown.

## Not built (next)

Data-centre flexible compute, water heaters and industrial demand response, locking parts of the fleet, automatic scenario sweeps, PDF reports, an upload flow for new zones.

## Deploy

- **Web (Vercel):** import the repo, set **Root Directory** to `apps/web`, add `NEXT_PUBLIC_API_URL` = your API's public URL.
- **API (Render, Docker):** `render.yaml` + `Dockerfile` at the repo root. Set `OPENAI_API_KEY` in the Render dashboard (never in the repo) and `CAPACITYOS_CORS_ORIGINS` to the Vercel URL. The API needs a long-lived Python host: OR-Tools and pandas are too large for Vercel functions, and a real-LLM run takes about 35s.
