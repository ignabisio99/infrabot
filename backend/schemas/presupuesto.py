from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from models.historial_estado_reclamo import OrigenCambioEstado
from models.presupuesto import EstadoPresupuesto, TipoItemPresupuesto
from models.reclamo import EstadoReclamo


class _ItemPresupuestoCampos(BaseModel):
    tipo: TipoItemPresupuesto = TipoItemPresupuesto.MATERIAL
    descripcion: str
    cantidad: Decimal
    unidad: str = "unidad"
    costo_unitario: Decimal


# Topes razonables para una obra escolar, y por debajo de lo que entra en las columnas
# (Numeric(10,2) y Numeric(12,2)): un número más grande no tiene sentido y haría fallar
# el guardado con un error de la base.
CANTIDAD_MAXIMA = Decimal("1000000")
COSTO_UNITARIO_MAXIMO = Decimal("1000000000")


class ItemPresupuestoCreate(_ItemPresupuestoCampos):
    """Un ítem que se carga: las reglas valen al crear o editar, no al leer lo guardado
    (por eso los de salida heredan solo los campos)."""

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, v):
        if len(v.strip()) < 1:
            raise ValueError("La descripción del ítem no puede estar vacía")
        return v

    @field_validator("cantidad")
    @classmethod
    def validar_cantidad(cls, v):
        if v <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        if v > CANTIDAD_MAXIMA:
            raise ValueError("La cantidad no puede superar 1.000.000")
        return v

    @field_validator("costo_unitario")
    @classmethod
    def validar_costo(cls, v):
        # Un ítem en $0 no es un presupuesto: si algo no se cobra, que no vaya como ítem.
        if v <= 0:
            raise ValueError("El costo unitario debe ser mayor a 0")
        if v > COSTO_UNITARIO_MAXIMO:
            raise ValueError("El costo unitario no puede superar $1.000.000.000")
        return v

    @field_validator("unidad")
    @classmethod
    def validar_unidad(cls, v):
        if len(v.strip()) < 1:
            raise ValueError("La unidad no puede estar vacía")
        if len(v) > 20:
            raise ValueError("La unidad no puede superar los 20 caracteres")
        return v


class ItemPresupuestoOut(_ItemPresupuestoCampos):
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
    items: list[ItemPresupuestoCreate]

    @field_validator("items")
    @classmethod
    def validar_items(cls, v):
        if len(v) < 1:
            raise ValueError("El presupuesto debe tener al menos un ítem")
        return v


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
    estado: EstadoReclamo


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
    # 1 = como se envió; suma uno cada vez que el contratista lo modifica.
    version: int
    editable: bool
    # Por qué se rechazó o qué ajustes se pidieron.
    motivo_estado: str | None

    @computed_field
    @property
    def monto(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0"))


class ItemVersionOut(_ItemPresupuestoCampos):
    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.costo_unitario


class VersionPresupuestoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    numero: int
    detalle_tarea: str | None
    observaciones: str | None
    items: list[ItemVersionOut]
    fecha_envio: datetime
    fecha_reemplazo: datetime
    ajustes_solicitados: str | None

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
