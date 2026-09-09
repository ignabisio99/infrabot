"""Simulador local del bot de WhatsApp (sin Meta ni Redis)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user
from core.storage import storage
from core.whatsapp_handler import procesar_audio, procesar_media, procesar_mensaje
from models.usuario import Usuario
from schemas.whatsapp import SimularTextoIn, SimularWhatsAppOut

router = APIRouter(prefix="/whatsapp", tags=["whatsapp-sim"])


def _salida(respuesta) -> SimularWhatsAppOut:
    if isinstance(respuesta, dict):
        return SimularWhatsAppOut(
            tipo=respuesta.get("tipo") or "texto",
            body=respuesta.get("body") or "",
            botones=respuesta.get("botones") or [],
            boton_texto=respuesta.get("boton_texto"),
            secciones=respuesta.get("secciones") or [],
        )
    return SimularWhatsAppOut(tipo="texto", body=str(respuesta or ""))


@router.post("/simular", response_model=SimularWhatsAppOut)
def simular_texto(
    datos: SimularTextoIn,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    return _salida(procesar_mensaje(db, datos.texto, usuario=datos.origen))


@router.post("/simular/media", response_model=SimularWhatsAppOut)
def simular_media(
    origen: str = Form("sim5491100000000"),
    caption: str = Form(""),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(get_current_user),
):
    mime = archivo.content_type or "application/octet-stream"
    if mime.startswith("audio/"):
        contenido = archivo.file.read()
        if not contenido:
            raise HTTPException(status_code=400, detail="El audio está vacío")
        return _salida(procesar_audio(db, usuario=origen, audio=contenido, mime_type=mime))

    url = storage.guardar(archivo, "whatsapp-sim")
    return _salida(
        procesar_media(db, usuario=origen, url_local=url, mime_type=mime, caption=caption)
    )
