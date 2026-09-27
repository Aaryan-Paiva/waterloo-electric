# CapacityOS

A living sandbox for local grid capacity planning: real historical electricity demand, synthetic DER agents, deterministic optimization, and simulation-backed recommendations. **A planning simulation, not a utility-grade study or interconnection approval.**

Source of truth: [CLAUDE.md](CLAUDE.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [BUILD_PLAN.md](BUILD_PLAN.md)

## Status: Phase 0-7 complete (5-6 = agentic DER layer + market; 7 = historical coordination engine)
- Phase 0-1: monorepo, Waterloo Demo world pack, core schemas, deterministic 30-day fixture + full 2021-2025 dataset, API, living-world screen with playback.
- Phase 2: **scenarios** (the baseline world is never mutated), a **data-centre project** (constant 24/7 load, configurable MW, Hypothetical), full-history net-load recompute, a `CapacityEvent` for every hour above modeled capacity, and surfaced constrained hours, affected days, worst deficit, projected peak and event windows in the API and UI. **Golden demo: +20 MW -> 268 constrained hours, 51 affected days, 59 windows, worst deficit 8.0 MW, projected peak 98.0 MW.**
- Phase 3: a **deterministic seeded DER population** (20 batteries, 14 EV fleets, 36 flexible buildings, 8 solar clusters; all Modeled) with per-agent time-varying state, participation, availability and physical constraints. Agents expose **potential flexibility** for a timestamp/window; nothing is dispatched. Solar is context only (already in the baseline, 0 relief). At the golden peak hour: 4.3 MW potential vs an 8.0 MW deficit (11.3 MW if every eligible agent enrolled).
- Phase 4: **single-event DER coordination.** `POST /api/scenarios/{id}/simulate/event` (alias `/coordinate`) with a `windowId` (or explicit start/end) runs a deterministic OR-Tools SCIP model over that event window plus a recovery tail, using ONLY enrolled and available batteries, EV fleets and buildings. It returns hourly dispatch, the optimized load and remaining-deficit curves, violation hours, energy above capacity, per-agent dispatch/state, an independent constraint check, and a status (resolved / partially_resolved / unresolved). Results are **Derived** from **Modeled** resources and make no project-level feasibility claim. Golden June 24 event (14 h, 08:00-22:00): 75.7 -> 67.3 MWh above capacity, worst deficit 8.0 -> 6.4 MW, **partially resolved**; at 100% participation 46.4 MWh; at 0% unresolved.
- **Phase 5-6 (agentic mode):** two kinds of "agent" are kept apart: the 78 deterministic **physical DER models** and 18 **owner/operator agents** (5 battery operators, 5 EV aggregators, 8 building portfolios; Modeled, seeded) that control the 70 flexible ones. In **Agentic mode** CapacityOS broadcasts a `FlexibilityRequest` for a selected event with an incentive ($/MWh ceiling); each owner decides through typed tools (`submit_offer` / `decline_offer` / `revise_offer` / `request_information`); a deterministic **physical validator** checks every offer (ownership, availability, SOC/reserve/inverter, EV deadline, building comfort/duration) and allows ONE bounded revision with the feasible envelope; only validated offers reach the OR-Tools **clearing** (violations first, price as a tie-breaker). **Manual mode** (participation sliders, no LLM) is unchanged. Owner decisions come from a provider: a deterministic **stub** (default, no API key, drives tests) or **OpenAI** (structured tool calling, timeouts, bounded retries, fallback to the stub). LLM output is untrusted and can never change SOC, load, the scenario, limits or capacity. Runs are stored, traceable and replayable. Golden June 24 event (stub owners; ceiling $40 / $80 / $120 per MWh): 1.5 / 10.8 / 27.2 MWh dispatched, energy above capacity 75.7 -> 74.2 / 66.2 / 51.5 MWh (all partially resolved, all checks pass). Manual mode still gives 67.3.
- **Phase 7 (historical coordination):** `POST /api/scenarios/{id}/historical-coordination {incentivePricePerMwh}` coordinates EVERY capacity-event window of the 2021-2025 history (not all 43,824 hours) chronologically with the **deterministic modeled owner policy (0 LLM calls)**, the same physical validator and OR-Tools clearing. Adjacent events (<= 24 h apart) are simulated jointly; battery energy is carried between events (recharge limited by inverter and zone headroom), so storage never resets magically. Per-event and aggregated results (total, year, season, DER type, severity) with an independent full-history verification. Golden 20 MW (268 constrained hours, 59 events, 532.5 MWh above capacity): **$40/MWh -> 264 h / 518.3 MWh / worst 8.0 MW; $80 -> 190 h / 383.8 MWh / 7.6 MW; $120 -> 88 h / 152.8 MWh / 6.3 MW** (42 events resolved at $120). These are user-selected scenarios: no recommendation, no feasibility verdict. Real-LLM Agentic runs are labelled `decisionSource=llm_openai` vs `deterministic_stub`.
- Not built yet (later phases): project-level feasibility (8), recommendations (9), NL assistant (10), reports & polish (11). Development log: [PROGRESS.md](PROGRESS.md).

Historical endpoints: `POST /api/scenarios/{id}/historical-coordination`, `GET /api/historical-runs/{id}[/events?year=&season=&status=&severity=]`.

Agentic endpoints: `GET /api/agentic/config`, `GET /api/scenarios/{id}/owner-agents`, `POST /api/scenarios/{id}/events/{eventId}/flexibility-request | agentic-run`, `POST /api/scenarios/{id}/agentic-run`, `GET /api/agentic-runs/{runId}[/offers|/dispatch|/trace]`, `POST /api/agentic-runs/{runId}/replay`.

Agent endpoints: `GET /api/worlds/{id}/population`, `/agents`, `/agents/{agentId}`, `/population/potential?timestamp=&windowHours=&scenarioId=`, `/population/decomposition?timestamp=`; `PATCH /api/scenarios/{id}/assumptions` (participation overrides).

New endpoints: `POST /api/scenarios`, `POST /api/scenarios/{id}/projects`, `PATCH|DELETE .../projects/{pid}`, `POST .../clone`, `GET .../analysis`, `GET .../events`, `GET .../load`.

## Run it
```bash
# API (Python 3.12)
cd apps/api && uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m src.data.ingestion --world waterloo-demo   # optional: rebuild parquet + fixture from data/raw
.venv/bin/uvicorn src.main:app --port 8000
# Optional: OpenAI owner agents (the stub needs nothing). cp .env.example .env, set OWNER_AGENT_PROVIDER=openai and OPENAI_API_KEY, then:
uv pip install --python .venv/bin/python -e ".[openai]"
# Web
cd apps/web && cp .env.example .env.local && npm install && npm run dev      # http://localhost:3000
```
The API serves the full 2021–2025 parquet when `data/processed/waterloo_demo_hourly.parquet` exists, otherwise the committed 30-day fixture, and labels which one ("Demo mode").

## Tests
```bash
cd apps/api && .venv/bin/python -m pytest -q     # 148 tests incl. the historical engine, measured 10/20/30 MW cases, the agent population, the optimizer's physics, the golden June 24 event, owner agents, the offer validator, providers and clearing
cd apps/web && npm test && npm run lint && npx tsc --noEmit
```

## Data honesty (read this)
- No observed Waterloo-only hourly series exists. The **Waterloo Demo Zone** uses the observed hourly *shape* of IESO's Southwest zone (which contains Waterloo, 2021–2025), scaled so its 5-year peak is 78 MW. It is labelled **Derived**, never "observed Waterloo demand".
- The **90 MW capacity** is a labelled **Modeled** hackathon assumption.
- IESO timestamps are treated as fixed EST (UTC-5), hour-ending; this convention is recorded as *unverified* in the world pack.
- Raw downloads live in `data/raw/` (gitignored). See `docs/data-provenance.md` and `docs/modeling-assumptions.md`.
