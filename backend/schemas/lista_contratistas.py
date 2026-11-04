from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from schemas.contratista import ContratistaOut


class ListaContratistasCreate(BaseModel):
    nombre: str
    contratista_ids: list[int]

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("El nombre de la lista debe tener al menos 2 caracteres")
        return v

    @field_validator("contratista_ids")
    @classmethod
    def validar_contratistas(cls, v):
        if len(v) < 1:
            raise ValueError("La lista debe tener al menos un contratista")
        return v


class ListaContratistasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    fecha_creacion: datetime
    contratistas: list[ContratistaOut] = []


class NotificarContratistasIn(BaseModel):
    """Notificar por WhatsApp a contratistas para que carguen presupuesto.

    Se debe enviar `contratista_ids` (selección manual) o `lista_id` (lista predefinida).
    `ya_notificados` dice qué hacer con los que ya fueron convocados para el reclamo:
    "preguntar" responde 409 con la lista sin enviar nada, "reenviar" les manda de nuevo
    y "omitir" notifica solo a los demás.
    """
    contratista_ids: list[int] | None = None
    lista_id: int | None = None
    ya_notificados: Literal["preguntar", "reenviar", "omitir"] = "preguntar"


class ContratistaYaNotificado(BaseModel):
    contratista_id: int
    nombre_empresa: str
    fecha_ultimo_aviso: datetime
    presupuesto_cargado: bool


class NotificacionResultado(BaseModel):
    contratista_id: int
    nombre_empresa: str
    telefono: str
    enviado: bool
    error: str | None = None


class NotificarContratistasOut(BaseModel):
    total: int
    enviados: int
    resultados: list[NotificacionResultado]


class SolicitudPresupuestoOut(BaseModel):
    """Una oferta de un contratista convocado para un reclamo, o la solicitud pendiente
    si todavía no mandó ninguna. Un contratista puede tener varias filas (ej. una
    rechazada y la que mandó después)."""
    contratista_id: int
    nombre_empresa: str
    especialidad: str
    telefono: str
    contratista_dado_de_baja: bool = False
    fecha_solicitud: datetime
    presupuesto_cargado: bool
    presupuesto_id: int | None = None
    presupuesto_estado: str | None = None
    presupuesto_fecha: datetime | None = None
    monto: Decimal | None = None
    version: int = 0


class SolicitarInformacionIn(BaseModel):
    """Pedido de información adicional de un contratista al creador del reclamo."""
    mensaje: str

    @field_validator("mensaje")
    @classmethod
    def validar_mensaje(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("El mensaje debe tener al menos 5 caracteres")
        if len(v) > 1000:
            raise ValueError("El mensaje no puede superar los 1000 caracteres")
        return v
