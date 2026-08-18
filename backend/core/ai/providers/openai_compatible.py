"""Proveedor compatible con la API Chat Completions de OpenAI (y clones)."""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        verify_ssl: bool = True,
    ):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._verify_ssl = verify_ssl

    @property
    def name(self) -> str:
        if "generativelanguage.googleapis.com" in self._base_url:
            return "gemini"
        return "openai"

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
            "messages": [
                {"role": "system", "content": system + schema_note},
                {"role": "user", "content": user_content},
            ],
        }
        if self.name != "gemini":
            payload["response_format"] = {"type": "json_object"}

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=self._timeout, verify=self._verify_ssl) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.is_error:
                logger.error(
                    "Error LLM %s: %s", response.status_code, response.text[:500]
                )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return _parse_json_content(content)


def _parse_json_content(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Respuesta LLM no es JSON válido: %s", text[:500])
    raise ValueError("El proveedor de IA no devolvió JSON válido")
