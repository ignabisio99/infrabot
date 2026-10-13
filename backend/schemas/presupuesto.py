from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from models.historial_estado_reclamo import OrigenCambioEstado
from models.presupuesto import EstadoPresupuesto, TipoItemPresupuesto


class ItemPresupuestoCreate(BaseModel):
    tipo: TipoItemPresupuesto = TipoItemPresupuesto.MATERIAL
    descripcion: str = Field(min_length=1)
    cantidad: Decimal = Field(gt=0)
    unidad: str = Field(default="unidad", min_length=1, max_length=20)
    costo_unitario: Decimal = Field(ge=0)


class ItemPresupuestoOut(ItemPresupuestoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.costo_unitario


class PresupuestoBase(BaseModel):
    contratista_id: int
    detalle_tarea: str | None = None
    observaciones: str | None = None
    items: list[ItemPresupuestoCreate] = Field(min_length=1)


class PresupuestoCreate(PresupuestoBase):
    reclamo_id: int


class PresupuestoUpdate(PresupuestoBase):
    """Lo mismo que crear, pero sin `reclamo_id`: el reclamo queda fijo desde el alta.

    Si el presupuesto se cargó en el reclamo equivocado, se da de baja y se carga de
    nuevo. `extra="forbid"` para que mandarlo igual devuelva un 422 explicando el
    error, en vez de descartarlo en silencio y hacer creer que el cambio se aplicó.
    """

    model_config = ConfigDict(extra="forbid")


class ReclamoResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_escuela: str


class ContratistaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_empresa: str


class PresupuestoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reclamo_id: int
    contratista_id: int
    fecha: datetime
    detalle_tarea: str | None
    observaciones: str | None
    items: list[ItemPresupuestoOut]
    reclamo: ReclamoResumen
    contratista: ContratistaResumen
    estado: EstadoPresupuesto
    # Qué decisiones habilitar en la UI para este presupuesto, según su estado actual.
    estados_posibles: list[EstadoPresupuesto]
    # Número de envío de este contratista para el reclamo (1 = primero).
    intento: int
    editable: bool
    reenviable: bool
    motivo_rechazo: str | None

    @computed_field
    @property
    def monto(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0"))


class DecisionPresupuesto(BaseModel):
    estado: EstadoPresupuesto
    motivo: str | None = None


class OfertaReutilizableOut(BaseModel):
    presupuesto_id: int
    contratista_id: int
    nombre_empresa: str
    monto: Decimal
    estado: EstadoPresupuesto


class AsignarOfertaExistenteIn(BaseModel):
    presupuesto_id: int


class HistorialEstadoPresupuestoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    presupuesto_id: int
    estado_anterior: EstadoPresupuesto | None
    estado_nuevo: EstadoPresupuesto
    origen: OrigenCambioEstado
    usuario_id: int | None
    motivo: str | None
    fecha: datetime
