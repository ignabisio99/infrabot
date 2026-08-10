import os

from fastapi import APIRouter, Depends, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import create_access_token, decode_access_token, hash_password, verify_password
from core.database import get_db
from core.email import enviar_confirmacion
from models.usuario import EstadoUsuario, Usuario
from schemas.usuario import (
    CompletarPerfil,
    MensajeOut,
    TokenOut,
    UsuarioLogin,
    UsuarioOut,
    UsuarioRegister,
)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MensajeOut, status_code=201)
def registrar_usuario(datos: UsuarioRegister, db: Session = Depends(get_db)):
    existente = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if existente:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")

    nuevo_usuario = Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password_hash=hash_password(datos.password),
        email_confirmado=False,
        estado=EstadoUsuario.PENDIENTE_PERFIL,
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    token = create_access_token({"sub": str(nuevo_usuario.id), "tipo": "confirmacion"})
    enviar_confirmacion(nuevo_usuario.email, token)

    return MensajeOut(mensaje="Registro exitoso. Revisá tu email para confirmar tu cuenta.")


@router.post("/login", response_model=TokenOut)
def iniciar_sesion(datos: UsuarioLogin, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    if not usuario.email_confirmado:
        raise HTTPException(
            status_code=403,
            detail="Necesitás confirmar tu email antes de iniciar sesión. Revisá tu bandeja de entrada.",
        )

    token = create_access_token({"sub": str(usuario.id), "email": usuario.email})

    return TokenOut(
        access_token=token,
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get("/confirmar", response_model=MensajeOut)
def confirmar_email(token: str, db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload or payload.get("tipo") != "confirmacion":
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

    usuario_id = int(payload["sub"])
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if usuario.email_confirmado:
        return MensajeOut(mensaje="Tu email ya estaba confirmado. Podés iniciar sesión.")

    usuario.email_confirmado = True
    db.commit()

    return MensajeOut(mensaje="Email confirmado exitosamente. Ya podés iniciar sesión.")


@router.post("/reenviar-confirmacion", response_model=MensajeOut)
def reenviar_confirmacion(datos: UsuarioLogin, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == datos.email).first()
    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    if usuario.email_confirmado:
        return MensajeOut(mensaje="Tu email ya está confirmado. Podés iniciar sesión.")

    token = create_access_token({"sub": str(usuario.id), "tipo": "confirmacion"})
    enviar_confirmacion(usuario.email, token)

    return MensajeOut(mensaje="Email de confirmación reenviado. Revisá tu bandeja de entrada.")


@router.post("/completar-perfil/{usuario_id}", response_model=MensajeOut)
def completar_perfil_usuario(usuario_id: int, datos: CompletarPerfil, db: Session = Depends(get_db)):
    """Completa el perfil del usuario después del registro."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if usuario.estado != EstadoUsuario.PENDIENTE_PERFIL:
        raise HTTPException(status_code=400, detail="El perfil ya fue completado")

    usuario.telefono = datos.telefono
    usuario.direccion = datos.direccion
    usuario.tipo = datos.tipo
    usuario.nombre_empresa = datos.nombre_empresa
    usuario.especialidad = datos.especialidad
    usuario.estado = EstadoUsuario.PENDIENTE_APROBACION
    db.commit()

    return MensajeOut(
        mensaje="Perfil completado. Tu cuenta será revisada por un administrador antes de poder acceder."
    )


@router.post("/aprobar/{usuario_id}", response_model=MensajeOut)
def aprobar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    """Aprueba un usuario pendiente (solo para admins)."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.estado != EstadoUsuario.PENDIENTE_APROBACION:
        raise HTTPException(status_code=400, detail="El usuario no está pendiente de aprobación")

    usuario.estado = EstadoUsuario.APROBADO
    db.commit()

    return MensajeOut(mensaje=f"Usuario {usuario.email} aprobado exitosamente.")


@router.post("/rechazar/{usuario_id}", response_model=MensajeOut)
def rechazar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    """Rechaza un usuario pendiente (solo para admins)."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.estado != EstadoUsuario.PENDIENTE_APROBACION:
        raise HTTPException(status_code=400, detail="El usuario no está pendiente de aprobación")

    usuario.estado = EstadoUsuario.RECHAZADO
    db.commit()

    return MensajeOut(mensaje=f"Usuario {usuario.email} rechazado.")


@router.get("/pendientes", response_model=list[UsuarioOut])
def listar_pendientes(db: Session = Depends(get_db)):
    """Lista usuarios pendientes de aprobación."""
    return (
        db.query(Usuario)
        .filter(Usuario.estado == EstadoUsuario.PENDIENTE_APROBACION)
        .order_by(Usuario.fecha_creacion.desc())
        .all()
    )


class GoogleTokenIn(BaseModel):
    credential: str


@router.post("/google", response_model=TokenOut)
def login_google(datos: GoogleTokenIn, db: Session = Depends(get_db)):
    """Autentica con Google. Crea el usuario si no existe."""
    try:
        idinfo = id_token.verify_oauth2_token(
            datos.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    email = idinfo["email"]
    nombre = idinfo.get("name", email.split("@")[0])

    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        usuario = Usuario(
            nombre=nombre,
            email=email,
            password_hash="",
            email_confirmado=True,
            estado=EstadoUsuario.PENDIENTE_PERFIL,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    if not usuario.email_confirmado:
        usuario.email_confirmado = True
        db.commit()
        db.refresh(usuario)

    token = create_access_token({"sub": str(usuario.id), "email": usuario.email})

    return TokenOut(
        access_token=token,
        usuario=UsuarioOut.model_validate(usuario),
    )
