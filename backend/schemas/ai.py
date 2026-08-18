from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from models.adjunto_presupuesto import TipoAdjuntoPresupuesto
from models.reclamo import EstadoReclamo, PrioridadReclamo
from services.ai.auditoria import RecomendacionAuditoria


class ClasificacionOut(BaseModel):
    reclamo_id: int
    categoria: str
    prioridad: PrioridadReclamo
    confianza: float = Field(ge=0, le=1)
    justificacion: str
    proveedor: str
    aplicada: bool = False


class DuplicadoOut(BaseModel):
    reclamo_id: int
    nombre_escuela: str
    categoria: str
    estado: EstadoReclamo
    descripcion: str
    similitud: float


class DuplicadosOut(BaseModel):
    reclamo_id: int
    candidatos: list[DuplicadoOut]


class EstimacionPreliminarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reclamo_id: int
    materiales: Decimal
    mano_obra: Decimal
    otros: Decimal
    total: Decimal
    confianza: float
    detalle: str | None
    proveedor: str
    fecha: datetime


class AuditoriaOut(BaseModel):
    presupuesto_id: int
    reclamo_id: int
    total_presupuesto: Decimal
    total_estimacion: Decimal | None
    desvio_absoluto: Decimal | None
    desvio_porcentual: Decimal | None
    recomendacion: RecomendacionAuditoria
    notas_tecnicas: str
    proveedor_notas: str
    sin_estimacion: bool


class InflacionSyncOut(BaseModel):
    filas: int
    serie_id: str
    mensaje: str


class AnalisisMediaOut(BaseModel):
    reclamo_id: int
    hallazgos: list[str]
    severidad: str
    sugerencia_descripcion: str
    fotos_analizadas: int
    proveedor: str
    enriquecido: bool = False


class ItemExtraidoOut(BaseModel):
    descripcion: str
    cantidad: Decimal
    costo_unitario: Decimal


class ExtraccionPresupuestoOut(BaseModel):
    adjunto_id: int
    url: str
    tipo: TipoAdjuntoPresupuesto
    items: list[ItemExtraidoOut]
    proveedor: str
    metodo: str
