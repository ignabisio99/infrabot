from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from models.foto_reclamo import TipoMedia
from models.historial_estado_reclamo import OrigenCambioEstado
from models.reclamo import EstadoReclamo, PrioridadReclamo


class ReclamoCreate(BaseModel):
    nombre_escuela: str = Field(min_length=3)
    ubicacion: str = Field(min_length=2)
    prioridad: PrioridadReclamo
    categoria: str = Field(min_length=1)
    descripcion: str = Field(min_length=10)
    observaciones: str | None = None


class FotoReclamoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reclamo_id: int
    nombre_archivo: str
    url: str
    tipo: TipoMedia
    fecha_creacion: datetime


class ReclamoOut(ReclamoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoReclamo
    requiere_revision: bool = False
    fecha_creacion: datetime
    fotos: list[FotoReclamoOut] = []
    # Qué transiciones habilitar en la UI para este reclamo, según su estado actual.
    estados_posibles: list[EstadoReclamo]


class CambioEstadoReclamo(BaseModel):
    estado: EstadoReclamo
    motivo: str | None = None


class HistorialEstadoReclamoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reclamo_id: int
    estado_anterior: EstadoReclamo | None
    estado_nuevo: EstadoReclamo
    origen: OrigenCambioEstado
    usuario_id: int | None
    motivo: str | None
    fecha: datetime
