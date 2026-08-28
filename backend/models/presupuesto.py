from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class Presupuesto(Base):
    __tablename__ = "presupuesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    contratista_id = Column(
        Integer, ForeignKey("contratista.id", ondelete="CASCADE"), nullable=False
    )
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    observaciones = Column(Text, nullable=True)

    items = relationship(
        "ItemPresupuesto", back_populates="presupuesto", cascade="all, delete-orphan"
    )
    reclamo = relationship("Reclamo")
    contratista = relationship("Contratista")


class ItemPresupuesto(Base):
    __tablename__ = "item_presupuesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    presupuesto_id = Column(
        Integer, ForeignKey("presupuesto.id", ondelete="CASCADE"), nullable=False
    )
    descripcion = Column(Text, nullable=False)
    cantidad = Column(Numeric(10, 2), nullable=False)
    unidad = Column(String(20), nullable=False, default="unidad", server_default="unidad")
    costo_unitario = Column(Numeric(12, 2), nullable=False)

    presupuesto = relationship("Presupuesto", back_populates="items")
