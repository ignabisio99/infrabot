from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class EstimacionPreliminar(Base):
    """Estimación de costos generada por el Motor de IA (no es un presupuesto final)."""

    __tablename__ = "estimacion_preliminar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    materiales = Column(Numeric(14, 2), nullable=False)
    mano_obra = Column(Numeric(14, 2), nullable=False)
    otros = Column(Numeric(14, 2), nullable=False)
    total = Column(Numeric(14, 2), nullable=False)
    confianza = Column(Float, nullable=False)
    detalle = Column(Text, nullable=True)
    proveedor = Column(String(50), nullable=False, default="mock")
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reclamo = relationship("Reclamo")
