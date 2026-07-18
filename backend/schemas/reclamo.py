from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.reclamo import PrioridadReclamo


class ReclamoCreate(BaseModel):
    nombre_escuela: str = Field(min_length=3)
    ubicacion: str = Field(min_length=2)
    prioridad: PrioridadReclamo
    categoria: str = Field(min_length=1)
    descripcion: str = Field(min_length=10)
    observaciones: str | None = None


class ReclamoOut(ReclamoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_creacion: datetime
