import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from core.database import Base
from models.reclamo import estado_reclamo_enum


class OrigenCambioEstado(str, enum.Enum):
    """Quién disparó el cambio: una persona desde la app, o el propio sistema."""

    MANUAL = "MANUAL"
    AUTOMATICO = "AUTOMATICO"


class HistorialEstadoReclamo(Base):
    """Registro de cada cambio de estado de un reclamo.

    Guarda quién lo hizo y por qué, que es lo que después permite auditar el
    expediente y medir cuánto tardó el reclamo en cada etapa.
    """

    __tablename__ = "historial_estado_reclamo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    # Nulo en el primer registro: el reclamo nace en PENDIENTE_REVISION sin estado previo.
    estado_anterior = Column(estado_reclamo_enum, nullable=True)
    estado_nuevo = Column(estado_reclamo_enum, nullable=False)
    origen = Column(
        Enum(OrigenCambioEstado, name="origen_cambio_estado"),
        nullable=False,
        default=OrigenCambioEstado.MANUAL,
        server_default=OrigenCambioEstado.MANUAL.value,
    )
    # Nulo mientras no haya roles, y también en los cambios AUTOMATICO, que por
    # definición no tienen una persona detrás. Por eso el origen va aparte: null
    # acá solo no alcanza para distinguir un caso del otro.
    usuario_id = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    motivo = Column(Text, nullable=True)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reclamo = relationship("Reclamo", back_populates="historial_estados")
    usuario = relationship("Usuario")
