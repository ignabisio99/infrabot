from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ItemPresupuestoCreate(BaseModel):
    descripcion: str = Field(min_length=1)
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal = Field(ge=0)


class ItemPresupuestoOut(ItemPresupuestoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.costo_unitario


class PresupuestoCreate(BaseModel):
    reclamo_id: int
    contratista_id: int
    observaciones: str | None = None
    items: list[ItemPresupuestoCreate] = Field(min_length=1)


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
    observaciones: str | None
    items: list[ItemPresupuestoOut]
    reclamo: ReclamoResumen
    contratista: ContratistaResumen

    @computed_field
    @property
    def monto(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0"))
