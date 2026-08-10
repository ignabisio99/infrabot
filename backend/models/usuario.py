import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String

from core.database import Base


class TipoUsuario(str, enum.Enum):
    ADMINISTRADOR = "ADMINISTRADOR"
    CONTRATISTA = "CONTRATISTA"


class EstadoUsuario(str, enum.Enum):
    PENDIENTE_PERFIL = "PENDIENTE_PERFIL"
    PENDIENTE_APROBACION = "PENDIENTE_APROBACION"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class Usuario(Base):
    __tablename__ = "usuario"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    email_confirmado = Column(Boolean, default=False, nullable=False)

    # Datos adicionales del perfil
    telefono = Column(String(50), nullable=True)
    direccion = Column(String(500), nullable=True)
    tipo = Column(Enum(TipoUsuario, name="tipo_usuario"), nullable=True)
    estado = Column(
        Enum(EstadoUsuario, name="estado_usuario"),
        default=EstadoUsuario.PENDIENTE_PERFIL,
        nullable=False,
    )

    # Campos exclusivos de contratistas
    nombre_empresa = Column(String(255), nullable=True)
    especialidad = Column(String(255), nullable=True)

    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
