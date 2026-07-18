from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.reclamo import PrioridadReclamo


class ReclamoCreate(BaseModel):
    nombre_escuela: str = Field(min_length=3)
    sector: str = Field(min_length=2)
    prioridad: PrioridadReclamo
    categoria: str = Field(min_length=1)
    descripcion: str = Field(min_length=10)


class ReclamoOut(ReclamoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creado_en: datetime
