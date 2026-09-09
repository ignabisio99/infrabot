"""Evaluación de completitud de datos del reclamo (ciclo conversacional CU-01)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.ai.factory import get_llm_provider
from services.ai.prompts import SYSTEM_COMPLETITUD, user_completitud

logger = logging.getLogger(__name__)

_SCHEMA = {
    "task": "completitud",
    "completo": True,
    "faltantes": [{"campo": "", "pregunta": ""}],
    "datos_extraidos": {},
}

MAX_RONDAS_FALTANTES = 3


@dataclass(frozen=True)
class PreguntaFaltante:
    campo: str
    pregunta: str


@dataclass(frozen=True)
class ResultadoCompletitud:
    completo: bool
    faltantes: list[PreguntaFaltante]
    datos_extraidos: dict
    proveedor: str


def evaluar_completitud(
    *,
    escuela: str,
    ubicacion: str,
    descripcion: str,
) -> ResultadoCompletitud:
    provider = get_llm_provider()
    raw = provider.complete_json(
        system=SYSTEM_COMPLETITUD,
        user=user_completitud(
            escuela=escuela,
            ubicacion=ubicacion,
            descripcion=descripcion,
        ),
        schema_hint=_SCHEMA,
    )
    faltantes_raw = raw.get("faltantes") or []
    faltantes: list[PreguntaFaltante] = []
    for f in faltantes_raw:
        if not isinstance(f, dict):
            continue
        pregunta = str(f.get("pregunta") or "").strip()
        if not pregunta:
            continue
        faltantes.append(
            PreguntaFaltante(
                campo=str(f.get("campo") or "descripcion").strip() or "descripcion",
                pregunta=pregunta,
            )
        )

    completo = bool(raw.get("completo", len(faltantes) == 0)) and len(faltantes) == 0
    datos = raw.get("datos_extraidos") if isinstance(raw.get("datos_extraidos"), dict) else {}
    return ResultadoCompletitud(
        completo=completo,
        faltantes=faltantes,
        datos_extraidos=datos,
        proveedor=provider.name,
    )


def fusionar_respuesta(
    *,
    datos: dict,
    campo: str,
    respuesta: str,
) -> None:
    """Actualiza el dict de conversación con la respuesta del usuario."""
    texto = respuesta.strip()
    if campo == "ubicacion":
        datos["ubicacion"] = f"{datos.get('ubicacion', '')} — {texto}".strip(" —")
    elif campo == "nombre_escuela":
        datos["nombre_escuela"] = texto or datos.get("nombre_escuela")
    else:
        # Por defecto enriquece la descripción
        base = datos.get("descripcion") or ""
        datos["descripcion"] = f"{base}\n{texto}".strip()
