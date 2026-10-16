"""Simulador local del bot de WhatsApp (sin Meta ni Redis)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from core.storage import storage
from core.whatsapp_handler import (
    procesar_audio_detalle,
    procesar_media,
    procesar_mensaje,
    reiniciar_conversacion,
)
from models.mensaje_conversacion import AutorMensaje, TipoMensaje
from models.usuario import Usuario
from schemas.conversacion import MensajeConversacionOut
from schemas.whatsapp import SimularOrigenIn, SimularTextoIn, SimularWhatsAppOut
from services import conversaciones as convs

router = APIRouter(prefix="/whatsapp", tags=["whatsapp-sim"])


def _salida(
    respuesta,
    transcripcion: str | None = None,
    proveedor_stt: str | None = None,
) -> SimularWhatsAppOut:
    extras = {"transcripcion": transcripcion, "proveedor_stt": proveedor_stt}
    if isinstance(respuesta, dict):
        return SimularWhatsAppOut(
            tipo=respuesta.get("tipo") or "texto",
            body=respuesta.get("body") or "",
            botones=respuesta.get("botones") or [],
            boton_texto=respuesta.get("boton_texto"),
            secciones=respuesta.get("secciones") or [],
            **extras,
        )
    return SimularWhatsAppOut(tipo="texto", body=str(respuesta or ""), **extras)


def _registrar_bot(db: Session, origen: str, respuesta) -> None:
    if isinstance(respuesta, dict):
        cuerpo = respuesta.get("body") or ""
    else:
        cuerpo = str(respuesta or "")
    if not (cuerpo or "").strip():
        return
    convs.registrar_saliente(db, origen, cuerpo)


@router.post("/simular", response_model=SimularWhatsAppOut)
def simular_texto(
    datos: SimularTextoIn,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    convs.registrar_entrante(db, datos.origen, texto=datos.texto)
    respuesta = procesar_mensaje(db, datos.texto, usuario=datos.origen)
    _registrar_bot(db, datos.origen, respuesta)
    return _salida(respuesta)


@router.post("/simular/reiniciar")
def simular_reiniciar(
    datos: SimularOrigenIn,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    reiniciar_conversacion(datos.origen)
    activa = convs.activa(db, datos.origen)
    if activa is not None:
        convs.cerrar(db, activa.id, motivo="Charla del simulador reiniciada. El bot vuelve a atender.")
    return {"ok": True}


@router.get("/simular/mensajes", response_model=list[MensajeConversacionOut])
def simular_mensajes(
    origen: str = Query(...),
    despues_de: int | None = Query(None),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    visibles = []
    for m in convs.mensajes_de_telefono(db, origen, despues_de=despues_de):
        if m.autor is AutorMensaje.OPERADOR:
            visibles.append(m)
        elif m.autor is AutorMensaje.BOT and m.texto == convs.AVISO_FIN_ATENCION:
            visibles.append(m)
    return [MensajeConversacionOut(**convs.serializar_mensaje(m)) for m in visibles]


@router.post("/simular/media", response_model=SimularWhatsAppOut)
def simular_media(
    origen: str = Form("sim5491100000000"),
    caption: str = Form(""),
    proveedor_stt: str = Form(""),
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    mime = archivo.content_type or "application/octet-stream"
    if mime.startswith("audio/"):
        contenido = archivo.file.read()
        if not contenido:
            raise HTTPException(status_code=400, detail="El audio está vacío")
        if convs.activa(db, origen) is not None:
            url = convs.guardar_media_operador(contenido, mime)
            if url is None:
                convs.registrar_entrante(
                    db, origen, texto="[Audio demasiado grande o vacío]", tipo=TipoMensaje.TEXTO
                )
                return _salida("")
            mensaje = convs.registrar_entrante(
                db,
                origen,
                tipo=TipoMensaje.AUDIO,
                media_url=url,
                mime_type=mime,
                con_ttl=True,
            )
            from services.ai import stt

            try:
                texto = stt.transcribir_audio(contenido, mime, proveedor=proveedor_stt or None)
            except stt.TranscripcionError:
                texto = None
            convs.actualizar_transcripcion(db, mensaje.id, texto)
            return _salida("", transcripcion=texto, proveedor_stt=proveedor_stt or None)

        texto, proveedor, respuesta = procesar_audio_detalle(
            db,
            usuario=origen,
            audio=contenido,
            mime_type=mime,
            proveedor_stt=proveedor_stt or None,
        )
        if texto:
            convs.registrar_entrante(db, origen, texto=texto)
        _registrar_bot(db, origen, respuesta)
        return _salida(respuesta, transcripcion=texto, proveedor_stt=proveedor)

    url = storage.guardar(archivo, "whatsapp-sim")
    tipo = convs._tipo_media(mime)
    con_ttl = convs.activa(db, origen) is not None
    convs.registrar_entrante(
        db,
        origen,
        texto=caption or None,
        tipo=tipo,
        media_url=url,
        mime_type=mime,
        con_ttl=con_ttl,
    )
    respuesta = procesar_media(db, usuario=origen, url_local=url, mime_type=mime, caption=caption)
    _registrar_bot(db, origen, respuesta)
    return _salida(respuesta)
