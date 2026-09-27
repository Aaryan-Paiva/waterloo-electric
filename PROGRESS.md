# CapacityOS Development Progress

## Current Status
- **Product:** Waterloo Electric, a live isometric flexible-grid sandbox (see `PLAN.md`). Engine (Phases 0-7) unchanged and tested.
- **Current stage: Stage D (credibility + submission prep).** Stages 0, A, B, C done and committed.
- Last verified: sandbox tests 18 passed; full backend suite 162 passed + 1 stale Phase-2 test fixed right after (housing/EV depot are now implemented); web 15 passed, lint and tsc clean, production build clean; browser-verified multi-load, device counts, season test.
- Known limitations: data-centre flexible compute not modeled; capacity 90 MW is an assumption (a real station limit was NOT added: no verified source, so it stays labelled Modeled); season test uses the deterministic policy unless real-LLM results are cached; LLM run takes ~35 s the first time, then is cached.

### Stage tracker (updated as I build; times are wall clock, deadline Sun 12:00)
| Stage | Scope | Status |
|---|---|---|
| 0 | Commit + remote | DONE: https://github.com/Aaryan-Paiva/waterloo-electric (private until final check), commit 045008f, authored as Aaryan-Paiva |
| 1 | Sandbox API on the existing engine | DONE (156 tests) |
| 2 | Device parameters + fleet size | DONE in reduced form (78 physical models kept; sizes scaled by `fleetSizeX`; behavior overrides). More clusters and data-centre flexibility deferred |
| 3 | Isometric world renderer | DONE (all seasons, night, states) |
| 4 | Drag-and-drop, script player, result | DONE, browser-verified |
| 5 | Device editor drawer | DONE (+ device inspector, "what changed" line) |
| A | Sandbox breadth: editable device counts, multiple loads, visible defaults | DONE |
| B | Experimentation: season test + run history | DONE |
| C | Live experience: streamed owner states, LLM default + cache, asset log, optimizations pane, light clock | DONE |
| D | Credibility + submission | NOT STARTED |
| 6 | Narration + polish | DONE (error/loading states, retry, 30 s request timeout, inspector, change note, projector-size check at 1280x720, pinned default scenario) |
| 7 | Freeze, docs, submit | IN PROGRESS |

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

### 2026-09-27 ~04:40 — Stage 6 (polish) DONE
What changed: backend `deviceDetails` in `/api/sandbox/world` (real per-type totals: clusters, MW, MWh, vehicles, owners, what it does, limits); numbers rounded once so overload, absorbed and remaining add up on screen. Web: `lib/sandboxLogic.ts` (phase, gauge, night, change note as pure tested functions), device Inspector (legend row or click a cluster), "what changed" line after an edit, 30 s request timeout with a plain error and "Try again", loading overlay, API-down screen with retry, bubble text fixed.
Tests: backend +2 (device details, pinned default demo scenario summer 2 pm 20 MW: base 76.4, before 96.4, holds, absorbed 6.4), web +5 (15 total).
Verification: sandbox tests 10 passed, web 15 passed, lint and tsc clean, production build clean; browser: inspector opens, reserve 25% -> 60% changes the result and prints "Absorbs 0.3 MW less than the previous run", layout fits 1280x720 with no clipping, API-down screen shown when the API is stopped.
Next: Stage 7: full backend suite, README (rewritten for the new product), clean-clone check, make the repo public (needs your confirmation), submit.

### 2026-09-27 ~02:45 — Stage A (sandbox breadth) and Stage B (experimentation) DONE
Stage A: `world/generator.py` counts per type (proportional kinds, prefix-stable seeded draws, defaults reproduce the original 20/14/36/8 world exactly); `population.py` variant key includes the counts; `owners/grouping.py` is variant-aware and adapts owner count when devices are few; `projects/loads.py` (housing: homes, evening-shaped, ~1.8 kW/home peak; EV depot: chargers x 19.2 kW, overnight; data centre unchanged) with `ProfileProject`; `SandboxRunRequest.loads` (up to 4 lots); the hidden 3x fleet multiplier is replaced by VISIBLE default counts 60/42/108/24 (= the old 3x world); `POST /api/sandbox/world` returns real totals for an edited configuration. Web: three draggable loads, an always-available dock, "Your loads" list with per-load size and remove, editor with device counts and live MW/MWh totals, isometric drawings of a housing block and an EV depot.
Stage B: `POST /api/sandbox/matrix` (4 seasons, one run each, concurrent, whole-day judgment: hours over capacity before/after, per-hour state strip, morning/afternoon/evening) and web tabs Result / Seasons / Runs (run history with "Load this setup").
Tests: backend +7 (sandbox file 18: counts, owner regroup, housing/depot loads, multi-load, acceptance sentence, matrix x3). Web unchanged (15).
Findings: default world (234 clusters) holds a 20 MW data centre at 2 pm summer (1.5 s run); 4-season test takes ~3 s with the stub; at 20 MW winter and spring show no overload; at 35 MW every season is stressed and summer breaks.
Next: Stage C.

