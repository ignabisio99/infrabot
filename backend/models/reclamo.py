import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text

from core.database import Base


class PrioridadReclamo(str, enum.Enum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class Reclamo(Base):
    __tablename__ = "reclamo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_escuela = Column(String(255), nullable=False)
    ubicacion = Column(String(255), nullable=False)
    prioridad = Column(Enum(PrioridadReclamo, name="prioridad_reclamo"), nullable=False)
    categoria = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=False)
    observaciones = Column(Text, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
