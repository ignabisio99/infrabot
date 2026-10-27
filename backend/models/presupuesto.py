import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class EstadoPresupuesto(str, enum.Enum):
    RECIBIDO = "RECIBIDO"
    # La oferta sigue en carrera, pero el organismo pidió corregirla. El contratista
    # manda una versión nueva y vuelve a RECIBIDO.
    AJUSTES_SOLICITADOS = "AJUSTES_SOLICITADOS"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    # Perdió contra otro presupuesto del mismo reclamo. Va aparte de RECHAZADO porque no
    # hubo un juicio sobre esta oferta: simplemente se eligió otra.
    NO_SELECCIONADO = "NO_SELECCIONADO"

    @property
    def etiqueta(self) -> str:
        """Para los mensajes que ve una persona. Igual que en el frontend (budgets/estados.js)."""
        return _ETIQUETAS_ESTADO_PRESUPUESTO[self]


_ETIQUETAS_ESTADO_PRESUPUESTO = {
    EstadoPresupuesto.RECIBIDO: "Recibido",
    EstadoPresupuesto.AJUSTES_SOLICITADOS: "Ajustes solicitados",
    EstadoPresupuesto.APROBADO: "Aprobado",
    EstadoPresupuesto.RECHAZADO: "Rechazado",
    EstadoPresupuesto.NO_SELECCIONADO: "No seleccionado",
}


# Mismo motivo que `estado_reclamo_enum` en models/reclamo.py: el tipo lo usan dos
# tablas (presupuesto e historial_estado_presupuesto) y asociarlo a la MetaData hace que
# `create_all` lo cree una sola vez en vez de emitir un CREATE TYPE por tabla.
estado_presupuesto_enum = Enum(
    EstadoPresupuesto, name="estado_presupuesto", metadata=Base.metadata
)


class TipoItemPresupuesto(str, enum.Enum):
    MATERIAL = "MATERIAL"
    MANO_OBRA = "MANO_OBRA"


tipo_item_presupuesto_enum = Enum(
    TipoItemPresupuesto, name="tipo_item_presupuesto", metadata=Base.metadata
)


class Presupuesto(Base):
    __tablename__ = "presupuesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    contratista_id = Column(
        Integer, ForeignKey("contratista.id", ondelete="RESTRICT"), nullable=False
    )
    estado = Column(
        estado_presupuesto_enum,
        nullable=False,
        default=EstadoPresupuesto.RECIBIDO,
        server_default=EstadoPresupuesto.RECIBIDO.value,
    )
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    detalle_tarea = Column(Text, nullable=True)
    observaciones = Column(Text, nullable=True)

    items = relationship(
        "ItemPresupuesto", back_populates="presupuesto", cascade="all, delete-orphan"
    )
    reclamo = relationship("Reclamo", back_populates="presupuestos")
    contratista = relationship("Contratista")
    historial_estados = relationship(
        "HistorialEstadoPresupuesto",
        back_populates="presupuesto",
        cascade="all, delete-orphan",
        order_by="HistorialEstadoPresupuesto.fecha",
    )
    versiones_anteriores = relationship(
        "VersionPresupuesto",
        back_populates="presupuesto",
        cascade="all, delete-orphan",
        order_by="VersionPresupuesto.numero",
    )

    @property
    def estados_posibles(self) -> list[EstadoPresupuesto]:
        """Decisiones que una persona puede tomar sobre este presupuesto ahora.

        No incluye las que sólo dispara el sistema, y queda vacía si el reclamo ya no
        está evaluando: sobre una oferta de un reclamo cancelado o ya resuelto no se
        decide más, aunque el presupuesto siga RECIBIDO. Así la UI no ofrece una acción
        que el backend después va a rechazar.

        Import local por lo mismo que en Reclamo.estados_posibles: el servicio importa
        este módulo.
        """
        from services.estados_presupuesto import hay_evaluacion_abierta, transiciones_posibles

        if not hay_evaluacion_abierta(self):
            return []

        permitidos = transiciones_posibles(self.estado)
        return [estado for estado in EstadoPresupuesto if estado in permitidos]

    @property
    def version(self) -> int:
        return len(self.versiones_anteriores) + 1

    @property
    def editable(self) -> bool:
        from services.estados_presupuesto import admite_edicion

        return admite_edicion(self)

    @property
    def motivo_estado(self) -> str | None:
        from services.estados_presupuesto import motivo_estado

        return motivo_estado(self)


class ItemPresupuesto(Base):
    __tablename__ = "item_presupuesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    presupuesto_id = Column(
        Integer, ForeignKey("presupuesto.id", ondelete="CASCADE"), nullable=False
    )
    tipo = Column(
        tipo_item_presupuesto_enum,
        nullable=False,
        default=TipoItemPresupuesto.MATERIAL,
        server_default=TipoItemPresupuesto.MATERIAL.value,
    )
    descripcion = Column(Text, nullable=False)
    cantidad = Column(Numeric(10, 2), nullable=False)
    unidad = Column(String(20), nullable=False, default="unidad", server_default="unidad")
    costo_unitario = Column(Numeric(12, 2), nullable=False)

    presupuesto = relationship("Presupuesto", back_populates="items")


class VersionPresupuesto(Base):
    """Lo que tenía un presupuesto antes de que el contratista lo modificara.

    El presupuesto guarda siempre la versión vigente; acá quedan las anteriores tal como
    se enviaron, para que se vea qué cambió entre una y otra.
    """

    __tablename__ = "version_presupuesto"

    id = Column(Integer, primary_key=True, autoincrement=True)
    presupuesto_id = Column(
        Integer, ForeignKey("presupuesto.id", ondelete="CASCADE"), nullable=False
    )
    numero = Column(Integer, nullable=False)
    detalle_tarea = Column(Text, nullable=True)
    observaciones = Column(Text, nullable=True)
    items = Column(JSON, nullable=False)
    fecha_envio = Column(DateTime(timezone=True), nullable=False)
    fecha_reemplazo = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # El pedido que motivó la versión siguiente; nulo si el contratista la cambió por su cuenta.
    ajustes_solicitados = Column(Text, nullable=True)

    presupuesto = relationship("Presupuesto", back_populates="versiones_anteriores")
