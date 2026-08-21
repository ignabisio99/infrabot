"""Webhook de WhatsApp Cloud API (Meta).

Meta envía un POST con los mensajes entrantes. Se encolan en Redis (si está)
para responder 200 rápido y reintentar si falla el procesamiento.
"""

import logging
import os

from fastapi import APIRouter, Query, Request, Response

from services.cola_whatsapp import encolar, procesar_job

logger = logging.getLogger(__name__)

WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "infrabot-verify-token")

router = APIRouter(prefix="/webhook", tags=["whatsapp"])


@router.get("/whatsapp")
def verificar_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """Verificación del webhook — Meta envía un GET para validar la URL."""
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
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
    body = await request.json()

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
