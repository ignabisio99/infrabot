import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models.usuario import EstadoUsuario, TipoUsuario
from core.telefonos import normalizar_telefono_ar


def validar_password_segura(v: str) -> str:
    """Reglas de contraseña: las mismas al registrarse y al restablecerla."""
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if not re.search(r"[A-Z]", v):
        raise ValueError("La contraseña debe tener al menos una mayúscula")
    if not re.search(r"[!@#$%^&*()\-_+=\[\]{};':\"\\|,.<>/?]", v):
        raise ValueError("La contraseña debe tener al menos un símbolo especial")
    return v


class UsuarioRegister(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    telefono: str
    direccion: str
    tipo: TipoUsuario
    nombre_empresa: str | None = None
    especialidad: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v

    @field_validator("password")
    @classmethod
    def validar_password(cls, v):
        return validar_password_segura(v)

    @field_validator("telefono")
    @classmethod
    def normalizar_telefono(cls, v):
        if len(v.strip()) < 6:
            raise ValueError("El teléfono debe tener al menos 6 dígitos")
        return normalizar_telefono_ar(v)

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("La dirección debe tener al menos 5 caracteres")
        return v

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


class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str


class CompletarPerfil(BaseModel):
    telefono: str
    direccion: str
    tipo: TipoUsuario
    nombre_empresa: str | None = None
    especialidad: str | None = None

    @field_validator("telefono")
    @classmethod
    def normalizar_telefono(cls, v):
        if len(v.strip()) < 6:
            raise ValueError("El teléfono debe tener al menos 6 dígitos")
        return normalizar_telefono_ar(v)

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("La dirección debe tener al menos 5 caracteres")
        return v

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


class UsuarioUpdate(BaseModel):
    nombre: str
    telefono: str
    direccion: str
    nombre_empresa: str | None = None
    especialidad: str | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v

    @field_validator("telefono")
    @classmethod
    def normalizar_telefono(cls, v):
        if len(v.strip()) < 6:
            raise ValueError("El teléfono debe tener al menos 6 dígitos")
        return normalizar_telefono_ar(v)

    @field_validator("direccion")
    @classmethod
    def validar_direccion(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("La dirección debe tener al menos 5 caracteres")
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


class LoginOut(BaseModel):
    """Respuesta de login exitoso (el token va en la cookie, no en el body)."""
    usuario: UsuarioOut


class TokenOut(BaseModel):
    """Mantiene compatibilidad con flujos que necesiten el token explícito."""
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class MensajeOut(BaseModel):
    mensaje: str


class OlvidePasswordIn(BaseModel):
    email: EmailStr


class RestablecerPasswordIn(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def validar_password(cls, v):
        return validar_password_segura(v)


class TokenRestablecerOut(BaseModel):
    """El link es válido: a qué cuenta corresponde, para mostrarlo en la pantalla."""

    email: str
