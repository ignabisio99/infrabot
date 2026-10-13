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


_UBICACIONES_VAGAS = {
    "patio",
    "aula",
    "baño",
    "bano",
    "escuela",
    "el colegio",
    "ahi",
    "ahí",
    "aca",
    "acá",
    "adentro",
}


def evaluar_completitud_heuristica(
    *,
    escuela: str,
    ubicacion: str,
    descripcion: str,
) -> ResultadoCompletitud:
    """Preguntas mínimas si Gemini no está (429, red, etc.)."""
    faltantes: list[PreguntaFaltante] = []
    if len((escuela or "").strip()) < 3:
        faltantes.append(
            PreguntaFaltante(
                campo="nombre_escuela",
                pregunta="¿Cuál es el nombre de la escuela?",
            )
        )
    ubi = (ubicacion or "").strip()
    if len(ubi) < 8 or ubi.lower() in _UBICACIONES_VAGAS:
        faltantes.append(
            PreguntaFaltante(
                campo="ubicacion",
                pregunta="¿En qué parte de la escuela es exactamente (piso, aula, patio, sector)?",
            )
        )
    desc = (descripcion or "").strip()
    if len(desc) < 40:
        faltantes.append(
            PreguntaFaltante(
                campo="descripcion",
                pregunta="¿Podés contar un poco más: qué elemento falló, desde cuándo y si afecta un aula o toda la escuela?",
            )
        )
    elif not any(
        pista in desc.lower()
        for pista in ("desde", "hace", "afect", "toda", "aula", "riesgo", "no anda", "no funciona")
    ):
        faltantes.append(
            PreguntaFaltante(
                campo="descripcion",
                pregunta="¿Desde cuándo pasa y qué tanto afecta (un aula, un sector, toda la escuela)?",
            )
        )
    faltantes = faltantes[:2]
    return ResultadoCompletitud(
        completo=len(faltantes) == 0,
        faltantes=faltantes,
        datos_extraidos={},
        proveedor="heuristica",
    )


def evaluar_completitud(
    *,
    escuela: str,
    ubicacion: str,
    descripcion: str,
) -> ResultadoCompletitud:
    try:
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
    except Exception:
        logger.warning("Completitud LLM no disponible; se usan preguntas heurísticas")
        return evaluar_completitud_heuristica(
            escuela=escuela,
            ubicacion=ubicacion,
            descripcion=descripcion,
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
        if datos.get("ubicacion"):
            datos["info_extra"] = f"{datos.get('info_extra', '')} {texto}".strip()
        else:
            datos["ubicacion"] = texto
    elif campo == "nombre_escuela":
        datos["nombre_escuela"] = texto or datos.get("nombre_escuela")
    else:
        base = datos.get("descripcion") or ""
        datos["descripcion"] = f"{base}\n{texto}".strip()
