import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class AutorMensaje(str, enum.Enum):
    USUARIO = "USUARIO"
    BOT = "BOT"
    OPERADOR = "OPERADOR"
    SISTEMA = "SISTEMA"


class TipoMensaje(str, enum.Enum):
    TEXTO = "TEXTO"
    IMAGEN = "IMAGEN"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"


class MensajeConversacion(Base):
    """Mensaje de una charla de WhatsApp (bot u operador)."""

    __tablename__ = "mensaje_conversacion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversacion_id = Column(
        Integer, ForeignKey("conversacion.id", ondelete="SET NULL"), nullable=True, index=True
    )
    telefono = Column(String(50), nullable=False, index=True)
    autor = Column(Enum(AutorMensaje, name="autor_mensaje_conversacion"), nullable=False)
    operador_id = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    tipo = Column(
        Enum(TipoMensaje, name="tipo_mensaje_conversacion"),
        nullable=False,
        default=TipoMensaje.TEXTO,
    )
    texto = Column(Text, nullable=True)
    media_url = Column(String(500), nullable=True)
    mime_type = Column(String(100), nullable=True)
    transcripcion = Column(Text, nullable=True)
    media_expira_en = Column(DateTime(timezone=True), nullable=True)
    media_eliminada = Column(Boolean, default=False, nullable=False)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    conversacion = relationship("Conversacion", back_populates="mensajes")
    operador = relationship("Usuario")
