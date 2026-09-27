"""Pre-run the demo scenarios with real LLM owners so the live demo replays instantly from the decision cache.

Run from apps/api with the key in ../../.env loaded:  set -a; . ../../.env; set +a; .venv/bin/python ../../scripts/warm_cache.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from src.capacityos.sandbox import run_sandbox  # noqa: E402
from src.schemas.sandbox import DeviceParams, LoadSpec, SandboxRunRequest  # noqa: E402

DC = LoadSpec(kind="data_centre", size=20)
HOMES = LoadSpec(kind="housing", size=1000)
SCENARIOS = [
    ("data centre 20 MW, defaults, summer 2 pm, $100", SandboxRunRequest(season="summer", hour=14, loads=[DC], provider="openai", incentive_per_mwh=100)),
    ("acceptance: 1000 homes + 20 MW DC, 40% enrolled, $75, summer 2 pm", SandboxRunRequest(season="summer", hour=14, loads=[HOMES, DC], provider="openai", incentive_per_mwh=75, device_params=DeviceParams(owners_enrolled_pct=40))),
    ("data centre 20 MW, defaults, fall 5 pm, $100", SandboxRunRequest(season="fall", hour=17, loads=[DC], provider="openai", incentive_per_mwh=100)),
]
for name, req in SCENARIOS:
    r = run_sandbox(req)
    print(f"{name}: {r.outcome}, absorbed {r.absorbed_mw}/{r.overload_mw} MW, source {r.decision_source}, cached-before={r.cached}")
