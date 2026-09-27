# CapacityOS — project planner (AF Hacks: Growing Canada)

Source of truth for what we build, why, and in what order. Read before planning or editing. Keep it updated when decisions change. Build a working demo, not a perfect spec.

> **PIVOT (2026-09-26 evening): "Waterloo World."** The user chose GridCity-style toggles on a **Waterloo-only world built on real data**, with DER cohort agents. See [PROJECT.md](PROJECT.md). Key discovery: IESO's **2026 KWCG IRRP Data Tables** (`data/kwcg_2026_irrp_tables.xlsx`) contain real station-level load forecasts 2026–2045 and real hourly capacity-**need** profiles for Kitchener MTS 6, Puslinch TS, Rush MTS, Kitchener MTS 1/4/7 and DxK supply, from which real station limits are derived (median Load−Need). This replaces the "capacity limit is an assumption" caveat **for Waterloo stations** (still an assumption elsewhere). Everything below about the engine, cohorts, honesty rules and demo structure still applies; the national/Ontario/Alberta material becomes context and stretch. Ontario/Alberta/BC/Quebec real-data notes below remain valid if we widen scope.

Working name: **CapacityOS** (pitch line: "GridUnlock"). Deadline: builds submitted **Sun Sep 27, 12:00 PM**; demo + pitch to judges **2:00 PM** (5-minute demo video + public GitHub repo, single main branch).

## 1. What we are building (one paragraph)

A **flexibility feasibility simulator on real Canadian grid data.** A planner picks a region, adds a new load (data centre, EV fleet, housing, factory), and CapacityOS replays a **real year of hourly demand** with that load added. It answers: *can the existing grid host it firm, can it host it if the load is flexible (and exactly how many MW, in which hours, how many hours a year), or does it need new build?* A second scene shows the flexible resources being dispatched in an overload event and delivery being verified. A national view shows the same question across regions and CER growth scenarios, and what remains as the **build gap**.

It is a planning tool. It is not a grid controller, not a connection approval, and not a forecaster.

## 2. Problem and why it is not already solved

- Canada expects electricity demand to grow **26%–85% (2023→2050)** across the CER's four scenarios (CER Energy Future 2026, Exec Summary). The federal strategy says the system must **at least double**, at **over $1 trillion** (NRCan, *Powering Canada Strong*, §2.1). Building takes a decade+.
- Idle capacity exists outside peak hours. Real data: Ontario 2024 average demand was 67% of peak; Alberta area-metered load factor 0.78 (see §4). Flexible load can use that room.
- NRCan §3.5 explicitly endorses demand response / DERs / planning tools ("curb peak loads, defer expensive new generation") and cites Hydro-Québec: $10B of efficiency was ~3x cheaper than new supply. NRCan §4 is **seeking input** on planning tools, data sharing and regional grid modelling (electricity-electricite@nrcan-rncan.gc.ca) — our concrete "next step".
- The data-centre queue is the sharpest pressure: McCord tracker (as of 2026-09-23) shows **13.8 GW announced vs ~449 MW operating**; Alberta 21.5 GW filed vs a 1,200 MW interim limit (fully allocated); BC 400 MW cap with a 10% curtailability / 24h-notice requirement. NRCan footnote 11 puts AI data-centre demand at 3–5 GW by 2030. (Different sources; frame as "consistent with much of the queue being speculative".)

**What exists (be ready to say so):**
- Utility capacity maps (Toronto Hydro, Alectra, Hydro One, OEB Centralized Capacity Information Map): **firm** headroom only, updated quarterly, no flexibility view.
- Flexible-interconnection software: Camus FlexConnect, GridCARE — US, US utility customers found (no Canadian customer found; not proven none).
- Flexibility supply/dispatch: EnergyHub (IESO Peak Perks VPP, reported 100k+ homes / up to ~90 MW), ecobee (~215 MW Canadian potential reported), Edgecom (IESO-approved aggregator). Big vendors: Siemens, GE Vernova, ETAP, Strata Grid (used in Canada).
- Emerald AI ($150M, US) — flexible data centres.
- **Gap we claim (from ~10 searches, not proof):** no open, cross-Canada tool that answers "is this new load feasible *if flexible*, and how much flexibility is needed" on public data. Say "we did not find one", never "none exists".

