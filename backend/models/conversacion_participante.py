"""Admins que participaron de un chat (toma, transferencia, reapertura)."""

from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from core.database import Base


class ConversacionParticipante(Base):
    __tablename__ = "conversacion_participante"
    __table_args__ = (
        UniqueConstraint("conversacion_id", "usuario_id", name="uq_conv_participante"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversacion_id = Column(
        Integer, ForeignKey("conversacion.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = Column(
        Integer, ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, index=True
    )

    conversacion = relationship("Conversacion")
    usuario = relationship("Usuario")
