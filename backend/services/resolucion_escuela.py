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


def mensaje_finalizado(reclamo: Reclamo) -> str:
    """Confirmación de cierre para la escuela."""
    return (
        f"✅ *Reclamo #{reclamo.id} finalizado*\n\n"
        f"🏫 {reclamo.nombre_escuela}\n\n"
        "Gracias por confirmar que se resolvió. Si vuelve a presentarse el problema, "
        "podés cargar un nuevo reclamo cuando quieras."
    )


def guardar_media_no_resuelto(db: Session, reclamo: Reclamo, url_local: str, mime_type: str) -> None:
    """Foto o video que manda la escuela para mostrar qué quedó mal. Va al reclamo."""
    from models.foto_reclamo import FotoReclamo, TipoMedia

    db.add(
        FotoReclamo(
            reclamo_id=reclamo.id,
            nombre_archivo=url_local.split("/")[-1],
            url=url_local,
            tipo=TipoMedia.VIDEO if "video" in (mime_type or "") else TipoMedia.IMAGEN,
        )
    )
    db.commit()


def registrar_no_resuelto(
    db: Session, reclamo: Reclamo, *, detalle: str | None = None, cantidad_media: int = 0
):
    """La escuela dijo que no quedó resuelto: se coordina una nueva visita con el
    contratista (ver coordinacion_visita.coordinar_nueva_visita) y se reactivan las
    preguntas de avance para cuando vuelva a ejecución. Queda en la línea de tiempo del
    reclamo, entre el "terminé" del contratista y lo que venga después.

    Devuelve el contratista al que se le pidió la nueva visita, o None si no se pudo (sin
    contratista o sin teléfono): ahí el reclamo sigue en ejecución con el seguimiento.
    """
    from services import coordinacion_visita, seguimiento

    texto = "[WhatsApp — Escuela]\nLa escuela indicó que el problema no quedó resuelto."
    if detalle:
        texto += f"\nQué quedó mal: {detalle.strip()}"
    if cantidad_media:
        texto += f"\nFotos/videos enviados: {cantidad_media}"
    db.add(ComentarioReclamo(reclamo_id=reclamo.id, usuario_id=None, texto=texto))
    seguimiento.reactivar_seguimiento(db, reclamo)
    contratista = coordinacion_visita.coordinar_nueva_visita(
        db, reclamo, detalle=detalle, cantidad_media=cantidad_media
    )
    db.commit()
    return contratista


def registrar_resolucion(db: Session, reclamo: Reclamo, *, avisar_escuela: bool = True) -> bool:
    """La escuela confirmó que se resolvió: EN_EJECUCION -> FINALIZADO.

    Deja un comentario de sistema y avisa al contratista y a la escuela. Con
    `avisar_escuela=False` no le manda la confirmación a la escuela: lo usa el handler
    cuando la escuela acaba de responder, para contestarle con un solo mensaje. Devuelve
    True si cambió el estado; False si el reclamo no estaba en EN_EJECUCION.
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
    if avisar_escuela and reclamo.telefono_creador:
        _enviar(reclamo.telefono_creador, mensaje_finalizado(reclamo))

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
