"""Speech-to-text de audios de WhatsApp (notas de voz → texto).

El endpoint OpenAI-compatible de Gemini no soporta /audio/transcriptions, así que
para Gemini se usa la API nativa generateContent con el audio inline en base64.
Con AI_PROVIDER=mock devuelve un transcript fijo configurable (AI_STT_MOCK_TEXTO).
"""

from __future__ import annotations

import base64
import logging

import httpx

from core.ai import config as ai_config

logger = logging.getLogger(__name__)

_PROMPT_TRANSCRIPCION = (
    "Transcribí literalmente este audio en español. "
    "Respondé solo con el texto transcripto, sin comillas ni comentarios."
)


class TranscripcionError(Exception):
    """Falló la transcripción del audio."""


def transcribir_audio(audio: bytes, mime_type: str) -> str:
    """Devuelve el transcript del audio según el proveedor configurado."""
    if not audio:
        raise TranscripcionError("Audio vacío")

    provider = ai_config.ai_provider_name()
    if provider == "mock" or not ai_config.openai_api_key():
        logger.info("STT mock (%d bytes, %s)", len(audio), mime_type)
        return ai_config.ai_stt_mock_texto()

    base_url = ai_config.ai_base_url()
    if "generativelanguage.googleapis.com" in base_url:
        return _transcribir_gemini(audio, mime_type)
    return _transcribir_openai(audio, mime_type)


def _transcribir_gemini(audio: bytes, mime_type: str) -> str:
    url = (
        f"{ai_config.ai_gemini_native_url()}/models/"
        f"{ai_config.openai_model()}:generateContent"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _PROMPT_TRANSCRIPCION},
                    {
                        "inline_data": {
                            "mime_type": mime_type.split(";")[0].strip() or "audio/ogg",
                            "data": base64.b64encode(audio).decode("ascii"),
                        }
                    },
                ]
            }
        ]
    }
    headers = {
        "Authorization": f"Bearer {ai_config.openai_api_key()}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=60.0, verify=ai_config.ai_ssl_verify()) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        partes = data["candidates"][0]["content"]["parts"]
        texto = "".join(p.get("text", "") for p in partes).strip()
    except Exception as exc:
        logger.error("Error STT Gemini: %s", exc)
        raise TranscripcionError(f"Gemini no pudo transcribir el audio: {exc}") from exc
    if not texto:
        raise TranscripcionError("Gemini devolvió una transcripción vacía")
    return texto


def _transcribir_openai(audio: bytes, mime_type: str) -> str:
    url = f"{ai_config.ai_base_url()}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {ai_config.openai_api_key()}"}
    extension = (mime_type.split("/")[-1].split(";")[0].strip() or "ogg")
    files = {"file": (f"audio.{extension}", audio, mime_type)}
    data = {"model": ai_config.ai_stt_model(), "language": "es"}
    try:
        with httpx.Client(timeout=60.0, verify=ai_config.ai_ssl_verify()) as client:
            response = client.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            texto = str(response.json().get("text") or "").strip()
    except Exception as exc:
        logger.error("Error STT OpenAI: %s", exc)
        raise TranscripcionError(f"Whisper no pudo transcribir el audio: {exc}") from exc
    if not texto:
        raise TranscripcionError("Whisper devolvió una transcripción vacía")
    return texto
