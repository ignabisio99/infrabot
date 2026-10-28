import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text
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
    PENDIENTE_COORDINACION = "PENDIENTE_COORDINACION"
    VISITA_COORDINADA = "VISITA_COORDINADA"
    EN_EJECUCION = "EN_EJECUCION"
    PENDIENTE_INTERVENCION = "PENDIENTE_INTERVENCION"
    FINALIZADO = "FINALIZADO"
    DESIERTO = "DESIERTO"
    RECHAZADO = "RECHAZADO"
    CANCELADO = "CANCELADO"

    @property
    def etiqueta(self) -> str:
        """Para los mensajes que ve una persona. Igual que en el frontend (claims/estados.js)."""
        return _ETIQUETAS_ESTADO_RECLAMO[self]


_ETIQUETAS_ESTADO_RECLAMO = {
    EstadoReclamo.PENDIENTE_REVISION: "Pendiente de revisión",
    EstadoReclamo.PENDIENTE_PRESUPUESTO: "Pendiente de presupuesto",
    EstadoReclamo.EN_EVALUACION: "En evaluación",
    EstadoReclamo.APROBADO: "Aprobado",
    EstadoReclamo.PENDIENTE_COORDINACION: "Pendiente de coordinación",
    EstadoReclamo.VISITA_COORDINADA: "Visita coordinada",
    EstadoReclamo.EN_EJECUCION: "En ejecución",
    EstadoReclamo.PENDIENTE_INTERVENCION: "Pendiente de intervención",
    EstadoReclamo.FINALIZADO: "Finalizado",
    EstadoReclamo.DESIERTO: "Desierto",
    EstadoReclamo.RECHAZADO: "Rechazado",
    EstadoReclamo.CANCELADO: "Cancelado",
}


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
    requiere_revision = Column(Boolean, nullable=False, default=False)
    # WhatsApp al que se le ofrecen los horarios de la visita. El bot lo llena con el
    # número que escribe; el alta web, con el teléfono de quien carga el reclamo.
    telefono_creador = Column(String(50), nullable=True)
    # True solo si el reclamo se cargó por el bot. El alta web queda en false.
    alta_whatsapp = Column(Boolean, nullable=False, default=False, server_default="false")
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
    comentarios = relationship(
        "ComentarioReclamo",
        back_populates="reclamo",
        cascade="all, delete-orphan",
        order_by="ComentarioReclamo.fecha",
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

    @property
    def ofertas_en_carrera(self) -> int:
        """Las que todavía esperan una decisión: si el reclamo se cancela, se les avisa."""
        from services.estados_presupuesto import esta_vigente

        return sum(1 for p in self.presupuestos if esta_vigente(p))
