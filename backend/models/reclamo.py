import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text

from core.database import Base


class PrioridadReclamo(str, enum.Enum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class Reclamo(Base):
    __tablename__ = "reclamos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_escuela = Column(String(255), nullable=False)
    sector = Column(String(255), nullable=False)
    prioridad = Column(Enum(PrioridadReclamo, name="prioridad_reclamo"), nullable=False)
    categoria = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=False)
    creado_en = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
