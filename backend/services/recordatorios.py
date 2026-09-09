"""Scheduler de recordatorios de visitas.

Corre como una tarea en background dentro del backend (se arranca en el lifespan de
main.py). Funciona igual en local y deployado porque no depende de cron externo.

Cada intervalo revisa las visitas confirmadas y envía:
- Un recordatorio el día ANTES de la visita.
- Un recordatorio el MISMO día de la visita.

Usa marcas en la fila (recordatorio_*_enviado) para no repetir. Es idempotente: si el
proceso se reinicia, no reenvía lo ya enviado.
"""

import asyncio
import logging
from datetime import datetime, timezone

from core.database import SessionLocal
from models.contratista import Contratista
from models.reclamo import Reclamo
from models.visita import EstadoVisita, Visita

logger = logging.getLogger(__name__)

# Cada cuánto revisar (segundos). 15 min es suficiente para recordatorios de día.
INTERVALO_SEGUNDOS = 15 * 60


def _enviar(to: str, body: str) -> None:
    from core.whatsapp_client import enviar_mensaje

    try:
        enviar_mensaje(to, body)
    except Exception as e:  # noqa: BLE001
        logger.warning("No se pudo enviar recordatorio a %s: %s", to, e)


def _avisar_a_ambos(db, visita: Visita, encabezado: str) -> None:
    reclamo = db.get(Reclamo, visita.reclamo_id)
    contratista = db.get(Contratista, visita.contratista_id)
    if reclamo is None:
        return

    cuerpo = (
        f"{encabezado}\n\n"
        f"🏫 Escuela: {reclamo.nombre_escuela}\n"
        f"📍 Ubicación: {reclamo.ubicacion}\n"
        f"🗓️ Horario: {visita.horario_confirmado}"
    )
    if contratista and contratista.telefono:
        _enviar(contratista.telefono, cuerpo)
    if reclamo.telefono_creador:
        _enviar(reclamo.telefono_creador, cuerpo)


def revisar_recordatorios(db) -> None:
    """Revisa las visitas confirmadas y envía los recordatorios que correspondan."""
    ahora = datetime.now(timezone.utc)

    visitas = (
        db.query(Visita)
        .filter(
            Visita.estado == EstadoVisita.CONFIRMADA,
            Visita.fecha_visita.isnot(None),
        )
        .all()
    )

    for visita in visitas:
        fecha = visita.fecha_visita
        if fecha is None:
            continue
        # Asegurar tz-aware
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)

        faltante = fecha - ahora
        horas = faltante.total_seconds() / 3600

        # Recordatorio "mismo día": entre 0 y 12 horas antes de la visita.
        if 0 <= horas <= 12 and visita.recordatorio_mismo_dia_enviado is None:
            _avisar_a_ambos(db, visita, "⏰ *Recordatorio: la visita es hoy*")
            visita.recordatorio_mismo_dia_enviado = ahora
            db.commit()
            continue

        # Recordatorio "día antes": entre 12 y 36 horas antes.
        if 12 < horas <= 36 and visita.recordatorio_dia_antes_enviado is None:
            _avisar_a_ambos(db, visita, "🔔 *Recordatorio: la visita es mañana*")
            visita.recordatorio_dia_antes_enviado = ahora
            db.commit()


async def loop_recordatorios() -> None:
    """Loop infinito que revisa recordatorios cada INTERVALO_SEGUNDOS."""
    logger.info("Scheduler de recordatorios de visitas iniciado.")
    while True:
        try:
            db = SessionLocal()
            try:
                revisar_recordatorios(db)
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001 - el loop no debe morir por un error puntual
            logger.warning("Error revisando recordatorios: %s", e)

        await asyncio.sleep(INTERVALO_SEGUNDOS)
