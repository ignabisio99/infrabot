from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MensajeConversacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversacion_id: int | None = None
    telefono: str
    autor: str
    operador_id: int | None = None
    operador_nombre: str | None = None
    tipo: str
    texto: str | None = None
    media_url: str | None = None
    mime_type: str | None = None
    transcripcion: str | None = None
    media_eliminada: bool = False
    fecha: datetime


class HistorialTelefonoOut(BaseModel):
    mensajes: list[MensajeConversacionOut]
    hay_mas: bool


class ConversacionBandejaOut(BaseModel):
    id: int
    telefono: str
    estado: str
    operador_id: int | None = None
    operador_nombre: str | None = None
    fecha_solicitud: datetime | None = None
    fecha_toma: datetime | None = None
    fecha_cierre: datetime | None = None
    ultimo_mensaje_usuario: datetime | None = None
    ventana_abierta: bool = False
    ultimo_texto: str | None = None
    ultimo_tipo: str | None = None
    ultimo_autor: str | None = None
    ultimo_id: int | None = None
    ultimo_fecha: datetime | None = None


class BandejaOut(BaseModel):
    en_espera: list[ConversacionBandejaOut]
    mias: list[ConversacionBandejaOut]


class EnviarMensajeIn(BaseModel):
    texto: str = Field(min_length=1, max_length=4096)


class TransferirIn(BaseModel):
    operador_id: int


class OperadorOut(BaseModel):
    id: int
    nombre: str
