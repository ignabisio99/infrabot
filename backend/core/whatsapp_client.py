"""Cliente para la API de WhatsApp Cloud (Meta).

Envía mensajes de texto y mensajes interactivos (botones) vía la Graph API de Meta.
Descarga archivos multimedia enviados por usuarios.
"""

import os
import uuid
from pathlib import Path

import httpx

from core.storage import UPLOADS_DIR

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
GRAPH_API_URL = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"


def _normalizar_numero_ar(phone_number: str) -> str:
    """Convierte números argentinos de formato 549xxx a 54xxx (sin el 9)."""
    if phone_number.startswith("549"):
        phone_number = "54" + phone_number[3:]
    return phone_number


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


def _enviar(payload: dict) -> dict:
    response = httpx.post(GRAPH_API_URL, headers=_headers(), json=payload, timeout=10)
    if response.status_code != 200:
        print(f"[WHATSAPP] Error: {response.status_code} - {response.text}")
    return response.json()


def enviar_mensaje(to: str, body: str) -> dict:
    """Envía un mensaje de texto simple."""
    to = _normalizar_numero_ar(to)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    return _enviar(payload)


def enviar_botones(to: str, body: str, botones: list[dict]) -> dict:
    """Envía un mensaje interactivo con botones (máximo 3).

    Args:
        to: Número del destinatario
        body: Texto del mensaje
        botones: Lista de dicts con "id" y "title" (max 3, title max 20 chars)
    """
    to = _normalizar_numero_ar(to)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in botones[:3]
                ]
            },
        },
    }
    return _enviar(payload)


def enviar_lista(to: str, body: str, boton_texto: str, secciones: list[dict]) -> dict:
    """Envía un mensaje interactivo con lista de opciones (máximo 10).

    Args:
        to: Número del destinatario
        body: Texto del mensaje
        boton_texto: Texto del botón que abre la lista (max 20 chars)
        secciones: Lista de secciones, cada una con "title" y "rows"
                   Cada row tiene "id", "title" y opcionalmente "description"
    """
    to = _normalizar_numero_ar(to)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": boton_texto,
                "sections": secciones,
            },
        },
    }
    return _enviar(payload)


# --- Descarga de archivos multimedia ---

EXTENSIONES_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/3gpp": ".3gp",
    "video/quicktime": ".mov",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/amr": ".amr",
    "audio/aac": ".aac",
}


def _descargar_binario(media_id: str) -> tuple[bytes, str]:
    """Descarga el media de WhatsApp y devuelve (contenido, mime_type)."""
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    # Paso 1: obtener la URL del archivo
    meta_url = f"https://graph.facebook.com/v21.0/{media_id}"
    try:
        resp = httpx.get(meta_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[WHATSAPP] Error obteniendo media URL: {resp.status_code} - {resp.text}")
            return (b"", "")
        data = resp.json()
        download_url = data.get("url", "")
        mime_type = data.get("mime_type", "")
    except Exception as e:
        print(f"[WHATSAPP] Excepción obteniendo media URL: {e}")
        return (b"", "")

    if not download_url:
        return (b"", "")

    # Paso 2: descargar el archivo
    try:
        resp = httpx.get(download_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"[WHATSAPP] Error descargando media: {resp.status_code}")
            return (b"", "")
    except Exception as e:
        print(f"[WHATSAPP] Excepción descargando media: {e}")
        return (b"", "")

    return (resp.content, mime_type)


def descargar_media_binario(media_id: str) -> tuple[bytes, str]:
    """Descarga un media y lo devuelve en memoria (para STT de audios)."""
    return _descargar_binario(media_id)


def descargar_media(media_id: str, subcarpeta: str = "reclamos") -> tuple[str, str]:
    """Descarga un archivo multimedia de WhatsApp y lo guarda localmente.

    Args:
        media_id: ID del media de WhatsApp (viene en el mensaje)
        subcarpeta: carpeta dentro de uploads donde guardar

    Returns:
        Tuple (url_local, mime_type) o ("", "") si falla.
    """
    contenido, mime_type = _descargar_binario(media_id)
    if not contenido:
        return ("", "")

    # Guardar en disco
    extension = EXTENSIONES_MIME.get(mime_type.split(";")[0].strip(), ".bin")
    nombre_unico = f"{uuid.uuid4().hex}{extension}"
    destino = UPLOADS_DIR / subcarpeta
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / nombre_unico

    with ruta.open("wb") as f:
        f.write(contenido)

    url_local = f"/uploads/{subcarpeta}/{nombre_unico}"
    print(f"[WHATSAPP] Media descargada: {url_local} ({mime_type})")
    return (url_local, mime_type)
