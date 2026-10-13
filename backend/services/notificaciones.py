"""Conteo de reclamos pendientes de intervención para la campanita."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.reclamo import EstadoReclamo, Reclamo


def contar_pendiente_intervencion(db: Session) -> int:
    return (
        db.query(Reclamo)
        .filter(Reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION)
        .count()
    )
