"""Configuración del Motor de IA (variables de entorno)."""

from __future__ import annotations

import os


def ai_provider_name() -> str:
    return (os.getenv("AI_PROVIDER") or "mock").strip().lower()


def openai_api_key() -> str | None:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    return key or None


def openai_model() -> str:
    return (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()


def ai_base_url() -> str:
    # Prefijo hasta antes de /chat/completions (ver OpenAICompatibleProvider).
    return (os.getenv("AI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")


def ai_ssl_verify() -> bool:
    """Si es False, httpx no verifica certificados (útil detrás de proxy corporativo)."""
    raw = (os.getenv("AI_SSL_VERIFY") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def inflacion_api_url() -> str:
    return (
        os.getenv("INFLACION_API_URL") or "https://apis.datos.gob.ar/series/api/series/"
    ).rstrip("/") + "/"


def inflacion_serie_id() -> str:
    # IPC Nivel General Nacional (base 2016) — reemplazable por env.
    return (os.getenv("INFLACION_SERIE_ID") or "101.1_I2NG_2016_M_22").strip()
