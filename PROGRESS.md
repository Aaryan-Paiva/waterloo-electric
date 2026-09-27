# CapacityOS Development Progress

## Current Status
- **Product now:** Waterloo Electric, a live isometric flexible-grid sandbox (see `PLAN.md`). The engine (Phases 0-7) underneath is unchanged and still tested.
- **Current stage: Stage 6 (polish) — IN PROGRESS.** Stages 0-5 done. Next: Stage 7 freeze and submit.
- Last verified: backend **156 passed** (pytest), web lint + `tsc` clean, browser-verified drop -> strain -> narrated rebalance -> result.
- Known limitations: fleet size default 3x is an assumption; data-centre flexible compute not modeled; device inspector not built; not yet checked at projector size; nothing committed since the scaffold; OpenAI owners untested live beyond the earlier partial run.

### Stage tracker (updated as I build; times are wall clock, deadline Sun 12:00)
| Stage | Scope | Status |
|---|---|---|
| 0 | Commit + remote | DONE: https://github.com/Aaryan-Paiva/waterloo-electric (private until final check), commit 045008f, authored as Aaryan-Paiva |
| 1 | Sandbox API on the existing engine | DONE (156 tests) |
| 2 | Device parameters + fleet size | DONE in reduced form (78 physical models kept; sizes scaled by `fleetSizeX`; behavior overrides). More clusters and data-centre flexibility deferred |
| 3 | Isometric world renderer | DONE (all seasons, night, states) |
| 4 | Drag-and-drop, script player, result | DONE, browser-verified |
| 5 | Device editor drawer | FIRST VERSION DONE; inspector and "what changed" delta not built |
| 6 | Narration + polish | PARTIAL (browser speech toggle exists; states/a11y/projector check pending) |
| 7 | Freeze, docs, submit | NOT STARTED |

## Progress Log

### 2026-09-26 — Phase 4 baseline (recorded retroactively)
What changed:
- Single-event OR-Tools coordination (`/simulate/event`, `/coordinate`), Coordinate DERs UI, independent constraint validator.
Verification: backend 102 passed, web 7 passed, lint/tsc/build clean. Golden June 24 event: 75.7 -> 67.3 MWh, worst 8.0 -> 6.4 MW, partially resolved.

### 2026-09-26 — Phase 5 kickoff: source-of-truth docs updated
What changed:
- CLAUDE.md: new §13b (owner/operator agents), AI-layer scope, phases renumbered (5 owner agents, 6 market, 7 multi-year, 8 feasibility, 9 recommendations, 10 NL assistant, 11 reports/polish), rule 13 (PROGRESS.md required) and rule 14 (two agent kinds).
- ARCHITECTURE.md (agentic layer + Mermaid), BUILD_PLAN.md (roadmap), docs/modeling-assumptions.md (Phase 5-6 assumptions).
Architecture decisions:
- Plain-Python bounded state machine for owner orchestration; NO LangGraph/LangChain/MCP (4 states, must be deterministic/auditable). OpenAI SDK is the only new optional dependency.
- Offers are per-asset time blocks; validated by a single-asset LP (max scale lambda); clearing reuses the Phase 4 MILP with offer caps and a low-weight price term.
Files changed: CLAUDE.md, ARCHITECTURE.md, BUILD_PLAN.md, docs/modeling-assumptions.md, PROGRESS.md
Next step: owner schemas, grouping, model refactor, provider abstraction.

### 2026-09-26 — Phase 5-6 backend: owner agents, providers, validator, clearing, API
What changed:
- `optimization/model.py`: offer caps + price term on delivering variables (Problem.caps/prices); new envelope mode (`scale_target`) = single-asset LP maximizing lambda so the asset can deliver lambda x offer as NET reduction (discharge-charge, defer-recover) — used by the validator. Manual mode unchanged (102 old tests still pass). `objectives.W_PRICE=0.01`.
- `optimization/dispatcher.build_problem(include=...)`: agentic enrolment = accepted offers, participation draw ignored.
- `capacityos/coordinator.py`: `AgenticInputs`, `check_window`, mode/clearingCost/owner/price/cost fields on the result; per-agent `delivered_mwh`.
- New `owners/`: `grouping` (18 owners over 70 flexible assets, seeded), `physical` (Physics + offer validator), `context`, `tools` (typed tools, authorization), `providers/{base,stub,openai_provider,replay,__init__}`, `runner` (bounded state machine, trace, fallbacks, diagnostics, replay), `run_store` (bounded in-memory, 50 runs).
- API (`api/owners.py`): GET /api/agentic/config, GET /api/scenarios/{id}/owner-agents, POST /api/scenarios/{id}/events/{eventId}/flexibility-request | agentic-run, POST /api/scenarios/{id}/agentic-run, GET /api/agentic-runs/{id}[/offers|/dispatch|/trace], POST /api/agentic-runs/{id}/replay.
- Schemas: `schemas/owners.py` (OwnerAgent + prefs, FlexibilityRequest, offer/tool models, validation, OwnerRecord, TraceEvent, MarketSummary, AgenticRun); CoordinationResult gained mode/clearingCost; AgentDispatch gained ownerId/pricePerMwh/deliveredMwh/cost.
- Settings: OWNER_AGENT_PROVIDER / OPENAI_API_KEY / OWNER_AGENT_MODEL / OWNER_AGENT_TIMEOUT_SECONDS / OWNER_AGENT_MAX_RETRIES (+ tiny .env loader). `openai` is an OPTIONAL extra (`pip install -e ".[openai]"`).
Architecture decisions:
- No LangGraph/LangChain/MCP (explicit 4-state machine is simpler and replayable). OpenAI Chat Completions with function calling; default model `gpt-4o-mini` (configurable, NOT verified live: no API key in this environment; tested with a fake client).
- Bug found & fixed while testing: validator originally counted gross discharge/defer, letting a battery "deliver" while recharging in the same hour; now net.
- Stub block selection weights hours by criticality x deliverable MW (first version clustered offers in early hours).
Golden June 24 (agentic stub, incentive 40/80/120 $/MWh): dispatched 1.5 / 10.8 / 27.2 MWh; energy above capacity 75.7 -> 74.2 / 66.2 / 51.5; all checks pass, reconciled. Manual mode still 67.3.
Tests: +29 (tests/test_owners.py). Backend 131 passed.
Limitations: OpenAI provider untested against the live API; run store is in-memory; offers cover only the event window (no pre-event charging offers).
Next step: Agentic Mode UI (mode selector, request panel, live owner feed, market summary, owner inspector).

