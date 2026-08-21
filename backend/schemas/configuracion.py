from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UmbralesAuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    umbral_aprobar: Decimal
    umbral_revisar: Decimal
    actualizado_en: datetime | None = None


class UmbralesAuditoriaUpdate(BaseModel):
    umbral_aprobar: Decimal = Field(gt=0, lt=1)
    umbral_revisar: Decimal = Field(gt=0, le=1)

    @model_validator(mode="after")
    def aprobar_menor_que_revisar(self):
        if self.umbral_aprobar >= self.umbral_revisar:
            raise ValueError("umbral_aprobar debe ser menor que umbral_revisar")
        return self
