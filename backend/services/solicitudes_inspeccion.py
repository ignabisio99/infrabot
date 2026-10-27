"""Pedidos de información a inspectores sobre un reclamo.

El admin elige inspectores y les pide que carguen información adicional. A cada uno le
llega por WhatsApp y por email, y además el pedido queda guardado: le aparece al entrar a
la app hasta que aporte algo al reclamo (un comentario o una foto).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from core import email as correo
from core import whatsapp_client
from models.reclamo import Reclamo
from models.solicitud_inspeccion import SolicitudInspeccion
from models.usuario import Usuario
from services import estados_reclamo

logger = logging.getLogger(__name__)
APP_URL = os.getenv("APP_URL", "http://localhost:3000")


@dataclass(frozen=True)
class ResultadoAviso:
    inspector: Usuario
    whatsapp: bool
    email: bool


def link_reclamo(reclamo_id: int) -> str:
    # El listado de reclamos abre el detalle con ?abrir=<id>.
    return f"{APP_URL}/reclamos?abrir={reclamo_id}"


def notificar(
    db: Session,
    reclamo: Reclamo,
    inspectores: list[Usuario],
    mensaje: str | None,
    admin: Usuario,
) -> list[ResultadoAviso]:
    """Registra el pedido para cada inspector y le avisa por WhatsApp y email. No hace commit.

    Si el inspector ya tenía un pedido pendiente de este reclamo se actualiza ese (mensaje y
    fecha) en vez de sumar otro: en su bandeja tiene que figurar una sola vez.
    """
    mensaje = (mensaje or "").strip() or None
    link = link_reclamo(reclamo.id)
    resultados = []
    for inspector in inspectores:
        pendiente = (
            db.query(SolicitudInspeccion)
            .filter(
                SolicitudInspeccion.reclamo_id == reclamo.id,
                SolicitudInspeccion.inspector_id == inspector.id,
                SolicitudInspeccion.atendida_en.is_(None),
            )
            .first()
        )
        if pendiente is None:
            db.add(
                SolicitudInspeccion(
                    reclamo_id=reclamo.id,
                    inspector_id=inspector.id,
                    solicitado_por_id=admin.id,
                    mensaje=mensaje,
                )
            )
        else:
            pendiente.mensaje = mensaje
            pendiente.solicitado_por_id = admin.id
            pendiente.fecha = datetime.now(timezone.utc)

        resultados.append(
            ResultadoAviso(
                inspector=inspector,
                whatsapp=_avisar_whatsapp(reclamo, inspector, mensaje, link),
                email=_avisar_email(reclamo, inspector, mensaje, link),
            )
        )
    db.flush()
    return resultados


def _avisar_whatsapp(reclamo: Reclamo, inspector: Usuario, mensaje: str | None, link: str) -> bool:
    if not inspector.telefono:
        return False
    pedido = f"📝 Qué se necesita: {mensaje}\n\n" if mensaje else ""
    texto = (
        f"🔎 Hola {inspector.nombre}, te pidieron que cargues información adicional del "
        f"reclamo #{reclamo.id}.\n\n"
        f"🏫 Escuela: {reclamo.nombre_escuela}\n"
        f"📍 Ubicación: {reclamo.ubicacion}\n\n"
        f"{pedido}"
        f"Entrá para ver el reclamo y agregar comentarios o fotos:\n{link}"
    )
    try:
        respuesta = whatsapp_client.enviar_mensaje(inspector.telefono, texto)
    except Exception:  # noqa: BLE001 - el resto de los canales sigue
        logger.exception("No se pudo avisar por WhatsApp al inspector %s", inspector.id)
        return False
    # La API de Meta devuelve "messages" si aceptó el envío.
    return isinstance(respuesta, dict) and "messages" in respuesta


def _avisar_email(reclamo: Reclamo, inspector: Usuario, mensaje: str | None, link: str) -> bool:
    if not inspector.email:
        return False
    try:
        return correo.enviar_solicitud_inspeccion(
            inspector.email,
            reclamo.id,
            reclamo.nombre_escuela,
            reclamo.ubicacion,
            mensaje,
            link,
        )
    except Exception:  # noqa: BLE001 - el resto de los canales sigue
        logger.exception("No se pudo avisar por email al inspector %s", inspector.id)
        return False


def pendientes_de(db: Session, inspector: Usuario) -> list[SolicitudInspeccion]:
    """Pedidos sin atender del inspector, el más nuevo primero. Los de reclamos ya
    cerrados no van: ahí no puede comentar ni subir fotos."""
    return (
        db.query(SolicitudInspeccion)
        .join(Reclamo, Reclamo.id == SolicitudInspeccion.reclamo_id)
        .options(
            joinedload(SolicitudInspeccion.reclamo),
            joinedload(SolicitudInspeccion.solicitado_por),
        )
        .filter(
            SolicitudInspeccion.inspector_id == inspector.id,
            SolicitudInspeccion.atendida_en.is_(None),
            Reclamo.estado.notin_(estados_reclamo.ESTADOS_FINALES),
        )
        .order_by(SolicitudInspeccion.fecha.desc())
        .all()
    )


def del_reclamo(db: Session, reclamo_id: int, usuario: Usuario) -> list[SolicitudInspeccion]:
    """Pedidos del reclamo: el admin ve todos; el inspector, solo los suyos."""
    query = (
        db.query(SolicitudInspeccion)
        .options(
            joinedload(SolicitudInspeccion.inspector),
            joinedload(SolicitudInspeccion.solicitado_por),
        )
        .filter(SolicitudInspeccion.reclamo_id == reclamo_id)
    )
    if not usuario.es_admin:
        query = query.filter(SolicitudInspeccion.inspector_id == usuario.id)
    return query.order_by(SolicitudInspeccion.fecha.desc()).all()


def marcar_atendidas(db: Session, reclamo_id: int, inspector: Usuario) -> None:
    """El inspector aportó algo al reclamo: sus pedidos pendientes quedan atendidos."""
    if not inspector.es_inspector:
        return
    db.query(SolicitudInspeccion).filter(
        SolicitudInspeccion.reclamo_id == reclamo_id,
        SolicitudInspeccion.inspector_id == inspector.id,
        SolicitudInspeccion.atendida_en.is_(None),
    ).update({SolicitudInspeccion.atendida_en: datetime.now(timezone.utc)})