### 2026-09-26 — Phase 5-6 frontend, docs, verification
What changed:
- Web: `types/api.ts` (owner/run types), `lib/api.ts` (+4 calls), `lib/agentic.ts` (+test, pure trace -> live status), `hooks/useAgentic.ts`, `components/coordination/ModeSelector.tsx` (Manual | Agentic), `components/agentic/AgenticPanel.tsx` (request card + incentive presets/custom + provider select, live owner feed replayed from the recorded backend trace, market summary, owner inspector with Modeled preferences / offers / validation), `CoordinationPanel.Result` exported and reused for before/after. The world canvas animates the deterministic dispatch of whichever mode is active; in Agentic mode the agent cards count assets with validated offers.
- Docs: README (status, endpoints, setup for optional OpenAI), `.env.example`, demo-script, data-provenance, modeling-assumptions, ARCHITECTURE/BUILD_PLAN/CLAUDE.md (earlier entry).
Verification:
- backend: 131 passed (pytest). frontend: 10 passed (vitest). lint clean. tsc clean. production build clean.
- browser (golden 20 MW, Jun 24 08:00-22:00, stub, $120): request 8.0 MW peak; 18 owners; feed showed a physical-validation failure ("insufficient usable energy") -> revision -> accepted; market REQUESTED 8.0 / OFFERED 8.8 / VALIDATED 6.3 / DISPATCHED 4.7 / REMAINING 6.3 MW; 75.7 -> 51.5 MWh above capacity, partially resolved; world showed "optimized · was 98.0" with battery/building dispatch.
Bugs/fixes: a stale-run banner correctly appeared when the scenario changed mid-run (test artifact from double-clicking Golden demo); wording fixed for agentic ("assets with validated offers"); feed animation sped to 45 ms/event.
Assumptions / limitations: see Current Status. LLM decisions are synthetic behavior, not predictions of real customers.
Next step: STOP for review. Then Phase 7 (multi-event/multi-year coordination) using deterministic or cached owner policies (no per-hour LLM calls).

### 2026-09-26 — Phase 7 backend: historical coordination engine
What changed:
- `capacityos/historical.py` (engine), `schemas/historical.py`, `api/historical.py`; `POST /api/scenarios/{id}/historical-coordination` (cached, ~8-13 s uncached), `GET /api/historical-runs/{id}[/events]`.
- Engine design: windows from the scenario analysis -> CLUSTERS (gap <= mergeGapHours, default 24, must be >= tail) simulated JOINTLY (one SOC trajectory / EV balance / per-24h-block building comfort budget over the cluster incl. the gap hours); chains > 96 h are split at the widest gap. Chronological loop carries battery SOC deviation (<= 0, never a surplus) between clusters; in the gap a battery recharges only within inverter spare power AND zone headroom below capacity (cannot create a violation), the remainder is carried in. Building curtailment hours of the previous 24 h are carried. Owners use the SAME Modeled preferences via the deterministic stub policy (per event window), plus a monthly quota (`maxEventsPerMonth`, decline code event_frequency). One joint physical validation + one revision per owner per cluster, then one OR-Tools clearing per cluster.
- Model: `Problem.duration_period_h` (per-block curtailment budget), `BatteryIn.init_dev`, `BuildingIn.prior_hours`; `build_physics` generalized to multi-window horizons; validator/model share them. Phase 4/5 behavior unchanged (defaults).
- Independent full-history verification (44k hours) inside the result: hours/energy after match a direct scan; no violation outside event windows; no event worse; aggregates reconcile; all cluster physical checks pass.
- `AgenticRun` now carries `decisionSource` (llm_openai | deterministic_stub | replay) and `llmOwnerCount`; historical results carry `decisionSource=deterministic_owner_policy`, `llmCalls=0`.
Tests: +17 (`tests/test_historical.py`): golden 20 MW (59 events / 268 h / 8.0 MW / June 24 = 75.7 MWh), determinism, chronology, adjacent merge, split, SOC carry (engine + hand-solvable model), aggregate reconciliation at $40/$80/$120, full-history scan, no-LLM, immutability, API. Backend 148 passed.
Measured golden 20 MW, five years, 268 constrained hours / 59 events / 532.5 MWh above capacity before:
- $40/MWh: 264 h, 518.3 MWh, worst 8.0 MW, dispatched 14.2 MWh (1 resolved / 22 partial / 36 unresolved).
- $80/MWh: 190 h, 383.8 MWh, worst 7.58 MW, dispatched 171.6 MWh (22 / 35 / 2).
- $120/MWh: 88 h, 152.8 MWh, worst 6.34 MW, dispatched 402.4 MWh (42 / 17 / 0).
Next: UI (Historical mode), docs, then final verification.

