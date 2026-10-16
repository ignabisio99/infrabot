from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.telefonos import normalizar_telefono_ar


class ContratistaCreate(BaseModel):
    nombre_empresa: str
    telefono: str
    direccion: str
    especialidad: str
    calificacion: int | None = None
    observaciones_calificacion: str | None = None

    @field_validator("nombre_empresa")
    @classmethod
    def validar_nombre_empresa(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("El nombre de la empresa debe tener al menos 3 caracteres")
        return v

    @field_validator("telefono")
    @classmethod
    def normalizar_telefono(cls, v):
        if len(v.strip()) < 6:
            raise ValueError("El teléfono debe tener al menos 6 dígitos")
        return normalizar_telefono_ar(v)

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("La dirección debe tener al menos 3 caracteres")
        return v

    @field_validator("especialidad")
    @classmethod
    def validar_especialidad(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("La especialidad debe tener al menos 2 caracteres")
        return v

    @field_validator("calificacion")
    @classmethod
    def validar_calificacion(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("La calificación debe estar entre 1 y 5")
        return v


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
    presupuesto_id: int | None = None
    presupuesto_estado: str | None = None
    version: int = 0
    puede_editar: bool = False
    # Puede cargar una oferta nueva: no tiene ninguna, o la que tenía quedó sin seleccionar
    # y se reabrió la convocatoria.
    puede_ofertar: bool = False
