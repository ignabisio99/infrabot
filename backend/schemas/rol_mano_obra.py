from pydantic import BaseModel, ConfigDict, field_validator


class RolManoObraCreate(BaseModel):
    nombre: str

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("El nombre del rol debe tener al menos 2 caracteres")
        if len(v) > 100:
            raise ValueError("El nombre del rol no puede superar los 100 caracteres")
        return v


class RolManoObraOut(RolManoObraCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