**Differentiation:** the question (feasibility-through-flexibility, not device control), the buyer (planners, ministries, developers without an engineering-study budget), open public data, minutes not months, cross-province, Canadian-built. Weak spots to admit: utilities/IESO have internal forecasts; ours is planning-level and cannot beat an engineering study; a vendor could add this feature.

## 3. Scope

### Must ship (MVP) — must work with no API key and offline
1. **Real-data region engine** — Ontario (IESO) and Alberta (AESO), full-year hourly replay.
2. **Add-a-load flow** — type (data centre / EV fleet / housing / factory), size (MW), flexibility profile.
3. **Feasibility verdict** — Firm ✅ / Feasible with flexibility ⚠ (with the exact requirement) / Needs new build ❌, computed from the data.
4. **The hero visual — "Replay the real year":** animate the year (or load-duration curve) with the new load added; overload hours flash red against the capacity line; toggle flexibility and watch them clear. Before/after numbers computed live.
5. **Sensitivity** — flexible-share slider and capacity-headroom slider; verdict and requirement update. Flexibility share is the weakest assumption; always show how the answer moves with it.
6. **Delivery scene** — an overload event; flexible resources respond; delivered vs promised, verified against a declared baseline; reliability score. Deterministic, seeded.
7. **Honest labelling** — every assumption visible; "planning-level estimate" banner; sources panel.

### Should ship
8. **National view** — Canada map, region tiles coloured by computed verdict/headroom; regions without real data use a labelled modelled shape (badge: *real data* / *modelled shape*).
9. **Growth scenarios** — CER four scenarios applied as a growth factor to the load shape (labelled "if demand grows by X", never "in 2040 it will be"). Default to near-term framing; 2050 is a labelled stretch.
10. **Build-gap view** — what remains at max realistic flexibility, with **sourced option cards** (interties, nuclear/SMR, storage) from the NRCan document. No invented costs.
11. **ElevenLabs voice briefing** — reads out the verdict and recommendation (sponsor prize: "Best Project Built with ElevenLabs").

### Sandbox framing ("play god") — layered on the same engine
The product is presented as a sandbox on a **real-data world**, but built in layers so the core never depends on the fancy part:
- **Layer 1 (must): the world.** Real regional baseline + heavy asset + flexible assets + optimizer + verdict + hero replay (= CapacityOS above).
- **Layer 2 (should): god-mode dials** that perturb the *real* baseline deterministically (labelled approximations): replay a real historical peak (e.g., Ontario 2024-06-19, Alberta 2024-01-11 cold snap, Quebec 2023-02-03), heat-wave / cold-snap load multiplier on chosen days, large generator or intertie outage (capacity limit −X MW, e.g. Pickering shutdown scenario), data-centre rush (add N heavy assets), EV/heat-pump adoption jump, policy dials (BC-style 10%-curtailable-on-24h requirement; curtailment-hours cap; incentive level).
- **Layer 3 (committed by the user, built after Layers 1–2 are demo-ready): cohort agents decide whether to enrol / opt out.** Prototype validated in the scratchpad and in the visual mockup: each cohort (asset operator, battery owners, industrial DR, EV fleets, thermostat households) has an incentive threshold and slope; `enrol = logistic((incentive − thr)/s) × (1 − fatigue × min(1, eventDays/30))`, so opt-outs rise when event days pile up. Enrolment scales each cohort's MW (asset flexible share, battery fleet, DR MW). Deterministic and seeded, no LLM needed; an LLM may later *narrate* or generate cohort personalities within schema, but the optimizer still does all dispatch and every number. Tested behaviour on real Ontario 2024 (limit 24,000 MW, 1,000 MW flat asset): incentive 0 → 12 of 14 overload hours remain; ~45 → 0 remain; firm headroom only ~148 MW vs ~2,000 MW with cohorts enrolled at incentive 60.
Two-world **A/B compare** (same seed, one dial changed) is the payoff feature of Layer 2.

