"""Sincroniza referencia_costo desde presupuestos del sistema (puente hasta históricos del Consejo)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from models.presupuesto import Presupuesto
from models.reclamo import EstadoReclamo
from models.referencia_costo import ReferenciaCosto

ESTADOS_HISTORICOS = frozenset(
    {
        EstadoReclamo.APROBADO,
        EstadoReclamo.EN_EJECUCION,
        EstadoReclamo.FINALIZADO,
    }
)


@dataclass(frozen=True)
class ResultadoSyncHistoricos:
    creadas: int
    actualizadas: int


def sync_desde_presupuestos(db: Session) -> ResultadoSyncHistoricos:
    """Upsert por fuente=presupuesto:{id} a partir de presupuestos de reclamos avanzados."""
    presupuestos = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.items), joinedload(Presupuesto.reclamo))
        .all()
    )

    creadas = 0
    actualizadas = 0
    for p in presupuestos:
        reclamo = p.reclamo
        if reclamo is None or reclamo.estado not in ESTADOS_HISTORICOS:
            continue

        total = sum(
            (item.cantidad * item.costo_unitario for item in p.items),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        if total <= 0:
            continue

        fuente = f"presupuesto:{p.id}"
        descripcion = reclamo.descripcion
        if p.observaciones:
            descripcion = f"{descripcion} | {p.observaciones}"

        fecha_ref = p.fecha.date() if p.fecha is not None else None
        existente = (
            db.query(ReferenciaCosto).filter(ReferenciaCosto.fuente == fuente).first()
        )
        if existente:
            existente.categoria = reclamo.categoria
            existente.descripcion = descripcion
            existente.monto_ars = total
            if fecha_ref is not None:
                existente.fecha_referencia = fecha_ref
            existente.unidad = "presupuesto"
            existente.activo = True
            actualizadas += 1
        else:
            kwargs = dict(
                categoria=reclamo.categoria,
                descripcion=descripcion,
                monto_ars=total,
                unidad="presupuesto",
                fuente=fuente,
                activo=True,
            )
            if fecha_ref is not None:
                kwargs["fecha_referencia"] = fecha_ref
            db.add(ReferenciaCosto(**kwargs))
            creadas += 1

    return ResultadoSyncHistoricos(creadas=creadas, actualizadas=actualizadas)
