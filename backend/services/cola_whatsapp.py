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
from core.whatsapp_handler import procesar_audio_detalle, procesar_media, procesar_mensaje
from models.mensaje_conversacion import TipoMensaje
from services import conversaciones as convs

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
    elif kind == "post_ia":
        _procesar_post_ia(int(job.get("reclamo_id") or 0))
    elif kind == "transcribir":
        _procesar_transcribir(int(job.get("mensaje_id") or 0))
    else:
        logger.warning("Job WhatsApp desconocido: %s", kind)


def _procesar_post_ia(reclamo_id: int) -> None:
    """Corre la IA de análisis (agente/pipeline + fotos) en segundo plano.

    Se dispara DESPUÉS de confirmarle al usuario que el reclamo fue creado, para que
    el resumen por WhatsApp salga al instante y no espere las (varias) llamadas al LLM.
    El resumen ya muestra categoría/prioridad de la clasificación rápida hecha en el
    paso de descripción; el agente enriquece el análisis (padrón, similares, costos)
    que se ve en la web.
    """
    if not reclamo_id:
        return
    from sqlalchemy.orm import joinedload

    from models.reclamo import Reclamo
    from services.ai.automatico import post_alta_reclamo, post_fotos_reclamo

    db = SessionLocal()
    try:
        reclamo = db.get(Reclamo, reclamo_id)
        if reclamo is None:
            return
        post_alta_reclamo(db, reclamo)
        recargado = (
            db.query(Reclamo)
            .options(joinedload(Reclamo.fotos))
            .filter(Reclamo.id == reclamo_id)
            .first()
        )
        if recargado is not None:
            post_fotos_reclamo(db, recargado)
        try:
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


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
        logger.info(
            "WhatsApp desencolado de Redis (%s) de %s [intento %s]",
            job.get("kind"),
            job.get("from"),
            job.get("intentos", 0),
        )
        procesar_job(job)
        logger.info("WhatsApp procesado OK (%s) de %s", job.get("kind"), job.get("from"))
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
        convs.registrar_entrante(db, origen, texto=texto)
        respuesta = procesar_mensaje(db, texto, usuario=origen)
        db.commit()
    except Exception:
        db.rollback()
        raise
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
        if convs.activa(db, origen) is not None:
            url = convs.guardar_media_operador(contenido, mime_type)
            if url is None:
                convs.registrar_entrante(
                    db, origen, texto="[Audio demasiado grande o vacío]", tipo=TipoMensaje.TEXTO
                )
            else:
                mensaje = convs.registrar_entrante(
                    db,
                    origen,
                    tipo=TipoMensaje.AUDIO,
                    media_url=url,
                    mime_type=mime_type,
                    con_ttl=True,
                )
                encolar({"kind": "transcribir", "mensaje_id": mensaje.id})
            db.commit()
            return
        texto, _proveedor, respuesta = procesar_audio_detalle(
            db, usuario=origen, audio=contenido, mime_type=mime_type
        )
        if texto:
            convs.registrar_entrante(db, origen, texto=texto)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    _enviar_respuesta(origen, respuesta)


def _procesar_media(origen: str, media_id: str, caption: str) -> None:
    db = SessionLocal()
    try:
        con_operador = convs.activa(db, origen) is not None
        if con_operador:
            contenido, mime_type = descargar_media_binario(media_id)
            if not contenido:
                enviar_mensaje(origen, "⚠️ No pude descargar el archivo. Intentá de nuevo.")
                return
            url = convs.guardar_media_operador(contenido, mime_type)
            tipo = convs._tipo_media(mime_type)
            if url is None:
                convs.registrar_entrante(
                    db,
                    origen,
                    texto=caption or "[Archivo demasiado grande o vacío]",
                    tipo=TipoMensaje.TEXTO,
                )
            else:
                convs.registrar_entrante(
                    db,
                    origen,
                    texto=caption or None,
                    tipo=tipo,
                    media_url=url,
                    mime_type=mime_type,
                    con_ttl=True,
                )
            db.commit()
            return
        url_local, mime_type = descargar_media(media_id)
        if not url_local:
            enviar_mensaje(origen, "⚠️ No pude descargar el archivo. Intentá de nuevo.")
            return
        convs.registrar_entrante(
            db,
            origen,
            texto=caption or None,
            tipo=convs._tipo_media(mime_type),
            media_url=url_local,
            mime_type=mime_type,
        )
        respuesta = procesar_media(
            db,
            usuario=origen,
            url_local=url_local,
            mime_type=mime_type,
            caption=caption,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    _enviar_respuesta(origen, respuesta)


def _procesar_transcribir(mensaje_id: int) -> None:
    if not mensaje_id:
        return
    from core.storage import UPLOADS_DIR
    from services.ai import stt

    db = SessionLocal()
    try:
        from models.mensaje_conversacion import MensajeConversacion

        mensaje = db.get(MensajeConversacion, mensaje_id)
        if mensaje is None or not mensaje.media_url or mensaje.media_eliminada:
            return
        relativo = mensaje.media_url.removeprefix("/uploads/")
        ruta = UPLOADS_DIR / relativo
        if not ruta.is_file():
            convs.actualizar_transcripcion(db, mensaje_id, None)
            return
        try:
            texto = stt.transcribir_audio(ruta.read_bytes(), mensaje.mime_type or "audio/ogg")
        except stt.TranscripcionError:
            texto = None
        convs.actualizar_transcripcion(db, mensaje_id, texto)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Falló la transcripción del mensaje %s", mensaje_id)
    finally:
        db.close()


def _texto_respuesta(respuesta) -> str:
    if respuesta is None:
        return ""
    if isinstance(respuesta, dict):
        return (respuesta.get("body") or "").strip()
    return str(respuesta).strip()


def _enviar_respuesta(to: str, respuesta) -> None:
    if not _texto_respuesta(respuesta) and not (
        isinstance(respuesta, dict) and (respuesta.get("botones") or respuesta.get("secciones"))
    ):
        return
    if isinstance(respuesta, dict):
        tipo = respuesta.get("tipo")
        if tipo == "botones":
            enviar_botones(to, respuesta["body"], respuesta["botones"])
        elif tipo == "lista":
            enviar_lista(to, respuesta["body"], respuesta["boton_texto"], respuesta["secciones"])
        else:
            enviar_mensaje(to, respuesta.get("body", str(respuesta)))
        cuerpo = respuesta.get("body") or ""
    else:
        enviar_mensaje(to, respuesta)
        cuerpo = str(respuesta)
    if not cuerpo:
        return
    db = SessionLocal()
    try:
        convs.registrar_saliente(db, to, cuerpo)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("No se pudo guardar la respuesta saliente a %s", to)
    finally:
        db.close()
