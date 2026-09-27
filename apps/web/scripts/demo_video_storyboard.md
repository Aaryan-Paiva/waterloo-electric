# CapacityOS Demo Video — Script ↔ Visual Storyboard

Legend: ✅ asset ready and matches script · ⚠️ asset ready but text/content differs from script · ❌ no asset yet

---

## PART 1 — PURPOSE (0:00–0:55)

### 0:00–0:14 — "Canada wants to build"
| | |
|---|---|
| **VO** | "Canada wants to build more. More housing. More AI data centres. More electrified transportation and industry. All of it needs electricity. So how do we make room for what comes next?" |
| **On-screen** | `HOUSING` → `AI DATA CENTRES` → `ELECTRIFICATION` (one per shot) |
| **Visual (script)** | Aerial neighbourhood dawn → data-centre server aisle → EV buses charging → industrial facility |
| **Asset** | `cinematic/01_neighborhood.mp4` (6s) → `cinematic/02_datacentre.mp4` (6s) → `cinematic/03_buses.mp4` (6s) → `cinematic/04_industrial.mp4` (6s) |
| **Status** | ✅ all 4 clips exist, no text baked in (text overlay needs to be added separately — see note below) |

### 0:14–0:28 — Ask the central question
| | |
|---|---|
| **VO** | "We'll need new infrastructure. But before deciding how much to add, how much more can we accommodate on the grid we already have? One opportunity is to reduce or shift demand during constrained hours." |
| **On-screen** | `MAKE BETTER USE OF EXISTING CAPACITY` + source caption `Context: NRCan — Powering Canada Strong; CER — Energy Future 2026` |
| **Visual (script)** | Animated community + demand curve rising toward "Local capacity" line |
| **Asset** | `motion/static/01-demand-vs-capacity-8s.png→mp4` (8s) — reads **"Demand is outpacing local capacity"** baked in |
| **Status** | ⚠️ visual concept matches (rising line crossing capacity line) but baked-in text says "Demand is outpacing local capacity", not "MAKE BETTER USE OF EXISTING CAPACITY" or the source caption. **Decision needed: keep as-is, or is the current line close enough since it lands the same beat?** |

### 0:28–0:42 — Introduce VPPs and their difficulty
| | |
|---|---|
| **VO** | "A virtual power plant coordinates batteries, EV charging and flexible buildings to do that together. But devices have limits, and owners have priorities. The challenge is designing a program that delivers enough flexibility when it's needed." |
| **On-screen** | `WHAT CAN WE ACTUALLY COUNT ON?` + constraint labels `Reserve` `Departure deadline` `Comfort` `Participation` |
| **Visual (script)** | Battery discharges, EV charging shifts, building demand drops, peak falls; then reveal constraint labels |
| **Asset** | `motion/static/02-vpp-devices-8s.png→mp4` (8s) — reads **"Batteries. EV fleets. Flexible buildings."** with battery/EV-fleet/building icons |
| **Status** | ⚠️ shows the three device types correctly but doesn't show the discharge/shift/drop animation or the constraint labels (Reserve/Deadline/Comfort/Participation) — it's a static icon card, not the described sequence. **Close enough as a device-intro card, but the constraint-limits beat isn't covered by this asset.** |

### 0:42–0:55 — Reveal CapacityOS
| | |
|---|---|
| **VO** | "CapacityOS is a VPP design sandbox. It lets planners test what a proposed program can deliver, where it falls short, and what additional capacity remains necessary—before deploying real resources." |
| **On-screen** | `CapacityOS` / `Design the VPP before you deploy it.` + progression `Capacity planning → Program design → Operation` (highlight Program design) |
| **Visual (script)** | Transition from illustrated community into the real CapacityOS world; title over live motion |
| **Asset** | `motion/static/04-capacityos-title-4s.png→mp4` (4s) — reads **"CapacityOS"** only, no tagline, no 3-stage progression, no live product behind it |
| **Status** | ⚠️ logo card works as a title card but is missing the tagline and the capacity-planning→program-design→operation progression graphic |

---

