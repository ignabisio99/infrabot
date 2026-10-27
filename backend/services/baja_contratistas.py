"""Dar de baja un contratista sin perder su historial.

No se borra: sus presupuestos, visitas y convocatorias son el expediente de los reclamos
en que trabajó. Dado de baja no aparece para convocar, no se le puede asignar una oferta
y no puede cargar presupuestos. Se puede reactivar.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Query, Session

from models.contratista import Contratista
from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import Reclamo
from services.estados_presupuesto import ESTADOS_VIGENTES
from services.estados_reclamo import ESTADOS_FINALES

ESTADOS_EN_CURSO = ESTADOS_VIGENTES | {EstadoPresupuesto.APROBADO}


class ContratistaConTrabajoEnCurso(Exception):
    def __init__(self, contratista: Contratista, reclamo_ids: list[int]):
        self.reclamo_ids = reclamo_ids
        reclamos = ", ".join(f"#{reclamo_id}" for reclamo_id in reclamo_ids)
        super().__init__(
            f"No se puede dar de baja a {contratista.nombre_empresa}: tiene presupuestos en "
            f"curso en {'el reclamo' if len(reclamo_ids) == 1 else 'los reclamos'} {reclamos}. "
            "Primero rechazá su oferta, cambiá de contratista o cancelá el reclamo."
        )


class ContratistaDadoDeBaja(Exception):
    def __init__(self, contratista: Contratista):
        super().__init__(f"{contratista.nombre_empresa} está dado de baja")


def solo_activos(query: Query) -> Query:
    return query.filter(Contratista.fecha_baja.is_(None))


def reclamos_en_curso(db: Session, contratista: Contratista) -> list[int]:
    """Reclamos abiertos donde tiene una oferta en evaluación o aprobada."""
    filas = (
        db.query(Presupuesto.reclamo_id)
        .join(Reclamo, Reclamo.id == Presupuesto.reclamo_id)
        .filter(
            Presupuesto.contratista_id == contratista.id,
            Presupuesto.estado.in_(ESTADOS_EN_CURSO),
            Reclamo.estado.notin_(ESTADOS_FINALES),
        )
        .distinct()
        .order_by(Presupuesto.reclamo_id)
    )
    return [reclamo_id for (reclamo_id,) in filas]


def dar_de_baja(db: Session, contratista: Contratista) -> None:
    """No hace commit. Las convocatorias sin oferta quedan como estaban: sin poder ofertar,
    ya no hay nada que esperar de ellas."""
    if contratista.dado_de_baja:
        return
    en_curso = reclamos_en_curso(db, contratista)
    if en_curso:
        raise ContratistaConTrabajoEnCurso(contratista, en_curso)
    contratista.fecha_baja = datetime.now(timezone.utc)


def reactivar(contratista: Contratista) -> None:
    contratista.fecha_baja = None


def exigir_activo(contratista: Contratista) -> None:
    if contratista.dado_de_baja:
        raise ContratistaDadoDeBaja(contratista)
