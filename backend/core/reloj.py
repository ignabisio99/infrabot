"""Módulo central de reloj virtual para InfraBot.

Permite consultar la fecha/hora actual (`ahora()`) y simular el paso del tiempo
avanzando horas o días (o reseteando a tiempo real). Utilizado por administradores
para probar y demostrar flujos completos de recordatorios, coordinación de visitas,
ejecución de obras y seguimiento posterior.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Zona horaria oficial para visualización y parsing en Argentina (UTC-3, sin DST)
ART = timezone(timedelta(hours=-3))

_lock = threading.Lock()
_offset_segundos: float = 0.0


def ahora() -> datetime:
    """Devuelve la fecha/hora actual en UTC, ajustada con el offset de simulación si existe."""
    with _lock:
        offset = _offset_segundos
    real = datetime.now(timezone.utc)
    if offset:
        return real + timedelta(seconds=offset)
    return real


def ahora_art() -> datetime:
    """Devuelve la fecha/hora actual simulada convertida a la zona horaria Argentina (ART, UTC-3)."""
    return ahora().astimezone(ART)


def obtener_offset() -> timedelta:
    """Devuelve el timedelta actual de desviación respecto del tiempo real."""
    with _lock:
        return timedelta(seconds=_offset_segundos)


def esta_simulado() -> bool:
    """Indica si el reloj está desplazado respecto al tiempo real (más de 1 segundo de diferencia)."""
    with _lock:
        return abs(_offset_segundos) > 1.0


def descripcion_offset() -> str:
    """Genera una descripción amigable en español de la diferencia con el tiempo real."""
    with _lock:
        segundos = _offset_segundos

    if abs(segundos) < 1.0:
        return "Tiempo real"

    signo = "+" if segundos >= 0 else "-"
    total = abs(int(segundos))
    dias = total // 86400
    resto = total % 86400
    horas = resto // 3600
    minutos = (resto % 3600) // 60

    partes = []
    if dias > 0:
        partes.append(f"{dias} {'día' if dias == 1 else 'días'}")
    if horas > 0:
        partes.append(f"{horas} {'hora' if horas == 1 else 'horas'}")
    if minutos > 0 and dias == 0:
        partes.append(f"{minutos} min")

    if not partes:
        partes.append(f"{total} seg")

    return f"{signo}{', '.join(partes)}"


def formatear_art(dt: datetime | None = None) -> str:
    """Formatea una fecha/hora en formato argentino: DD/MM/AAAA HH:MM."""
    if dt is None:
        dt = ahora()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_art = dt.astimezone(ART)
    return dt_art.strftime("%d/%m/%Y %H:%M")


def avanzar_tiempo(
    horas: float = 0.0,
    dias: float = 0.0,
    minutos: float = 0.0,
) -> datetime:
    """Avanza el reloj virtual agregando las horas, días y minutos especificados."""
    global _offset_segundos
    delta_segundos = timedelta(days=dias, hours=horas, minutes=minutos).total_seconds()
    with _lock:
        _offset_segundos += delta_segundos
    logger.info("Reloj virtual avanzado: offset acumulado = %s s (%s)", _offset_segundos, descripcion_offset())
    return ahora()


def fijar_tiempo(dt: datetime) -> datetime:
    """Fija el reloj virtual en un instante absoluto específico."""
    global _offset_segundos
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    target_utc = dt.astimezone(timezone.utc)
    real_utc = datetime.now(timezone.utc)
    delta_segundos = (target_utc - real_utc).total_seconds()
    with _lock:
        _offset_segundos = delta_segundos
    logger.info("Reloj virtual fijado a %s (offset = %s s)", target_utc, _offset_segundos)
    return ahora()


def resetear_tiempo() -> datetime:
    """Restablece el reloj virtual al tiempo real."""
    global _offset_segundos
    with _lock:
        _offset_segundos = 0.0
    logger.info("Reloj virtual restablecido a tiempo real.")
    return ahora()
