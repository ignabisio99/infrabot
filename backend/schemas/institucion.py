from pydantic import BaseModel, ConfigDict, field_validator


class InstitucionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    domicilio: str | None
    localidad: str | None

    # El padrón trae dobles espacios (ej: 'MENDOZA 1069  BARRIO'); el domicilio se copia
    # tal cual a la ubicación del reclamo, así que sale limpio igual que en el bot.
    @field_validator("nombre", "domicilio", "localidad", mode="before")
    @classmethod
    def colapsar_espacios(cls, v):
        return " ".join(v.split()) if isinstance(v, str) else v
