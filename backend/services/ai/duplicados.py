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
    """Jaccard primero; si AI_DUPLICADOS_SEMANTICOS=true, reordena con LLM."""
    tokens_origen = _tokens(reclamo.descripcion)
    escuela = reclamo.nombre_escuela.strip()

    candidatos = (
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

    resultados: list[CandidatoDuplicado] = []
    for otro in candidatos:
        sim = _jaccard(tokens_origen, _tokens(otro.descripcion))
        if (
            reclamo.categoria
            and otro.categoria
            and reclamo.categoria.lower() == otro.categoria.lower()
            and reclamo.categoria.lower() != "sin clasificar"
        ):
            sim = min(1.0, sim + 0.1)
        if sim >= umbral:
            resultados.append(
                CandidatoDuplicado(
                    reclamo_id=otro.id,
                    nombre_escuela=otro.nombre_escuela,
                    categoria=otro.categoria,
                    estado=otro.estado,
                    descripcion=otro.descripcion,
                    similitud=round(sim, 3),
                )
            )

    resultados.sort(key=lambda c: c.similitud, reverse=True)
    resultados = resultados[:limite]

    if ai_config.duplicados_semanticos_enabled() and resultados:
        try:
            resultados = _reordenar_semantico(reclamo, resultados)
        except Exception:
            logger.exception("Fallo duplicados semánticos; se mantiene Jaccard")

    return resultados


def _reordenar_semantico(
    reclamo: Reclamo, candidatos: list[CandidatoDuplicado]
) -> list[CandidatoDuplicado]:
    provider = get_llm_provider()
    lista = "\n".join(
        f"- id={c.reclamo_id} sim_jaccard={c.similitud}: {c.descripcion[:200]}"
        for c in candidatos
    )
    user = (
        f"Reclamo origen #{reclamo.id}:\n{reclamo.descripcion}\n\n"
        f"Candidatos:\n{lista}\n\n"
        "Devolvé similitud_semantica (0 a 1) por cada reclamo_id."
    )
    raw = provider.complete_json(
        system=(
            "Comparás si dos reclamos de infraestructura escolar describen el mismo "
            "problema. Respondé solo JSON con scores."
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

    # Si el mock/LLM no devolvió scores, usar Jaccard como similitud semántica.
    if not score_map:
        score_map = {c.reclamo_id: c.similitud for c in candidatos}

    refinados: list[CandidatoDuplicado] = []
    for c in candidatos:
        sim = score_map.get(c.reclamo_id, c.similitud)
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