### Stretch (only after MVP is demo-ready)
12. Voice *control* (ElevenLabs agent with client tools that set the scenario) — buttons remain the fallback.
13. Agent-swarm behaviour layer (archetype cohorts deciding enrolment/opt-out) — deterministic solver still does dispatch; LLMs never control dispatch or invent numbers.
14. BC / Quebec real data if hourly downloads are confirmed. Winter-peak case study.

### Explicitly out of scope
Blockchain/ledger, synthetic power-flow network, N-1 contingency studies, real device control, real connection approvals, cost-optimal capacity-expansion modelling, allocation/ranking of who gets capacity (one pitch slide only), forecasting.

## 4. Data (verified 2026-09-26; files in `data/`)

| Dataset | File | Status |
|---|---|---|
| IESO Ontario hourly demand 2024 | `data/ieso_demand_2024.csv` (+ 2021–2023 also downloaded) | ✅ Clean. 366 days × 24 h = 8,784 rows, hours 1–24, no nulls, no duplicates, no zeros. Ontario Demand min/mean/max = 11,158 / 15,986 / 23,852 MW; peak 2024-06-19 hour 17; load factor 0.67. Summer peak 23,852 vs winter peak 20,929 (Ontario is currently summer-peaking). 16 rows have Ontario Demand slightly > Market Demand (max 114 MW, <1%) — harmless; use **Ontario Demand**. |
| AESO hourly load by area/region, Nov 2023–Dec 2024 | `data/aeso_hourly_2023_2024.xlsx` | ⚠ Usable **for load shape only**. 10,248 hourly rows, no gaps/nulls/negatives, MST timestamps. **Trap:** 42 area columns + 6 region columns are the *same load twice* (areas-only sum = regions-only sum). Never sum all columns. Correct total: mean 6,915 / peak 8,869 MW (2024-01-11 17:00), load factor 0.78. This is **not full Alberta Internal Load** (AIL peaks near ~12 GW, from memory — verify); it is metered area load, so use the normalized shape and scale to a stated system peak, and label it. AESO says the file will not be updated. |
| CER Energy Future 2026 | `https://www.cer-rec.gc.ca/open/energy/energyfutures2026/<file>.csv` (Open Gov dataset `07c42deb-…`) → `data/cer_*.csv` | ✅ Verified. Columns `Scenario, Region, Variable, Year, Value, Sector`. **Provincial + territorial + Canada**, 4 scenarios (Current Measures, Higher Scenario, Lower Scenario, Canada Net-zero), 2005–2050. Use `end-use-demand-2026.csv` with `Variable=Electricity`, `Sector=Total End-Use` (values in **PJ**; Canada 2024 = 2,050.7 PJ ≈ 570 TWh, sanity-checked). Growth 2024→2035 / 2024→2050, Canada: Lower +10/+25%, Current +16/+43%, Higher +25/+72%, Net-zero +26/+83%. Provinces (Current Measures 2024→2035/2050): ON +21/+58%, AB +23/+64%, BC +37/+73%, QC +7/+22%, SK +16/+43%, MB +5/+20%. Also `electricity-generation/capacity/interchange-2026.csv` (build-gap context). Note EV standard repeal (Feb 2026) postdates the modelling. |
| BC Hydro balancing-authority hourly load | `.../balancing_authority_load_data/Historical Transmission Data/BalancingAuthorityLoad 2025.xls` (also 2001–2026; "Current" file is month-to-date only) → `data/bc_2025.xls` | ✅ Verified 2025: 8,760 hourly rows (HE 1–24, 365 days), no nulls. Min/mean/max 5,359 / 7,682 / 11,359 MW; peak 2025-02-03 HE18 (winter); load factor 0.68. XLS: header rows above data; find the row where col 0 == "Date". Needs `xlrd`. |
| Hydro-Québec hourly demand | `https://donnees.hydroquebec.com/api/explore/v2.1/catalog/datasets/historique-demande-electricite-quebec/exports/csv` → `data/hq_demand.csv` | ✅ Verified, 2019-01-01 → 2025-01-01 (UTC timestamps), cols `date, moyenne_mw`. 52,608 rows; **45 null MW, 7 duplicate timestamps (DST) — dedupe/interpolate.** Peak 42,473 MW (2023-02-03), 2024 peak 36,348; mean ~21.6 GW; **load factor ~0.51 (strongly winter-peaking = lots of idle capacity)**. HQ says open data is informational, not official. A separate 15-minute "current demand" dataset exists (untested). |
| Nova Scotia Power OASIS | nspower.ca/oasis "Hourly Total Net Nova Scotia Load" | ⚠ Exists; monthly reports were disrupted by the April 2025 cyber incident. Not downloaded → modelled shape unless verified. |
| SaskPower, Manitoba Hydro, NB Power, NL, territories | — | ❌ No public hourly file found in searches → **modelled shape, clearly badged**. (Do not claim real data.) |
| IESO current-year hourly | `https://reports-public.ieso.ca/public/Demand/PUB_Demand.csv` → `data/ieso_demand_current.csv` | ✅ Live-ish: 2026 YTD, refreshed about daily. Use rolling last-12-months baseline. **No CORS headers seen** → fetch server-side / at build time; ship a cached snapshot with a live/cached badge. |
| **Live data summary (status panel only, never verdicts)** | — | **IESO** 5-min totals ✅ and hourly file refreshed ~daily ✅. **Hydro-Québec** 15-min live demand ✅ (`.../datasets/demande-electricite-quebec/records`, filter `valeurs_demandetotal is not null`, order `date desc`; latest ~17.5 GW at test time; newest rows are null, so always filter). **AESO** live = Current Supply Demand API on the AESO API portal (`developer-apim.aeso.ca`, Azure APIM): **needs a free key the user must register for themselves** (I cannot create accounts); until then Alberta is historical-shape only. **BC Hydro** "Current" file = previous-day hourly (updated daily, Mondays cover Fri–Sun) → *near-real-time*, not live. Saskatchewan/Manitoba/NB/NL/territories: no live source found. Live panel must show source + timestamp + "live/cached" badge per region. |
| IESO real-time totals | `.../public/RealtimeTotals/PUB_RealtimeTotals.csv` | ✅ 5-minute system totals (a market total incl. exports — do not mix with Ontario Demand). Status-panel only, never used for verdicts. |
| Data-centre queue | AESO project list; McCord Investments tracker (secondary source, cite as such) | Manual snapshot into a JSON fixture. |

