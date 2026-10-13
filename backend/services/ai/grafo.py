"""Grafo LangGraph del pipeline IA: clasificar → duplicados → estimar."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from models.reclamo import Reclamo
from models.recomendacion_ia import TipoRecomendacionIA
from services.ai import clasificacion, duplicados, estimacion, registro
from services.ai.contexto_reclamo import texto_para_ia
from services.ai.derivacion import UMBRAL_CONFIANZA_DERIVACION, evaluar_derivacion

logger = logging.getLogger(__name__)


class EstadoPipeline(TypedDict, total=False):
    reclamo_id: int
    pasos: list[str]
    categoria: str
    prioridad: str
    confianza: float
    justificacion: str
    razonamiento: str
    proveedor: str
    duplicados: list[dict[str, Any]]
    estimacion_id: int | None
    total: float | None
    requiere_revision: bool
    error: str | None


def _puede_avanzar_tras_ia(db: Session, reclamo: Reclamo, state: EstadoPipeline) -> bool:
    """Sólo deja atrás PENDIENTE_REVISION si la clasificación fue del LLM y no hay que derivar."""
    if state.get("proveedor") == "fallback":
        return False
    if (state.get("confianza") or 0) < UMBRAL_CONFIANZA_DERIVACION:
        return False
    der = evaluar_derivacion(
        descripcion=texto_para_ia(reclamo, db),
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


def _clasificar_con_agente(db: Session, reclamo: Reclamo):
    """Corre el agente con herramientas y devuelve un ResultadoClasificacion.

    Devuelve None si el agente no está disponible o falla, para que el caller use
    la clasificación simple como fallback. Aplica la categoría/prioridad al reclamo.
    """
    from models.reclamo import PrioridadReclamo
    from services.ai import agente as agente_svc
    from services.ai.clasificacion import ResultadoClasificacion
    from services.ai.prompts import CATEGORIAS_VALIDAS

    try:
        res = agente_svc.analizar_reclamo(db, reclamo)
    except Exception:
        logger.warning("Agente no disponible en reclamo %s; uso clasificación simple", reclamo.id)
        return None

    analisis = res.analisis or {}
    categoria = str(analisis.get("categoria") or "").strip()
    if categoria not in CATEGORIAS_VALIDAS:
        categoria = "Otro"
    try:
        prioridad = PrioridadReclamo(str(analisis.get("prioridad") or "MEDIA").strip().upper())
    except ValueError:
        prioridad = PrioridadReclamo.MEDIA
    try:
        confianza = max(0.0, min(1.0, float(analisis.get("confianza", 0.5))))
    except (TypeError, ValueError):
        confianza = 0.5

    resultado = ResultadoClasificacion(
        categoria=categoria,
        prioridad=prioridad,
        confianza=confianza,
        justificacion=str(analisis.get("resumen_para_operador") or "").strip(),
        proveedor=res.proveedor or "agente",
        razonamiento=str(analisis.get("razonamiento") or "").strip(),
    )
    clasificacion.aplicar_clasificacion(reclamo, resultado)
    return resultado


def _compilar(db: Session):
    from langgraph.graph import END, START, StateGraph

    def nodo_clasificar(state: EstadoPipeline) -> dict[str, Any]:
        reclamo = db.get(Reclamo, state["reclamo_id"])
        if reclamo is None:
            return {"error": "Reclamo no encontrado", "pasos": [*state.get("pasos", []), "error"]}

        # Primero intentamos el AGENTE con herramientas: consulta el padrón y reclamos
        # similares reales antes de clasificar, así la categoría/prioridad quedan
        # fundamentadas en datos del sistema y no solo en el texto. Si el agente o el
        # LLM fallan, se cae a la clasificación simple (y de ahí al fallback del alta).
        resultado = _clasificar_con_agente(db, reclamo)
        if resultado is None:
            try:
                resultado = clasificacion.clasificar_reclamo(reclamo, db)
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
                "razonamiento": resultado.razonamiento,
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
            "razonamiento": resultado.razonamiento,
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
        transicionar = _puede_avanzar_tras_ia(db, reclamo, state)
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
