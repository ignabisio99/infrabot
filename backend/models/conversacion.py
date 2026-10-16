import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.database import Base


class EstadoConversacion(str, enum.Enum):
    ESPERANDO_OPERADOR = "ESPERANDO_OPERADOR"
    CON_OPERADOR = "CON_OPERADOR"
    CERRADA = "CERRADA"


class Conversacion(Base):
    """Sesión de atención humana con un número de WhatsApp."""

    __tablename__ = "conversacion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telefono = Column(String(50), nullable=False, index=True)
    estado = Column(
        Enum(EstadoConversacion, name="estado_conversacion"),
        nullable=False,
        default=EstadoConversacion.ESPERANDO_OPERADOR,
        index=True,
    )
    operador_id = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    fecha_solicitud = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    fecha_toma = Column(DateTime(timezone=True), nullable=True)
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    ultimo_mensaje_usuario = Column(DateTime(timezone=True), nullable=True)
    aviso_espera_enviado = Column(Boolean, default=False, nullable=False)

    operador = relationship("Usuario")
    mensajes = relationship("MensajeConversacion", back_populates="conversacion")