Notes: IESO "Ontario Demand" is grid-supplied demand (I understand it excludes embedded generation — verify before claiming). DST is not an issue in either file (IESO uses hour-ending 1–24; AESO uses MST).

**Capacity limit is an input, not a fact.** No public source gives real substation/feeder/regional firm capacity. Default: `firmCapacity = observedAnnualPeak × (1 + headroom)` with headroom default 10% (slider, clearly labelled "assumption — a utility supplies the real value"). Never present the verdict as more than planning-level.

**There is no public asset-level dataset of Canadian flexible fleets.** Flexible assets are **parameterized archetypes with sourced defaults** (all editable, all labelled "assumption"):
- **Batteries** — real specs exist: Oneida 250 MW / 1,000 MWh (operating, Haldimand ON; 20-yr IESO capacity contract); Hagersville 300 MW / 1,200 MWh; Tilbury 80 MW / 320 MWh; IESO LT1 1,784 MW across 10 facilities, E-LT1 ~882 MW, LT2 640 MW (8-hour). Use 4 h duration default, round-trip efficiency an assumption (~85–90%).
- **Value of flexibility** — IESO 2025 Capacity Auction (news release, ieso.ca): 1,833 MW summer 2026 / 1,125 MW winter 2026–27 procured; cleared ~$170,000/MW-yr (secondary sources Voltus/Edgecom; demand response cited ~$171,319/MW-yr — verify against IESO before quoting). Use as an *indicative* $/MW-yr for "value of the MW unlocked", labelled.
- **Thermostats/residential DR** — Peak Perks reported 100k homes / up to ~90 MW (~0.9 kW/home, derived); ecobee reports ~215 MW Canadian potential (vendor claim).
- **EV charging** — StatCan Table 20-10-0025-01 (new ZEV registrations by province; ZEVs were 9.5% of new registrations in 2025, down from 14.6%); studies report unmanaged home charging amplifies household evening peak (~39% max in one study) and vehicles stay plugged in ~12 h on average, so charging is highly shiftable (cite study, treat as assumption). ChargeTO (Toronto) piloted incentive-based charge shifting.
- **Data-centre flexibility** — Duke (US) curtailment ranges; BC rule 10% curtailable on 24 h notice; Emerald AI field demo (Phoenix, arXiv 2507.00909; verify figures before quoting).
- **Heavy industrial presets** (steel, smelter, electrolyser, mine) — no public hourly profiles; use stylized shapes with stated basis.

