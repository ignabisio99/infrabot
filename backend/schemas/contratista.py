from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.telefonos import normalizar_telefono_ar


# Mínimo para el nombre de la empresa, el mismo en todos lados: alta desde la web, registro,
# completar el perfil y "Mi perfil" (la ficha de un contratista que se registra sale de ahí).
MIN_NOMBRE_EMPRESA = 3


def validar_nombre_empresa(v: str) -> str:
    v = v.strip()
    if len(v) < MIN_NOMBRE_EMPRESA:
        raise ValueError(
            f"El nombre de la empresa debe tener al menos {MIN_NOMBRE_EMPRESA} caracteres"
        )
    return v


class _ContratistaCampos(BaseModel):
    nombre_empresa: str
    telefono: str
    direccion: str
    especialidad: str
    calificacion: int | None = None
    observaciones_calificacion: str | None = None


class ContratistaCreate(_ContratistaCampos):
    """Lo que se carga. Las reglas valen al crear o editar, no al leer lo guardado: si el
    de salida las heredara, un contratista viejo que no las cumpla (ej. un nombre de 2
    letras) haría fallar todos los listados que lo incluyen."""

    @field_validator("nombre_empresa")
    @classmethod
    def validar_nombre_empresa(cls, v):
        return validar_nombre_empresa(v)

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
        return v.strip()

    @field_validator("especialidad")
    @classmethod
    def validar_especialidad(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("La especialidad debe tener al menos 2 caracteres")
        return v.strip()

    @field_validator("calificacion")
    @classmethod
    def validar_calificacion(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("La calificación debe estar entre 1 y 5")
        return v


class ContratistaOut(_ContratistaCampos):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None = None
    fecha_baja: datetime | None = None


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
