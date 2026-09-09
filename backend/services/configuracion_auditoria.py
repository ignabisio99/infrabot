"""Lectura/escritura de umbrales de auditoría (fila única)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from models.configuracion_auditoria import ConfiguracionAuditoria

UMBRAL_APROBAR_DEFAULT = Decimal("0.05")
UMBRAL_REVISAR_DEFAULT = Decimal("0.20")
FILA_ID = 1


def obtener_o_crear(db: Session) -> ConfiguracionAuditoria:
    fila = db.get(ConfiguracionAuditoria, FILA_ID)
    if fila is None:
        fila = ConfiguracionAuditoria(
            id=FILA_ID,
            umbral_aprobar=UMBRAL_APROBAR_DEFAULT,
            umbral_revisar=UMBRAL_REVISAR_DEFAULT,
        )
        db.add(fila)
        db.flush()
    return fila


def obtener_umbrales(db: Session) -> tuple[Decimal, Decimal]:
    fila = obtener_o_crear(db)
    return Decimal(fila.umbral_aprobar), Decimal(fila.umbral_revisar)
