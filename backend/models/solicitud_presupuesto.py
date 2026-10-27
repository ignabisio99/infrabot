"""Registro de solicitudes de presupuesto a contratistas.

Cuando un administrador notifica a un contratista para que cargue presupuesto de un
reclamo, se guarda una fila acá. Permite después mostrar a quiénes se les pidió y si
ya respondieron (cruzando con la tabla de presupuestos).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from core.database import Base


class SolicitudPresupuesto(Base):
    __tablename__ = "solicitud_presupuesto"
    __table_args__ = (
        UniqueConstraint("reclamo_id", "contratista_id", name="uq_solicitud_reclamo_contratista"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    contratista_id = Column(
        Integer, ForeignKey("contratista.id", ondelete="CASCADE"), nullable=False
    )
    fecha_solicitud = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # Cambia con cada reenvío; `fecha_solicitud` queda como la del primer pedido.
    fecha_ultimo_aviso = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    contratista = relationship("Contratista")
