from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from models.adjunto_presupuesto import TipoAdjuntoPresupuesto
from models.reclamo import EstadoReclamo, PrioridadReclamo
from models.recomendacion_ia import TipoRecomendacionIA
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
    requiere_revision: bool = False
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


class ReferenciasSyncOut(BaseModel):
    creadas: int
    actualizadas: int
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


class RecomendacionIAOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoRecomendacionIA
    reclamo_id: int | None
    presupuesto_id: int | None
    proveedor: str | None
    confianza: float | None
    payload: str
    requiere_revision: bool
    fecha: datetime


class ContratistaSugeridoOut(BaseModel):
    contratista_id: int
    nombre_empresa: str
    especialidad: str
    calificacion: int
    carga_activa: int
    score: int
    motivos: list[str]


class PipelineDuplicadoOut(BaseModel):
    reclamo_id: int
    nombre_escuela: str
    categoria: str
    estado: str
    descripcion: str
    similitud: float


class PipelineOut(BaseModel):
    reclamo_id: int
    pasos: list[str]
    categoria: str | None = None
    prioridad: str | None = None
    confianza: float | None = None
    justificacion: str | None = None
    razonamiento: str | None = None
    duplicados: list[PipelineDuplicadoOut] = []


class HerramientaUsadaOut(BaseModel):
    herramienta: str
    args: dict = {}


class AgenteOut(BaseModel):
    reclamo_id: int
    razonamiento: str | None = None
    categoria: str | None = None
    prioridad: str | None = None
    escuela_en_padron: bool | None = None
    es_posible_duplicado: bool | None = None
    resumen_para_operador: str | None = None
    confianza: float | None = None
    herramientas_usadas: list[HerramientaUsadaOut] = []
    proveedor: str | None = None
    estimacion_id: int | None = None
    total: float | None = None
    requiere_revision: bool = False
    error: str | None = None


class SeguimientoOut(BaseModel):
    enviados: int
    omitidos: int
    umbral_horas: float
    mensaje: str
