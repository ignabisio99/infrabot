from pydantic import BaseModel, ConfigDict, Field


class RolManoObraCreate(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)


class RolManoObraOut(RolManoObraCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
