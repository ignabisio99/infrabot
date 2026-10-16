"""Bandeja de chats de WhatsApp para administradores."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_admin
from core.redis_client import redis_url
from models.conversacion import Conversacion
from models.usuario import EstadoUsuario, TipoUsuario, Usuario
from schemas.conversacion import (
    BandejaOut,
    ConversacionBandejaOut,
    EnviarMensajeIn,
    HistorialTelefonoOut,
    MensajeConversacionOut,
    OperadorOut,
    TransferirIn,
)
from services import conversaciones as svc
from services.conversaciones import CANAL, ConversacionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversaciones", tags=["conversaciones"])


def _http(exc: ConversacionError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.mensaje)


def _item(db: Session, conv: Conversacion) -> ConversacionBandejaOut:
    return ConversacionBandejaOut(**svc.resumen_bandeja_item(db, conv))


@router.get("/bandeja", response_model=BandejaOut)
def obtener_bandeja(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    datos = svc.bandeja(db, admin.id)
    return BandejaOut(
        en_espera=[_item(db, c) for c in datos["en_espera"]],
        mias=[_item(db, c) for c in datos["mias"]],
    )


@router.get("/operadores", response_model=list[OperadorOut])
def listar_operadores(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    filas = (
        db.query(Usuario)
        .filter(
            Usuario.tipo == TipoUsuario.ADMINISTRADOR,
            Usuario.estado == EstadoUsuario.APROBADO,
            Usuario.id != admin.id,
        )
        .order_by(Usuario.nombre.asc())
        .all()
    )
    return [OperadorOut(id=u.id, nombre=u.nombre) for u in filas]


@router.get("/historial", response_model=list[ConversacionBandejaOut])
def listar_historial(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    return [_item(db, c) for c in svc.historial_admin(db, admin.id, limit=limit, offset=offset)]


@router.get("/stream")
async def stream_conversaciones(
    request: Request,
    admin: Usuario = Depends(get_current_admin),
):
    admin_id = admin.id

    async def eventos():
        cliente = Redis.from_url(redis_url(), decode_responses=True, socket_connect_timeout=2)
        try:
            await cliente.ping()
        except Exception:
            await cliente.aclose()
            yield 'event: error\ndata: {"detail":"Redis no disponible"}\n\n'
            return
        pubsub = cliente.pubsub()
        await pubsub.subscribe(CANAL)
        try:
            while True:
                if await request.is_disconnected():
                    break
                mensaje = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if mensaje is None:
                    yield ": ping\n\n"
                    continue
                bruto = mensaje.get("data")
                if not bruto:
                    continue
                try:
                    evento = json.loads(bruto)
                except json.JSONDecodeError:
                    continue
                if not svc.visible_para_admin(evento, admin_id):
                    continue
                tipo = evento.get("tipo") or "message"
                data = json.dumps(evento.get("data") or {}, ensure_ascii=False, default=str)
                yield f"event: {tipo}\ndata: {data}\n\n"
        finally:
            try:
                await pubsub.unsubscribe(CANAL)
                await pubsub.aclose()
            except Exception:
                logger.debug("Cierre de pubsub SSE", exc_info=True)
            await cliente.aclose()

    return StreamingResponse(
        eventos(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/telefono/{telefono}/historial", response_model=HistorialTelefonoOut)
def historial_telefono(
    telefono: str,
    limit: int = Query(30, ge=1, le=100),
    antes_de: int | None = Query(None),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    mensajes, hay_mas = svc.pagina_mensajes_telefono(
        db, telefono, limite=limit, antes_de=antes_de
    )
    return HistorialTelefonoOut(
        mensajes=[MensajeConversacionOut(**svc.serializar_mensaje(m)) for m in mensajes],
        hay_mas=hay_mas,
    )


@router.get("/{conv_id}/mensajes", response_model=list[MensajeConversacionOut])
def listar_mensajes(
    conv_id: int,
    despues_de: int | None = Query(None),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    conv = db.get(Conversacion, conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="No encontré esa conversación")
    return [
        MensajeConversacionOut(**svc.serializar_mensaje(m))
        for m in svc.mensajes_de_telefono(db, conv.telefono, despues_de=despues_de)
    ]


@router.post("/{conv_id}/tomar", response_model=ConversacionBandejaOut)
def tomar_conversacion(
    conv_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    try:
        conv = svc.tomar(db, conv_id, admin)
    except ConversacionError as exc:
        raise _http(exc) from exc
    db.commit()
    return _item(db, conv)


@router.post("/{conv_id}/liberar", response_model=ConversacionBandejaOut)
def liberar_conversacion(
    conv_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    try:
        conv = svc.liberar(db, conv_id, admin)
    except ConversacionError as exc:
        raise _http(exc) from exc
    db.commit()
    return _item(db, conv)


@router.post("/{conv_id}/cerrar", response_model=ConversacionBandejaOut)
def cerrar_conversacion(
    conv_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    try:
        conv = svc.cerrar(db, conv_id, admin)
    except ConversacionError as exc:
        raise _http(exc) from exc
    db.commit()
    return _item(db, conv)


@router.post("/{conv_id}/reabrir", response_model=ConversacionBandejaOut)
def reabrir_conversacion(
    conv_id: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    try:
        conv = svc.reabrir(db, conv_id, admin)
    except ConversacionError as exc:
        raise _http(exc) from exc
    db.commit()
    return _item(db, conv)


@router.post("/{conv_id}/transferir", response_model=ConversacionBandejaOut)
def transferir_conversacion(
    conv_id: int,
    datos: TransferirIn,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    try:
        conv = svc.transferir(db, conv_id, admin, datos.operador_id)
    except ConversacionError as exc:
        raise _http(exc) from exc
    db.commit()
    return _item(db, conv)


@router.post("/{conv_id}/mensajes", response_model=MensajeConversacionOut)
def enviar_mensaje_operador(
    conv_id: int,
    datos: EnviarMensajeIn,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_current_admin),
):
    try:
        mensaje = svc.enviar_texto_operador(db, conv_id, admin, datos.texto)
    except ConversacionError as exc:
        raise _http(exc) from exc
    db.commit()
    return MensajeConversacionOut(**svc.serializar_mensaje(mensaje))
