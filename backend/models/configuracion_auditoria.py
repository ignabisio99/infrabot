"""Umbrales de auditoría de presupuestos (CU-03), editables por el operador."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Integer, Numeric

from core.database import Base


class ConfiguracionAuditoria(Base):
    """Fila única (id=1) con los umbrales vigentes."""

    __tablename__ = "configuracion_auditoria"

    id = Column(Integer, primary_key=True, default=1)
    umbral_aprobar = Column(Numeric(5, 4), nullable=False, default=Decimal("0.05"))
    umbral_revisar = Column(Numeric(5, 4), nullable=False, default=Decimal("0.20"))
    actualizado_en = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
