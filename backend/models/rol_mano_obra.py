from sqlalchemy import Column, Integer, String

from core.database import Base

ROLES_MANO_OBRA_INICIALES = [
    "Oficial",
    "Medio oficial",
    "Ayudante",
    "Capataz",
    "Electricista",
    "Plomero",
    "Albañil",
    "Pintor",
    "Otro",
]


class RolManoObra(Base):
    __tablename__ = "rol_mano_obra"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False, unique=True)


def asegurar_roles_iniciales(db):
    """Carga el catálogo de oficios si la tabla está vacía."""
    if db.query(RolManoObra).first() is not None:
        return
    db.add_all([RolManoObra(nombre=nombre) for nombre in ROLES_MANO_OBRA_INICIALES])
    db.commit()
