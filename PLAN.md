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

## C. Stages (what exactly gets built)

### Stage 1 — Sandbox API on the existing engine (target 00:15–02:30)
- `schemas/sandbox.py`: request/response models, `DeviceParams`, script item.
- `capacityos/sandbox.py`:
  - `pick_reference_day(season)`: the real day with the highest net load in that season (2021–25), fixed and cached.
  - `run_sandbox(req)`: temp `Scenario` with a data-centre project of `dcMw` (never stored, baseline untouched) → find the event window containing/nearest `hour` that day → `run_agentic(provider)` → `build_script(run)` → outcome label (`holds` = no violation left; `partly_holds`; `breaks` = < 25% absorbed) → curve for the day.
  - Owner-level params applied now: `ownersEnrolledPct` (deterministic subset by seeded draw), `minPriceScale` (scales owner reservation prices).
  - No-overload path returns `no_overload` with the load shown (e.g. winter at 20 MW).
- `api/sandbox.py` routes; register in `main.py`.
- Tests: deterministic script; golden summer 20 MW; no-overload path; params change the outcome; baseline immutable; stub default, openai fallback label.
- **Done when:** `curl POST /api/sandbox/run` returns a full script and outcome in < ~3 s.

### Stage 2 — More devices + device parameters (02:30–04:30)
- `world/generator.py`: add home-scale clusters by reusing existing classes (home batteries = battery kind `residential`; home EV charging = EV `residential_managed`; home thermostat clusters = building kind `residential`; more solar). Target ~230 devices, seeded. Owner grouping extended (≤ 25 owners).
- Parameter overrides plumbed into generation/state: battery reserve → `min_soc`; EV shiftable share + longest delay; building offset → `shed_fraction`, max curtail hours, rebound. Population cached per parameter tuple.
- Re-pin measured numbers in tests/docs (population changed). Manual mode still works.
- Data-centre flexible share (optional): deferrable-load variable in `optimization/model.py` (like EV defer/recover). **Cut first** if late: slider shown as "next".
- **Cut line:** if not done by 04:30, keep 78 devices and render fleet units as labelled "units in this fleet".

### Stage 3 — Isometric world (04:30–07:00)
- `iso/layout.ts`: deterministic tile grid (14×14): roads, districts (homes NW, downtown + university NE, depot SW, industry SE, empty lots), device anchors (batteries, chargers, buildings, solar roofs), lot rectangles for drop targets; each anchor carries a device-group id.
- `iso/draw.ts`: painter's-algorithm sprites (houses with gable roofs and solar, towers, depot, battery containers, chargers, cars, warehouse, chimney, substation, power lines with flow dots, data centre) and looks: season palette (summer/spring/fall/winter with snow) and time-of-day tint (night, dusk, lit windows, streetlights).
- `iso/anim.ts`: state-bound effects only — battery glow/rise when its group dispatches, chargers amber when paused, building dim, line colour/thickness from load vs capacity, data-centre glow, car density by hour.
- Hud components matching the mockups: Brand + provenance chips, Gauge, Tray, Conditions strip (season buttons + 24 h strip), Caption bar.
- **Done when:** all four seasons and day/night render at ~60 fps with correct provenance labels.

### Stage 4 — Interaction and the rebalance (07:00–09:00)
- `useDragDrop`: pointer drag from the tray, highlighted lots, snap to a free 2×2 lot, building "rises", triggers `POST /api/sandbox/run`.
- `ScriptPlayer`: timed state machine over `script[]` → captions, owner speech bubbles anchored to real anchors, physical-check callout for `validation_fail`/`revision`, steps card, gauge falling per `loadAfterMw`.
- `ResultCard`: absorbed vs overload, breakdown by group, before/after day curve, outcome chip, actions (edit devices, try winter night, reset).
- Conditions strip re-runs the conditions; `no_overload` handled with clear copy.
- **Done when:** open → drag → strain → narrated rebalance → readout works end to end on the golden scenario.

### Stage 5 — Device editor (09:00–10:00)
- `DeviceDrawer`: concrete controls bound to `deviceParams` (batteries: reserve, enrolled, min price; EV: movable share, longest delay; buildings/homes: offset, longest curtailment, rebound; data centre: size, flexible share, longest deferral), debounced re-run, "what changed" delta vs previous run.
- Click a cluster → inspector (type, size, owner, state, limits).
- **Done when:** edit → drop again → visibly different result.

### Stage 6 — Narration and polish (10:00–11:00)
- `useNarration`: browser speech synthesis (silent by default toggle); ElevenLabs only if time.
- "Real LLM owners" toggle (OpenAI; `decisionSource` shown; stub stays default and fallback).
- Loading/empty/error states, reduced-motion, keyboard access for the tray, 1280–1440 layout.

### Stage 7 — Freeze and submit (11:00–12:00)
- Backend tests, web tests, lint, `tsc`, production build; README, `PROGRESS.md`; clean-clone run check.
- Commit, single `main`, push, make the repo public (user's confirmation), submit on DevPost with the video.

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
