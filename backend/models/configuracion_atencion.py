"""Horarios de atención humana y mensaje fuera de horario (fila única)."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from core.database import Base

MENSAJE_FUERA_DEFAULT = (
    "Estamos fuera del horario de atención. "
    "El equipo atiende de lunes a viernes de 9 a 18 (Argentina). "
    "Podés seguir usando el asistente o escribir de nuevo en ese horario."
)


class ConfiguracionAtencion(Base):
    """Fila única (id=1) con días, franja horaria y textos de atención."""

    __tablename__ = "configuracion_atencion"

    id = Column(Integer, primary_key=True, default=1)
    dias = Column(JSON, nullable=False, default=lambda: [0, 1, 2, 3, 4])
    hora_desde = Column(String(5), nullable=False, default="09:00")
    hora_hasta = Column(String(5), nullable=False, default="18:00")
    mensaje_fuera_horario = Column(Text, nullable=False, default=MENSAJE_FUERA_DEFAULT)
    inactividad_usuario_min = Column(Integer, nullable=False, default=60)
    actualizado_en = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
