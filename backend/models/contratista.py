from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from core.database import Base


class Contratista(Base):
    __tablename__ = "contratista"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_empresa = Column(String(255), nullable=False)
    telefono = Column(String(50), nullable=False)
    direccion = Column(String(255), nullable=False)
    especialidad = Column(String(255), nullable=False)
    # Nullable: un contratista recién dado de alta no tiene calificación (N/A) hasta
    # que un administrador se la asigna.
    calificacion = Column(Integer, nullable=True)
    # Nota opcional del admin sobre por qué asignó esa calificación.
    observaciones_calificacion = Column(String(1000), nullable=True)
    # Vínculo opcional con la cuenta de usuario (tipo CONTRATISTA) que se loguea.
    # Permite que el contratista cargue presupuestos desde su sesión.
    usuario_id = Column(
        Integer, ForeignKey("usuario.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    # Un contratista no se borra: sus presupuestos y visitas son el expediente de los
    # reclamos en que trabajó. Dado de baja no se lo convoca ni puede ofertar.
    fecha_baja = Column(DateTime(timezone=True), nullable=True)

    usuario = relationship("Usuario")

    @property
    def dado_de_baja(self) -> bool:
        return self.fecha_baja is not None
