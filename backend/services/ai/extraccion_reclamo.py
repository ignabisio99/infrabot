"""Extracción de campos del reclamo desde texto libre (modo conversacional CU-01)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.ai.factory import get_llm_provider
from services.ai.prompts import (
    SYSTEM_EXTRACCION_RECLAMO,
    SYSTEM_RESUMEN_RECLAMO,
    user_extraccion_reclamo,
    user_resumen_reclamo,
)

logger = logging.getLogger(__name__)

_SCHEMA = {
    "task": "extraccion_reclamo",
    "nombre_escuela": "",
    "ubicacion": "",
    "descripcion": "",
    "confianza": 0.5,
}


@dataclass(frozen=True)
class DatosReclamoExtraidos:
    nombre_escuela: str | None
    ubicacion: str | None
    descripcion: str
    confianza: float
    proveedor: str


_SCHEMA_RESUMEN = {
    "task": "resumen_reclamo",
    "descripcion": "",
}


def redactar_descripcion_local(notas: str) -> str:
    """Quita muletillas y uniones literales si no hay LLM."""
    utiles: list[str] = []
    for linea in (notas or "").replace(". ", ".\n").splitlines():
        t = linea.strip()
        if not t:
            continue
        bajo = t.lower()
        if bajo in ("ok", "si", "sí", "dale", "listo") or "flakito" in bajo or "ya te dije" in bajo:
            continue
        if t not in utiles:
            utiles.append(t)
    return " ".join(utiles) or (notas or "").strip()


def redactar_descripcion(notas: str) -> str:
    """Reescribe notas de chat en un párrafo de informe. Si falla, limpia en local."""
    bruto = (notas or "").strip()
    if not bruto:
        return ""
    try:
        provider = get_llm_provider()
        raw = provider.complete_json(
            system=SYSTEM_RESUMEN_RECLAMO,
            user=user_resumen_reclamo(notas=bruto),
            schema_hint=_SCHEMA_RESUMEN,
        )
        limpio = str(raw.get("descripcion") or "").strip()
        return limpio or redactar_descripcion_local(bruto)
    except Exception:
        logger.warning("Resumen LLM no disponible; se limpia en local")
        return redactar_descripcion_local(bruto)


def extraer_datos_reclamo(texto: str) -> DatosReclamoExtraidos:
    """Interpreta un mensaje libre y devuelve los campos del reclamo.

    Lo que no se menciona queda en None; el loop de faltantes de `completitud`
    se encarga de pedirlo después.
    """
    provider = get_llm_provider()
    raw = provider.complete_json(
        system=SYSTEM_EXTRACCION_RECLAMO,
        user=user_extraccion_reclamo(texto=texto),
        schema_hint=_SCHEMA,
    )

    descripcion = str(raw.get("descripcion") or "").strip()
    if descripcion.lower() in ("null", "none", "n/a", "nil"):
        descripcion = ""
    escuela = _limpiar_opcional(raw.get("nombre_escuela"))
    ubicacion = _limpiar_opcional(raw.get("ubicacion"))
    try:
        confianza = float(raw.get("confianza", 0.5))
    except (TypeError, ValueError):
        confianza = 0.5
    confianza = max(0.0, min(1.0, confianza))

    return DatosReclamoExtraidos(
        nombre_escuela=escuela,
        ubicacion=ubicacion,
        descripcion=descripcion,
        confianza=confianza,
        proveedor=provider.name,
    )


def _limpiar_opcional(valor) -> str | None:
    texto = str(valor or "").strip()
    return texto or None
