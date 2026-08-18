"""Detección de reclamos duplicados / similares (RF09 / CU-01)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from models.reclamo import EstadoReclamo, Reclamo

# Estados terminales (misma regla que services.estados_reclamo).
_ESTADOS_FINALES = frozenset(
    {
        EstadoReclamo.FINALIZADO,
        EstadoReclamo.RECHAZADO,
        EstadoReclamo.CANCELADO,
    }
)


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
    """Busca reclamos activos en la misma escuela con descripción similar.

    Heurística léxica (Jaccard sobre tokens). Expandible a embeddings / LLM después.
    """
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
        # Bonus si la categoría coincide (cuando ya está clasificada).
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
    return resultados[:limite]
