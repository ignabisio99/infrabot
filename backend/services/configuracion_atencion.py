"""Horario laboral de operadores y mensaje fuera de franja."""

from __future__ import annotations

import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from models.configuracion_atencion import MENSAJE_FUERA_DEFAULT, ConfiguracionAtencion

FILA_ID = 1
TZ_AR = ZoneInfo("America/Argentina/Buenos_Aires")
_HORA = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
DIAS_DEFAULT = [0, 1, 2, 3, 4]


def obtener_o_crear(db: Session) -> ConfiguracionAtencion:
    fila = db.get(ConfiguracionAtencion, FILA_ID)
    if fila is None:
        fila = ConfiguracionAtencion(
            id=FILA_ID,
            dias=list(DIAS_DEFAULT),
            hora_desde="09:00",
            hora_hasta="18:00",
            mensaje_fuera_horario=MENSAJE_FUERA_DEFAULT,
            inactividad_usuario_min=60,
        )
        db.add(fila)
        db.flush()
    return fila


def validar_hora(valor: str) -> str:
    texto = (valor or "").strip()
    if len(texto) >= 8 and texto[5] == ":":
        texto = texto[:5]
    if not _HORA.match(texto):
        raise ValueError("La hora tiene que ser HH:MM (00:00 a 23:59)")
    return texto


def validar_dias(dias: list[int]) -> list[int]:
    limpios = sorted({int(d) for d in dias})
    if not limpios or any(d < 0 or d > 6 for d in limpios):
        raise ValueError("Los días tienen que ser números de 0 (lunes) a 6 (domingo)")
    return limpios


def dentro_de_atencion(db: Session, ahora: datetime | None = None) -> bool:
    fila = obtener_o_crear(db)
    momento = ahora or datetime.now(TZ_AR)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=TZ_AR)
    else:
        momento = momento.astimezone(TZ_AR)
    dias = fila.dias if isinstance(fila.dias, list) else DIAS_DEFAULT
    if momento.weekday() not in {int(d) for d in dias}:
        return False
    try:
        desde = time.fromisoformat(fila.hora_desde)
        hasta = time.fromisoformat(fila.hora_hasta)
    except ValueError:
        return True
    actual = momento.time().replace(tzinfo=None)
    if desde <= hasta:
        return desde <= actual < hasta
    return actual >= desde or actual < hasta


def mensaje_fuera_horario(db: Session) -> str:
    fila = obtener_o_crear(db)
    return (fila.mensaje_fuera_horario or MENSAJE_FUERA_DEFAULT).strip()


def inactividad_usuario_minutos(db: Session) -> int:
    fila = obtener_o_crear(db)
    try:
        return max(1, int(fila.inactividad_usuario_min or 60))
    except (TypeError, ValueError):
        return 60
