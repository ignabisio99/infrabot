import hashlib
import os
from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.auth import create_access_token, decode_access_token, hash_password, invalidar_token, verify_password
from core.database import get_db
from core.dependencies import get_current_admin, get_current_user, get_usuario_de_sesion
from core.email import (
    enviar_aprobacion,
    enviar_confirmacion,
    enviar_rechazo_cuenta,
    enviar_restablecer_password,
)
from models.contratista import Contratista
from schemas.contratista import MIN_NOMBRE_EMPRESA
from models.usuario import EstadoUsuario, TipoUsuario, Usuario
from schemas.usuario import (
    CompletarPerfil,
    normalizar_email,
    LoginOut,
    MensajeOut,
    OlvidePasswordIn,
    RestablecerPasswordIn,
    TokenRestablecerOut,
    UsuarioLogin,
    UsuarioOut,
    UsuarioRegister,
    UsuarioUpdate,
)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
COOKIE_NAME = "infrabot_session"
# En desarrollo local usamos SameSite=Lax (funciona con localhost)
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

router = APIRouter(prefix="/auth", tags=["auth"])

# Una cuenta rechazada queda bloqueada: no entra por ningún medio ni se puede volver a pedir.
MENSAJE_CUENTA_RECHAZADA = "Tu cuenta fue rechazada. Contactá a un administrador para más información."


def _set_session_cookie(response: Response, token: str):
    """Setea la cookie HttpOnly con el token de sesión."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=24 * 60 * 60,  # 24 horas
        path="/",
    )


def _clear_session_cookie(response: Response):
    """Elimina la cookie de sesión."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


def _usuario_por_email(db: Session, email: str) -> Usuario | None:
    """Busca sin distinguir mayúsculas: también encuentra cuentas guardadas antes de que
    los emails se normalizaran."""
    return db.query(Usuario).filter(func.lower(Usuario.email) == normalizar_email(email)).first()


