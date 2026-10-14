"""Respuestas de avance del contratista sobre un reclamo en ejecución (CU-05)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from core import reloj
from models.comentario_reclamo import ComentarioReclamo
from models.foto_reclamo import FotoReclamo, TipoMedia
from models.presupuesto import Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.historial_estado_reclamo import OrigenCambioEstado
from models.recordatorio_contratista import RecordatorioContratista
from services import estados_reclamo
from services.seguimiento import quitar_lineas_marca_intervencion, tiene_marca_intervencion

_ESTADOS_AVANCE = frozenset(
    {EstadoReclamo.EN_EJECUCION, EstadoReclamo.PENDIENTE_INTERVENCION}
)


def _digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def mismo_numero(a: str, b: str) -> bool:
    da, db_ = _digitos(a), _digitos(b)
    if not da or not db_:
        return False
    return da[-8:] == db_[-8:]


def reclamo_en_ejecucion_de(db: Session, telefono: str) -> tuple[Reclamo, object] | None:
    """Reclamo en obra (o pendiente de intervención) cuyo contratista coincide con el teléfono."""
    reclamos = (
        db.query(Reclamo)
        .filter(Reclamo.estado.in_(_ESTADOS_AVANCE))
        .order_by(Reclamo.id.desc())
        .all()
    )
    for reclamo in reclamos:
        presupuesto = (
            db.query(Presupuesto)
            .options(joinedload(Presupuesto.contratista))
            .filter(Presupuesto.reclamo_id == reclamo.id)
            .order_by(Presupuesto.fecha.desc())
            .first()
        )
        contratista = presupuesto.contratista if presupuesto else None
        if contratista and mismo_numero(contratista.telefono, telefono):
            return reclamo, contratista
    return None


def estado_conversacion_avance(db: Session, telefono: str) -> dict | None:
    """Solo si hay un recordatorio sin responder: no deja el chat en avances para siempre."""
    hallado = reclamo_en_ejecucion_de(db, telefono)
    if hallado is None:
        return None
    reclamo, _contratista = hallado
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    if reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION:
        return {"paso": "avance_ejecucion", "reclamo_id": reclamo.id}
    if not fila or (fila.cantidad_envios or 0) < 1:
        return None
    return {"paso": "avance_ejecucion", "reclamo_id": reclamo.id}


def _marcar_actividad(db: Session, reclamo: Reclamo) -> None:
    """Reinicia el reloj de 48 h y, si estaba escalado, levanta la intervención."""
    ahora = reloj.ahora()
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    if fila is None:
        db.add(
            RecordatorioContratista(
                reclamo_id=reclamo.id,
                ultimo_envio=ahora,
                cantidad_envios=0,
            )
        )
    else:
        fila.ultimo_envio = ahora
        fila.cantidad_envios = 0
    _volver_a_ejecucion(db, reclamo)


def _volver_a_ejecucion(db: Session, reclamo: Reclamo) -> None:
    """Si estaba pendiente de intervención, el avance lo devuelve a ejecución."""
    if tiene_marca_intervencion(reclamo.observaciones):
        reclamo.observaciones = quitar_lineas_marca_intervencion(reclamo.observaciones)
    if reclamo.estado != EstadoReclamo.PENDIENTE_INTERVENCION:
        return
    estados_reclamo.cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.EN_EJECUCION,
        motivo="El contratista respondió un avance",
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    db.add(
        ComentarioReclamo(
            reclamo_id=reclamo.id,
            usuario_id=None,
            texto="[Sistema]\nEl contratista respondió. El reclamo vuelve a ejecución.",
        )
    )


def registrar_avance_texto(
    db: Session, reclamo: Reclamo, contratista, texto: str, *, termino: bool = False
) -> ComentarioReclamo:
    empresa = (contratista.nombre_empresa if contratista else "Contratista").strip()
    if termino:
        cuerpo = (
            f"[WhatsApp — {empresa}]\n"
            "El contratista reportó que el trabajo está terminado."
        )
        extra = (texto or "").strip()
        if extra and extra.lower() not in ("terminé", "termine", "finalizado", "finalicé", "finalice"):
            cuerpo = f"{cuerpo}\n{extra}"
    else:
        cuerpo = f"[WhatsApp — {empresa}]\n{(texto or '').strip()}"
    comentario = ComentarioReclamo(
        reclamo_id=reclamo.id,
        usuario_id=getattr(contratista, "usuario_id", None),
        texto=cuerpo,
    )
    db.add(comentario)
    _marcar_actividad(db, reclamo)
    db.commit()
    db.refresh(comentario)
    return comentario


def registrar_avance_media(
    db: Session, reclamo: Reclamo, url_local: str, mime_type: str
) -> FotoReclamo:
    tipo = TipoMedia.VIDEO if "video" in (mime_type or "") else TipoMedia.IMAGEN
    foto = FotoReclamo(
        reclamo_id=reclamo.id,
        nombre_archivo=url_local.split("/")[-1],
        url=url_local,
        tipo=tipo,
    )
    db.add(foto)
    _marcar_actividad(db, reclamo)
    db.commit()
    db.refresh(foto)
    return foto
