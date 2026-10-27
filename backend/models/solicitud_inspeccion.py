from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from core.database import Base


class SolicitudInspeccion(Base):
    """Un admin le pidió a un inspector que cargue información adicional de un reclamo.

    Queda pendiente hasta que el inspector aporte algo al reclamo (un comentario o una
    foto): ahí se marca `atendida_en`. Mientras tanto le aparece al entrar a la app.
    """

    __tablename__ = "solicitud_inspeccion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    inspector_id = Column(Integer, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False)
    solicitado_por_id = Column(
        Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True
    )
    # Qué información necesita el admin (opcional).
    mensaje = Column(Text, nullable=True)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    atendida_en = Column(DateTime(timezone=True), nullable=True)

    reclamo = relationship("Reclamo")
    inspector = relationship("Usuario", foreign_keys=[inspector_id])
    solicitado_por = relationship("Usuario", foreign_keys=[solicitado_por_id])
