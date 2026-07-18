from sqlalchemy import Column, Integer, String

from core.database import Base


class Contratista(Base):
    __tablename__ = "contratista"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_empresa = Column(String(255), nullable=False)
    telefono = Column(String(50), nullable=False)
    direccion = Column(String(255), nullable=False)
    especialidad = Column(String(255), nullable=False)
    calificacion = Column(Integer, nullable=False)
