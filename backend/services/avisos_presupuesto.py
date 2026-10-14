"""Avisos al contratista, por WhatsApp y mail, cuando cambia la suerte de su presupuesto.

Un aviso que falla se loguea y no corta nada: la decisión ya quedó registrada.
"""

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from core.email import (
    APP_URL,
    enviar_ajustes_presupuesto,
    enviar_no_seleccionado_presupuesto,
    enviar_rechazo_presupuesto,
    enviar_reclamo_cancelado_presupuesto,
)
from core.whatsapp_client import enviar_mensaje
from models.presupuesto import EstadoPresupuesto, Presupuesto
from services.estados_presupuesto import motivo_estado

logger = logging.getLogger(__name__)


def _enviar(
    db: Session, presupuesto: Presupuesto, mensaje: str, mail: Callable[[str], object]
) -> None:
    # Import local: api.reclamos usa este módulo para avisar cancelaciones.
    from api.reclamos import _email_del_contratista

    contratista = presupuesto.contratista
    try:
        enviar_mensaje(contratista.telefono, mensaje)
    except Exception:
        logger.exception("No se pudo avisar por WhatsApp sobre el presupuesto %s", presupuesto.id)

    email = _email_del_contratista(db, contratista)
    if email:
        try:
            mail(email)
        except Exception:
            logger.exception("No se pudo avisar por email sobre el presupuesto %s", presupuesto.id)


def avisar_decision(db: Session, presupuesto: Presupuesto) -> None:
    """Sin el aviso, el contratista no se entera de qué corregir ni de que quedó afuera."""
    reclamo = presupuesto.reclamo
    escuela = reclamo.nombre_escuela
    motivo = motivo_estado(presupuesto)

    link = f"{APP_URL}/portal/reclamos/{reclamo.id}/presupuestar"

    if presupuesto.estado is EstadoPresupuesto.AJUSTES_SOLICITADOS:
        mensaje = (
            f"✏️ Le pidieron ajustes a su presupuesto para el reclamo #{reclamo.id} ({escuela}).\n\n"
            f"Qué corregir: {motivo}\n\n"
            f"Puede enviar la versión corregida desde:\n{link}"
        )
        _enviar(
            db,
            presupuesto,
            mensaje,
            lambda email: enviar_ajustes_presupuesto(email, reclamo.id, escuela, motivo, link),
        )
    elif presupuesto.estado is EstadoPresupuesto.RECHAZADO:
        mensaje = (
            f"❌ Su presupuesto para el reclamo #{reclamo.id} ({escuela}) fue rechazado.\n\n"
            f"Motivo: {motivo}\n\n"
            f"Mientras la convocatoria siga abierta, puede enviar una nueva oferta desde:\n{link}"
        )
        _enviar(
            db,
            presupuesto,
            mensaje,
            lambda email: enviar_rechazo_presupuesto(email, reclamo.id, escuela, motivo, link),
        )
    elif presupuesto.estado is EstadoPresupuesto.NO_SELECCIONADO:
        mensaje = (
            f"ℹ️ Para el reclamo #{reclamo.id} ({escuela}) se eligió otra oferta: su "
            "presupuesto no fue seleccionado. Gracias por participar."
        )
        _enviar(
            db,
            presupuesto,
            mensaje,
            lambda email: enviar_no_seleccionado_presupuesto(email, reclamo.id, escuela),
        )


def avisar_reclamo_cancelado(db: Session, presupuesto: Presupuesto, motivo: str | None) -> None:
    reclamo = presupuesto.reclamo
    escuela = reclamo.nombre_escuela
    mensaje = (
        f"🚫 El reclamo #{reclamo.id} ({escuela}) se canceló: su presupuesto ya no se va a "
        f"evaluar.\n\nMotivo: {motivo or '—'}"
    )
    _enviar(
        db,
        presupuesto,
        mensaje,
        lambda email: enviar_reclamo_cancelado_presupuesto(email, reclamo.id, escuela, motivo),
    )
