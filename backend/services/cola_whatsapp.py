"""Cola Redis de mensajes WhatsApp (el webhook responde 200 y el worker procesa)."""

from __future__ import annotations

import json
import logging
from typing import Any

from core.database import SessionLocal
from core.redis_client import get_redis
from core.whatsapp_client import (
    descargar_media,
    descargar_media_binario,
    enviar_botones,
    enviar_lista,
    enviar_mensaje,
)
from core.whatsapp_handler import procesar_audio, procesar_media, procesar_mensaje

logger = logging.getLogger(__name__)

COLA = "infrabot:whatsapp:inbox"
MAX_INTENTOS = 3


def encolar(job: dict[str, Any]) -> bool:
    """True si quedó en Redis; False si hay que procesar ahora."""
    client = get_redis()
    if client is None:
        return False
    job.setdefault("intentos", 0)
    client.rpush(COLA, json.dumps(job, ensure_ascii=False))
    return True


def procesar_job(job: dict[str, Any]) -> None:
    kind = job.get("kind")
    origen = job.get("from") or ""
    if kind == "text":
        _procesar_texto(origen, job.get("texto") or "")
    elif kind == "audio":
        _procesar_audio(origen, job.get("media_id") or "")
    elif kind == "media":
        _procesar_media(origen, job.get("media_id") or "", job.get("caption") or "")
    else:
        logger.warning("Job WhatsApp desconocido: %s", kind)


def consumir_uno(timeout: int = 1) -> bool:
    """Bloquea hasta timeout segundos. True si procesó un job."""
    client = get_redis()
    if client is None:
        return False
    item = client.blpop(COLA, timeout=timeout)
    if not item:
        return False
    _, raw = item
    try:
        job = json.loads(raw)
        procesar_job(job)
    except Exception:
        logger.exception("Fallo procesando job WhatsApp")
        _reencolar(raw)
    return True


def _reencolar(raw: str) -> None:
    try:
        job = json.loads(raw)
    except json.JSONDecodeError:
        return
    job["intentos"] = int(job.get("intentos") or 0) + 1
    if job["intentos"] >= MAX_INTENTOS:
        logger.error("Job WhatsApp descartado tras %s intentos: %s", MAX_INTENTOS, job)
        return
    client = get_redis()
    if client is not None:
        client.rpush(COLA, json.dumps(job, ensure_ascii=False))


def _procesar_texto(origen: str, texto: str) -> None:
    if not texto:
        return
    db = SessionLocal()
    try:
        respuesta = procesar_mensaje(db, texto, usuario=origen)
    finally:
        db.close()
    _enviar_respuesta(origen, respuesta)


def _procesar_audio(origen: str, media_id: str) -> None:
    contenido, mime_type = descargar_media_binario(media_id)
    if not contenido:
        enviar_mensaje(origen, "⚠️ No pude descargar el audio. Intentá de nuevo.")
        return
    db = SessionLocal()
    try:
        respuesta = procesar_audio(db, usuario=origen, audio=contenido, mime_type=mime_type)
    finally:
        db.close()
    _enviar_respuesta(origen, respuesta)


def _procesar_media(origen: str, media_id: str, caption: str) -> None:
    url_local, mime_type = descargar_media(media_id)
    if not url_local:
        enviar_mensaje(origen, "⚠️ No pude descargar el archivo. Intentá de nuevo.")
        return
    db = SessionLocal()
    try:
        respuesta = procesar_media(
            db,
            usuario=origen,
            url_local=url_local,
            mime_type=mime_type,
            caption=caption,
        )
    finally:
        db.close()
    _enviar_respuesta(origen, respuesta)


def _enviar_respuesta(to: str, respuesta) -> None:
    if isinstance(respuesta, dict):
        tipo = respuesta.get("tipo")
        if tipo == "botones":
            enviar_botones(to, respuesta["body"], respuesta["botones"])
        elif tipo == "lista":
            enviar_lista(to, respuesta["body"], respuesta["boton_texto"], respuesta["secciones"])
        else:
            enviar_mensaje(to, respuesta.get("body", str(respuesta)))
    else:
        enviar_mensaje(to, respuesta)
