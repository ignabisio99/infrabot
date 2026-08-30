import enum
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class PrioridadReclamo(str, enum.Enum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"


class EstadoReclamo(str, enum.Enum):
    PENDIENTE_REVISION = "PENDIENTE_REVISION"
    PENDIENTE_PRESUPUESTO = "PENDIENTE_PRESUPUESTO"
    EN_EVALUACION = "EN_EVALUACION"
    APROBADO = "APROBADO"
    EN_EJECUCION = "EN_EJECUCION"
    FINALIZADO = "FINALIZADO"
    DESIERTO = "DESIERTO"
    RECHAZADO = "RECHAZADO"
    CANCELADO = "CANCELADO"


# El tipo enum de Postgres lo usan dos tablas (reclamo e historial_estado_reclamo). Al
# asociarlo a la MetaData, SQLAlchemy lo crea una sola vez en `create_all` en vez de
# emitir un CREATE TYPE por tabla.
estado_reclamo_enum = Enum(EstadoReclamo, name="estado_reclamo", metadata=Base.metadata)


class Reclamo(Base):
    __tablename__ = "reclamo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_escuela = Column(String(255), nullable=False)
    ubicacion = Column(String(255), nullable=False)
    prioridad = Column(Enum(PrioridadReclamo, name="prioridad_reclamo"), nullable=False)
    estado = Column(
        estado_reclamo_enum,
        nullable=False,
        default=EstadoReclamo.PENDIENTE_REVISION,
        server_default=EstadoReclamo.PENDIENTE_REVISION.value,
    )
    categoria = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=False)
    observaciones = Column(Text, nullable=True)
    # Número de WhatsApp de quien creó el reclamo por el bot. Null si se creó desde la web.
    telefono_creador = Column(String(50), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    fotos = relationship(
        "FotoReclamo",
        back_populates="reclamo",
        cascade="all, delete-orphan",
        order_by="FotoReclamo.id",
    )
    presupuestos = relationship(
        "Presupuesto",
        back_populates="reclamo",
        cascade="all, delete-orphan",
        order_by="Presupuesto.id",
    )
    historial_estados = relationship(
        "HistorialEstadoReclamo",
        back_populates="reclamo",
        cascade="all, delete-orphan",
        order_by="HistorialEstadoReclamo.fecha",
    )

    @property
    def estados_posibles(self) -> list[EstadoReclamo]:
        """Transiciones que una persona puede elegir desde el estado actual, en el
        orden del enum. No incluye las que sólo dispara el sistema, así el menú de
        cambio de estado no ofrece nada que después vaya a fallar.

        El import va acá adentro porque el servicio importa este módulo: a nivel
        de módulo sería un import circular.
        """
        from services.estados_reclamo import transiciones_posibles

        permitidos = transiciones_posibles(self.estado)
        return [estado for estado in EstadoReclamo if estado in permitidos]

    @property
    def admite_presupuesto(self) -> bool:
        """Si en el estado actual se le pueden cargar presupuestos.

        Lo consume el formulario de presupuestos para no ofrecer reclamos que el
        backend después va a rechazar. Import local por lo mismo que arriba.
        """
        from services.estados_reclamo import admite_presupuesto as estado_admite_presupuesto

        return estado_admite_presupuesto(self.estado)
