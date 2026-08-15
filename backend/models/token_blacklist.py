"""Modelo para tokens invalidados (logout)."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from core.database import Base


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(255), nullable=False, unique=True, index=True)
    expira_en = Column(DateTime(timezone=True), nullable=False)
    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
