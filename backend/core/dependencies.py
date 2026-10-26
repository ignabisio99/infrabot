"""Dependencias compartidas para inyección en endpoints protegidos."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.auth import decode_access_token, token_esta_invalidado
from core.database import get_db
from models.usuario import EstadoUsuario, Usuario

COOKIE_NAME = "infrabot_session"


# Los tokens de los emails (confirmar la cuenta, restablecer la contraseña) están firmados
# con la misma clave que los de sesión: sin mirar el tipo, el link de un email serviría
# como cookie de sesión. Los de sesión llevan tipo "sesion"; los emitidos antes de que
# existiera el campo no tienen tipo y se siguen aceptando hasta que venzan (24 h).
TIPOS_DE_SESION = (None, "sesion")


def get_usuario_de_sesion(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    """Verifica la cookie de sesión y devuelve el usuario, esté o no aprobado.

    Rechaza tokens expirados, inválidos, invalidados (logout) o que no son de sesión.
    Solo para lo que necesita una cuenta sin aprobar (ver su estado en /auth/me, completar
    el perfil): el resto usa `get_current_user`, que además exige la cuenta aprobada.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
        )

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada. Iniciá sesión nuevamente.",
        )

    if payload.get("tipo") not in TIPOS_DE_SESION:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )

    if token_esta_invalidado(token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión cerrada. Iniciá sesión nuevamente.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )

    usuario = db.get(Usuario, int(user_id))
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    return usuario


def get_current_user(
    usuario: Usuario = Depends(get_usuario_de_sesion),
) -> Usuario:
    """El usuario de la sesión, con la cuenta aprobada.

    Rechaza cuentas que un admin todavía no aprobó o rechazó: con la sesión abierta
    podrían llamar a la API directo aunque la app les muestre la pantalla de "pendiente".
    """
    if usuario.estado == EstadoUsuario.RECHAZADO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta fue rechazada. Contactá a un administrador para más información.",
        )
    if usuario.estado != EstadoUsuario.APROBADO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta todavía no fue aprobada por un administrador.",
        )

    return usuario


def get_current_admin(
    usuario: Usuario = Depends(get_current_user),
) -> Usuario:
    """Igual que get_current_user pero exige que sea ADMINISTRADOR."""
    if not usuario.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores pueden realizar esta acción",
        )
    return usuario


def get_current_inspector(
    usuario: Usuario = Depends(get_current_user),
) -> Usuario:
    """Exige que el usuario autenticado sea INSPECTOR."""
    if not usuario.es_inspector:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los inspectores pueden realizar esta acción",
        )
    return usuario


def get_current_admin_o_inspector(
    usuario: Usuario = Depends(get_current_user),
) -> Usuario:
    """Exige que el usuario autenticado sea ADMINISTRADOR o INSPECTOR."""
    if not (usuario.es_admin or usuario.es_inspector):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los administradores e inspectores pueden realizar esta acción",
        )
    return usuario


def get_current_contratista(
    usuario: Usuario = Depends(get_current_user),
) -> Usuario:
    """Exige que el usuario autenticado sea CONTRATISTA."""
    from models.usuario import TipoUsuario

    if usuario.tipo is not TipoUsuario.CONTRATISTA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los contratistas pueden realizar esta acción",
        )
    return usuario
