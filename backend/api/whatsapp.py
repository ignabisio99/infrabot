"""Webhook de WhatsApp Cloud API (Meta).

Meta envía un POST con los mensajes entrantes. Se encolan en Redis (si está)
para responder 200 rápido y reintentar si falla el procesamiento.

Cada POST viene firmado por Meta (X-Hub-Signature-256: HMAC-SHA256 del cuerpo con el App
Secret de la app). Sin verificarla, cualquiera que conozca la URL podría mandar mensajes
"de" una escuela o un contratista (confirmar que un reclamo quedó resuelto, elegir un
horario...), porque los teléfonos no son secretos.
"""

import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Query, Request, Response

from services.cola_whatsapp import encolar, procesar_job

logger = logging.getLogger(__name__)


def _verify_token() -> str:
    # Sin valor por defecto: uno conocido (el de .env.example) dejaría pasar el alta.
    return os.getenv("WHATSAPP_VERIFY_TOKEN", "")


def _app_secret() -> str:
    return os.getenv("WHATSAPP_APP_SECRET", "")


def firma_valida(cuerpo: bytes, firma: str | None) -> bool:
    """Si `firma` (X-Hub-Signature-256) corresponde al cuerpo. Sin App Secret configurado
    rechaza todo: que un olvido en la configuración no deje el webhook abierto."""
    secreto = _app_secret()
    if not secreto or not firma or not firma.startswith("sha256="):
        return False
    esperada = hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, firma.removeprefix("sha256="))

router = APIRouter(prefix="/webhook", tags=["whatsapp"])


@router.get("/whatsapp")
def verificar_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """Verificación del webhook — Meta envía un GET para validar la URL."""
    esperado = _verify_token()
    if mode == "subscribe" and esperado and token is not None and hmac.compare_digest(token, esperado):
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


def _extraer_texto(message: dict) -> str | None:
    """Extrae el texto del mensaje, ya sea texto plano o respuesta de botón."""
    msg_type = message.get("type")

    if msg_type == "text":
        return message["text"]["body"]

    if msg_type == "interactive":
        interactive = message.get("interactive", {})
        if interactive.get("type") == "button_reply":
            return interactive["button_reply"]["id"]
        if interactive.get("type") == "list_reply":
            return interactive["list_reply"]["id"]

    return None


def _extraer_media(message: dict) -> dict | None:
    """Extrae información de media (imagen, video o audio) del mensaje."""
    msg_type = message.get("type")

    if msg_type == "image":
        img = message.get("image", {})
        return {
            "media_id": img.get("id", ""),
            "mime_type": img.get("mime_type", ""),
            "caption": img.get("caption", ""),
            "tipo": "image",
        }

    if msg_type == "video":
        vid = message.get("video", {})
        return {
            "media_id": vid.get("id", ""),
            "mime_type": vid.get("mime_type", ""),
            "caption": vid.get("caption", ""),
            "tipo": "video",
        }

    if msg_type == "audio":
        aud = message.get("audio", {})
        return {
            "media_id": aud.get("id", ""),
            "mime_type": aud.get("mime_type", ""),
            "caption": "",
            "tipo": "audio",
        }

    return None


def _despachar(job: dict) -> None:
    if encolar(job):
        logger.info("WhatsApp encolado (%s) de %s", job.get("kind"), job.get("from"))
        return
    procesar_job(job)


@router.post("/whatsapp")
async def recibir_mensaje(request: Request):
    """Recibe mensajes entrantes de WhatsApp vía Meta Cloud API."""
    # La firma se calcula sobre los bytes tal como llegaron: leerlos antes de parsear.
    cuerpo = await request.body()
    if not firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256")):
        if not _app_secret():
            logger.error("Webhook de WhatsApp rechazado: falta configurar WHATSAPP_APP_SECRET")
        else:
            logger.warning("Webhook de WhatsApp rechazado: firma inválida o ausente")
        return Response(status_code=403)
    try:
        body = json.loads(cuerpo)
    except ValueError:
        return Response(status_code=400)

    entries = body.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            messages = value.get("messages", [])

            for message in messages:
                from_number = message["from"]

                media_info = _extraer_media(message)
                if media_info:
                    logger.info(
                        "Media de %s: %s (%s)",
                        from_number,
                        media_info["tipo"],
                        media_info["mime_type"],
                    )
                    if media_info["tipo"] == "audio":
                        _despachar(
                            {
                                "kind": "audio",
                                "from": from_number,
                                "media_id": media_info["media_id"],
                            }
                        )
                    else:
                        _despachar(
                            {
                                "kind": "media",
                                "from": from_number,
                                "media_id": media_info["media_id"],
                                "caption": media_info.get("caption") or "",
                            }
                        )
                    continue

                texto = _extraer_texto(message)
                if not texto:
                    continue

                logger.info("Mensaje de %s: %s", from_number, texto)
                _despachar({"kind": "text", "from": from_number, "texto": texto})

    return Response(status_code=200)
