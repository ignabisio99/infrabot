"""Padrón de instituciones (escuelas) que el sistema cubre.

Se carga desde el CSV oficial con `scripts/importar_instituciones.py`. Sirve para que
al crear un reclamo el bot valide/sugiera la escuela contra este padrón.
"""

from sqlalchemy import Column, Integer, String

from core.database import Base


class Institucion(Base):
    __tablename__ = "institucion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Identificador oficial del CSV (único).
    identificador = Column(String(50), nullable=True, unique=True, index=True)
    nombre = Column(String(500), nullable=False, index=True)
    domicilio = Column(String(500), nullable=True)
    localidad = Column(String(255), nullable=True)
    codigo_postal = Column(String(20), nullable=True)
