"""Coordinación de la visita de trabajo entre contratista y creador del reclamo.

Se crea cuando se aprueba un presupuesto. El bot pide disponibilidad al contratista,
el creador elige un horario, y se envían recordatorios el día antes y el mismo día.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from core.database import Base


class EstadoVisita(str, enum.Enum):
    ESPERANDO_DISPONIBILIDAD = "ESPERANDO_DISPONIBILIDAD"  # se le pidió al contratista
    ESPERANDO_ELECCION = "ESPERANDO_ELECCION"  # el creador debe elegir un horario
    CONFIRMADA = "CONFIRMADA"  # hay fecha/hora acordada
    CANCELADA = "CANCELADA"


class Visita(Base):
    __tablename__ = "visita"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    contratista_id = Column(
        Integer, ForeignKey("contratista.id", ondelete="RESTRICT"), nullable=False
    )
    estado = Column(
        Enum(EstadoVisita, name="estado_visita"),
        nullable=False,
        default=EstadoVisita.ESPERANDO_DISPONIBILIDAD,
    )

    # Disponibilidades propuestas por el contratista, una por línea (texto libre).
    disponibilidades = Column(Text, nullable=True)
    # Franja elegida por el creador (texto).
    horario_confirmado = Column(Text, nullable=True)
    # Fecha/hora concreta de la visita, para los recordatorios.
    fecha_visita = Column(DateTime(timezone=True), nullable=True)

    # Marcas para no repetir recordatorios.
    recordatorio_dia_antes_enviado = Column(DateTime(timezone=True), nullable=True)
    recordatorio_mismo_dia_enviado = Column(DateTime(timezone=True), nullable=True)
    # Cuándo se le preguntó al contratista si pudo empezar (en el horario pactado). Se
    # pregunta una sola vez; si responde "no pude" se reprograma la visita.
    pregunta_inicio_enviada = Column(DateTime(timezone=True), nullable=True)
    # El contratista escribió *cancelar* mientras cargaba disponibilidad: el bot no lo
    # vuelve a meter en la carga hasta que escriba *cargar horario <id del reclamo>*.
    disponibilidad_pausada = Column(Boolean, nullable=False, default=False)
    # La escuela escribió *cancelar* mientras elegía un horario: el bot no la vuelve a
    # meter en la elección hasta que escriba *elegir horario <id del reclamo>*.
    eleccion_pausada = Column(Boolean, nullable=False, default=False)

    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reclamo = relationship("Reclamo")
    contratista = relationship("Contratista")