**Flexibility parameters are assumptions with sources:** data-centre curtailment ranges (Duke *Rethinking Load Growth*: US, 76–126 GW at 0.25–1% curtailment; note critiques of its over-application), BC's 10%/24h requirement, Peak Perks (~90 MW reported), ecobee (~215 MW Canada). Label as assumptions; expose all as sliders.

## 5. Architecture

```
  DATA PIPELINE (offline, Python + pandas)          scripts/build_data.py
  IESO CSV, AESO XLSX, CER scenarios, queue JSON
        -> clean/validate -> normalized hourly JSON  public/data/*.json  (+ data_manifest.json with provenance)

  BROWSER APP (Next.js + TypeScript; all math client-side; no backend required)
  ┌──────────────────────────────────────────────────────────────────┐
  │ UI                                                                │
  │  National map/tiles │ Region view (Replay the year) │ Add-a-load  │
  │  Verdict card │ Sensitivity sliders │ Delivery scene │ Sources    │
  │  Voice briefing (ElevenLabs)                                      │
  └───────────────▲──────────────────────────────────────────────────┘
                  │ typed state (scenario, results)
  ┌───────────────┴──────────────────────────────────────────────────┐
  │ ENGINE (pure TS, deterministic, unit-tested)      src/engine/     │
  │  loadShape   : region baseline hourly series (+ growth factor)    │
  │  newLoad     : profile generators (flat DC, EV evening, housing)  │
  │  capacity    : firm limit = peak × (1+headroom)                   │
  │  feasibility : firm check → flex requirement → build-gap verdict  │
  │  flex        : resource archetypes + dispatcher (shift/curtail)   │
  │  verify      : delivered vs baseline, reliability, settlement calc│
  │  gap         : per-region aggregation across scenarios            │
  └───────────────▲──────────────────────────────────────────────────┘
                  │ reads
  public/data/*.json   (fixtures; reset = reload; seeded RNG)
  Optional: ElevenLabs API (TTS / agent). LLM only narrates structured results.
```

**Principle: agents propose, arithmetic validates.** LLMs (if used) only narrate or parse intent against a schema; they never produce a number, a verdict or a dispatch. Everything must work with no API key.

### Engine spec (the part that must be right)

