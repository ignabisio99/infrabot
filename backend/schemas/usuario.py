import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models.usuario import EstadoUsuario, TipoUsuario


class UsuarioRegister(BaseModel):
    nombre: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validar_password(cls, v):
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe tener al menos una mayúscula")
        if not re.search(r"[!@#$%^&*()_+\\-=\\[\\]{};':\"\\\\|,.<>\\/?]", v):
            raise ValueError("La contraseña debe tener al menos un símbolo especial")
        return v


class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str


class CompletarPerfil(BaseModel):
    telefono: str = Field(min_length=6)
    direccion: str = Field(min_length=5)
    tipo: TipoUsuario
    nombre_empresa: str | None = None
    especialidad: str | None = None

    @field_validator("nombre_empresa")
    @classmethod
    def validar_empresa(cls, v, info):
        if info.data.get("tipo") == TipoUsuario.CONTRATISTA and (not v or len(v.strip()) < 2):
            raise ValueError("Los contratistas deben especificar el nombre de la empresa")
        return v

    @field_validator("especialidad")
    @classmethod
    def validar_especialidad(cls, v, info):
        if info.data.get("tipo") == TipoUsuario.CONTRATISTA and (not v or len(v.strip()) < 2):
            raise ValueError("Los contratistas deben especificar su especialidad")
        return v


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: str
    email_confirmado: bool
    telefono: str | None = None
    direccion: str | None = None
    tipo: TipoUsuario | None = None
    estado: EstadoUsuario
    nombre_empresa: str | None = None
    especialidad: str | None = None
    fecha_creacion: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class MensajeOut(BaseModel):
    mensaje: str
