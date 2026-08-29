"""Webhook de WhatsApp Cloud API (Meta).

Meta envía un POST con los mensajes entrantes. El endpoint los procesa
y responde usando la Graph API.
"""

import os

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.whatsapp_client import descargar_media, enviar_botones, enviar_lista, enviar_mensaje
from core.whatsapp_handler import procesar_mensaje, procesar_media

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
        # Respuesta de botón
        if interactive.get("type") == "button_reply":
            return interactive["button_reply"]["id"]
        # Respuesta de lista
        if interactive.get("type") == "list_reply":
            return interactive["list_reply"]["id"]

    return None


def _extraer_media(message: dict) -> dict | None:
    """Extrae información de media (imagen o video) del mensaje."""
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

    return None


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

                # Procesar media (foto/video)
                media_info = _extraer_media(message)
                if media_info:
                    print(f"📎 Media de {from_number}: {media_info['tipo']} ({media_info['mime_type']})")
                    # Descargar el archivo
                    url_local, mime_type = descargar_media(media_info["media_id"])
                    if url_local:
                        db: Session = SessionLocal()
                        try:
                            respuesta = procesar_media(
                                db,
                                usuario=from_number,
                                url_local=url_local,
                                mime_type=mime_type,
                                caption=media_info.get("caption", ""),
                            )
                        finally:
                            db.close()
                        print(f"📤 Respuesta: {str(respuesta)[:80]}...")
                        _enviar_respuesta(from_number, respuesta)
                    else:
                        enviar_mensaje(from_number, "⚠️ No pude descargar el archivo. Intentá de nuevo.")
                    continue

                # Procesar texto
                texto = _extraer_texto(message)
                if not texto:
                    continue

                print(f"📩 Mensaje de {from_number}: {texto}")

                db: Session = SessionLocal()
                try:
                    respuesta = procesar_mensaje(db, texto, usuario=from_number)
                finally:
                    db.close()

                print(f"📤 Respuesta: {str(respuesta)[:80]}...")

                # Enviar respuesta según el tipo
                _enviar_respuesta(from_number, respuesta)

    return Response(status_code=200)


def _enviar_respuesta(to: str, respuesta):
    """Envía la respuesta. Si es un dict con tipo 'botones' o 'lista', usa interactivo."""
    # Respuesta vacía = no responder (ej. número bloqueado por spam).
    if not respuesta:
        return

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
