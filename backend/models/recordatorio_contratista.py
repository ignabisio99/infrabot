"""Último recordatorio de avance enviado al contratista (CU-05)."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer

from core.database import Base


class RecordatorioContratista(Base):
    __tablename__ = "recordatorio_contratista"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(
        Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    ultimo_envio = Column(DateTime(timezone=True), nullable=False)
    cantidad_envios = Column(Integer, nullable=False, default=1)
    creado_en = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
