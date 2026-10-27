"""Ranking de contratistas sugeridos para un reclamo (solo sugerencia)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from models.contratista import Contratista
from models.presupuesto import Presupuesto
from models.reclamo import Reclamo
from services.baja_contratistas import solo_activos
from services.estados_reclamo import ESTADOS_FINALES

PUNTOS_ESPECIALIDAD = 50
PUNTOS_POR_ESTRELLA = 10
PENALIZACION_CARGA = 5


@dataclass(frozen=True)
class ContratistaSugerido:
    contratista_id: int
    nombre_empresa: str
    especialidad: str
    calificacion: int
    carga_activa: int
    score: int
    motivos: list[str]


def _normalizar(texto: str) -> str:
    return (texto or "").strip().lower()


def sugerir_para_reclamo(db: Session, reclamo: Reclamo) -> list[ContratistaSugerido]:
    contratistas = (
        solo_activos(db.query(Contratista)).order_by(Contratista.nombre_empresa).all()
    )
    if not contratistas:
        return []

    presupuestos = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.reclamo))
        .all()
    )
    carga_por_id: dict[int, int] = {c.id: 0 for c in contratistas}
    for p in presupuestos:
        if p.reclamo is None or p.reclamo.estado in ESTADOS_FINALES:
            continue
        carga_por_id[p.contratista_id] = carga_por_id.get(p.contratista_id, 0) + 1

    categoria = _normalizar(reclamo.categoria)
    resultados: list[ContratistaSugerido] = []
    for c in contratistas:
        especialidad = _normalizar(c.especialidad)
        carga = carga_por_id.get(c.id, 0)
        score = c.calificacion * PUNTOS_POR_ESTRELLA
        motivos = [f"Calificación {c.calificacion}/5"]

        if especialidad and categoria and especialidad == categoria:
            score += PUNTOS_ESPECIALIDAD
            motivos.append("Especialidad coincide con la categoría")
        elif especialidad and categoria and (
            especialidad in categoria or categoria in especialidad
        ):
            score += PUNTOS_ESPECIALIDAD // 2
            motivos.append("Especialidad relacionada con la categoría")

        if carga:
            score -= carga * PENALIZACION_CARGA
            motivos.append(f"{carga} obra(s) activa(s)")
        else:
            motivos.append("Sin obras activas")

        resultados.append(
            ContratistaSugerido(
                contratista_id=c.id,
                nombre_empresa=c.nombre_empresa,
                especialidad=c.especialidad,
                calificacion=c.calificacion,
                carga_activa=carga,
                score=score,
                motivos=motivos,
            )
        )

    resultados.sort(key=lambda s: (-s.score, s.nombre_empresa))
    return resultados
