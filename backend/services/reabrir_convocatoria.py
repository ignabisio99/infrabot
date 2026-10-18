"""Salir de pendiente de intervención: convocar de nuevo o elegir una oferta ya enviada."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from core.whatsapp_client import enviar_mensaje
from core.whatsapp_handler import reiniciar_conversacion
from models.contratista import Contratista
from models.historial_estado_reclamo import OrigenCambioEstado
from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.recordatorio_contratista import RecordatorioContratista
from models.visita import EstadoVisita, Visita
from services import coordinacion_visita, estados_presupuesto, estados_reclamo
from services.seguimiento import quitar_lineas_marca_intervencion

logger = logging.getLogger(__name__)

ESTADOS_REABRIR = frozenset({EstadoReclamo.PENDIENTE_INTERVENCION})

MOTIVO_CONVOCAR = (
    "El contratista no respondió los recordatorios de avance. "
    "Se cancela el presupuesto aprobado para convocar a otro."
)

MOTIVO_ASIGNAR = (
    "El contratista no respondió los recordatorios de avance. "
    "Se elige una oferta que ya había sido enviada."
)


class ReaperturaInvalida(Exception):
    """No se puede reabrir la convocatoria ni reasignar en este reclamo."""


class OfertaReutilizable:
    def __init__(
        self,
        presupuesto_id: int,
        contratista_id: int,
        nombre_empresa: str,
        monto: Decimal,
        estado: EstadoPresupuesto,
    ):
        self.presupuesto_id = presupuesto_id
        self.contratista_id = contratista_id
        self.nombre_empresa = nombre_empresa
        self.monto = monto
        self.estado = estado


def listar_ofertas_reutilizables(db: Session, reclamo: Reclamo) -> list[OfertaReutilizable]:
    filas = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.contratista), joinedload(Presupuesto.items))
        .filter(
            Presupuesto.reclamo_id == reclamo.id,
            Presupuesto.estado == EstadoPresupuesto.NO_SELECCIONADO,
        )
        .all()
    )
    ofertas = []
    for presupuesto in filas:
        monto = sum((item.cantidad * item.costo_unitario for item in presupuesto.items), Decimal("0"))
        nombre = (
            presupuesto.contratista.nombre_empresa if presupuesto.contratista else "Contratista"
        )
        ofertas.append(
            OfertaReutilizable(
                presupuesto_id=presupuesto.id,
                contratista_id=presupuesto.contratista_id,
                nombre_empresa=nombre,
                monto=monto,
                estado=presupuesto.estado,
            )
        )
    return ofertas


def reabrir_por_inaccion(
    db: Session,
    reclamo: Reclamo,
    *,
    usuario_id: int | None = None,
    motivo: str | None = None,
) -> Reclamo:
    texto = (motivo or MOTIVO_CONVOCAR).strip()
    aprobado = _exigir_aprobado(db, reclamo)
    contratista = aprobado.contratista
    _rechazar_aprobado_y_limpiar(db, reclamo, aprobado, texto, usuario_id)
    estados_reclamo.cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.PENDIENTE_PRESUPUESTO,
        motivo=texto,
        usuario_id=usuario_id,
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    _avisar_vuelta_a_presupuestos(reclamo, contratista)
    return reclamo


def asignar_oferta_existente(
    db: Session,
    reclamo: Reclamo,
    presupuesto_id: int,
    *,
    usuario_id: int | None = None,
    motivo: str | None = None,
) -> Reclamo:
    texto = (motivo or MOTIVO_ASIGNAR).strip()
    aprobado = _exigir_aprobado(db, reclamo)
    elegido = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.reclamo), joinedload(Presupuesto.contratista))
        .filter(Presupuesto.id == presupuesto_id)
        .first()
    )
    if elegido is None or elegido.reclamo_id != reclamo.id:
        raise ReaperturaInvalida("Ese presupuesto no es de este reclamo")
    if elegido.estado != EstadoPresupuesto.NO_SELECCIONADO:
        raise ReaperturaInvalida(
            "Solo se puede elegir una oferta que había quedado sin seleccionar"
        )

    anterior = aprobado.contratista
    _rechazar_aprobado_y_limpiar(db, reclamo, aprobado, texto, usuario_id)
    estados_presupuesto.cambiar_estado(
        db,
        elegido,
        EstadoPresupuesto.APROBADO,
        motivo=texto,
        usuario_id=usuario_id,
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    estados_reclamo.cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.APROBADO,
        motivo=texto,
        usuario_id=usuario_id,
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    coordinacion_visita.iniciar_coordinacion(db, reclamo, elegido.contratista)
    _avisar_cambio_de_contratista(reclamo, anterior, elegido.contratista)
    return reclamo


def _exigir_aprobado(db: Session, reclamo: Reclamo) -> Presupuesto:
    if reclamo.estado not in ESTADOS_REABRIR:
        raise ReaperturaInvalida(
            f'El reclamo está en estado "{reclamo.estado.etiqueta}" y no se puede volver a convocar así'
        )
    aprobado = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.reclamo), joinedload(Presupuesto.contratista))
        .filter(
            Presupuesto.reclamo_id == reclamo.id,
            Presupuesto.estado == EstadoPresupuesto.APROBADO,
        )
        .first()
    )
    if aprobado is None:
        raise ReaperturaInvalida("No hay un presupuesto aprobado para cancelar")
    return aprobado


def _rechazar_aprobado_y_limpiar(
    db: Session,
    reclamo: Reclamo,
    aprobado: Presupuesto,
    texto: str,
    usuario_id: int | None,
) -> None:
    estados_presupuesto.cambiar_estado(
        db,
        aprobado,
        EstadoPresupuesto.RECHAZADO,
        motivo=texto,
        usuario_id=usuario_id,
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    visitas = db.query(Visita).filter(Visita.reclamo_id == reclamo.id).all()
    for visita in visitas:
        if visita.estado != EstadoVisita.CANCELADA:
            visita.estado = EstadoVisita.CANCELADA
    reclamo.observaciones = quitar_lineas_marca_intervencion(reclamo.observaciones)
    db.query(RecordatorioContratista).filter(
        RecordatorioContratista.reclamo_id == reclamo.id
    ).delete(synchronize_session=False)


def _avisar_vuelta_a_presupuestos(reclamo: Reclamo, contratista: Contratista | None) -> None:
    escuela = reclamo.nombre_escuela or "la escuela"
    empresa = (contratista.nombre_empresa if contratista else None) or "el contratista"

    if reclamo.telefono_creador:
        _enviar(
            reclamo.telefono_creador,
            (
                f"📋 *Reclamo #{reclamo.id} — volvió a presupuestos*\n\n"
                f"🏫 Escuela: {escuela}\n\n"
                f"El contratista *{empresa}* no respondió los recordatorios de avance, "
                "así que se canceló el presupuesto aprobado. El reclamo vuelve a la fase "
                "de presupuestos para convocar a otro."
            ),
        )

    _avisar_contratista_fuera(reclamo, contratista, escuela)


def _avisar_cambio_de_contratista(
    reclamo: Reclamo,
    anterior: Contratista | None,
    nuevo: Contratista | None,
) -> None:
    escuela = reclamo.nombre_escuela or "la escuela"
    empresa_nueva = (nuevo.nombre_empresa if nuevo else None) or "otro contratista"

    if reclamo.telefono_creador:
        _enviar(
            reclamo.telefono_creador,
            (
                f"📋 *Reclamo #{reclamo.id} — cambia el contratista*\n\n"
                f"🏫 Escuela: {escuela}\n\n"
                "El contratista asignado no respondió los recordatorios de avance. "
                f"Se eligió la oferta de *{empresa_nueva}* y se va a coordinar una nueva visita."
            ),
        )

    _avisar_contratista_fuera(reclamo, anterior, escuela)


def _avisar_contratista_fuera(
    reclamo: Reclamo, contratista: Contratista | None, escuela: str
) -> None:
    telefono = contratista.telefono if contratista else None
    if not telefono:
        return
    reiniciar_conversacion(telefono)
    _enviar(
        telefono,
        (
            f"📋 *Reclamo #{reclamo.id} — ya no estás asignado*\n\n"
            f"🏫 Escuela: {escuela}\n\n"
            "Como no hubo respuesta a los recordatorios de avance, se canceló el "
            "presupuesto aprobado. Ya no estás asignado a este trabajo."
        ),
    )


def _enviar(to: str, body: str) -> None:
    try:
        enviar_mensaje(to, body)
    except Exception:
        logger.exception("No se pudo avisar por WhatsApp a %s", to)
