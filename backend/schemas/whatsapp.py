from pydantic import BaseModel, Field


class BotonWhatsAppOut(BaseModel):
    id: str
    title: str


class FilaListaWhatsAppOut(BaseModel):
    id: str
    title: str
    description: str | None = None


class SeccionListaWhatsAppOut(BaseModel):
    title: str
    rows: list[FilaListaWhatsAppOut] = []


class SimularOrigenIn(BaseModel):
    origen: str = Field(default="sim5491100000000", min_length=3, max_length=32)


class SimularTextoIn(BaseModel):
    texto: str = Field(min_length=1)
    origen: str = Field(default="sim5491100000000", min_length=3, max_length=32)


class SimularWhatsAppOut(BaseModel):
    tipo: str
    body: str
    botones: list[BotonWhatsAppOut] = []
    boton_texto: str | None = None
    secciones: list[SeccionListaWhatsAppOut] = []
    transcripcion: str | None = None
    proveedor_stt: str | None = None
