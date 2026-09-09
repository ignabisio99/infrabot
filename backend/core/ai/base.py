"""Contrato común para proveedores de LLM."""

from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    """Adaptador de modelo de lenguaje. Todos los proveedores exponen la misma interfaz."""

    @property
    def name(self) -> str:
        """Identificador del proveedor (ej. mock, openai)."""
        ...

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Completa una consulta y devuelve un objeto JSON parseado."""
        ...

    def complete_json_with_images(
        self,
        *,
        system: str,
        user: str,
        images: list[bytes],
        mime_types: list[str] | None = None,
        schema_hint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Igual que complete_json pero con imágenes (vision / OCR)."""
        ...
