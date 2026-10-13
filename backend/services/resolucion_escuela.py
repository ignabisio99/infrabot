"""CU-05 paso 5: la escuela confirma por WhatsApp que el problema se resolvió.

Hasta ahora el reclamo quedaba en EN_EJECUCION: el "terminé" del contratista es solo un
reporte (ver avance_contratista), no cierra el reclamo. El cierre lo confirma la escuela
que lo creó. Acá se identifica al creador por su teléfono (reclamo.telefono_creador) y,
cuando confirma, se dispara EN_EJECUCION -> FINALIZADO.

La transición ya es válida en la máquina de estados con origen AUTOMATICO, así que no
hace falta tocar estados_reclamo.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session, joinedload

from models.comentario_reclamo import ComentarioReclamo
from models.historial_estado_reclamo import OrigenCambioEstado
from models.presupuesto import Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from services import estados_reclamo


def _digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _mismo_numero(a: str, b: str) -> bool:
    """Compara dos teléfonos por los últimos 8 dígitos (ignora prefijos/formato)."""
    da, db_ = _digitos(a), _digitos(b)
    if not da or not db_:
        return False
    return da[-8:] == db_[-8:]


def _enviar(to: str, body: str) -> None:
    """Envía un WhatsApp sin romper el flujo si falla."""
    from core.whatsapp_client import enviar_mensaje

    try:
        enviar_mensaje(to, body)
    except Exception as e:  # noqa: BLE001
        print(f"[RESOLUCION] No se pudo enviar mensaje a {to}: {e}")


def reclamo_en_ejecucion_del_creador(db: Session, telefono: str) -> Reclamo | None:
    """Reclamo EN_EJECUCION cuyo creador (telefono_creador) coincide con el teléfono."""
    reclamos = (
        db.query(Reclamo)
        .filter(Reclamo.estado == EstadoReclamo.EN_EJECUCION)
        .order_by(Reclamo.id.desc())
        .all()
    )
    for reclamo in reclamos:
        if reclamo.telefono_creador and _mismo_numero(reclamo.telefono_creador, telefono):
            return reclamo
    return None


def registrar_resolucion(db: Session, reclamo: Reclamo) -> bool:
    """La escuela confirmó que se resolvió: EN_EJECUCION -> FINALIZADO.

    Deja un comentario de sistema y avisa al contratista y a la escuela. Devuelve True si
    cambió el estado; False si el reclamo no estaba en EN_EJECUCION.
    """
    if reclamo.estado != EstadoReclamo.EN_EJECUCION:
        return False

    estados_reclamo.cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.FINALIZADO,
        motivo="La escuela confirmó por WhatsApp que el problema se resolvió",
        origen=OrigenCambioEstado.AUTOMATICO,
    )
    db.add(
        ComentarioReclamo(
            reclamo_id=reclamo.id,
            usuario_id=None,
            texto="[Sistema]\nLa escuela confirmó que el problema se resolvió. "
            "El reclamo queda finalizado.",
        )
    )
    db.commit()

    # Avisar a la escuela (confirmación de cierre).
    if reclamo.telefono_creador:
        _enviar(
            reclamo.telefono_creador,
            f"✅ *Reclamo #{reclamo.id} finalizado*\n\n"
            f"🏫 {reclamo.nombre_escuela}\n\n"
            "Gracias por confirmar que se resolvió. Si vuelve a presentarse el problema, "
            "podés cargar un nuevo reclamo cuando quieras.",
        )

    # Avisar al contratista que la escuela dio por resuelto el trabajo (best-effort).
    presupuesto = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.contratista))
        .filter(Presupuesto.reclamo_id == reclamo.id)
        .order_by(Presupuesto.fecha.desc())
        .first()
    )
    contratista = presupuesto.contratista if presupuesto else None
    if contratista and contratista.telefono:
        _enviar(
            contratista.telefono,
            f"✅ *Reclamo #{reclamo.id} finalizado*\n\n"
            f"🏫 {reclamo.nombre_escuela}\n\n"
            "La escuela confirmó que el trabajo quedó resuelto. ¡Gracias!",
        )
    return True