- **Inputs:** baseline series `L[h]` (MW, 8,784 hours), new load profile `N[h]`, firm capacity `C`, flexibility config.
- **Firm check:** overload hours = `{h : L[h] + N[h] > C}`. If none → **Firm feasible**.
- **Flexibility requirement:** `need[h] = max(0, L[h] + N[h] − C)`. Report: max MW curtailed, hours/year curtailed (and % of year), number and length of events, total energy deferred (MWh), longest consecutive event.
- **Flexible supply:** resources (see below) each with power limit, energy limit, duration, notice, rebound. Dispatcher covers `need[h]` hour by hour subject to constraints (battery SoC and efficiency, recharge must not create a new overload, deferred compute restored before deadline, EV energy delivered by departure, rebound counted). **The same overload check is re-run on the dispatched result** — a scenario passes only if all hours pass.
- **Verdict:** ✅ Firm; ⚠ Feasible with flexibility (state requirement); ❌ Needs build (state residual MW / hours uncovered even at max flexibility) → build-gap.
- **Heavy asset (the thing we add):** a large real-world load placed on a real region, chosen from presets with editable parameters: hyperscale/AI data centre (flat 24/7, high load factor, partly deferrable compute), EAF steel mill (batchy, high peak), aluminium smelter (very flat, large, limited ramp), hydrogen electrolyser (curtailable, price/stress-responsive), mine/mill, EV bus-fleet depot (evening arrival, morning deadline), new housing development. Profiles are **assumptions with a stated basis**, never presented as measured.
- **Optimizer ("Optimize Capacity" button):** given the overload, choose flexible-resource schedules to **minimize the max hourly load (then overload energy)** subject to: EV/fleet energy delivered by departure, battery power/energy/SoC/efficiency, deferrable-compute deadlines and rebound limits, industrial ramp/deadline limits, and per-resource curtailment caps. Solve as an LP/MILP in rolling **day-ahead windows** (24 h, battery SoC carried between days) — only days containing overload need solving — in-browser with a WASM solver (HiGHS via `highs-js`); fall back to the deterministic greedy dispatcher if the solver fails. Report before/after peak, hours over limit, MW unlocked, energy shifted, and which constraint bound. The same overload check re-validates the optimized result. Do not hard-code any "% saved".
- **Resource archetypes:** flexible data-centre share (max curtail MW, max hours/yr, notice), battery (MW/MWh/η), EV fleet (energy, window, deadline), thermostat/heat-pump cohort (pre-condition + rebound), industrial curtailable load.
- **Monotonicity checks** (must be tested): more flexibility never worsens the verdict; larger new load never improves it; results identical for identical seeds.
- **Delivery scene:** pick the worst event; each resource has a seeded reliability; delivered = promised × reliability noise; `deliveredMWh = max(0, baseline − observed)`, capped at promised; never double-count two resources reducing the same metered draw; show shortfall and what the backup does.
- **Growth:** scale `L[h]` by `(1 + g)` where `g` comes from a CER scenario (or user slider). Wording: "if demand grows by g".

### Hero visual — "Replay the real year"
Full-year sweep (or load-duration curve) of real demand, new load stacked on top, capacity line, red for overload hours with a running counter. Press "Enable flexibility" → flexible resources light up, red hours clear, counters show MW/hours/energy needed. Must run smoothly on a laptop and on the recorded demo video.

## 6. Repo layout
```
CLAUDE.md               this file
README.md               setup, demo script, assumptions, limits, sources
data/                   raw downloads (git-ignored if large) + data_manifest notes
scripts/build_data.py   clean + normalize -> public/data/*.json
public/data/            processed fixtures (committed, small)
src/engine/             pure TS engine + tests (vitest)
src/app/, src/components/   Next.js UI
src/lib/voice.ts        ElevenLabs wrapper with offline fallback
```
Stack defaults (change if the user says otherwise): Next.js (App Router) + TypeScript, Tailwind, SVG/canvas charts (no map tokens), vitest. Python only for the data script.

