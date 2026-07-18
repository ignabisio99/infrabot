from pydantic import BaseModel, ConfigDict, Field


class ContratistaCreate(BaseModel):
    nombre_empresa: str = Field(min_length=3)
    telefono: str = Field(min_length=6)
    direccion: str = Field(min_length=3)
    especialidad: str = Field(min_length=2)
    calificacion: int = Field(ge=1, le=5)


class ContratistaOut(ContratistaCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
