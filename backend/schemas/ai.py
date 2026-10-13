import json
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

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


def _detalle_sin_precedentes(detalle: str | None) -> bool:
    if not detalle:
        return False
    try:
        data = json.loads(detalle) if isinstance(detalle, str) else detalle
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    motivo = (data.get("validacion") or {}).get("motivo")
    if motivo in ("sin_referencias", "promedio_refs_invalido"):
        return True
    refs = data.get("referencias_ids")
    return isinstance(refs, list) and len(refs) == 0


def _justificacion_de_detalle(detalle: str | None) -> str | None:
    if not detalle:
        return None
    try:
        data = json.loads(detalle) if isinstance(detalle, str) else detalle
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    texto = data.get("justificacion")
    if isinstance(texto, str) and texto.strip():
        return texto.strip()
    return None


class TranscripcionOut(BaseModel):
    texto: str
    proveedor: str
    mime_type: str


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

    @computed_field
    @property
    def sin_precedentes(self) -> bool:
        return _detalle_sin_precedentes(self.detalle)

    @computed_field
    @property
    def justificacion(self) -> str | None:
        return _justificacion_de_detalle(self.detalle)


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
    sin_precedentes: bool = False


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
    escalados: int = 0
    umbral_horas: float
    mensaje: str
