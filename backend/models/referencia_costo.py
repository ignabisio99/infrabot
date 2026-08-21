"""Tabla de costos históricos.

Puente actual: se alimenta con seed placeholder y con sync desde presupuestos
del sistema (`POST /ai/referencias/sync`, fuente=`presupuesto:{id}`).
Más adelante se reemplaza/alimenta con datos reales del Consejo Escolar.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, Numeric, String, Text

from core.database import Base


class ReferenciaCosto(Base):
    __tablename__ = "referencia_costo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    categoria = Column(String(255), nullable=False, index=True)
    descripcion = Column(Text, nullable=False)
    monto_ars = Column(Numeric(14, 2), nullable=False)
    fecha_referencia = Column(Date, nullable=False, default=date.today)
    unidad = Column(String(100), nullable=True)
    fuente = Column(String(255), nullable=True, index=True)
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
