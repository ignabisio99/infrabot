"""Listas predefinidas de contratistas que arman los administradores.

Una lista agrupa varios contratistas para poder notificarlos a todos de una vez
al momento de pedir presupuestos para un reclamo. Las listas son compartidas
entre todos los administradores (no son privadas).
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from core.database import Base

# Tabla intermedia N:N entre listas y contratistas
lista_contratista_asociacion = Table(
    "lista_contratista_asociacion",
    Base.metadata,
    Column("lista_id", Integer, ForeignKey("lista_contratistas.id", ondelete="CASCADE"), primary_key=True),
    Column("contratista_id", Integer, ForeignKey("contratista.id", ondelete="CASCADE"), primary_key=True),
)


class ListaContratistas(Base):
    __tablename__ = "lista_contratistas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(255), nullable=False)
    creada_por_id = Column(Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    contratistas = relationship(
        "Contratista",
        secondary=lista_contratista_asociacion,
        lazy="joined",
    )
