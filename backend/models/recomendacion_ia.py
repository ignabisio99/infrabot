"""Log de recomendaciones del Motor de IA (RNF04)."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class TipoRecomendacionIA(str, enum.Enum):
    CLASIFICACION = "CLASIFICACION"
    ESTIMACION = "ESTIMACION"
    AUDITORIA = "AUDITORIA"
    DUPLICADOS = "DUPLICADOS"
    VISION = "VISION"
    OCR = "OCR"
    COMPLETITUD = "COMPLETITUD"
    STT = "STT"
    DERIVACION = "DERIVACION"


class RecomendacionIA(Base):
    __tablename__ = "recomendacion_ia"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(
        Enum(TipoRecomendacionIA, name="tipo_recomendacion_ia"),
        nullable=False,
    )
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="SET NULL"), nullable=True)
    presupuesto_id = Column(
        Integer, ForeignKey("presupuesto.id", ondelete="SET NULL"), nullable=True
    )
    proveedor = Column(String(50), nullable=True)
    confianza = Column(Float, nullable=True)
    payload = Column(Text, nullable=False)
    requiere_revision = Column(Boolean, nullable=False, default=False)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reclamo = relationship("Reclamo")
    presupuesto = relationship("Presupuesto")
