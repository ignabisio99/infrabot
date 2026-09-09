"""Grafo LangGraph del pipeline IA: clasificar → duplicados → estimar."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from models.reclamo import Reclamo
from models.recomendacion_ia import TipoRecomendacionIA
from services.ai import clasificacion, duplicados, estimacion, registro
from services.ai.derivacion import UMBRAL_CONFIANZA_DERIVACION, evaluar_derivacion

logger = logging.getLogger(__name__)


class EstadoPipeline(TypedDict, total=False):
    reclamo_id: int
    pasos: list[str]
    categoria: str
    prioridad: str
    confianza: float
    justificacion: str
    proveedor: str
    duplicados: list[dict[str, Any]]
    estimacion_id: int | None
    total: float | None
    requiere_revision: bool
    error: str | None


def _puede_avanzar_tras_ia(reclamo: Reclamo, state: EstadoPipeline) -> bool:
    """Sólo deja atrás PENDIENTE_REVISION si la clasificación fue del LLM y no hay que derivar."""
    if state.get("proveedor") == "fallback":
        return False
    if (state.get("confianza") or 0) < UMBRAL_CONFIANZA_DERIVACION:
        return False
    der = evaluar_derivacion(
        descripcion=reclamo.descripcion,
        categoria=state.get("categoria") or reclamo.categoria,
        confianza=state.get("confianza"),
    )
    return not der.derivar


def ejecutar_pipeline(db: Session, reclamo: Reclamo) -> EstadoPipeline:
    """Corre el grafo sobre un reclamo. Aplica clasificación y persiste estimación (sin commit)."""
    inicial: EstadoPipeline = {
        "reclamo_id": reclamo.id,
        "pasos": [],
        "duplicados": [],
        "estimacion_id": None,
        "requiere_revision": bool(reclamo.requiere_revision),
    }
    grafo = _compilar(db)
    return grafo.invoke(inicial)


def _compilar(db: Session):
    from langgraph.graph import END, START, StateGraph

    def nodo_clasificar(state: EstadoPipeline) -> dict[str, Any]:
        reclamo = db.get(Reclamo, state["reclamo_id"])
        if reclamo is None:
            return {"error": "Reclamo no encontrado", "pasos": [*state.get("pasos", []), "error"]}
        try:
            resultado = clasificacion.clasificar_reclamo(reclamo)
            clasificacion.aplicar_clasificacion(reclamo, resultado)
        except Exception:
            logger.exception(
                "Clasificación LLM falló en reclamo %s; se mantiene la del alta",
                reclamo.id,
            )
            resultado = clasificacion.ResultadoClasificacion(
                categoria=reclamo.categoria,
                prioridad=reclamo.prioridad,
                confianza=0.0,
                justificacion="El proveedor de IA no respondió; se mantiene categoría y prioridad del alta.",
                proveedor="fallback",
            )
        registro.registrar(
            db,
            tipo=TipoRecomendacionIA.CLASIFICACION,
            payload={
                "categoria": resultado.categoria,
                "prioridad": resultado.prioridad.value,
                "justificacion": resultado.justificacion,
                "aplicada": True,
                "orquestado": True,
            },
            reclamo_id=reclamo.id,
            proveedor=resultado.proveedor,
            confianza=resultado.confianza,
        )
        db.flush()
        return {
            "pasos": [*state.get("pasos", []), "clasificar"],
            "categoria": resultado.categoria,
            "prioridad": resultado.prioridad.value,
            "confianza": resultado.confianza,
            "justificacion": resultado.justificacion,
            "proveedor": resultado.proveedor,
        }

    def nodo_duplicados(state: EstadoPipeline) -> dict[str, Any]:
        if state.get("error"):
            return {}
        reclamo = db.get(Reclamo, state["reclamo_id"])
        candidatos = duplicados.buscar_duplicados(db, reclamo)
        payload = [
            {
                "reclamo_id": c.reclamo_id,
                "similitud": c.similitud,
                "categoria": c.categoria,
                "nombre_escuela": c.nombre_escuela,
                "estado": c.estado.value,
                "descripcion": c.descripcion,
            }
            for c in candidatos
        ]
        registro.registrar(
            db,
            tipo=TipoRecomendacionIA.DUPLICADOS,
            payload={"orquestado": True, "candidatos": payload},
            reclamo_id=reclamo.id,
            proveedor="jaccard",
        )
        return {
            "pasos": [*state.get("pasos", []), "duplicados"],
            "duplicados": payload,
        }

    def nodo_estimar(state: EstadoPipeline) -> dict[str, Any]:
        if state.get("error"):
            return {}
        reclamo = db.get(Reclamo, state["reclamo_id"])
        # No se salta PENDIENTE_REVISION si la IA no clasificó de verdad
        # (LLM caído, confianza baja) o si el caso pide operador.
        transicionar = _puede_avanzar_tras_ia(reclamo, state)
        try:
            est = estimacion.generar_estimacion(db, reclamo, transicionar=transicionar)
        except Exception:
            logger.exception("Estimación falló en reclamo %s", reclamo.id)
            return {"pasos": [*state.get("pasos", []), "estimar_error"]}
        requiere = bool(est.requiere_revision or reclamo.requiere_revision)
        return {
            "pasos": [*state.get("pasos", []), "estimar"],
            "estimacion_id": est.id,
            "total": float(est.total),
            "requiere_revision": requiere,
        }

    builder = StateGraph(EstadoPipeline)
    # Los nombres de nodo no pueden coincidir con claves del estado (LangGraph).
    builder.add_node("nodo_clasificar", nodo_clasificar)
    builder.add_node("nodo_buscar_similares", nodo_duplicados)
    builder.add_node("nodo_estimar", nodo_estimar)
    builder.add_edge(START, "nodo_clasificar")
    builder.add_edge("nodo_clasificar", "nodo_buscar_similares")
    builder.add_edge("nodo_buscar_similares", "nodo_estimar")
    builder.add_edge("nodo_estimar", END)
    return builder.compile()
