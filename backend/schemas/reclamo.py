from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from models.foto_reclamo import TipoMedia
from models.historial_estado_reclamo import OrigenCambioEstado
from models.reclamo import EstadoReclamo, PrioridadReclamo


class ReclamoCreate(BaseModel):
    nombre_escuela: str
    ubicacion: str
    prioridad: PrioridadReclamo
    categoria: str
    descripcion: str
    observaciones: str | None = None

    @field_validator("nombre_escuela")
    @classmethod
    def validar_nombre_escuela(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("El nombre de la escuela debe tener al menos 3 caracteres")
        return v

    @field_validator("ubicacion")
    @classmethod
    def validar_ubicacion(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("La ubicación debe tener al menos 2 caracteres")
        return v

    @field_validator("categoria")
    @classmethod
    def validar_categoria(cls, v):
        if len(v.strip()) < 1:
            raise ValueError("La categoría es obligatoria")
        return v

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v):
        if len(v.strip()) < 10:
            raise ValueError("La descripción debe tener al menos 10 caracteres")
        return v


class FotoReclamoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reclamo_id: int
    nombre_archivo: str
    url: str
    tipo: TipoMedia
    fecha_creacion: datetime
    usuario_id: int | None = None
    autor: str | None = None


class ReclamoOut(ReclamoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoReclamo
    requiere_revision: bool = False
    telefono_creador: str | None = None
    fecha_creacion: datetime
    fotos: list[FotoReclamoOut] = []
    # Qué transiciones habilitar en la UI para este reclamo, según su estado actual.
    estados_posibles: list[EstadoReclamo]
    # Si el reclamo se puede cotizar; lo usa el formulario de presupuestos.
    admite_presupuesto: bool


class CambioEstadoReclamo(BaseModel):
    estado: EstadoReclamo
    motivo: str | None = None


class ComentarioReclamoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    texto: str

    @field_validator("texto")
    @classmethod
    def validar_texto(cls, v):
        if len(v.strip()) < 1:
            raise ValueError("El comentario no puede estar vacío")
        return v


class ComentarioReclamoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reclamo_id: int
    usuario_id: int | None
    autor: str | None
    texto: str
    fecha: datetime


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
