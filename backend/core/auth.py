"""Utilidades de autenticación: hashing de contraseñas y JWT con invalidación."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-cambiar-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(data: dict, expira_en: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expira_en or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({
        "exp": expire,
        "jti": uuid.uuid4().hex,
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def invalidar_token(token: str, db: Session) -> bool:
    """Agrega un token a la blacklist para invalidarlo."""
    from models.token_blacklist import TokenBlacklist

    payload = decode_access_token(token)
    if not payload:
        return False

    jti = payload.get("jti")
    if not jti:
        return False

    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    existente = db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first()
    if existente:
        return True  # Ya estaba invalidado

    entrada = TokenBlacklist(jti=jti, expira_en=exp)
    db.add(entrada)
    db.commit()
    return True


def token_esta_invalidado(token: str, db: Session) -> bool:
    """Verifica si un token fue invalidado (logout)."""
    from models.token_blacklist import TokenBlacklist

    payload = decode_access_token(token)
    if not payload:
        return True  # Token inválido se trata como invalidado

    jti = payload.get("jti")
    if not jti:
        return False  # Tokens viejos sin JTI se permiten (backward compat)

    return db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first() is not None


def limpiar_tokens_expirados(db: Session) -> int:
    """Elimina tokens expirados de la blacklist (limpieza periódica)."""
    from models.token_blacklist import TokenBlacklist

    ahora = datetime.now(timezone.utc)
    eliminados = db.query(TokenBlacklist).filter(TokenBlacklist.expira_en < ahora).delete()
    db.commit()
    return eliminados