@router.post("/register", response_model=MensajeOut, status_code=201)
def registrar_usuario(datos: UsuarioRegister, db: Session = Depends(get_db)):
    existente = _usuario_por_email(db, datos.email)
    if existente and existente.estado == EstadoUsuario.RECHAZADO:
        raise HTTPException(
            status_code=409,
            detail="Ese email tiene una solicitud de cuenta rechazada. Contactá a un "
            "administrador para más información.",
        )
    if existente:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese email")

    nuevo_usuario = Usuario(
        nombre=datos.nombre,
        email=datos.email,
        password_hash=hash_password(datos.password),
        email_confirmado=False,
        telefono=datos.telefono,
        direccion=datos.direccion,
        tipo=datos.tipo,
        nombre_empresa=datos.nombre_empresa,
        especialidad=datos.especialidad,
        estado=EstadoUsuario.PENDIENTE_APROBACION,
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    token = create_access_token({"sub": str(nuevo_usuario.id), "tipo": "confirmacion"})
    enviar_confirmacion(nuevo_usuario.email, token)

    return MensajeOut(mensaje="Registro exitoso. Revisá tu email para confirmar tu cuenta.")


@router.post("/login", response_model=LoginOut)
def iniciar_sesion(datos: UsuarioLogin, response: Response, db: Session = Depends(get_db)):
    usuario = _usuario_por_email(db, datos.email)
    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    if not usuario.email_confirmado:
        raise HTTPException(
            status_code=403,
            detail="Necesitás confirmar tu email antes de iniciar sesión. Revisá tu bandeja de entrada.",
        )

    if usuario.estado == EstadoUsuario.PENDIENTE_APROBACION:
        raise HTTPException(
            status_code=403,
            detail="Tu cuenta está pendiente de aprobación por un administrador.",
        )

    if usuario.estado == EstadoUsuario.RECHAZADO:
        raise HTTPException(status_code=403, detail=MENSAJE_CUENTA_RECHAZADA)

    token = create_access_token({"sub": str(usuario.id), "email": usuario.email, "tipo": "sesion"})
    _set_session_cookie(response, token)

    return LoginOut(usuario=UsuarioOut.model_validate(usuario))


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
        return MensajeOut(mensaje="Tu email ya estaba confirmado. Tu cuenta está pendiente de aprobación por un administrador.")

    usuario.email_confirmado = True
    db.commit()

    return MensajeOut(mensaje="Email confirmado exitosamente. Tu cuenta será revisada por un administrador antes de poder acceder.")


# --- Restablecer contraseña ----------------------------------------------------------
# El link lleva un JWT que vence en 1 hora y guarda una huella de la contraseña actual:
# al cambiarla la huella deja de coincidir, así que cada link sirve una sola vez (y uno
# viejo no sirve después de que la cambiaste por otro lado) sin guardar nada en la base.

VENCIMIENTO_RESTABLECER = timedelta(hours=1)
MENSAJE_LINK_INVALIDO = "El link no es válido o ya venció. Pedí uno nuevo desde el inicio de sesión."


def _huella_password(usuario: Usuario) -> str:
    return hashlib.sha256((usuario.password_hash or "").encode()).hexdigest()[:16]


def _usuario_del_link(token: str, db: Session) -> Usuario:
    payload = decode_access_token(token)
    if not payload or payload.get("tipo") != "restablecer_password":
        raise HTTPException(status_code=400, detail=MENSAJE_LINK_INVALIDO)
    usuario = db.get(Usuario, int(payload["sub"]))
    if usuario is None or payload.get("huella") != _huella_password(usuario):
        raise HTTPException(status_code=400, detail=MENSAJE_LINK_INVALIDO)
    return usuario


@router.post("/olvide-password", response_model=MensajeOut)
def olvide_password(datos: OlvidePasswordIn, db: Session = Depends(get_db)):
    """Manda el link para elegir una contraseña nueva. La respuesta es la misma exista o
    no la cuenta, para no revelar qué emails están registrados."""
    usuario = _usuario_por_email(db, datos.email)
    if usuario is not None:
        token = create_access_token(
            {"sub": str(usuario.id), "tipo": "restablecer_password", "huella": _huella_password(usuario)},
            expira_en=VENCIMIENTO_RESTABLECER,
        )
        enviar_restablecer_password(usuario.email, usuario.nombre, token)
    return MensajeOut(
        mensaje="Si el email está registrado, te enviamos un link para restablecer la "
        "contraseña. Revisá tu bandeja de entrada (y la carpeta de spam)."
    )


@router.get("/restablecer-password", response_model=TokenRestablecerOut)
def validar_link_restablecer(token: str, db: Session = Depends(get_db)):
    """La pantalla lo consulta al abrirse: si el link ya no sirve, lo dice antes de que
    la persona escriba la contraseña nueva."""
    return TokenRestablecerOut(email=_usuario_del_link(token, db).email)


@router.post("/restablecer-password", response_model=MensajeOut)
def restablecer_password(datos: RestablecerPasswordIn, db: Session = Depends(get_db)):
    usuario = _usuario_del_link(datos.token, db)
    usuario.password_hash = hash_password(datos.password)
    # Recibió el link en ese email: queda confirmado aunque no hubiera abierto el de alta.
    usuario.email_confirmado = True
    db.commit()
    return MensajeOut(mensaje="Listo, cambiaste tu contraseña. Ya podés iniciar sesión con la nueva.")


@router.post("/reenviar-confirmacion", response_model=MensajeOut)
def reenviar_confirmacion(datos: UsuarioLogin, db: Session = Depends(get_db)):
    usuario = _usuario_por_email(db, datos.email)
    if not usuario or not verify_password(datos.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    if usuario.email_confirmado:
        return MensajeOut(mensaje="Tu email ya está confirmado. Podés iniciar sesión.")

    token = create_access_token({"sub": str(usuario.id), "tipo": "confirmacion"})
    enviar_confirmacion(usuario.email, token)

    return MensajeOut(mensaje="Email de confirmación reenviado. Revisá tu bandeja de entrada.")


@router.post("/completar-perfil/{usuario_id}", response_model=MensajeOut)
def completar_perfil_usuario(
    usuario_id: int,
    datos: CompletarPerfil,
    db: Session = Depends(get_db),
    sesion: Usuario = Depends(get_usuario_de_sesion),
):
    """Completa el perfil del usuario después de registrarse con Google.

    Solo el propio usuario, con su sesión: si no, cualquiera podría completarle el perfil
    (tipo, teléfono, dirección) a una cuenta ajena sabiendo su ID.
    """
    if sesion.id != usuario_id:
        raise HTTPException(status_code=403, detail="Solo podés completar tu propio perfil")
    usuario = sesion

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


def _crear_ficha_contratista(db: Session, usuario: Usuario) -> None:
    """Crea (si no existe) la ficha de Contratista vinculada a un usuario contratista.

    Se llama al aprobar un usuario tipo CONTRATISTA para que quede listo para recibir
    solicitudes de presupuesto sin que un admin lo cargue a mano.
    """
    if usuario.tipo != TipoUsuario.CONTRATISTA:
        return

    # Si ya tiene una ficha vinculada, no duplicar.
    ya_vinculado = db.query(Contratista).filter(Contratista.usuario_id == usuario.id).first()
    if ya_vinculado:
        return

    ficha = Contratista(
        nombre_empresa=usuario.nombre_empresa or usuario.nombre,
        telefono=usuario.telefono or "",
        direccion=usuario.direccion or "",
        especialidad=usuario.especialidad or "General",
        calificacion=None,  # N/A hasta que un admin la asigne
        usuario_id=usuario.id,
    )
    db.add(ficha)


@router.post("/aprobar/{usuario_id}", response_model=MensajeOut)
def aprobar_usuario(usuario_id: int, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    """Aprueba un usuario pendiente (solo para admins).

    Si el usuario es contratista, se crea automáticamente su ficha de Contratista
    para que pueda recibir solicitudes de presupuesto.
    """
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.estado != EstadoUsuario.PENDIENTE_APROBACION:
        raise HTTPException(status_code=400, detail="El usuario no está pendiente de aprobación")

    usuario.estado = EstadoUsuario.APROBADO
    _crear_ficha_contratista(db, usuario)
    db.commit()

    enviar_aprobacion(usuario.email)

    return MensajeOut(mensaje=f"Usuario {usuario.email} aprobado exitosamente.")


@router.post("/rechazar/{usuario_id}", response_model=MensajeOut)
def rechazar_usuario(usuario_id: int, db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    """Rechaza un usuario pendiente (solo para admins)."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.estado != EstadoUsuario.PENDIENTE_APROBACION:
        raise HTTPException(status_code=400, detail="El usuario no está pendiente de aprobación")

    usuario.estado = EstadoUsuario.RECHAZADO
    db.commit()

    enviar_rechazo_cuenta(usuario.email)

    return MensajeOut(mensaje=f"Usuario {usuario.email} rechazado.")


@router.get("/pendientes", response_model=list[UsuarioOut])
def listar_pendientes(db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    """Lista usuarios pendientes de aprobación."""
    return (
        db.query(Usuario)
        .filter(Usuario.estado == EstadoUsuario.PENDIENTE_APROBACION)
        .order_by(Usuario.fecha_creacion.desc())
        .all()
    )


@router.get("/administradores", response_model=list[UsuarioOut])
def listar_administradores(db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    """Lista los administradores con la cuenta aprobada."""
    return (
        db.query(Usuario)
        .filter(Usuario.tipo == TipoUsuario.ADMINISTRADOR, Usuario.estado == EstadoUsuario.APROBADO)
        .order_by(Usuario.nombre)
        .all()
    )


@router.get("/inspectores", response_model=list[UsuarioOut])
def listar_inspectores(db: Session = Depends(get_db), _admin: Usuario = Depends(get_current_admin)):
    """Lista los inspectores con la cuenta aprobada, para pedirles información de un reclamo."""
    return (
        db.query(Usuario)
        .filter(Usuario.tipo == TipoUsuario.INSPECTOR, Usuario.estado == EstadoUsuario.APROBADO)
        .order_by(Usuario.nombre)
        .all()
    )


@router.get("/me", response_model=UsuarioOut)
def obtener_usuario_actual(usuario: Usuario = Depends(get_usuario_de_sesion)):
    """Devuelve el usuario de la sesión, aprobado o no: con esto la app decide si muestra la
    pantalla de "pendiente", la de "rechazada" o el sistema."""
    return usuario


@router.put("/me", response_model=UsuarioOut)
def actualizar_usuario_actual(
    datos: UsuarioUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    """Actualiza los datos de perfil del usuario logueado. No cambia email, tipo ni estado."""
    if usuario.tipo == TipoUsuario.CONTRATISTA:
        if not datos.nombre_empresa or len(datos.nombre_empresa.strip()) < MIN_NOMBRE_EMPRESA:
            raise HTTPException(
                status_code=422,
                detail=f"El nombre de la empresa debe tener al menos {MIN_NOMBRE_EMPRESA} caracteres",
            )
        if not datos.especialidad or len(datos.especialidad.strip()) < 2:
            raise HTTPException(
                status_code=422, detail="Los contratistas deben especificar su especialidad"
            )

    usuario.nombre = datos.nombre
    usuario.telefono = datos.telefono
    usuario.direccion = datos.direccion
    if usuario.tipo == TipoUsuario.CONTRATISTA:
        usuario.nombre_empresa = datos.nombre_empresa.strip()
        usuario.especialidad = datos.especialidad.strip()

    ficha = db.query(Contratista).filter(Contratista.usuario_id == usuario.id).first()
    if ficha is not None:
        ficha.telefono = datos.telefono
        ficha.direccion = datos.direccion
        if usuario.tipo == TipoUsuario.CONTRATISTA:
            ficha.nombre_empresa = usuario.nombre_empresa or ficha.nombre_empresa
            ficha.especialidad = datos.especialidad or ficha.especialidad

    db.commit()
    db.refresh(usuario)
    return usuario


class GoogleTokenIn(BaseModel):
    credential: str


@router.post("/google", response_model=LoginOut)
def login_google(datos: GoogleTokenIn, response: Response, db: Session = Depends(get_db)):
    """Autentica con Google. Crea el usuario si no existe."""
    try:
        idinfo = id_token.verify_oauth2_token(
            datos.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Token de Google inválido")

    email = normalizar_email(idinfo["email"])
    nombre = idinfo.get("name", email.split("@")[0])

    # Mismo criterio que el registro: si ya hay una cuenta con ese email (con o sin
    # mayúsculas), Google entra a esa y no crea otra.
    usuario = _usuario_por_email(db, email)
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

    # Igual que con email y contraseña: una cuenta rechazada no entra.
    if usuario.estado == EstadoUsuario.RECHAZADO:
        raise HTTPException(status_code=403, detail=MENSAJE_CUENTA_RECHAZADA)

    if not usuario.email_confirmado:
        usuario.email_confirmado = True
        db.commit()
        db.refresh(usuario)

    token = create_access_token({"sub": str(usuario.id), "email": usuario.email, "tipo": "sesion"})
    _set_session_cookie(response, token)

    return LoginOut(usuario=UsuarioOut.model_validate(usuario))


@router.post("/logout", response_model=MensajeOut)
def cerrar_sesion(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Invalida el token actual y borra la cookie de sesión."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        invalidar_token(token, db)
    _clear_session_cookie(response)
    return MensajeOut(mensaje="Sesión cerrada exitosamente.")
