# Waterloo Electric

**A live sandbox of a flexible Waterloo grid.** Drag a data centre onto an empty lot, watch the zone strain, then watch batteries, EV charging and buildings rebalance the load, checked against each device's physical limits. Edit how the devices behave, switch season and time of day, and see where the flexible grid holds and where it breaks.

Built for **AF Hacks: Growing Canada** (Sep 26-27, 2026). Under the hood it is **CapacityOS**, a deterministic engine for local-grid capacity planning with flexibility.

> A planning simulation, **not** a forecast, a recommendation engine, a feasibility verdict or a utility-grade engineering study.

## Why
Connecting big new loads (AI data centres, EV depots, housing) to the grid takes years, and planners can't easily see how much local flexibility (VPPs, batteries, smart charging, flexible buildings) could absorb. Flexibility is real in Canada (Ontario's Peak Perks VPP has 100,000+ homes), but there is no quick way to test a flexibility program against a specific new load before committing. Waterloo Electric is that testing ground.

**Users:** utility and municipal planners, VPP and flexibility-program designers, developers evaluating sites.
**Next step after the hackathon:** a pilot with a local distribution utility, replacing the synthetic devices, assumed capacity and derived demand with real meter data, real ratings and real enrolled devices. A location is a "world pack" (a demand file plus a config), so the simulator itself does not change.

## What you can do
- **Drag a data centre** (5-60 MW) onto an empty lot. The zone strains against a 90 MW modeled capacity.
- **Watch it rebalance:** 18 modeled owners offer or decline, a physical check reduces impossible offers (battery charge, EV departure deadlines, building comfort), and an OR-Tools optimizer decides who does what. Speech bubbles, captions and optional spoken narration follow it.
- **Read the result:** how much of the overload was absorbed, by device type, a before/after chart of the real day, and a plain label (holds / partly holds / breaks). It states what happened in the simulation, not a real-world verdict.
- **Change the conditions:** four seasons and a time-of-day slider. Each season replays the real highest-demand day of 2021-2025 for that season.
- **Edit the devices:** fleet size, owners enrolled, owners' minimum price, battery reserve, EV shiftable share, allowed temperature offset, longest curtailment, rebound. A "what changed" line compares with the previous run.
- **Inspect a device type** (click a legend row or a cluster): what it does, size, owners, limits and its contribution in the current run.

## Data honesty (labelled on screen)
| Item | Label |
|---|---|
| Hourly demand shape: IESO Southwest zone 2021-2025, scaled to a 78 MW peak | **Derived** (never "observed Waterloo demand") |
| 90 MW zone capacity | **Modeled** (assumption) |
| 78 device clusters (batteries, EV fleets, buildings, solar) and 18 owners | **Modeled** (synthetic, seeded; a cluster stands for many units) |
| Data centre | **Hypothetical** |
| Runs and results | **Derived** |

Fleet size (default 3x, 1x = up to 25% of load controllable) is an explicit assumption you can edit. IESO timestamps are treated as fixed EST (unverified convention).

## Architecture
```
web (Next.js, canvas)  ──►  FastAPI /api/sandbox/{world,run}  ──►  engine
 isometric town, HUD,        thin orchestration: throwaway        world pack · seeded DER population
 script player, editor       scenario overlay, real reference     physical device models
                             day, playback script from the        owner agents + physical offer validator
                             real run trace                       OR-Tools clearing · historical coordination
```
The UI computes nothing: it plays a script the backend built from the real optimizer trace. Owner decisions come from a deterministic policy by default; an optional OpenAI provider (structured tool calling, validated, with fallback) can be switched on and is labelled `decisionSource`. LLM output is untrusted and can never change physics. Details: [PLAN.md](PLAN.md), [ARCHITECTURE.md](ARCHITECTURE.md), [CLAUDE.md](CLAUDE.md), [docs/modeling-assumptions.md](docs/modeling-assumptions.md), journal in [PROGRESS.md](PROGRESS.md).

## Run it
```bash
# API (Python 3.12)
cd apps/api && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/uvicorn src.main:app --port 8000

# Web (another terminal)
cd apps/web && cp .env.example .env.local && npm install && npm run dev      # http://localhost:3000
```
No API key is needed. Optional real LLM owners: `cp .env.example .env`, set `OWNER_AGENT_PROVIDER=openai` and `OPENAI_API_KEY`, and `uv pip install -e ".[openai]"` (never commit `.env`).

## Tests
```bash
cd apps/api && .venv/bin/python -m pytest -q          # engine, owners, validator, historical coordination, sandbox
cd apps/web && npm test && npm run lint && npx tsc --noEmit && npm run build
```

## Also in the repo
The engine's earlier analysis screens live at `/world/waterloo-demo` (scenario events, agents, single-event and historical coordination). API reference for those is in [CLAUDE.md](CLAUDE.md) and [PROGRESS.md](PROGRESS.md).

## Not built (next)
Data-centre flexible compute, water heaters and industrial demand response, locking parts of the fleet, automatic scenario sweeps, recommendations, reports, an upload flow for new zones.
