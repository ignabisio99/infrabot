"""Qué reclamos puede ver y presupuestar cada usuario.

Admins e inspectores ven todos. Un contratista, solo aquellos a los que lo convocaron a
presupuestar (o en los que ya tiene una oferta, ej. una que le asignó el organismo): si
no, alcanzaría con saber el ID para ver los datos de la escuela o mandar un presupuesto.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Query, Session

from models.contratista import Contratista
from models.presupuesto import Presupuesto
from models.reclamo import Reclamo
from models.solicitud_presupuesto import SolicitudPresupuesto
from models.usuario import TipoUsuario, Usuario

SIN_ACCESO = "No fuiste convocado a presupuestar este reclamo."


def ficha_de(db: Session, usuario: Usuario) -> Contratista | None:
    return db.query(Contratista).filter(Contratista.usuario_id == usuario.id).first()


def _ids_convocados(db: Session, contratista_id: int):
    solicitados = db.query(SolicitudPresupuesto.reclamo_id).filter(
        SolicitudPresupuesto.contratista_id == contratista_id
    )
    con_oferta = db.query(Presupuesto.reclamo_id).filter(
        Presupuesto.contratista_id == contratista_id
    )
    return solicitados.union(con_oferta)


def fue_convocado(db: Session, reclamo_id: int, contratista_id: int) -> bool:
    return (
        db.query(SolicitudPresupuesto)
        .filter(
            SolicitudPresupuesto.reclamo_id == reclamo_id,
            SolicitudPresupuesto.contratista_id == contratista_id,
        )
        .first()
        is not None
        or db.query(Presupuesto)
        .filter(Presupuesto.reclamo_id == reclamo_id, Presupuesto.contratista_id == contratista_id)
        .first()
        is not None
    )


def _ve_todos(usuario: Usuario) -> bool:
    return usuario.es_admin or usuario.es_inspector


def exigir_acceso(db: Session, reclamo_id: int, usuario: Usuario) -> None:
    """403 si el usuario no puede ver este reclamo."""
    if _ve_todos(usuario):
        return
    if usuario.tipo is TipoUsuario.CONTRATISTA:
        ficha = ficha_de(db, usuario)
        if ficha is not None and fue_convocado(db, reclamo_id, ficha.id):
            return
    raise HTTPException(status_code=403, detail=SIN_ACCESO)


def filtrar_visibles(db: Session, query: Query, usuario: Usuario) -> Query:
    """Acota un listado de reclamos a los que el usuario puede ver."""
    if _ve_todos(usuario):
        return query
    ficha = ficha_de(db, usuario) if usuario.tipo is TipoUsuario.CONTRATISTA else None
    if ficha is None:
        return query.filter(False)
    return query.filter(Reclamo.id.in_(_ids_convocados(db, ficha.id)))
