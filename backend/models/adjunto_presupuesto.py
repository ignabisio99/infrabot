"""Adjuntos de presupuesto para OCR/Vision (imagen o PDF)."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.database import Base


class TipoAdjuntoPresupuesto(str, enum.Enum):
    IMAGEN = "IMAGEN"
    PDF = "PDF"


class AdjuntoPresupuesto(Base):
    __tablename__ = "adjunto_presupuesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    presupuesto_id = Column(
        Integer, ForeignKey("presupuesto.id", ondelete="SET NULL"), nullable=True
    )
    nombre_archivo = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    tipo = Column(
        Enum(TipoAdjuntoPresupuesto, name="tipo_adjunto_presupuesto"),
        nullable=False,
    )
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    presupuesto = relationship("Presupuesto")
