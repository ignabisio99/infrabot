"""Seguimiento del avance del contratista sobre un reclamo en ejecución (CU-05).

Guarda cuándo se le preguntó por última vez si terminó, cuántas veces se preguntó sin
respuesta (para escalar a DESIERTO tras el máximo), cuándo toca volver a preguntar
(según el tiempo estimado que da el contratista) y si ya se le preguntó a la escuela si
quedó resuelto.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer

from core.database import Base


class RecordatorioContratista(Base):
    __tablename__ = "recordatorio_contratista"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(
        Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    ultimo_envio = Column(DateTime(timezone=True), nullable=False)
    cantidad_envios = Column(Integer, nullable=False, default=1)
    # Cuándo volver a preguntar "¿terminaste?". Si está seteada, manda sobre el umbral
    # fijo de horas: la fija el tiempo estimado que informó el contratista.
    proxima_pregunta = Column(DateTime(timezone=True), nullable=True)
    # True una vez que el contratista confirmó que terminó y se le preguntó a la escuela
    # si quedó resuelto. Evita volver a molestar al contratista mientras tanto.
    consulto_escuela = Column(Boolean, nullable=False, default=False)
    creado_en = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