### 2026-09-26 — Phase 7 UI, docs, verification
What changed: `HistoricalPanel` (incentive presets/custom, cached comparison table across scenarios, whole-history before/after, DER contribution, by year/season/severity, event list with jump, verification/continuity), `hooks/useHistorical.ts`, third mode in `ModeSelector`, world/timeline overlay of the selected historical run at the cursor (optimized net + dispatch), Agentic panel badge distinguishing Real LLM owner agents vs deterministic stub vs replay. Docs: CLAUDE.md (Phase 7 marked done, Phase 8 note), ARCHITECTURE.md (+Mermaid), BUILD_PLAN.md, modeling-assumptions.md, README, demo-script.
Verification: backend 148 passed; web 10 passed; lint/tsc/build clean; browser (golden 20 MW): ran $40/$80/$120 in Historical mode, table matched the backend (264/190/88 h; 518.3/383.8/152.8 MWh), clicking an event showed "optimized · was 91.8" in the world.
Next step: STOP for review; Phase 8 project-level feasibility.

### 2026-09-27 ~03:30 — Waterloo Electric sandbox: Stages 1-5 first pass
What changed (backend):
- `schemas/sandbox.py`, `capacityos/sandbox.py`, `api/sandbox.py` (registered in `main.py`): `GET /api/sandbox/world`, `POST /api/sandbox/run`.
- `pick reference day` = the real day with the highest demand per season (2021-25): winter 2025-01-20, spring 2022-05-31, summer 2025-06-24, fall 2023-09-05.
- `run_sandbox`: throwaway scenario overlay with the dropped data centre (nothing stored, baseline untouched), finds the overload window containing the chosen hour (long overloads are played one day at a time), runs the existing agentic pipeline (owner policy -> physical validation -> OR-Tools) and builds a playback script ONLY from the real trace; outcome labels holds / partly_holds / breaks / no_overload are descriptive readouts.
- `owners/runner.py`: `owners_override` (enrolled subset + minimum-price scale). `world/population.py`: `use_variant()` contextvar returns a cached parameter variant of the same seeded population (fleet size multiplier and behavior overrides), base population untouched.
- Tests: `tests/test_sandbox.py` (+8): reference days, script from real trace, determinism, no-overload paths, winter big data centre, parameters change outcome (fleet size, reserve, enrolment, price), immutability, API validation.
What changed (web):
- `components/iso/scene.ts` + `IsoWorld.tsx`: deterministic isometric renderer (homes with solar, downtown towers, university, depot with chargers/cars, battery containers, industry, substation, power lines with flow dots, data centre, seasons, night) at 1440x900 logical px; effects bound to simulation state only.
- `components/sandbox/Sandbox.tsx`: the screen: brand + provenance chips, gauge, tray (drag or Enter), steps card with physical-check callout, owner speech bubbles anchored to device groups, result card with before/after chart, season + hour controls, device editor drawer, speech toggle. `lib/sandbox.ts` API client. `/` now renders the sandbox; old UI stays at `/world/waterloo-demo`.
Architecture decisions:
- Thin orchestration layer (`capacityos/sandbox.py`) over the proven engine; no physics in the API layer or the UI. The UI is a player of a recorded script.
- Fleet size is an explicit, labelled assumption (1x = up to 25% of load controllable) instead of inventing more device models under time pressure.
Findings:
- Relief varies strongly by hour: at 20 MW summer, 2 pm holds (batteries 3.5 + buildings 2.9 MW), 4 pm partly holds, 7 pm holds via EV shifting (7.2 MW). Default hour set to 2 pm.
- Winter at 20 MW has no overload (only summer/fall in the golden data); a 45 MW data centre creates winter stress.
Verification: backend 156 passed; web lint/tsc clean; browser: drag onto a lot -> strain -> 64-step script -> result card.
Next: see the plan in the reply; then Stage 5/6 gaps, docs, commit.
