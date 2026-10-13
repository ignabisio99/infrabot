from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.telefonos import normalizar_telefono_ar


class ContratistaCreate(BaseModel):
    nombre_empresa: str = Field(min_length=3)
    telefono: str = Field(min_length=6)
    direccion: str = Field(min_length=3)
    especialidad: str = Field(min_length=2)
    calificacion: int | None = Field(default=None, ge=1, le=5)
    observaciones_calificacion: str | None = None

    @field_validator("telefono")
    @classmethod
    def normalizar_telefono(cls, v):
        return normalizar_telefono_ar(v)


class ContratistaOut(ContratistaCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None = None


class MiSolicitudOut(BaseModel):
    """Un reclamo donde el contratista logueado fue convocado a presupuestar."""

    reclamo_id: int
    nombre_escuela: str
    ubicacion: str
    categoria: str
    prioridad: str
    estado_reclamo: str
    fecha_solicitud: datetime
    presupuesto_cargado: bool
    # Del último envío: tras un rechazo el contratista puede cargar otro.
    presupuesto_id: int | None = None
    presupuesto_estado: str | None = None
    intentos: int = 0
    puede_editar: bool = False
    puede_reenviar: bool = False
