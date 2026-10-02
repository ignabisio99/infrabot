"""Dependencias compartidas para inyección en endpoints protegidos."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.auth import decode_access_token, token_esta_invalidado
from core.database import get_db
from models.usuario import Usuario

COOKIE_NAME = "infrabot_session"


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    """Verifica la cookie de sesión y devuelve el usuario autenticado.

    Rechaza tokens expirados, inválidos o que fueron invalidados (logout).
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
