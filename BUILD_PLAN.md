# CapacityOS — Build Plan

## Goal

Deliver one polished end-to-end hackathon flow:

**Waterloo Demo Zone → add 20 MW data centre → stress-test historical conditions → watch DER agents coordinate → inspect residual bottleneck → apply simulation-backed recommendation → rerun → generate report.**

## Build order

### 1. Bootstrap
- Next.js frontend
- FastAPI backend
- shared types/contracts
- deterministic demo fixture
- Waterloo world pack

### 2. Baseline
- ingest/normalize hourly load
- capacity assumption
- time-series chart
- playback controls
- provenance labels

### 3. Project insertion
- data-centre model
- add/edit/remove project
- projected load
- capacity-event detection

### 4. Synthetic agents
- battery agents
- EV fleet agents
- building agents
- solar agents
- deterministic generator with seed
- participation controls

### 5. Single-event coordination (DONE, Phase 4)
- OR-Tools dispatch for one event window over enrolled physical DERs
- independent physical-constraint validator, before/after, per-agent dispatch

### 5b. Agentic DER decision layer (Phase 5-6, DONE)
- owner/operator agents (15-25, deterministic grouping of the physical DERs)
- typed tools: submit_offer / decline_offer / revise_offer / request_information
- provider abstraction: deterministic stub (default) + OpenAI (structured tool calling)
- physical offer validation + one bounded revision
- OR-Tools clearing from validated offers (price as a lower-priority objective)
- Manual vs Agentic mode, incentive input, run store / replay / trace, live owner feed UI

### 6. Historical coordination (Phase 7, DONE)
- every capacity-event window 2021-2025, chronological, joint simulation of adjacent events, carried battery/building state
- deterministic owner policy (0 LLM calls), user-selected incentive scenarios, aggregates by year/season/DER type/severity
- (bottleneck clustering / project feasibility verdict come in Phase 8-9)

### 7. Project-level feasibility (Phase 8)

### 8. Counterfactual recommendations (Phase 9)
- parameter-sweep/counterfactual trials incl. modeled compensation level
- minimum sufficient flexibility search, Apply recommendation, verification rerun

### 9. Natural-language planning assistant (Phase 10)
- natural-language project creation, result-grounded explanations, world-edit commands

### 10. Reports, export, polish (Phase 11)
- report model, HTML preview, PDF export
- living-world animation, scenario branching/compare, deterministic reset, demo script

Roadmap: Phase 0-7 DONE (5 owner/operator agents · 6 request/offer/market · 7 historical coordination) · 8 project feasibility · 9 recommendations · 10 NL assistant · 11 reports & polish.

## Golden demo acceptance test

1. Reset demo.
2. Waterloo world loads.
3. Add 20 MW data centre.
4. Stress test returns nonzero violations.
5. Open representative event.
6. Agent offers/declines stream in.
7. Optimizer dispatch changes net load.
8. Some residual events remain.
9. Recommendation engine returns at least two validated pathways.
10. Applying one pathway yields zero residual violations in the golden fixture.
11. Generate report.

If this flow breaks, stop adding features and fix it.
