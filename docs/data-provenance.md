# Data provenance

| Item | Source | Provenance label |
|---|---|---|
| Historical hourly demand shape | IESO Hourly Zonal Demand Report, Southwest zone, 2021–2025 (`https://reports-public.ieso.ca/public/DemandZonal/`) | Observed shape → scaled to the demo zone = **Derived** |
| Scale factor | 78 MW ÷ 5-year zone peak (≈0.0155) | Modeling choice, stored per row in the dataset |
| Zone capacity (90 MW) | Hackathon assumption | **Modeled** (`capacity.provenance = modeled`) |
| DER population | Generated in Phase 3 from seed 42017 | **Modeled** |
| Owner/operator agents and their preferences (Phase 5) | Generated from seed 42017 | **Modeled** (synthetic behavior, not real customers) |
| Flexibility requests, validation, clearing results | Computed | **Derived** |
| New projects | User-added | **Hypothetical** |

Ingestion rules: hour-ending 1..24 → start-of-hour timestamps in fixed UTC-5 (IESO convention, unverified); missing hours ≤ 6 are linearly interpolated and flagged `interpolated` (1 hour in the 5-year set); longer gaps and non-positive values are refused. Full set = 43,824 hours (2021–2025, incl. leap 2024).

Earlier Waterloo-specific research (IESO 2026 KWCG IRRP station forecasts and planning profiles, derived station limits) is preserved in `docs/PROJECT_waterloo_stations.md` and `docs/PREVIOUS_PLANNER_CLAUDE.md`, with processed files in `data/processed/legacy/` (gitignored, regenerable via `scripts/`). It is a candidate source for future world packs.
