from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from core.database import Base


class BusquedaReclamo(Base):
    """Reclamo propio que un número consultó por WhatsApp.

    Una fila por (teléfono, reclamo): volver a buscarlo actualiza la fecha. Sirve para
    mostrarle sus últimas consultas al tocar *Buscar reclamo*.
    """

    __tablename__ = "busqueda_reclamo"
    __table_args__ = (
        UniqueConstraint("telefono", "reclamo_id", name="uq_busqueda_telefono_reclamo"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    telefono = Column(String(50), nullable=False, index=True)
    reclamo_id = Column(Integer, ForeignKey("reclamo.id", ondelete="CASCADE"), nullable=False)
    fecha = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
