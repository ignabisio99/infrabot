"""Recordatorios a contratistas por WhatsApp si un reclamo en ejecución lleva demasiado sin aviso (CU-05)."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from core.whatsapp_client import enviar_mensaje
from models.presupuesto import Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.recordatorio_contratista import RecordatorioContratista

logger = logging.getLogger(__name__)


def seguimiento_horas() -> float:
    try:
        return float(os.getenv("SEGUIMIENTO_HORAS") or "48")
    except ValueError:
        return 48.0


def seguimiento_intervalo_segundos() -> int:
    try:
        return int(os.getenv("SEGUIMIENTO_INTERVALO_SEGUNDOS") or "900")
    except ValueError:
        return 900


@dataclass(frozen=True)
class ResultadoSeguimiento:
    enviados: int
    omitidos: int


def ejecutar_seguimiento(db: Session) -> ResultadoSeguimiento:
    """Envía recordatorio si pasaron SEGUIMIENTO_HORAS desde el último aviso (o desde EN_EJECUCION)."""
    umbral = timedelta(hours=seguimiento_horas())
    ahora = datetime.now(timezone.utc)
    reclamos = (
        db.query(Reclamo)
        .options(joinedload(Reclamo.historial_estados))
        .filter(Reclamo.estado == EstadoReclamo.EN_EJECUCION)
        .all()
    )
    enviados = 0
    omitidos = 0
    for reclamo in reclamos:
        if _vencer(db, reclamo, ahora, umbral):
            if _enviar(db, reclamo, ahora):
                enviados += 1
            else:
                omitidos += 1
        else:
            omitidos += 1
    return ResultadoSeguimiento(enviados=enviados, omitidos=omitidos)


def _vencer(db: Session, reclamo: Reclamo, ahora: datetime, umbral: timedelta) -> bool:
    fila = (
        db.query(RecordatorioContratista)
        .filter(RecordatorioContratista.reclamo_id == reclamo.id)
        .first()
    )
    referencia = fila.ultimo_envio if fila else _fecha_en_ejecucion(reclamo)
    if referencia is None:
        referencia = reclamo.fecha_creacion
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=timezone.utc)
    return ahora - referencia >= umbral


def _fecha_en_ejecucion(reclamo: Reclamo):
    for evento in reversed(reclamo.historial_estados or []):
        if evento.estado_nuevo == EstadoReclamo.EN_EJECUCION:
            return evento.fecha
    return reclamo.fecha_creacion


def _enviar(db: Session, reclamo: Reclamo, ahora: datetime) -> bool:
    presupuesto = (
        db.query(Presupuesto)
        .options(joinedload(Presupuesto.contratista))
        .filter(Presupuesto.reclamo_id == reclamo.id)
        .order_by(Presupuesto.fecha.desc())
        .first()
    )
    if presupuesto is None or presupuesto.contratista is None:
        logger.info("Seguimiento reclamo %s: sin contratista", reclamo.id)
        return False

    telefono = _normalizar_telefono(presupuesto.contratista.telefono)
    if not telefono:
        logger.info("Seguimiento reclamo %s: teléfono inválido", reclamo.id)
        return False

    cuerpo = (
        f"Hola {presupuesto.contratista.nombre_empresa}, "
        f"el reclamo #{reclamo.id} ({reclamo.nombre_escuela}) está en ejecución. "
        "¿Podés enviarnos un avance (porcentaje o fotos)?"
    )
    try:
        enviar_mensaje(telefono, cuerpo)
    except Exception:
        logger.exception("No se pudo enviar recordatorio del reclamo %s", reclamo.id)
        return False

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
                cantidad_envios=1,
            )
        )
    else:
        fila.ultimo_envio = ahora
        fila.cantidad_envios = (fila.cantidad_envios or 0) + 1
    db.flush()
    return True


def _normalizar_telefono(valor: str) -> str:
    digitos = re.sub(r"\D", "", valor or "")
    if not digitos:
        return ""
    if digitos.startswith("54"):
        return digitos
    if digitos.startswith("0"):
        digitos = digitos.lstrip("0")
    if len(digitos) == 10:
        return "54" + digitos
    return digitos
