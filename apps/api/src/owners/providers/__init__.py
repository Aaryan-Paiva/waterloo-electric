from typing import Optional

from ... import settings
from .base import OwnerAgentProvider, ProviderError, ProviderResult, ProviderUnavailable
from .openai_provider import OpenAIProvider
from .stub import StubProvider

__all__ = ["OwnerAgentProvider", "ProviderError", "ProviderResult", "ProviderUnavailable", "StubProvider", "OpenAIProvider", "get_provider", "provider_status"]


def get_provider(name: Optional[str] = None) -> OwnerAgentProvider:
    """Raises ProviderUnavailable for `openai` without a key/SDK; the caller decides how to degrade (the runner falls back to the stub)."""
    cfg = settings.owner_agent_config()
    name = (name or cfg["provider"]).lower()
    if name == "openai":
        return OpenAIProvider(cfg["openai_api_key"], cfg["model"], cfg["timeout_s"], cfg["max_retries"], min_interval_s=cfg["min_interval_s"])
    if name == "stub":
        return StubProvider()
    raise ProviderUnavailable(f"unknown provider {name!r}")


def provider_status() -> dict:
    cfg = settings.owner_agent_config()
    try:
        import openai  # noqa: F401
        sdk = True
    except ImportError:
        sdk = False
    return {"default": cfg["provider"], "stubAvailable": True, "openaiAvailable": bool(cfg["openai_api_key"]) and sdk, "openaiKeyConfigured": bool(cfg["openai_api_key"]),
            "openaiSdkInstalled": sdk, "model": cfg["model"], "timeoutSeconds": cfg["timeout_s"]}
