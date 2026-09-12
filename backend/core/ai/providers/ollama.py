"""Proveedor para Ollama corriendo local (endpoint OpenAI-compatible).

Separado de OpenAICompatibleProvider a propósito: Ollama no valida la API key,
soporta `reasoning_effort` para desactivar el razonamiento (Gemma 4 y Qwen3 lo
hacen por defecto y multiplica por ~7 el tiempo de respuesta) y conviene que
quede registrado como proveedor propio en `recomendacion_ia`, para distinguir
las corridas locales de las de un proveedor pago.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

# Parseo tolerante compartido: los modelos locales suelen envolver el JSON en
# ```json o agregar texto alrededor. Se importa en vez de duplicarse.
from core.ai.providers.openai_compatible import _parse_json_content

logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        reasoning_effort: str | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._reasoning_effort = reasoning_effort

    @property
    def name(self) -> str:
        return "ollama"

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._chat(system=system, user_content=user, schema_hint=schema_hint)

    def complete_json_with_images(
        self,
        *,
        system: str,
        user: str,
        images: list[bytes],
        mime_types: list[str] | None = None,
        schema_hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"type": "text", "text": user}]
        mimes = mime_types or ["image/jpeg"] * len(images)
        for raw, mime in zip(images, mimes):
            b64 = base64.b64encode(raw).decode("ascii")
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )
        return self._chat(system=system, user_content=parts, schema_hint=schema_hint)

    def _chat(
        self,
        *,
        system: str,
        user_content: str | list[dict[str, Any]],
        schema_hint: dict[str, Any] | None,
    ) -> dict[str, Any]:
        schema_note = ""
        if schema_hint:
            expected = {k: v for k, v in schema_hint.items() if k != "task"}
            schema_note = (
                "\n\nRespondé ÚNICAMENTE con un JSON válido que respete estas claves "
                f"(valores de ejemplo / tipos):\n{json.dumps(expected, ensure_ascii=False)}"
            )

        payload: dict[str, Any] = {
            "model": self._model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system + schema_note},
                {"role": "user", "content": user_content},
            ],
        }
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort

        url = f"{self._base_url}/chat/completions"

        with httpx.Client(timeout=self._timeout) as client:
            response = client.post(url, json=payload)
            if response.is_error:
                logger.error("Error Ollama %s: %s", response.status_code, response.text[:500])
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return _parse_json_content(content)
