"""Clasificación automática de categoría y prioridad (CU-01 / RF02)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.ai.factory import get_llm_provider
from models.reclamo import PrioridadReclamo, Reclamo
from services.ai.prompts import CATEGORIAS_VALIDAS, SYSTEM_CLASIFICACION, user_clasificacion

logger = logging.getLogger(__name__)

_SCHEMA = {
    "task": "clasificacion",
    "categorias": CATEGORIAS_VALIDAS,
    "categoria": "Otro",
    "prioridad": "MEDIA",
    "confianza": 0.5,
    "justificacion": "",
}


@dataclass(frozen=True)
class ResultadoClasificacion:
    categoria: str
    prioridad: PrioridadReclamo
    confianza: float
    justificacion: str
    proveedor: str


def clasificar_texto(
    descripcion: str,
    *,
    escuela: str | None = None,
    ubicacion: str | None = None,
) -> ResultadoClasificacion:
    provider = get_llm_provider()
    raw = provider.complete_json(
        system=SYSTEM_CLASIFICACION,
        user=user_clasificacion(descripcion=descripcion, escuela=escuela, ubicacion=ubicacion),
        schema_hint=_SCHEMA,
    )
    return _parse(raw, provider.name)


def clasificar_reclamo(reclamo: Reclamo) -> ResultadoClasificacion:
    return clasificar_texto(
        reclamo.descripcion,
        escuela=reclamo.nombre_escuela,
        ubicacion=reclamo.ubicacion,
    )


def aplicar_clasificacion(reclamo: Reclamo, resultado: ResultadoClasificacion) -> None:
    """Aplica categoría y prioridad al reclamo. No hace commit."""
    reclamo.categoria = resultado.categoria
    reclamo.prioridad = resultado.prioridad


def _parse(raw: dict, proveedor: str) -> ResultadoClasificacion:
    categoria = str(raw.get("categoria") or "Otro").strip()
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = "Otro"

    prioridad_raw = str(raw.get("prioridad") or "MEDIA").strip().upper()
    try:
        prioridad = PrioridadReclamo(prioridad_raw)
    except ValueError:
        prioridad = PrioridadReclamo.MEDIA

    try:
        confianza = float(raw.get("confianza", 0.5))
    except (TypeError, ValueError):
        confianza = 0.5
    confianza = max(0.0, min(1.0, confianza))

    justificacion = str(raw.get("justificacion") or "").strip()
    return ResultadoClasificacion(
        categoria=categoria,
        prioridad=prioridad,
        confianza=confianza,
        justificacion=justificacion,
        proveedor=proveedor,
    )
