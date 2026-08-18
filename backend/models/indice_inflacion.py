"""Cache local del IPC (INDEC) vía API Series de Tiempo."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint

from core.database import Base


class IndiceInflacion(Base):
    __tablename__ = "indice_inflacion"
    __table_args__ = (UniqueConstraint("periodo", name="uq_indice_inflacion_periodo"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    periodo = Column(String(7), nullable=False)  # YYYY-MM
    indice = Column(Float, nullable=False)
    fuente = Column(String(255), nullable=False, default="datos.gob.ar")
    actualizado_en = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
