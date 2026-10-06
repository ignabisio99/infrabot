"""Agente de análisis de reclamos con herramientas (Nivel 3).

A diferencia del pipeline lineal (clasificar → duplicados → estimar), acá el LLM
DECIDE qué herramientas usar (consultar padrón, buscar similares, buscar costos) para
fundamentar su análisis en datos reales de la base, y produce un análisis integral.

Si el proveedor no soporta tools o el agente falla, el caller puede caer al pipeline
determinista de siempre (ejecutar_pipeline). Este agente NO reemplaza ese flujo:
lo complementa con un análisis más rico y trazable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from core.ai.factory import get_llm_provider
from models.reclamo import Reclamo
from models.recomendacion_ia import TipoRecomendacionIA
from services.ai import herramientas
from services.ai.prompts import SYSTEM_AGENTE, user_agente
from services.ai.registro import registrar

logger = logging.getLogger(__name__)

_SCHEMA_AGENTE = {
    "task": "analisis_agente",
    "razonamiento": "",
    "categoria": "Otro",
    "prioridad": "MEDIA",
    "escuela_en_padron": False,
    "es_posible_duplicado": False,
    "resumen_para_operador": "",
    "confianza": 0.5,
}


@dataclass(frozen=True)
class ResultadoAgente:
    analisis: dict
    pasos_agente: list = field(default_factory=list)
    proveedor: str = ""


def analizar_reclamo(db: Session, reclamo: Reclamo) -> ResultadoAgente:
    """Corre el agente con herramientas sobre un reclamo y persiste el análisis.

    Lanza si el proveedor no soporta tool-calling (el caller decide el fallback).
    """
    provider = get_llm_provider()
    if not hasattr(provider, "complete_with_tools"):
        raise RuntimeError(f"El proveedor {provider.name} no soporta herramientas")

    ejecutores = herramientas.construir_ejecutores(db, reclamo)
    salida = provider.complete_with_tools(
        system=SYSTEM_AGENTE,
        user=user_agente(
            escuela=reclamo.nombre_escuela,
            ubicacion=reclamo.ubicacion,
            descripcion=reclamo.descripcion,
        ),
        tools=herramientas.DEFINICIONES_TOOLS,
        tool_ejecutores=ejecutores,
        schema_hint=_SCHEMA_AGENTE,
    )
    analisis = salida.get("resultado") or {}
    pasos = salida.get("pasos_agente") or []

    try:
        confianza = float(analisis.get("confianza", 0.5))
    except (TypeError, ValueError):
        confianza = 0.5

    registrar(
        db,
        tipo=TipoRecomendacionIA.ANALISIS_AGENTE,
        payload={
            "razonamiento": analisis.get("razonamiento", ""),
            "categoria": analisis.get("categoria"),
            "prioridad": analisis.get("prioridad"),
            "escuela_en_padron": analisis.get("escuela_en_padron"),
            "es_posible_duplicado": analisis.get("es_posible_duplicado"),
            "resumen_para_operador": analisis.get("resumen_para_operador", ""),
            # Traza de qué herramientas usó el agente y con qué resultados.
            "herramientas_usadas": [
                {"herramienta": p.get("herramienta"), "args": p.get("args")} for p in pasos
            ],
        },
        reclamo_id=reclamo.id,
        proveedor=provider.name,
        confianza=max(0.0, min(1.0, confianza)),
    )

    return ResultadoAgente(analisis=analisis, pasos_agente=pasos, proveedor=provider.name)
