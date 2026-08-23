"""Grafo LangGraph del pipeline IA: clasificar → duplicados → estimar."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from models.reclamo import Reclamo
from models.recomendacion_ia import TipoRecomendacionIA
from services.ai import clasificacion, duplicados, estimacion, registro

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
        resultado = clasificacion.clasificar_reclamo(reclamo)
        clasificacion.aplicar_clasificacion(reclamo, resultado)
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
        est = estimacion.generar_estimacion(db, reclamo, transicionar=True)
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
