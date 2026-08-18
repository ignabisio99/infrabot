"""Búsqueda de costos históricos de referencia (tabla placeholder)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from models.referencia_costo import ReferenciaCosto
from services.ai import inflacion


def _tokens(texto: str) -> set[str]:
    return {t for t in re.findall(r"[a-záéíóúñü0-9]{3,}", texto.lower())}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass(frozen=True)
class ReferenciaAjustada:
    id: int
    categoria: str
    descripcion: str
    monto_original: Decimal
    monto_ajustado: Decimal
    similitud: float
    fecha_referencia: str
    meta_inflacion: dict


def buscar_referencias(
    db: Session,
    *,
    categoria: str,
    descripcion: str,
    limit: int = 5,
    umbral: float = 0.15,
) -> list[ReferenciaAjustada]:
    """Misma categoría + similitud Jaccard; montos ajustados por IPC."""
    tokens_q = _tokens(descripcion)
    candidatos = (
        db.query(ReferenciaCosto)
        .filter(
            ReferenciaCosto.activo.is_(True),
            ReferenciaCosto.categoria.ilike(categoria.strip()),
        )
        .all()
    )
    # Si no hay en esa categoría, buscar en todas (menos estricto).
    if not candidatos:
        candidatos = db.query(ReferenciaCosto).filter(ReferenciaCosto.activo.is_(True)).all()

    resultados: list[ReferenciaAjustada] = []
    for ref in candidatos:
        sim = _jaccard(tokens_q, _tokens(ref.descripcion))
        if categoria and ref.categoria.lower() == categoria.strip().lower():
            sim = min(1.0, sim + 0.15)
        if sim < umbral and len(candidatos) > 3:
            continue
        monto_aj, meta = inflacion.ajustar_monto(db, Decimal(ref.monto_ars), ref.fecha_referencia)
        resultados.append(
            ReferenciaAjustada(
                id=ref.id,
                categoria=ref.categoria,
                descripcion=ref.descripcion,
                monto_original=Decimal(ref.monto_ars),
                monto_ajustado=monto_aj,
                similitud=round(sim, 3),
                fecha_referencia=ref.fecha_referencia.isoformat(),
                meta_inflacion=meta,
            )
        )

    resultados.sort(key=lambda r: (r.similitud, r.monto_ajustado), reverse=True)
    return resultados[:limit]


def confianza_por_precedentes(referencias: list[ReferenciaAjustada]) -> float:
    """Confianza heurística según cantidad y similitud de precedentes (CU-02)."""
    if not referencias:
        return 0.25
    n = len(referencias)
    avg_sim = sum(r.similitud for r in referencias) / n
    base = {1: 0.4, 2: 0.55, 3: 0.68}.get(n, 0.78)
    return round(min(0.92, base + avg_sim * 0.15), 3)