## 7. Build order (≈18 h to submit; keep it runnable after every step)
1. **Data script** → `public/data/ontario_2024.json`, `alberta_shape_2024.json`, `cer_scenarios.json`, `queue_snapshot.json`, `data_manifest.json`. Assert row counts and the numbers in §4. *(1–1.5 h)*
2. **Engine + tests** — feasibility on Ontario with a 500 MW flat data centre: verify overload hours, requirement stats, monotonicity. Log real values. *(2–3 h)*
3. **Region view + hero replay + verdict card + sliders.** This alone must be a demo. *(3–4 h)*
4. **Alberta as second region;** national tiles with real/modelled badges. *(1.5–2 h)*
5. **Delivery scene** (seeded, deterministic) *(2 h)*
6. **Growth scenarios + build-gap cards** with sourced facts *(1.5 h)*
7. **ElevenLabs voice briefing** (claim coupon via the Discord bot; TTS from the structured verdict) *(1 h)*
8. **Polish:** labelling, sources panel, empty/error states, reset, README, laptop + narrow-screen check. **Freeze features ≥ 2 h before submission.** Record the 5-minute demo video (purpose → value to users → feature walkthrough). Merge everything into `main`; repo must be public.
9. Stretch only if time remains: voice control, agent behaviour layer, BC data.

## 8. Demo script (≈3 min)
1. Hook: "Canada must double its grid — over $1T, a decade+. 13.8 GW of data centres are asking; about 0.45 GW are running."
2. Region: Ontario, real 2024 hourly demand. Add a 500 MW data centre → red hours appear (firm: ❌).
3. Enable flexibility → hours clear. Show the requirement: "X MW curtailed, Y hours/year (Z% of the year)". Drag the flexibility slider to show sensitivity.
4. Delivery: trigger the worst event; resources respond; delivered vs promised; verified.
5. National view: which regions absorb it firm / with flexibility / need build; what remains is the build gap with sourced options.
6. Voice briefing reads the recommendation. Close with the ask: this is the planning tool NRCan is asking for input on; next step is a pilot with a system operator or a submission to the national strategy consultation.

## 9. Judging rubric mapping (0–4 each; no technical judges — VC-style panel)
- **Relevance to theme:** national-scale demand growth, competitiveness (attracting data centres/industry), government planning function.
- **Viability:** named users (ministries, operators, developers), what exists (§2), differentiation, next step (NRCan input / IESO or AESO pilot), what happens after the hackathon.
- **Pitch:** one clear story, live hero visual, honest limits, ready answers below.

**Tough questions to rehearse:** Who pays and who adopts? Utilities already have this — what do you add? Where does the capacity limit come from? How do you know loads will actually be flexible? Why should we trust a simulation? What if EnergyHub/Camus add this? How is this different from a capacity map? Why Canada / why sovereign? (Answer sovereignty modestly: NRCan §2.5/§3.6 supports domestic smart-grid software capability and cites cybersecurity; it does **not** mandate Canadian-built software.)

## 10. Honesty and guardrails (non-negotiable)
- Every number on screen comes from the data or a stated, editable assumption. No hard-coded "saves X%".
- Never say "approved", "guaranteed" or "predicts". Use "passes the modelled check", "feasible under these assumptions", "if demand grows by X".
- Label modelled vs real data per region. Show the capacity-limit assumption next to every verdict.
- CER results are scenarios, not predictions. The CER report notes the federal EV standard was repealed in Feb 2026 after modelling — treat EV-driven growth as likely overstated.
- Flexibility defers and shrinks the build; it does not replace it (federal plan is to double the system).
- Cite competitors and unverified claims as "reported"/"from search"; never claim "nobody does this".
- No LLM controls dispatch or creates figures. No fake grid topology. No real connection claims.

## 11. Open decisions / risks
- **Stack and team size not confirmed** — defaults in §6; adjust on reply.
- **Alberta absolute scale:** decide between scaling the area-metered shape to a stated peak vs fetching AESO AIL via API (verify before claiming absolute MW).
- **CER provincial split:** confirm the dataset provides it; else national growth only.
- **ElevenLabs access:** claim the coupon via the Discord bot with the registration email; keep a text fallback.
- **Time:** it is already Saturday evening — cut stretch items first, never the hero visual.
- Keep the AESO double-count trap and the IESO column choice documented in code comments and the README.
