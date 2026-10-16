"""Conteos para la campanita: lo que espera una acción del administrador."""

from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo, Reclamo


def contar_pendiente_intervencion(db: Session) -> int:
    return (
        db.query(Reclamo)
        .filter(Reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION)
        .count()
    )


def contar_versiones_por_decidir(db: Session) -> int:
    """Presupuestos que volvieron corregidos tras un pedido de ajustes y esperan decisión.

    Se deduce del historial y no de un aviso guardado: deja de contar en cuanto se decide.
    """
    recibidos = (
        db.query(Presupuesto)
        .join(Presupuesto.reclamo)
        .filter(
            Presupuesto.estado == EstadoPresupuesto.RECIBIDO,
            Reclamo.estado == EstadoReclamo.EN_EVALUACION,
        )
        .options(selectinload(Presupuesto.historial_estados))
        .all()
    )
    return sum(
        1
        for p in recibidos
        if p.historial_estados
        and p.historial_estados[-1].estado_anterior is EstadoPresupuesto.AJUSTES_SOLICITADOS
    )
