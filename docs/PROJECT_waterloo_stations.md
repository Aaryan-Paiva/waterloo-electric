# Waterloo World — quick project doc

**One line:** A living map of Waterloo Region's real electricity network where DER agents (batteries, EV fleets, thermostat homes, industrial DR, the data centre itself) decide whether to help, and you play god: drop a data centre on a real station, flip GridCity-style toggles, and see whether it is feasible *and* what it takes.

Builds due **Sun 27 Sep, 12:00**. Demo/pitch **2:00 PM** (QNC, University of Waterloo — the pitch is about the grid under the room). Planner with the full engine spec: [CLAUDE.md](CLAUDE.md).

## Why this, why here, why now (all sourced)
- IESO published the **2026 KWCG Integrated Regional Resource Plan** (report dated 08/07/2026; Waterloo Region, Guelph, Wellington). It says demand is expected to grow rapidly, driven by housing, electrification and **new large loads such as data centres**, with "several requests to connect from potential data centre customers" (§5.2). News reports +133% by 2045 (unverified).
- Hydro One proposed the **Waterloo Wellington Power Line** (~600 MW, ~2032, reported).
- Region already hosts six data centres incl. a 54 MW Cambridge site (reported); the Region is studying data-centre impacts (report expected early 2027, reported).
- IESO itself recommends **distributed energy resources** at Puslinch DS and Kitchener MTS #6 to solve station needs — the exact thing our DER agents simulate.
- National frame: federal strategy says the grid must roughly double (>$1T) and endorses demand-side/planning tools; CER demand +26–85% by 2050 (scenarios, not predictions).

