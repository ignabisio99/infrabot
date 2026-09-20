from datetime import datetime

from pydantic import BaseModel, ConfigDict

from models.visita import EstadoVisita


class VisitaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reclamo_id: int
    contratista_id: int
    estado: EstadoVisita
    disponibilidades: str | None = None
    horario_confirmado: str | None = None
    fecha_visita: datetime | None = None


class VisitaCalendarioOut(VisitaOut):
    nombre_escuela: str
    ubicacion: str
    nombre_empresa: str
