from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from core.database import Base
from models.historial_estado_reclamo import OrigenCambioEstado
from models.presupuesto import estado_presupuesto_enum


class HistorialEstadoPresupuesto(Base):
    """Registro de cada cambio de estado de un presupuesto.

    Espejo de HistorialEstadoReclamo, y reusa su enum `origen_cambio_estado`: la
    distinción entre lo que decide una persona y lo que deduce el sistema es la misma en
    las dos máquinas. Acá lo automático es NO_SELECCIONADO, que sale de haber aprobado
    otro presupuesto del mismo reclamo.
    """

    __tablename__ = "historial_estado_presupuesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    presupuesto_id = Column(
        Integer, ForeignKey("presupuesto.id", ondelete="CASCADE"), nullable=False
    )
    # Nulo en el primer registro: el presupuesto nace RECIBIDO sin estado previo.
    estado_anterior = Column(estado_presupuesto_enum, nullable=True)
    estado_nuevo = Column(estado_presupuesto_enum, nullable=False)
    origen = Column(
        Enum(OrigenCambioEstado, name="origen_cambio_estado"),
        nullable=False,
        default=OrigenCambioEstado.MANUAL,
        server_default=OrigenCambioEstado.MANUAL.value,
    )
    usuario_id = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    motivo = Column(Text, nullable=True)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    presupuesto = relationship("Presupuesto", back_populates="historial_estados")
    usuario = relationship("Usuario")
