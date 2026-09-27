"""Runtime settings. Paths resolve to the monorepo `data/` directory unless overridden."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.environ.get("CAPACITYOS_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FIXTURES_DIR = DATA_DIR / "fixtures"
WORLD_PACKS_DIR = DATA_DIR / "world_packs"
CORS_ORIGINS = [o for o in os.environ.get("CAPACITYOS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o]


def _load_dotenv() -> None:
    """Tiny .env loader (no dependency). Never overrides real environment variables; values are never logged."""
    for p in (REPO_ROOT / ".env", REPO_ROOT / "apps" / "api" / ".env"):
        if not p.is_file():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def owner_agent_config() -> dict:
    """Read at call time so tests/env changes apply. `openai_api_key` must never be logged or serialized."""
    return {"provider": os.environ.get("OWNER_AGENT_PROVIDER", "stub").strip().lower() or "stub",
            "openai_api_key": os.environ.get("OPENAI_API_KEY", "").strip(),
            "model": os.environ.get("OWNER_AGENT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
            "timeout_s": float(os.environ.get("OWNER_AGENT_TIMEOUT_SECONDS", "20") or 20),
            "max_retries": int(os.environ.get("OWNER_AGENT_MAX_RETRIES", "1") or 1),
            "min_interval_s": float(os.environ.get("OWNER_AGENT_MIN_INTERVAL_SECONDS", "0") or 0)}
