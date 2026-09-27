# Waterloo Electric — technical build plan

Read with `CLAUDE.md` (engine spec), `PROGRESS.md` (journal). Design reference: the "Waterloo Electric world" canvas (5 screens) and the interactive mockup v3.
Deadline: **Sun Sep 27 12:00** (started 00:06). Public repo, one `main`, demo video ≤ 5 min.

**Product in one line:** a live isometric sandbox of a flexible Waterloo grid. Drag a data centre onto a lot → the zone strains → device clusters rebalance through the physics-checked optimizer while the world narrates it → plain readout. Edit concrete device parameters, change season/time. A testing ground for flexibility programs (VPPs), not a recommender, verdict or report.

## A. Architecture

```
web (Next.js, canvas)                         api (FastAPI)                       engine (existing)
────────────────────────────────────────────  ─────────────────────────────────   ─────────────────────────────
/  SandboxPage                                GET  /api/sandbox/world             world/  population generator
 ├ IsoWorld.tsx     canvas renderer           POST /api/sandbox/run               agents/ battery·EV·building·solar
 │  ├ iso/layout.ts   deterministic scene      (thin: builds a scenario overlay,   owners/ owners·validator·providers
 │  ├ iso/draw.ts     sprites + looks           picks the real window, runs the     optimization/ OR-Tools clearing
 │  └ iso/anim.ts     state-bound effects       agentic pipeline, returns a         capacityos/ coordinator·historical
 ├ Hud (Brand, Gauge, Tray, Conditions,         playback script)                    simulation/ stress-test frame
 │      Caption)
 ├ ScriptPlayer (state machine)  ◄── script JSON (every step comes from the real trace)
 ├ ResultCard · StepsCard · DeviceDrawer
 └ hooks: useSandbox, useDragDrop, useNarration
```

Truth model (always labelled on screen): demand shape = real IESO, derived; devices, owners, capacity = modeled/assumed; data centre = hypothetical; results = derived. LLM output is untrusted; deterministic code owns physics and state.

## B. Contract

`GET /api/sandbox/world` → `{ zone, capacityMw, provenance, devices{count by type}, seasons{ winter|spring|summer|fall: { referenceDay, hourlyBaselineMw[24] } }, defaults: DeviceParams, owners }`

`POST /api/sandbox/run` body `{ season, hour, dcMw, dcFlexShare?, deviceParams?, provider:"stub"|"openai", incentivePerMwh }` → 
`{ conditions{season,hour,dateUsed}, baseMw, loadBeforeMw, capacityMw, overloadMw, hasOverload, script[], dispatchByGroup{battery,ev,building}, absorbedMw, remainingMw, curve{hours,before,after}, outcome:"holds"|"partly_holds"|"breaks"|"no_overload", decisionSource, checksPassed, provenance }`

`script[]` items: `{ i, kind:"request"|"owner_offer"|"owner_decline"|"validation_fail"|"revision"|"accepted"|"clearing"|"dispatch"|"done", ownerId?, ownerName?, group?, text, mw?, price?, loadAfterMw? }` — generated only from the run trace + coordination result.

`DeviceParams`: `{ batteryReservePct, ownersEnrolledPct, minPriceScale, evShiftablePct, evMaxDelayH, buildingOffsetC, buildingMaxHours, reboundPct, dcFlexPct, dcMaxDeferH }`.

## C. Stages (revised 01:15, after the scope freeze)

Scope in one sentence: **test whether a set of flexibility constraints holds against real conditions in each season, with new loads added; LLM operators decide, physics checks, an optimizer coordinates.** Out: Settlers-style hourly LLM loop, recommendations, verdicts, reports, more device types.

### Stage A — Sandbox breadth (01:15–04:30)
1. Editable device counts (batteries, EV fleets, buildings, solar) as REAL modeled clusters; the hidden 3x multiplier is replaced by visible counts (defaults 60/42/108/24 = the old 3x world). Owners regroup automatically.
2. Multiple loads: data centre (MW), housing (homes, evening-shaped), EV depot (chargers, evening/night). Place up to 4; resize and remove each.
3. Reset world; run history (Stage B).
4. Tests: population counts deterministic and prefix-stable, base engine population untouched, multi-load net load adds, sandbox re-pinned.
### Stage B — Experimentation (04:30–06:30)
Season matrix (4 real reference days, per-hour cells from one run each), run history (constraints -> outcome), before/after, easy rerun and compare.
### Stage C — Live experience (DONE)
Streamed owner states, real LLM owners as the visible default (decision cache, stub fallback labelled), asset log + optimizations pane, light live clock.
### Stage D — Credibility and submission (09:00–12:00)
Waterloo station limit (derived, labelled), projector layout, fallback recording, README/PLAN/PROGRESS, public repo (user's OK), video.

Acceptance test the build must pass: "40% battery participation, flexible EV charging, $75/MWh incentive. What happens if this community adds 1,000 homes and a 20 MW data centre?"

## D. Risks and cut lines

| Risk | Cut line |
|---|---|
| Population change shifts pinned numbers / slows runs | Reuse physics; re-pin once; else keep 78 + draw units |
| Renderer eats the schedule | Only what the mockups show; no zoom/pan/3D |
| Winter/spring show no stress at 20 MW | Say so on screen; size dial creates winter stress |
| Data-centre flexibility needs optimizer work | Stretch; "next" label |
| OpenAI limits | Stub default; LLM optional and labelled |
| Repo not public / not on main at 12:00 | Commit early; check a clean clone |

## E. Definition of done
1. Golden loop works end to end. 2. Editing device parameters changes the result. 3. Season and time change the world and the replayed conditions. 4. Provenance visible; nothing claimed beyond a planning sandbox. 5. Tests, lint, types, build pass; README and `PROGRESS.md` current. 6. Public repo, single `main`, demo video linked.
