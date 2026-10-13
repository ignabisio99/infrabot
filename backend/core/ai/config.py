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


def duplicados_semanticos_enabled() -> bool:
    raw = (os.getenv("AI_DUPLICADOS_SEMANTICOS") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def ai_whatsapp_enabled() -> bool:
    """Habilita el modo conversacional IA opt-in en el bot de WhatsApp."""
    raw = (os.getenv("AI_WHATSAPP") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def ai_stt_provider() -> str:
    """Quién transcribe: mock | local | openai | gemini.

    Por defecto Whisper local (faster-whisper). Mock sólo si AI_PROVIDER=mock
    o si se setea AI_STT_PROVIDER=mock.
    """
    explicit = (os.getenv("AI_STT_PROVIDER") or "").strip().lower()
    if explicit in ("mock", "local", "openai", "gemini"):
        return explicit
    if ai_provider_name() == "mock":
        return "mock"
    return "local"


def resolver_stt_provider(override: str | None = None) -> str:
    raw = (override or "").strip().lower()
    if raw in ("mock", "local", "openai", "gemini"):
        return raw
    return ai_stt_provider()


def ai_stt_model() -> str:
    return (os.getenv("AI_STT_MODEL") or "whisper-1").strip()


def ai_stt_local_model() -> str:
    return (os.getenv("AI_STT_LOCAL_MODEL") or "base").strip()


def ai_stt_base_url() -> str | None:
    raw = (os.getenv("AI_STT_BASE_URL") or "").strip().rstrip("/")
    return raw or None


def ai_stt_mock_texto() -> str:
    return (
        os.getenv("AI_STT_MOCK_TEXTO")
        or "Escuela Técnica N°1, baño del primer piso: hay una pérdida de agua "
        "importante en el inodoro desde ayer."
    ).strip()


def ai_gemini_native_url() -> str:
    """Base de la API nativa de Gemini (para STT, que el endpoint OpenAI-compatible no soporta)."""
    return (
        os.getenv("AI_GEMINI_NATIVE_URL") or "https://generativelanguage.googleapis.com/v1beta"
    ).rstrip("/")


def ollama_base_url() -> str:
    """Endpoint OpenAI-compatible de Ollama. En Docker el host es host.docker.internal."""
    return (
        os.getenv("OLLAMA_BASE_URL") or "http://host.docker.internal:11434/v1"
    ).rstrip("/")


def ollama_model() -> str:
    return (os.getenv("OLLAMA_MODEL") or "gemma4:12b").strip()


def ollama_reasoning_effort() -> str | None:
    """Gemma 4 y Qwen3 razonan por defecto: ~7x más lento y peores hallazgos en
    visión. "none" lo desactiva. Vacío = no se manda el parámetro."""
    return (os.getenv("OLLAMA_REASONING_EFFORT") or "").strip().lower() or None