## PART 2 — VALUE TO USERS (0:55–1:20)
| | |
|---|---|
| **VO** | "For a utility planner: how much of this capacity shortfall could flexibility address? For an aggregator: what participation, incentives and resource mix should we target? For an energy consultant or municipal planner: which designs accommodate proposed growth across different conditions? The value is making those assumptions testable, comparing outcomes, and understanding failure before committing to a program. Let's test one." |
| **On-screen** | `UTILITY — How much can flexibility contribute?` / `AGGREGATOR — What program should we design?` / `PLANNER — Under which conditions does it hold?` |
| **Visual (script)** | Real product visible, 3 planning-question overlays pointing at relevant UI controls/results (not static persona cards) |
| **Asset** | **❌ none generated** — this needs a live screen recording of the sandbox idle/overview with text overlays, not a standalone motion clip |
| **Status** | ❌ **gap** — needs a short screen-recorded clip of the app (or a few seconds pulled from the front of `walkthrough.mp4`) with 3 text overlays added in post |

---

## PART 3 — FEATURE WALKTHROUGH (1:20–4:35)

All of Part 3 maps to one continuous asset: **`walkthrough.mp4`** (currently 1:28.84, cursor-overlay version — recorded against the verified real scenario: 20MW data centre + 1000-home housing, summer 2pm, $130/MWh → `partly_holds`, 6.2/7.3 MW absorbed).

| Script beat | Time | Covered by walkthrough.mp4? |
|---|---|---|
| Establish the world | 1:20–1:40 | ✅ beat 1 (establish world, provenance) |
| Design the program (sliders) | 1:40–1:56 | ✅ beat 2 (editor, incentive $130) |
| Add growth (drag data centre) | 1:56–2:10 | ✅ beat 3 (drag Data centre + Housing) |
| Ask the owners (offers/declines) | 2:10–2:35 | ✅ beat 4 (wait for real run) |
| Physics check → dispatch | 2:35–2:57 | ✅ beat 6 (Log tab — real rejection+revision pair) |
| Read the result (partly holds) | 2:57–3:14 | ✅ beat 5 (Result tab) |
| Fix It / counterfactual | 3:14–3:48 | ✅ beat 7 (Fix it tab) |
| Seasonal comparison | 3:48–4:06 | ✅ beat 8 (Seasons tab) |
| Inspect/compare/repeat (log, history, guide, reset) | 4:06–4:20 | ✅ beats 6, 9, 10, 11 (Log, Runs/History, tour, Reset) |
| State the boundaries (provenance legend) | 4:20–4:35 | ⚠️ partially — reset/provenance close is the last beat, but there's no dedicated "3-label boundary" overlay card |

**Status:** ✅ walkthrough.mp4 covers essentially the entire Part 3 narrative in the right order already, since it was built directly from this script. On-screen text overlays (labels like `TESTED CHANGE: ...`, `SAME DESIGN. DIFFERENT CONDITIONS.`) still need to be burned in over it in post — none of that text exists on the recording yet, it's silent/raw screen capture.

---

## CLOSE (4:35–4:50)
| | |
|---|---|
| **VO** | "Next: a calibrated utility pilot with local constraints and actual DER inventory, benchmarked against an existing planning case. How much more can we accommodate with the grid we already have? CapacityOS helps test what flexibility can deliver—before deployment." |
| **On-screen** | `Demo world → Calibrated utility pilot → Operational handoff` then end card: `CapacityOS` / `Make room for what's next.` / `Design the VPP before you deploy it.` / `[LIVE URL]` `[GITHUB URL]` |
| **Visual (script)** | Progression graphic → wide community shot (echo opening) → logo + URL end card |
| **Asset** | `motion/static/06-pilot-to-rollout-8s.png→mp4` (8s) — reads **"From pilot to zone-wide rollout"**, shows 1 building → 4 buildings → 8-building neighbourhood |
| **Status** | ⚠️ good conceptual match (single site → scaled-up rollout) but wording says "zone-wide rollout" not "calibrated utility pilot / operational handoff", and there's no dedicated end card with the CapacityOS logo + tagline + URLs |

---

## Summary of gaps to resolve before final assembly

1. **Part 2 (0:55–1:20)** — no asset exists at all; needs a short live screen clip + 3 text overlays, or repurpose seconds from the front of `walkthrough.mp4`.
2. **On-screen text overlays for Part 1 cinematic clips** — the 4 cinematic clips (`HOUSING` / `AI DATA CENTRES` / `ELECTRIFICATION`) have no text burned in yet.
3. **On-screen text overlays throughout Part 3** — `walkthrough.mp4` is currently silent/raw with no on-screen labels burned in.
4. **6 static motion graphics carry different wording** than the exact script lines (see ⚠️ rows above) — decide keep-as-is vs. regenerate text to match script exactly.
5. **No dedicated end card** (logo + tagline + URLs) exists yet.
6. **Source caption** (`Context: NRCan...`) not present anywhere.

Tell me which of these to fix and I'll close the gaps, then run final assembly in this exact script order.
