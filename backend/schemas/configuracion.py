from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class ConfiguracionAtencionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dias: list[int]
    hora_desde: str
    hora_hasta: str
    mensaje_fuera_horario: str
    inactividad_usuario_min: int
    actualizado_en: datetime | None = None


class ConfiguracionAtencionUpdate(BaseModel):
    dias: list[int] = Field(min_length=1)
    hora_desde: str
    hora_hasta: str
    mensaje_fuera_horario: str = Field(min_length=1, max_length=2000)
    inactividad_usuario_min: int = Field(ge=1, le=1440)

    @field_validator("dias")
    @classmethod
    def dias_validos(cls, value: list[int]) -> list[int]:
        limpios = sorted({int(d) for d in value})
        if not limpios or any(d < 0 or d > 6 for d in limpios):
            raise ValueError("Los días tienen que ser de 0 (lunes) a 6 (domingo)")
        return limpios