## Stage C DONE
- Real LLM owners are the visible default when a key is configured (`llmAvailable` on the world; otherwise labelled deterministic policy). Owner decisions stream to the UI as each returns (`POST /api/sandbox/run-stream`, NDJSON): "5 of 18 owners have decided".
- Decision cache: identical constraint sets replay instantly (memory + `apps/api/.cache/sandbox`, gitignored); labelled "saved from an earlier identical run". Season test reuses cached LLM runs, otherwise deterministic policy.
- Log tab: per-owner asset log (status, offer, price, dispatched MWh, cost, the owner's own explanation, LLM vs policy) plus optimizer summary (requested/offered/passed physics/dispatched/cost/calls/seconds).
- Light clock: "Play the day" sweeps the real reference day (gauge, day/night, overload state from the run's curve).
- Live check: 18/18 real gpt-5.4-mini owners in 34 s, repeat 0.03 s from cache. Tests: 170 backend passed (4 new), web 15 passed, lint/tsc/build clean.


## Stage D (in progress)
- Incentive slider ($25-200/MWh) so the acceptance scenario (40% enrolled, $75, 1000 homes + 20 MW DC) is runnable; editor panel scrolls.
- LLM owners were making poorly shaped offers (0.0 MW absorbed at the peak hour). Fixed the context, not the physics: each asset now carries `deliverableMwhTotal` (from the physical model), the prompt says to offer only in high-need hours, to copy the validator's envelope when revising, and the request lists `highestNeedHourIndexes`. Validated energy rose ~19 -> ~70 MWh in a 20 MW summer run. Results still vary run to run (real model): e.g. 20 MW summer 2 pm partly holds 5.4/6.4 MW; the acceptance scenario breaks at 40% enrolled and $75. That is a real finding of the sandbox, not a bug.
- `scripts/warm_cache.py` pre-runs 3 demo scenarios with the real LLM so the demo replays instantly.
- Projector check: fits 1280x720 without scroll (stage scales 0.8x); scale is min(width/1440, (height-24)/900).
- Cut: real Waterloo station limit (no verified source; capacity stays labelled Modeled/assumed).

## Stage D: recommendation engine ("Fix it")
- Two verified pathways, both real reruns of the day, never estimates: (1) constraint changes to the flexibility program — enrolment, incentive, min price, device counts, battery reserve, EV shiftable share, building comfort — tried as single levers first, then the strongest levers combined (pairs, then +1 more) if no single change is enough; (2) the smallest zone-capacity increase that holds with the current flexibility, plus how much of that upgrade the flexibility already defers vs. no flexibility at all.
- New: `POST /api/sandbox/recommend`, `capacityMw` override on `/run` and `/matrix` (labelled `user_assumption`, not `modeled`, when set); a "Zone limit" slider in the device editor; a "Fix it" tab with Apply-to-world and Try-this-limit buttons.
- Search always uses the fast deterministic owner policy (not real LLM: 20-30 reruns per search would be too slow/costly), labelled as such; real-LLM owners may behave differently, which is stated in the panel.
- Bug the search surfaced and fixed: a real-LLM owner controlling 42 assets crashed on submit_offer's 40-item cap (schemas/owners.py `SubmitOffer`/`RequestInformation` max_length raised to 200). Caught by the search hammering high device counts, not by manual testing — a good example of why to build this.
- Tests: 175 backend passed (5 new: already-holds no-op, verified pathways, capacity-pathway rerun, capacity override changes result + provenance, the route). Browser-verified: search runs (~35-45s, 20-25 reruns), constraint pathway shown even when insufficient, capacity pathway "Try this limit" applies and reruns correctly labelled as a user assumption.
- Known limits: search runs 20-30 s to a minute; only levers already below their bound are offered; the acceptance-scenario constraint pathway does not fully close the gap in the current search (capacity pathway does, verified).

## Polish pass (post-Stage-D, pre-deploy)
- Graceful failures: every sandbox API route now catches unexpected errors as a plain 500 message (no stack trace to the client), not just ValueErrors.
- Recommend ("Fix it") is now cached to disk like a run, so a rehearsed demo search replays instantly instead of taking up to a minute.
- Full reset: a "reset the whole world" icon is always reachable (top-left brand card), clears every param/provider/incentive/capacity/tab/history/cache-key back to defaults, and cancels any in-flight run cleanly (verified mid-stream in the browser).
- New: a "How to use" overlay (also shown once automatically per browser via localStorage) and a public landing page at `/` (pitch, how it works, data-honesty table, CTA); the sandbox itself moved to `/sandbox`.
- Fixed: the "?"/reset icons were overlapping the tray panel at 1280x720; moved into the brand card.
- Retested: 175 backend, 15 web, lint/tsc/build clean; browser-verified help overlay, reset mid-run, landing page at 1280x720.
- Clean-machine check: fresh `git clone` -> install -> test -> build passed (27 sandbox tests, 15 web tests, clean build) in an isolated worktree.

### Demo cache warmed with real OpenAI owners
- The OpenAI key had zero credits mid-session (`RateLimitError: no credits remaining`, confirmed via `provider_status()` that key/SDK/config were otherwise fine); every owner fell back to the labelled deterministic policy, which is the graceful-failure path working as designed, not a bug. User added credits.
- Cleared the stale disk cache (it was holding `deterministic_stub` results under the same request-hash keys real runs would use) and re-ran `scripts/warm_cache.py`: all 3 demo scenarios now cache with `decisionSource=llm_openai` (0 fallbacks). Restarted the uvicorn process afterward — its in-memory decision cache was still serving pre-credit stub results even after the disk cache was cleared.
- Also warmed `recommend()` ("Fix it") for the two scenarios that break (acceptance scenario, fall 5pm DC): the search always uses the fast deterministic policy internally regardless of the run's provider, so this needed no LLM credits and took ~36s total.
- Verified live via curl against the running API: all 3 run scenarios and both recommend searches now return instantly (`cached: true`) with the correct decision source.
- Note: `.cache/sandbox/` is local and gitignored — it does not travel with a deploy. The Render instance will need its own warm-up run (either via a one-off `warm_cache.py` invocation against it, or by clicking through the demo once after deploy so its own cache fills).
- Remaining for "deploy it": actually creating the Vercel and Render projects, which needs the user's login on both dashboards — prep files (`Dockerfile`, `render.yaml`) already exist from an earlier stage.

### Deployed live
- API on Render (Free tier, manual Web Service, not Blueprint — Blueprints require a card on file): https://waterloo-electric.onrender.com. `OWNER_AGENT_*` + `OPENAI_API_KEY` set via the dashboard's "Add from .env"; health check path `/health`.
- Web on Vercel: https://waterloo-electric.vercel.app, root directory `apps/web`, `NEXT_PUBLIC_API_URL` pointing at the Render URL; `CAPACITYOS_CORS_ORIGINS` set on Render to the Vercel URL.
- Verified end-to-end live: world loads (234 device clusters, `llmAvailable: true`), a live LLM run on the deployed API completes and then replays instantly from Render's own cache (separate from the local machine's warmed cache — a fresh deploy starts with an empty one).
- Free-tier tradeoff accepted deliberately (not Starter): spins down after 15 min idle and loses its filesystem cache on spin-down/restart. Plan for the actual demo: warm the 3 scenarios once right before presenting and keep the tab active during the demo window so it doesn't spin down.

### Three-tab site + redesigned landing page
- Added a global sticky nav (`components/site/Nav.tsx`, in the root layout) with exactly 3 tabs: Home (`/`), Product (`/sandbox`), How it works (new `/how-it-works`) — active-tab highlighted, one line at all widths including mobile.
- Sandbox page's viewport-fit math (`window.innerHeight`-based scale, both `main` blocks) adjusted for the nav's fixed height so the verified 1280x720 projector fit still holds with the nav present.
- Home page (`app/page.tsx`) rewritten for a judge/VC audience: problem/why-now framing, a "why it holds up" 4-pillar section mapped directly to the real architecture (real demand, real agents, real physics validation, real optimizer), a condensed how-it-works teaser linking out, who-it's-for, and an honest "what's next" (real utility pilot) section answering the roadmap question without fabricating traction numbers.
- New `/how-it-works` page: the full 6-step pipeline explanation, the provenance table (moved here from home), "what this is not", and a judge-facing FAQ (real customers? does the LLM control the grid? OpenAI-down behavior? is 90 MW real? does it generalize? what changes for a real pilot?) — all answered from what's actually built, nothing fabricated.
- Verified: lint/tsc/build clean, 15 web tests pass, browser-checked at desktop, 1280x720 projector size, and 375px mobile (nav wraps/overflows fixed with `nowrap` + responsive sizing).
