"""Detección de reclamos duplicados / similares (RF09 / CU-01)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.ai import config as ai_config
from core.ai.factory import get_llm_provider
from models.reclamo import EstadoReclamo, Reclamo

logger = logging.getLogger(__name__)

_ESTADOS_FINALES = frozenset(
    {
        EstadoReclamo.FINALIZADO,
        EstadoReclamo.RECHAZADO,
        EstadoReclamo.CANCELADO,
    }
)

UMBRAL_SEMANTICO = 0.5

# Cuántos candidatos abiertos de la misma escuela se mandan al LLM como máximo.
# Con modo semántico no prefiltramos por Jaccard, así que acotamos por acá.
MAX_CANDIDATOS_LLM = 25

_SCHEMA_SEMANTICO = {
    "task": "duplicados_semanticos",
    "scores": [{"reclamo_id": 0, "similitud_semantica": 0.0}],
}


@dataclass(frozen=True)
class CandidatoDuplicado:
    reclamo_id: int
    nombre_escuela: str
    categoria: str
    estado: EstadoReclamo
    descripcion: str
    similitud: float


def _tokens(texto: str) -> set[str]:
    return {t for t in re.findall(r"[a-záéíóúñü0-9]{3,}", texto.lower())}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def buscar_duplicados(
    db: Session,
    reclamo: Reclamo,
    *,
    umbral: float = 0.35,
    limite: int = 10,
) -> list[CandidatoDuplicado]:
    """Busca reclamos que describan el mismo problema en la misma escuela.

    Estrategia:
    - Modo semántico ON (AI_DUPLICADOS_SEMANTICOS=true, recomendado con Gemini):
      NO prefiltra por Jaccard. Manda TODOS los candidatos abiertos de la escuela al
      LLM para que decida cuáles son el mismo problema, aunque estén redactados
      distinto. Jaccard queda solo como señal de respaldo si el LLM falla.
    - Modo semántico OFF (sin LLM): usa Jaccard con `umbral` como filtro.
    """
    escuela = reclamo.nombre_escuela.strip()

    candidatos_db = (
        db.query(Reclamo)
        .filter(
            Reclamo.id != reclamo.id,
            Reclamo.nombre_escuela.ilike(escuela),
            Reclamo.estado.notin_(list(_ESTADOS_FINALES)),
        )
        .order_by(Reclamo.fecha_creacion.desc())
        .limit(50)
        .all()
    )
    if not candidatos_db:
        return []

    semantico = ai_config.duplicados_semanticos_enabled()

    if semantico:
        # Sin prefiltro Jaccard: el LLM ve todos los candidatos (acotados) y decide.
        preseleccion = _preparar_candidatos(reclamo, candidatos_db, con_jaccard=True)
        preseleccion = preseleccion[:MAX_CANDIDATOS_LLM]
        try:
            return _evaluar_semantico(reclamo, preseleccion)[:limite]
        except Exception:
            logger.exception("Fallo duplicados semánticos; se cae a Jaccard")
            # Fallback: quedarse con los que Jaccard considera similares.
            return _filtrar_por_jaccard(preseleccion, umbral)[:limite]

    # Modo sin LLM: Jaccard puro.
    preseleccion = _preparar_candidatos(reclamo, candidatos_db, con_jaccard=True)
    return _filtrar_por_jaccard(preseleccion, umbral)[:limite]


def _preparar_candidatos(
    reclamo: Reclamo,
    candidatos_db: list[Reclamo],
    *,
    con_jaccard: bool,
) -> list[CandidatoDuplicado]:
    """Convierte filas de Reclamo en CandidatoDuplicado, calculando Jaccard como pista."""
    tokens_origen = _tokens(reclamo.descripcion)
    preparados: list[CandidatoDuplicado] = []
    for otro in candidatos_db:
        sim = 0.0
        if con_jaccard:
            sim = _jaccard(tokens_origen, _tokens(otro.descripcion))
            if (
                reclamo.categoria
                and otro.categoria
                and reclamo.categoria.lower() == otro.categoria.lower()
                and reclamo.categoria.lower() != "sin clasificar"
            ):
                sim = min(1.0, sim + 0.1)
        preparados.append(
            CandidatoDuplicado(
                reclamo_id=otro.id,
                nombre_escuela=otro.nombre_escuela,
                categoria=otro.categoria,
                estado=otro.estado,
                descripcion=otro.descripcion,
                similitud=round(sim, 3),
            )
        )
    preparados.sort(key=lambda c: c.similitud, reverse=True)
    return preparados


def _filtrar_por_jaccard(
    candidatos: list[CandidatoDuplicado], umbral: float
) -> list[CandidatoDuplicado]:
    return [c for c in candidatos if c.similitud >= umbral]


def _evaluar_semantico(
    reclamo: Reclamo, candidatos: list[CandidatoDuplicado]
) -> list[CandidatoDuplicado]:
    """Le pide al LLM (ej. Gemini) que puntúe qué candidatos son el MISMO problema.

    A diferencia del enfoque viejo, no asume que los candidatos ya pasaron un
    prefiltro Jaccard: el LLM evalúa todos, así detecta duplicados descritos con
    palabras distintas. Devuelve solo los que superan UMBRAL_SEMANTICO.
    """
    if not candidatos:
        return []

    provider = get_llm_provider()
    lista = "\n".join(
        f"- id={c.reclamo_id} categoria={c.categoria or 'sin clasificar'}: "
        f"{c.descripcion[:300]}"
        for c in candidatos
    )
    user = (
        f"RECLAMO NUEVO (a cargar) en la escuela «{reclamo.nombre_escuela}»:\n"
        f"categoria={reclamo.categoria or 'sin clasificar'}\n"
        f"descripcion: {reclamo.descripcion}\n\n"
        f"RECLAMOS YA EXISTENTES en la misma escuela (candidatos):\n{lista}\n\n"
        "Para CADA candidato devolvé similitud_semantica entre 0 y 1, donde:\n"
        "- 1.0 = describe el MISMO problema físico concreto (misma falla, mismo lugar), "
        "aunque esté redactado con otras palabras.\n"
        "- 0.0 = es un problema distinto.\n"
        "Considerá que dos textos pueden referirse al mismo problema aunque usen "
        "sinónimos o distinto nivel de detalle (ej: «pérdida de agua en el baño» y "
        "«gotea la canilla del sanitario»). No exijas que compartan palabras."
    )
    raw = provider.complete_json(
        system=(
            "Sos un detector de reclamos duplicados de infraestructura escolar. "
            "Comparás un reclamo nuevo contra reclamos existentes de la misma escuela "
            "y decidís cuáles describen el mismo problema. Respondé SOLO JSON con la "
            "clave 'scores': una lista de {reclamo_id, similitud_semantica}."
        ),
        user=user,
        schema_hint=_SCHEMA_SEMANTICO,
    )
    scores_raw = raw.get("scores") or []
    score_map: dict[int, float] = {}
    for item in scores_raw:
        if not isinstance(item, dict):
            continue
        try:
            rid = int(item.get("reclamo_id"))
            score = float(item.get("similitud_semantica", 0))
        except (TypeError, ValueError):
            continue
        score_map[rid] = max(0.0, min(1.0, score))

    # Si el LLM no devolvió nada usable, caemos a Jaccard como respaldo.
    if not score_map:
        raise ValueError("El LLM no devolvió scores de duplicados usables")

    refinados: list[CandidatoDuplicado] = []
    for c in candidatos:
        sim = score_map.get(c.reclamo_id)
        if sim is None:
            continue
        if sim >= UMBRAL_SEMANTICO:
            refinados.append(
                CandidatoDuplicado(
                    reclamo_id=c.reclamo_id,
                    nombre_escuela=c.nombre_escuela,
                    categoria=c.categoria,
                    estado=c.estado,
                    descripcion=c.descripcion,
                    similitud=round(sim, 3),
                )
            )
    refinados.sort(key=lambda c: c.similitud, reverse=True)
    return refinados
