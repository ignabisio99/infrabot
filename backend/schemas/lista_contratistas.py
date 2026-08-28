from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.contratista import ContratistaOut


class ListaContratistasCreate(BaseModel):
    nombre: str = Field(min_length=2)
    contratista_ids: list[int] = Field(min_length=1)


class ListaContratistasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    fecha_creacion: datetime
    contratistas: list[ContratistaOut] = []


class NotificarContratistasIn(BaseModel):
    """Notificar por WhatsApp a contratistas para que carguen presupuesto.

    Se debe enviar `contratista_ids` (selección manual) o `lista_id` (lista predefinida).
    """
    contratista_ids: list[int] | None = None
    lista_id: int | None = None


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
    """Estado de una solicitud de presupuesto a un contratista para un reclamo."""
    contratista_id: int
    nombre_empresa: str
    especialidad: str
    telefono: str
    fecha_solicitud: datetime
    presupuesto_cargado: bool
    presupuesto_id: int | None = None
