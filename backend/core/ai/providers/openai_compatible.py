"""Proveedor compatible con la API Chat Completions de OpenAI (y clones)."""

from __future__ import annotations

import base64
import html
import json
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Reintentos ante errores transitorios del LLM (Gemini 503 por saturación, etc.).
_MAX_REINTENTOS_LLM = 3
_BACKOFF_BASE = 1.0  # segundos; crece 1s, 2s, 4s entre intentos.
_STATUS_REINTENTABLES = frozenset({429, 500, 502, 503, 504})


# Instrucción de formato que se agrega a TODOS los prompts JSON. Evita que el modelo
# genere entidades HTML (&eacute;, &#xfa;, etc.) que a veces se corrompen en el
# transporte y aparecen crudas/mal formadas en el texto que ve el usuario.
_INSTRUCCION_TEXTO_PLANO = (
    "\n\nIMPORTANTE sobre el texto: escribí en español normal con acentos y ñ "
    "directos en UTF-8 (á, é, í, ó, ú, ñ, ¿, ¡). NO uses entidades HTML ni escapes "
    "(nada de &eacute;, &aacute;, &#xfa;, \\u00e9, etc.). Texto plano legible."
)


def _desescapar_html(valor: Any) -> Any:
    """Decodifica entidades HTML (ej. '&#xfa;' -> 'ú') en strings, recursivamente.

    Red de seguridad por si el modelo igual devuelve alguna entidad bien formada.
    (La prevención principal es _INSTRUCCION_TEXTO_PLANO en el prompt.)
    """
    if isinstance(valor, str):
        return html.unescape(valor)
    if isinstance(valor, list):
        return [_desescapar_html(v) for v in valor]
    if isinstance(valor, dict):
        return {k: _desescapar_html(v) for k, v in valor.items()}
    return valor


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

    def complete_with_tools(
        self,
        *,
        system: str,
        user: str,
        tools: list[dict[str, Any]],
        tool_ejecutores: dict[str, Any],
        schema_hint: dict[str, Any] | None = None,
        max_iteraciones: int = 5,
    ) -> dict[str, Any]:
        """Loop agéntico de function calling.

        El modelo recibe las 'tools' (definiciones OpenAI) y decide cuáles llamar.
        Por cada tool que pide, se ejecuta el callable de 'tool_ejecutores[nombre]'
        con los argumentos que dio el modelo, y se le devuelve el resultado. El loop
        sigue hasta que el modelo responde sin pedir más tools (respuesta final JSON)
        o hasta 'max_iteraciones'. Devuelve dict con: {resultado, pasos_agente}.

        pasos_agente registra qué herramientas usó y con qué args (para mostrar el
        "razonamiento y acciones" del agente en la UI / defensa).
        """
        schema_note = ""
        if schema_hint:
            expected = {k: v for k, v in schema_hint.items() if k != "task"}
            schema_note = (
                "\n\nCuando tengas toda la información, respondé ÚNICAMENTE con un JSON "
                f"que respete estas claves:\n{json.dumps(expected, ensure_ascii=False)}"
            )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system + schema_note + _INSTRUCCION_TEXTO_PLANO},
            {"role": "user", "content": user},
        ]
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        pasos_agente: list[dict[str, Any]] = []

        for _ in range(max_iteraciones):
            payload: dict[str, Any] = {
                "model": self._model,
                "temperature": 0.2,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            }
            data = self._post_con_reintentos(url, headers, payload)
            msg = data["choices"][0]["message"]
            tool_calls = msg.get("tool_calls") or []

            if not tool_calls:
                # Respuesta final: no pidió más herramientas.
                contenido = msg.get("content") or "{}"
                return {
                    "resultado": _parse_json_content(contenido),
                    "pasos_agente": pasos_agente,
                }

            # El modelo pidió ejecutar una o más herramientas.
            messages.append(msg)
            for call in tool_calls:
                nombre = call.get("function", {}).get("name", "")
                args_raw = call.get("function", {}).get("arguments") or "{}"
                try:
                    args = json.loads(args_raw)
                except json.JSONDecodeError:
                    args = {}
                ejecutor = tool_ejecutores.get(nombre)
                if ejecutor is None:
                    resultado_tool = {"error": f"herramienta desconocida: {nombre}"}
                else:
                    try:
                        resultado_tool = ejecutor(**args)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Herramienta %s falló", nombre)
                        resultado_tool = {"error": str(exc)}
                pasos_agente.append({"herramienta": nombre, "args": args, "resultado": resultado_tool})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": json.dumps(resultado_tool, ensure_ascii=False, default=str),
                    }
                )

        # Se agotaron las iteraciones sin respuesta final.
        logger.warning("Agente: se alcanzó el máximo de iteraciones sin respuesta final")
        return {"resultado": {}, "pasos_agente": pasos_agente}

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
                {"role": "system", "content": system + schema_note + _INSTRUCCION_TEXTO_PLANO},
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

        data = self._post_con_reintentos(url, headers, payload)
        content = data["choices"][0]["message"]["content"]
        return _parse_json_content(content)

    def _post_con_reintentos(
        self, url: str, headers: dict, payload: dict
    ) -> dict[str, Any]:
        """POST al LLM reintentando ante errores transitorios (503/429/5xx/red).

        Gemini devuelve 503 cuando está saturado ("spikes are usually temporary");
        un par de reintentos con backoff lo resuelven casi siempre.
        """
        ultimo_error: Exception | None = None
        for intento in range(_MAX_REINTENTOS_LLM):
            try:
                with httpx.Client(timeout=self._timeout, verify=self._verify_ssl) as client:
                    response = client.post(url, headers=headers, json=payload)
                if response.status_code in _STATUS_REINTENTABLES:
                    ultimo_error = httpx.HTTPStatusError(
                        f"status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    logger.warning(
                        "LLM %s (intento %s/%s); reintentando...",
                        response.status_code,
                        intento + 1,
                        _MAX_REINTENTOS_LLM,
                    )
                    time.sleep(_BACKOFF_BASE * (2**intento))
                    continue
                if response.is_error:
                    logger.error(
                        "Error LLM %s: %s", response.status_code, response.text[:500]
                    )
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                # Errores de red/timeout: también son transitorios.
                ultimo_error = exc
                logger.warning(
                    "LLM error de red (intento %s/%s): %s; reintentando...",
                    intento + 1,
                    _MAX_REINTENTOS_LLM,
                    type(exc).__name__,
                )
                time.sleep(_BACKOFF_BASE * (2**intento))

        # Se agotaron los reintentos: propagamos el último error (el caller ya
        # tiene su propio fallback: heurística, históricos, mantener clasificación).
        assert ultimo_error is not None
        raise ultimo_error


def _parse_json_content(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    try:
        return _desescapar_html(json.loads(text))
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return _desescapar_html(json.loads(fence.group(1)))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return _desescapar_html(json.loads(text[start : end + 1]))
        except json.JSONDecodeError:
            pass

    logger.error("Respuesta LLM no es JSON válido: %s", text[:500])
    raise ValueError("El proveedor de IA no devolvió JSON válido")
