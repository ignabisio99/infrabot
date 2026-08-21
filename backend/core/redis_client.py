"""Cliente Redis opcional: si no hay servidor, las colas caen a procesamiento inline."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_client = None


def redis_url() -> str:
    return (os.getenv("REDIS_URL") or "redis://redis:6379/0").strip()


def get_redis():
    """Devuelve un cliente o None si Redis no responde."""
    global _client
    if _client is not None:
        try:
            _client.ping()
            return _client
        except Exception:
            _client = None
    try:
        import redis

        client = redis.Redis.from_url(
            redis_url(),
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=2,
        )
        client.ping()
        _client = client
        logger.info("Redis conectado (%s)", redis_url())
        return _client
    except Exception as exc:
        logger.debug("Redis no disponible: %s", exc)
        return None


def reset_redis_cache() -> None:
    global _client
    _client = None
