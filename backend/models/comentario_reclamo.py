from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from core.database import Base


class ComentarioReclamo(Base):
    """Comentario que deja un inspector sobre un reclamo.

    No se editan ni se borran: quedan en el expediente y los ve quien presupuesta.
    """

    __tablename__ = "comentario_reclamo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    texto = Column(Text, nullable=False)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reclamo = relationship("Reclamo", back_populates="comentarios")
    usuario = relationship("Usuario")

    @property
    def autor(self) -> str | None:
        return self.usuario.nombre if self.usuario else None
