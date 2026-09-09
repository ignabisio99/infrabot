"""Factory de proveedores LLM según configuración de entorno."""

from __future__ import annotations

import logging

from core.ai import config
from core.ai.base import LLMProvider
from core.ai.providers.mock import MockProvider
from core.ai.providers.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)

_cached: LLMProvider | None = None


def get_llm_provider(*, force_reload: bool = False) -> LLMProvider:
    """Devuelve el proveedor activo.

    - `AI_PROVIDER=mock` → MockProvider
    - `AI_PROVIDER=openai` + `OPENAI_API_KEY` → OpenAICompatibleProvider
    - Si piden openai sin key → fallback a mock (con warning)
    """
    global _cached
    if _cached is not None and not force_reload:
        return _cached

    name = config.ai_provider_name()
    api_key = config.openai_api_key()

    if name in ("openai", "openai_compatible") and api_key:
        provider: LLMProvider = OpenAICompatibleProvider(
            api_key=api_key,
            base_url=config.ai_base_url(),
            model=config.openai_model(),
            verify_ssl=config.ai_ssl_verify(),
        )
        logger.info(
            "Motor IA: proveedor openai (model=%s, base=%s)",
            config.openai_model(),
            config.ai_base_url(),
        )
    else:
        if name not in ("mock", "") and not api_key:
            logger.warning(
                "AI_PROVIDER=%s pero no hay OPENAI_API_KEY; usando mock.",
                name,
            )
        provider = MockProvider()
        logger.info("Motor IA: proveedor mock")

    _cached = provider
    return _cached


def reset_llm_provider_cache() -> None:
    """Útil en tests."""
    global _cached
    _cached = None