## Real Waterloo data we already hold (`data/`)
| Data | Source | What it gives |
|---|---|---|
| `kwcg_2026_irrp_tables.xlsx` (35 tables, June 2026) | IESO | **Station-level load forecasts 2026–2045** for ~28 Waterloo/Guelph/Cambridge stations (Kitchener MTS #1–9, Waterloo Rush MTS, Scheifele, MTS #3, Galt, Preston, Puslinch, Arlen, Cedar, Campbell, …) in low/reference/high, summer/winter, coincident/non-coincident; CDM and DG assumptions; **hourly (8760) load and capacity-NEED profiles** for Kitchener MTS 6, Puslinch TS (all 20 years), Rush MTS, Kitchener MTS 1/4/7, DxK supply. **These are IESO's modelled planning profiles for future years (weather-normalised forecasts), not meter history — label them "Modeled (IESO planning forecast)", never "Observed".** |
| `kwcg_2026_irrp_report.pdf/.txt` | IESO | Needs table with dates and MW, non-wires screening, recommended plan, data-centre drivers. |
| `ieso_demand_20xx.csv`, `ieso_zonal_current.csv` | IESO | Ontario/zone hourly demand (real weather-year shapes). |

**Derived real station limits — SEASONAL** (summer May–Oct / winter Nov–Apr; median of Load − Need in overload hours; validated: Need ≈ max(0, Load − limit) with 0 mismatching rows for 6 of 7 stations, 0.2% for Kitchener MTS 6): Kitchener MTS 6 = 91.8 / 108.9 MW · Puslinch TS = 41.6 / 48.4 · Rush MTS = 67.5 / 67.5 · Kitchener MTS 1 = 54.0 / 62.1 · Kitchener MTS 4 = 91.8 / 108.0 · Kitchener MTS 7 = 54.9 / 64.8 · DxK supply = 127.0 / 148.0. Label as *derived from IESO profiles*, not published ratings.
**Published ratings found in the IRRP text (better than derived, use these when present):** Rush MTS = two 115/13.8 kV transformers, LTR **68 MW** (matches derived 67.5); Scheifele MTS = four 230/13.8 kV transformers, summer LTR **161 MW**, winter LTR **175 MW**; Waterloo North MTS #3 rating not found in the text extracted (may be in an appendix — check). IESO Table 7 needs (DxV sub-system, Planning Forecast): Scheifele summer need from 2028 (144 MW by 2045), winter from 2029 (185 MW by 2045); Waterloo MTS #3 **immediate** summer need (254 MW by 2045), winter 2028 (243 MW); DxV supply need immediate (574 MW summer by 2045; supply limit ~350 MW). Rush 2045 need profile: peak 51 MW, up to 94 consecutive hours, ~42,000 MWh/yr; IESO screened wind/BESS/solar combinations and found **none feasible** at Rush (need profile + DG connection limits, siting on residential land); its plan is new 230 kV stations in the Waterloo area (2030+) and transferring Rush load (2032). **So the City-of-Waterloo stations are the "needs wires" case; the DER-coverable cases are Kitchener MTS #6 and Puslinch.**
**Real needs (Planning Forecast):** Puslinch TS from 2029, up to 12.5 MW / 733 h a year by 2043; Kitchener MTS 6 from 2034, up to ~11.8 MW / ≤97 h; Rush MTS 2045 peak need 51.5 MW / 2,920 h; K-MTS 4 47 MW / 2,821 h; K-MTS 1 43 MW / 2,330 h; DxK 90 MW / 3,854 h; K-MTS 7 32 MW / 3,101 h; Wolverton DS 17 MW (summer) immediately.

**Insight the demo can prove:** small, short needs (Puslinch, Kitchener MTS 6) are coverable by DER agents — matches IESO's recommendation — while big, long needs (Rush, K-MTS 1/4/7, DxK) are not, and need wires. Our tool shows that boundary and where a data centre changes it.

## The world
- **Map** of Waterloo Region: real station names on a stylised map (positions illustrative — no public coordinates used), coloured by headroom/need for the chosen year, season and forecast case.
- **Station panel:** real hourly load, derived limit, IESO's own need profile, and what our agents change.
- Rest of region without profiles uses the IESO station forecast scaled to a labelled shape.

## Actors
Data-centre developer · Station/grid operator (limit, rules) · **DER cohorts as agents** (asset operator, battery owners, industrial DR, EV fleets, thermostat homes): each weighs an incentive against its own threshold and fatigue, opts in/out; a deterministic solver dispatches and the same overload check validates (agents propose, physics validates).

## Toggles (GridCity-style)
Place data centre on a station (click) · MW slider · year 2026–2045 (IESO forecast) · season summer/winter · forecast Low/Ref/High · CDM/DG on/off · cohort switches + incentive · notice/curtailment-hour caps · station derate / outage · policy (BC-style 10% curtailable) · overlay: headroom vs need · **Replay the year** · **A/B two worlds**, same seed.

## Verdicts
✅ Firm fits · ⚠ Feasible with flexibility (MW, hours/yr, notice) · ❌ Needs wires (residual MW/hours) — planning-level, never "approved".

## World packs (select an area) — engine is geography-agnostic
The engine takes a `WorldPack` (JSON): `{ id, name, tier, load: {source, provenance, series}, capacity: {value|seasonal, provenance}, derAssumptions, weather/profile notes }`. Nothing in the engine knows the place. Packs we can build **from data already in hand** (verified 2026-09-26):
| Tier | Pack | Load data | Capacity | Provenance |
|---|---|---|---|---|
| A (headline) | **Waterloo Region stations** (7 with hourly profiles, 21 more forecast-only) | IESO KWCG IRRP 2026 planning profiles | Seasonal limits derived from IESO need profiles | Modeled (IESO) / Derived |
| B | **10 Ontario IESO zones** (Northwest, Northeast, Ottawa, East, Toronto, Essa, Bruce, Southwest, Niagara, West) | IESO hourly zonal demand **2021–2024, observed** (`ieso_zonal_20xx.csv`) | **None published** → user assumption (default observed peak × (1+headroom)) | Observed load / Hypothetical capacity |
| C (stretch) | Ontario, Quebec (2019–24), BC (2025), Alberta (area-metered shape) | Observed hourly, see CLAUDE.md §4 | Assumption | Observed / Hypothetical |
Only KWCG publishes a data-tables spreadsheet with hourly station profiles; other Ontario regional plans (e.g. Windsor-Essex 2025, London 2017) are PDFs. So station-level realism = Waterloo only. DER population per pack comes from templates (urban / industrial / mixed) — always **Hypothetical**.

## Areas, DER constraints, project types (spec)
**Areas.** A1 (hourly + derived limits): Kitchener MTS #6, Puslinch (TS/DS), Waterloo Rush MTS, Kitchener MTS #1, #4, #7, DxK supply. A2 (forecast-only, 21 stations; hourly shape borrowed from IESO Southwest-zone observed load scaled to the forecast peak; limit = user assumption → *Hypothetical*): Arlen MTS, Campbell TS (T1/T2, T3/T4), Cedar TS (T1/T2, T7/T8), Elmira TS, GrandBridge Energy MTS1/MTS2, Fergus TS, Galt TS, Hanlon TS, Kitchener MTS #3/#5/#8/#9, Preston TS, Waterloo Scheifele MTS, Waterloo MTS #3, Wolverton DS, CTS 1/2. B: 10 Ontario IESO zones (observed 2021–24; capacity = assumption). C (stretch): Ontario, Quebec, BC, Alberta shape.

**DER constraints (all editable per agent or per population).**
- *Battery:* MW, MWh, round-trip efficiency, min/max SoC, starting SoC, reserve %, max cycles/day, availability window, notice, participation.
- *EV fleet (depot / commuter / residential):* vehicles, charger kW, energy per vehicle/day, plug-in window, departure deadline + required SoC, max shift hours, V2G on/off (default off), participation %, override/opt-out rate.
- *Solar:* MWp, hourly profile by season/weather, inverter limit, curtailable yes/no.
- *Flexible building / heat pump:* baseline kW, max shed kW, max shed duration, pre-conditioning window, rebound %, comfort band, notice, participation.
- *Industrial DR:* max shed MW, max hours/event, max events/yr, notice, min run time, rebound, penalty/cost.
- *Data-centre flexible compute (part of the project):* flexible share, max deferral hours, deadline, rebound.
- *Backup generator (stretch):* MW, run-hours cap, notice.
- *Program-wide:* incentive level, notice, event-duration cap, events/yr cap, curtailment-hours cap, opt-out fatigue.

**Project types and what is editable** (common to all: name, station, start year, phase-in schedule, size, hourly shape, flexibility %, notice/duration limits, on-site battery/solar):
- *Data centre:* peak MW, load factor/shape, ramp rate, flexible share, max deferral h, deadline, backup gen, phase-in.
- *Housing development:* homes, peak kW/home, heating type (gas / heat pump / resistive), EV adoption %, rooftop solar %, diversity factor, phase-in.
- *EV charging depot:* chargers, kW each, vehicles, arrival/departure windows, energy/day, managed-charging %, on-site battery/solar.
- *Factory / industrial:* peak MW, shifts (1/2/3), weekend ops, ramp, process flexibility %, max curtailment duration, seasonal factor.

**Stacking.** World state = baseline + ordered projects + DER changes (applied recommendations) + settings; every run simulates *all of it together* so shared DERs are allocated by the optimizer across projects. Flow: add project A → stress test → apply recommendation (a change, not a hack) → add project B → re-stress the combined world (old recommendations may no longer suffice; recompute). Report incremental attribution (B on top of A+fix) and combined. Scenario branches: Baseline · +A · +A+fix · +A+fix+B. Undo/redo via change log.

## Feature triage (user's full CapacityOS list → what actually ships)
Core loop (unchanged): **world → add project → stress test → detect failures → DER agents respond → optimizer coordinates → feasibility → bottlenecks → recommend → apply → rerun → report.**

| Ships (must) | Notes |
|---|---|
| World from real Waterloo station data | Replaces "synthetic world". Per-station seasonal limits are derived from IESO profiles. |
| Multi-hour stress test | ~35k planning hours (7 stations × sampled years). It is a *planning-profile* stress test, not observed history — say so. |
| Place/edit project | data centre, housing, EV depot, factory; size, shape, flexibility, hours, ramp |
| ~40–60 DER agents with individual state, participation %, live offers/declines, activity feed | Batteries, EV fleets, flexible buildings, industrial DR, solar; not thousands |
| Event detection + optimizer + battery dispatch + load-shift visual | Optimizer (not the LLM) produces every number |
| Feasibility: Feasible as-is / with flexibility / Not feasible + **capacity-feasibility %** | Never call it "reliability" |
| Bottleneck analysis (season, window, frequency, worst deficit) | |
| Counterfactual recommendations, **validated by rerun**, + minimum-flexibility solve | Bisection reruns of the same engine (`34 h → 0`) |
| Before/after chart, event replay, provenance labels (Observed / Modeled / Hypothetical), assumption inspector | Provenance is non-negotiable |
| Scenario branches + side-by-side compare, saved scenarios (localStorage), printable planning report | Print-to-PDF page, no backend |

| If time | Cut / later |
|---|---|
| Natural-language project creation + AI commands (LLM → schema; regex fallback), AI explanation of results, ElevenLabs voice briefing, simple solar profile | Microgrids, generators as agents, heat-pump thermal detail beyond one cohort, share links/backend, connected multi-station power flow, real map coordinates |

Infrastructure fallback = residual constrained hours after all flexibility → label "additional physical capacity required" (cheap; ship it).
Note: the pasted list said "historical" demand — station profiles are IESO's modelled planning years; observed history exists only at Ontario/zone level (IESO zonal, 2021–2024).

## Build order (≈17 h left; keep it runnable)
1. Data script → `public/data/waterloo.json` (stations, forecasts, 7 need profiles, derived limits, provenance) — 1.5 h
2. Engine + tests (feasibility, optimizer, cohorts) on Kitchener MTS 6 / Puslinch — 3 h
3. Map + station panel + verdict + replay — 4 h
4. Data-centre placement + toggles + A/B — 2.5 h
5. Cohort agents + delivery scene — 2 h
6. ElevenLabs voice briefing, README, video, polish — 2.5 h. Freeze features 2 h before deadline.

## Guardrails
Every number from data or a labelled assumption · no fake topology claims · IESO forecasts are IESO's, not ours · flexibility params are sourced-range assumptions · cohort behaviour deterministic/seeded, LLM only narrates · works with no API key.

## Patterns we reuse from Settlers of Solana (`Downloads/agent-economy-main`, read 2026-09-26)
- **Brain interface** (`backend/src/brains/`): every agent acts through one `decide(agent, tools)` call; brains are swappable (`stub` free heuristic, `openai`, `baseten`) via `BRAIN=` env. We copy this: **stub cohort brain first** (no API key), LLM brain optional, identical tools.
- **Tools are the only action surface** (`tools.mjs`): typed JSON-schema tools with a short `reason`; tool descriptions are rebuilt from live config so what agents are told equals what the sim does. Ours: `enrol(mw, price, notice)`, `opt_out(reason)`, `set_reserve(mw)`, `respond_to_event(mw)`.
- **Dials system** (`tunables.mjs`): one declarative list (key path, group, min/max/step, `live`, `help`, `say`) drives both the control panel and agent announcements ("the fishing has changed…") — plain facts, never advice; a `REV` counter memoizes prompts. **This is our GridCity toggle panel** (station derate, incentive, notice, curtailment cap, forecast case…).
- **Round loop** (`world.mjs round()`): all agents decide at once; round closes at 90% answered or 8 s; per-model concurrency gates, retry-after handling, per-model token/cost stats. Ours: event rounds.
- **Seeded RNG** for a reproducible world; **authoritative settlement** the agents cannot edit (their chain ↔ our overload validator).
- **Info-design lesson** (their write-up): agents anchor on what they are shown; show forecast overload, event counts, own payback — not just a price.
- **Not reused:** Anchor/Rust chain, 3D island (`island3d.js`, 1,462 lines). Admin `Swarm.js` (per-agent log drawer) is a good UI model.

## Open items / risks
- Station coordinates not public → stylised layout (say so).
- Only 7 stations have hourly profiles; others use scaled shapes.
- Data-centre load on Waterloo MTS#3 jump (≈82→260 MW by 2030) is in IESO's forecast; cause not verified — do not claim it is a data centre.
- Hydro One line, +133%, six data centres: from news search, verify before quoting.
- ElevenLabs coupon via Discord bot needed; reference repo for the agent-economy format is in `Downloads/agent-economy-main` (not inspected yet).
