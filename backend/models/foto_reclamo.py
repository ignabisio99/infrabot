"""Modelo de archivos multimedia asociados a reclamos (fotos y videos)."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.database import Base


class TipoMedia(str, enum.Enum):
    IMAGEN = "IMAGEN"
    VIDEO = "VIDEO"


class FotoReclamo(Base):
    __tablename__ = "foto_reclamo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    nombre_archivo = Column(String(255), nullable=False)
    url = Column(String(500), nullable=False)
    tipo = Column(Enum(TipoMedia, name="tipo_media"), nullable=False, default=TipoMedia.IMAGEN)
    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reclamo = relationship("Reclamo", back_populates="fotos")
