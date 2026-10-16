"""Conversaciones de WhatsApp con operador humano."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, desc, func, nullslast, or_
from sqlalchemy.orm import Session, joinedload

from core.redis_client import get_redis
from core.storage import UPLOADS_DIR, storage
from models.conversacion import Conversacion, EstadoConversacion
from models.conversacion_participante import ConversacionParticipante
from models.mensaje_conversacion import AutorMensaje, MensajeConversacion, TipoMensaje
from models.usuario import TipoUsuario, Usuario

logger = logging.getLogger(__name__)

CANAL = "infrabot:conversaciones"
SUBCARPETA_MEDIA = "conversaciones"
VENTANA_WHATSAPP = timedelta(hours=24)
AVISO_FIN_ATENCION = (
    "La atención con el operador terminó. El asistente vuelve a atenderte. "
    "Escribí *operador* si necesitás hablar de nuevo con una persona."
)


class ConversacionError(Exception):
    def __init__(self, mensaje: str, status_code: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code


def media_ttl_dias() -> int:
    try:
        return max(1, int(os.getenv("CONVERSACION_MEDIA_TTL_DIAS") or "7"))
    except ValueError:
        return 7


def media_max_bytes() -> int:
    try:
        mb = int(os.getenv("CONVERSACION_MEDIA_MAX_MB") or "16")
    except ValueError:
        mb = 16
    return max(1, mb) * 1024 * 1024


def limpieza_intervalo_segundos() -> int:
    try:
        return max(60, int(os.getenv("CONVERSACION_LIMPIEZA_INTERVALO_SEGUNDOS") or "21600"))
    except ValueError:
        return 21600


def espera_aviso_minutos() -> int:
    try:
        return max(1, int(os.getenv("CONVERSACION_ESPERA_AVISO_MIN") or "15"))
    except ValueError:
        return 15


def inactividad_horas() -> int:
    try:
        return max(1, int(os.getenv("CONVERSACION_INACTIVIDAD_HORAS") or "4"))
    except ValueError:
        return 4


def es_simulador(telefono: str) -> bool:
    return (telefono or "").lower().startswith("sim")


def variantes_telefono(telefono: str) -> list[str]:
    """El sim puede guardar el número con o sin prefijo `sim`."""
    t = (telefono or "").strip()
    if not t:
        return []
    variantes = {t}
    if t.lower().startswith("sim"):
        resto = t[3:]
        if resto:
            variantes.add(resto)
    else:
        variantes.add(f"sim{t}")
    return list(variantes)


def expiracion_media() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=media_ttl_dias())


def ventana_abierta(conv: Conversacion | None) -> bool:
    if conv is None or conv.ultimo_mensaje_usuario is None:
        return False
    ultimo = conv.ultimo_mensaje_usuario
    if ultimo.tzinfo is None:
        ultimo = ultimo.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - ultimo < VENTANA_WHATSAPP


def publicar(tipo: str, data: dict) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        client.publish(CANAL, json.dumps({"tipo": tipo, "data": data}, default=str, ensure_ascii=False))
    except Exception:
        logger.exception("No se pudo publicar evento de conversación")


def activa(db: Session, telefono: str) -> Conversacion | None:
    return (
        db.query(Conversacion)
        .options(joinedload(Conversacion.operador))
        .filter(
            Conversacion.telefono.in_(variantes_telefono(telefono)),
            Conversacion.estado.in_(
                (EstadoConversacion.ESPERANDO_OPERADOR, EstadoConversacion.CON_OPERADOR)
            ),
        )
        .order_by(Conversacion.id.desc())
        .first()
    )


def _tipo_media(mime_type: str) -> TipoMensaje:
    mime = (mime_type or "").lower()
    if mime.startswith("audio/"):
        return TipoMensaje.AUDIO
    if mime.startswith("video/"):
        return TipoMensaje.VIDEO
    return TipoMensaje.IMAGEN


def _evento_estado(db: Session, tipo: str, conv: Conversacion) -> None:
    db.commit()
    publicar(
        tipo,
        {
            "id": conv.id,
            "telefono": conv.telefono,
            "estado": conv.estado.value,
            "operador_id": conv.operador_id,
            "operador_nombre": conv.operador.nombre if conv.operador else None,
            "fecha_solicitud": conv.fecha_solicitud.isoformat() if conv.fecha_solicitud else None,
            "fecha_toma": conv.fecha_toma.isoformat() if conv.fecha_toma else None,
            "ultimo_mensaje_usuario": (
                conv.ultimo_mensaje_usuario.isoformat() if conv.ultimo_mensaje_usuario else None
            ),
            "ventana_abierta": ventana_abierta(conv),
        },
    )


def _evento_mensaje(db: Session, tipo: str, conv: Conversacion | None, mensaje: MensajeConversacion) -> None:
    payload = serializar_mensaje(mensaje)
    db.commit()
    publicar(
        tipo,
        {
            "conversacion_id": conv.id if conv else mensaje.conversacion_id,
            "telefono": mensaje.telefono,
            "estado": conv.estado.value if conv else None,
            "operador_id": conv.operador_id if conv else None,
            "mensaje": payload,
        },
    )


def serializar_mensaje(m: MensajeConversacion) -> dict:
    return {
        "id": m.id,
        "conversacion_id": m.conversacion_id,
        "telefono": m.telefono,
        "autor": m.autor.value,
        "operador_id": m.operador_id,
        "operador_nombre": nombre_operador(m.operador) if m.operador else None,
        "tipo": m.tipo.value,
        "texto": m.texto,
        "media_url": None if m.media_eliminada else m.media_url,
        "mime_type": m.mime_type,
        "transcripcion": m.transcripcion,
        "media_eliminada": m.media_eliminada,
        "fecha": m.fecha.isoformat() if m.fecha else None,
    }


def registrar_entrante(
    db: Session,
    telefono: str,
    *,
    texto: str | None = None,
    tipo: TipoMensaje = TipoMensaje.TEXTO,
    media_url: str | None = None,
    mime_type: str | None = None,
    transcripcion: str | None = None,
    con_ttl: bool = False,
) -> MensajeConversacion:
    conv = activa(db, telefono)
    ahora = datetime.now(timezone.utc)
    mensaje = MensajeConversacion(
        conversacion_id=conv.id if conv else None,
        telefono=conv.telefono if conv is not None else telefono,
        autor=AutorMensaje.USUARIO,
        tipo=tipo,
        texto=texto,
        media_url=media_url,
        mime_type=mime_type,
        transcripcion=transcripcion,
        media_expira_en=expiracion_media() if con_ttl and media_url else None,
        fecha=ahora,
    )
    db.add(mensaje)
    if conv is not None:
        conv.ultimo_mensaje_usuario = ahora
    db.flush()
    if conv is not None:
        _evento_mensaje(db, "mensaje", conv, mensaje)
    else:
        db.commit()
    return mensaje


def registrar_saliente(
    db: Session,
    telefono: str,
    texto: str,
    *,
    autor: AutorMensaje = AutorMensaje.BOT,
    operador_id: int | None = None,
) -> MensajeConversacion:
    conv = activa(db, telefono)
    mensaje = MensajeConversacion(
        conversacion_id=conv.id if conv else None,
        telefono=conv.telefono if conv is not None else telefono,
        autor=autor,
        operador_id=operador_id,
        tipo=TipoMensaje.TEXTO,
        texto=texto,
        fecha=datetime.now(timezone.utc),
    )
    db.add(mensaje)
    db.flush()
    if conv is not None:
        _evento_mensaje(db, "mensaje", conv, mensaje)
    else:
        db.commit()
    return mensaje


def nombre_operador(usuario: Usuario | None) -> str:
    if usuario is None:
        return "Un operador"
    nombre = (usuario.nombre or "").strip()
    if nombre:
        return nombre
    email = (usuario.email or "").strip()
    if "@" in email:
        return email.split("@", 1)[0]
    return "Un operador"


def _mensaje_sistema(
    db: Session, conv: Conversacion, texto: str, operador: Usuario | None = None
) -> MensajeConversacion:
    mensaje = MensajeConversacion(
        conversacion_id=conv.id,
        telefono=conv.telefono,
        autor=AutorMensaje.SISTEMA,
        tipo=TipoMensaje.TEXTO,
        texto=texto,
        operador_id=operador.id if operador is not None else None,
        fecha=datetime.now(timezone.utc),
    )
    db.add(mensaje)
    if operador is not None:
        mensaje.operador = operador
    db.flush()
    _evento_mensaje(db, "mensaje", conv, mensaje)
    return mensaje


def solicitar(db: Session, telefono: str) -> Conversacion:
    existente = activa(db, telefono)
    if existente is not None:
        return existente
    ahora = datetime.now(timezone.utc)
    conv = Conversacion(
        telefono=telefono,
        estado=EstadoConversacion.ESPERANDO_OPERADOR,
        fecha_solicitud=ahora,
        ultimo_mensaje_usuario=ahora,
    )
    db.add(conv)
    db.flush()
    _mensaje_sistema(db, conv, "El usuario pidió hablar con un operador.")
    db.refresh(conv)
    _evento_estado(db, "en_espera", conv)
    return conv


def tomar(db: Session, conv_id: int, operador: Usuario) -> Conversacion:
    ahora = datetime.now(timezone.utc)
    actualizadas = (
        db.query(Conversacion)
        .filter(
            Conversacion.id == conv_id,
            Conversacion.estado == EstadoConversacion.ESPERANDO_OPERADOR,
        )
        .update(
            {
                "estado": EstadoConversacion.CON_OPERADOR,
                "operador_id": operador.id,
                "fecha_toma": ahora,
            },
            synchronize_session=False,
        )
    )
    if actualizadas == 0:
        raise ConversacionError("Otro operador ya tomó esta conversación", 409)
    db.flush()
    conv = (
        db.query(Conversacion)
        .options(joinedload(Conversacion.operador))
        .filter(Conversacion.id == conv_id)
        .one()
    )
    registrar_participante(db, conv.id, operador.id)
    _mensaje_sistema(
        db, conv, f"{nombre_operador(operador)} tomó la conversación.", operador=operador
    )
    _evento_estado(db, "asignada", conv)
    return conv


def _exigir_asignado(conv: Conversacion, operador: Usuario) -> None:
    if conv.estado != EstadoConversacion.CON_OPERADOR or conv.operador_id != operador.id:
        raise ConversacionError("Esta conversación no está asignada a vos", 403)


def liberar(db: Session, conv_id: int, operador: Usuario) -> Conversacion:
    """Suelta el chat y lo devuelve al bot (no vuelve a la cola de espera)."""
    return cerrar(
        db,
        conv_id,
        operador,
        motivo=f"{nombre_operador(operador)} liberó la conversación. El bot vuelve a atender.",
    )


def transferir(db: Session, conv_id: int, operador: Usuario, destino_id: int) -> Conversacion:
    conv = _obtener(db, conv_id)
    _exigir_asignado(conv, operador)
    if destino_id == operador.id:
        raise ConversacionError("Elegí otro operador para transferir", 400)
    destino = db.get(Usuario, destino_id)
    if destino is None or destino.tipo is not TipoUsuario.ADMINISTRADOR:
        raise ConversacionError("El destinatario no es un administrador", 400)
    conv.operador_id = destino.id
    conv.fecha_toma = datetime.now(timezone.utc)
    registrar_participante(db, conv.id, operador.id)
    registrar_participante(db, conv.id, destino.id)
    _mensaje_sistema(
        db,
        conv,
        f"{nombre_operador(operador)} transfirió la conversación a {nombre_operador(destino)}.",
        operador=operador,
    )
    db.flush()
    db.refresh(conv)
    _evento_estado(db, "asignada", conv)
    return conv


def cerrar(db: Session, conv_id: int, operador: Usuario | None = None, motivo: str | None = None) -> Conversacion:
    conv = _obtener(db, conv_id)
    if conv.estado == EstadoConversacion.CERRADA:
        return conv
    if operador is not None and conv.estado == EstadoConversacion.CON_OPERADOR:
        _exigir_asignado(conv, operador)
    conv.estado = EstadoConversacion.CERRADA
    conv.fecha_cierre = datetime.now(timezone.utc)
    texto = motivo or (
        f"{nombre_operador(operador)} cerró la conversación. El bot vuelve a atender."
        if operador
        else "La conversación se cerró. El bot vuelve a atender."
    )
    _mensaje_sistema(db, conv, texto, operador=operador)
    registrar_saliente(db, conv.telefono, AVISO_FIN_ATENCION, autor=AutorMensaje.BOT)
    if not es_simulador(conv.telefono):
        from core.whatsapp_client import enviar_mensaje

        try:
            enviar_mensaje(conv.telefono, AVISO_FIN_ATENCION)
        except Exception:
            logger.exception("No se pudo avisar el fin de atención a %s", conv.telefono)
    db.flush()
    _evento_estado(db, "cerrada", conv)
    return conv


def registrar_participante(db: Session, conv_id: int, usuario_id: int | None) -> None:
    if not usuario_id:
        return
    existe = (
        db.query(ConversacionParticipante)
        .filter(
            ConversacionParticipante.conversacion_id == conv_id,
            ConversacionParticipante.usuario_id == usuario_id,
        )
        .first()
    )
    if existe is not None:
        return
    db.add(ConversacionParticipante(conversacion_id=conv_id, usuario_id=usuario_id))
    db.flush()


def es_participante(db: Session, conv_id: int, usuario_id: int) -> bool:
    return (
        db.query(ConversacionParticipante)
        .filter(
            ConversacionParticipante.conversacion_id == conv_id,
            ConversacionParticipante.usuario_id == usuario_id,
        )
        .first()
        is not None
    )


def backfill_participantes(db: Session) -> None:
    for conv in db.query(Conversacion).filter(Conversacion.operador_id.isnot(None)).all():
        registrar_participante(db, conv.id, conv.operador_id)
    filas = (
        db.query(MensajeConversacion.conversacion_id, MensajeConversacion.operador_id)
        .filter(
            MensajeConversacion.operador_id.isnot(None),
            MensajeConversacion.conversacion_id.isnot(None),
        )
        .distinct()
        .all()
    )
    for conv_id, operador_id in filas:
        registrar_participante(db, conv_id, operador_id)


def historial_admin(
    db: Session, admin_id: int, *, limit: int = 50, offset: int = 0
) -> list[Conversacion]:
    backfill_participantes(db)
    visibilidad = or_(
        Conversacion.estado == EstadoConversacion.CERRADA,
        and_(
            Conversacion.estado == EstadoConversacion.CON_OPERADOR,
            Conversacion.operador_id != admin_id,
        ),
    )
    clave_telefono = func.regexp_replace(func.lower(Conversacion.telefono), r"^sim", "")
    ultima_por_numero = (
        db.query(func.max(Conversacion.id).label("max_id"))
        .join(
            ConversacionParticipante,
            ConversacionParticipante.conversacion_id == Conversacion.id,
        )
        .filter(ConversacionParticipante.usuario_id == admin_id)
        .filter(visibilidad)
        .group_by(clave_telefono)
        .subquery()
    )
    return (
        db.query(Conversacion)
        .options(joinedload(Conversacion.operador))
        .filter(Conversacion.id.in_(db.query(ultima_por_numero.c.max_id)))
        .order_by(nullslast(desc(Conversacion.fecha_cierre)), Conversacion.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def reabrir(db: Session, conv_id: int, operador: Usuario) -> Conversacion:
    conv = _obtener(db, conv_id)
    if conv.estado != EstadoConversacion.CERRADA:
        raise ConversacionError("Solo se puede reabrir una conversación cerrada", 400)
    if not es_participante(db, conv.id, operador.id):
        raise ConversacionError("No participaste de esta conversación", 403)
    if not ventana_abierta(conv):
        raise ConversacionError(
            "Pasaron más de 24 horas desde el último mensaje del usuario. "
            "WhatsApp no permite retomar hasta que escriba de nuevo.",
            400,
        )
    otra = activa(db, conv.telefono)
    if otra is not None:
        raise ConversacionError("Ya hay una conversación activa para este número", 409)
    ahora = datetime.now(timezone.utc)
    conv.estado = EstadoConversacion.CON_OPERADOR
    conv.operador_id = operador.id
    conv.fecha_toma = ahora
    conv.fecha_cierre = None
    registrar_participante(db, conv.id, operador.id)
    _mensaje_sistema(
        db, conv, f"{nombre_operador(operador)} reabrió la conversación.", operador=operador
    )
    db.flush()
    db.refresh(conv)
    _evento_estado(db, "asignada", conv)
    return conv


def enviar_texto_operador(db: Session, conv_id: int, operador: Usuario, texto: str) -> MensajeConversacion:
    conv = _obtener(db, conv_id)
    _exigir_asignado(conv, operador)
    if not ventana_abierta(conv):
        raise ConversacionError(
            "Pasaron más de 24 horas desde el último mensaje del usuario. "
            "WhatsApp no permite responder hasta que escriba de nuevo.",
            400,
        )
    limpio = (texto or "").strip()
    if not limpio:
        raise ConversacionError("El mensaje no puede estar vacío", 400)
    if len(limpio) > 4096:
        raise ConversacionError("El mensaje supera el máximo de 4096 caracteres", 400)
    mensaje = registrar_saliente(
        db, conv.telefono, limpio, autor=AutorMensaje.OPERADOR, operador_id=operador.id
    )
    mensaje.operador = operador
    if not es_simulador(conv.telefono):
        from core.whatsapp_client import enviar_mensaje

        try:
            enviar_mensaje(conv.telefono, limpio)
        except Exception:
            logger.exception("WhatsApp no envió el mensaje de operador a %s", conv.telefono)
            raise ConversacionError(
                "El mensaje quedó en el chat interno, pero WhatsApp no lo pudo enviar.",
                502,
            ) from None
    return mensaje


def _obtener(db: Session, conv_id: int) -> Conversacion:
    conv = (
        db.query(Conversacion)
        .options(joinedload(Conversacion.operador))
        .filter(Conversacion.id == conv_id)
        .first()
    )
    if conv is None:
        raise ConversacionError("No encontré esa conversación", 404)
    return conv


def bandeja(db: Session, operador_id: int) -> dict[str, list[Conversacion]]:
    en_espera = (
        db.query(Conversacion)
        .options(joinedload(Conversacion.operador))
        .filter(Conversacion.estado == EstadoConversacion.ESPERANDO_OPERADOR)
        .order_by(Conversacion.fecha_solicitud.asc())
        .all()
    )
    mias = (
        db.query(Conversacion)
        .options(joinedload(Conversacion.operador))
        .filter(
            Conversacion.estado == EstadoConversacion.CON_OPERADOR,
            Conversacion.operador_id == operador_id,
        )
        .order_by(Conversacion.fecha_toma.desc())
        .all()
    )
    return {"en_espera": en_espera, "mias": mias}


def _query_mensajes_telefono(db: Session, telefono: str):
    return (
        db.query(MensajeConversacion)
        .options(joinedload(MensajeConversacion.operador))
        .filter(MensajeConversacion.telefono.in_(variantes_telefono(telefono)))
    )


def mensajes_de_telefono(
    db: Session, telefono: str, *, despues_de: int | None = None, limite: int = 200
) -> list[MensajeConversacion]:
    q = _query_mensajes_telefono(db, telefono)
    if despues_de:
        q = q.filter(MensajeConversacion.id > despues_de)
    return q.order_by(MensajeConversacion.id.asc()).limit(limite).all()


def pagina_mensajes_telefono(
    db: Session, telefono: str, *, limite: int = 30, antes_de: int | None = None
) -> tuple[list[MensajeConversacion], bool]:
    """Últimos `limite` mensajes (o los anteriores a `antes_de`), en orden cronológico."""
    q = _query_mensajes_telefono(db, telefono)
    if antes_de is not None:
        q = q.filter(MensajeConversacion.id < antes_de)
    filas = q.order_by(MensajeConversacion.id.desc()).limit(limite + 1).all()
    hay_mas = len(filas) > limite
    return list(reversed(filas[:limite])), hay_mas


def resumen_bandeja_item(db: Session, conv: Conversacion) -> dict:
    ultimo = (
        db.query(MensajeConversacion)
        .filter(MensajeConversacion.telefono.in_(variantes_telefono(conv.telefono)))
        .order_by(MensajeConversacion.id.desc())
        .first()
    )
    preview = ""
    if ultimo is not None:
        if ultimo.tipo == TipoMensaje.AUDIO:
            preview = ultimo.transcripcion or "Audio"
        elif ultimo.tipo == TipoMensaje.IMAGEN:
            preview = ultimo.texto or "Imagen"
        elif ultimo.tipo == TipoMensaje.VIDEO:
            preview = ultimo.texto or "Video"
        else:
            preview = (ultimo.texto or "")[:140]
    return {
        "id": conv.id,
        "telefono": conv.telefono,
        "estado": conv.estado.value,
        "operador_id": conv.operador_id,
        "operador_nombre": conv.operador.nombre if conv.operador else None,
        "fecha_solicitud": conv.fecha_solicitud,
        "fecha_toma": conv.fecha_toma,
        "fecha_cierre": conv.fecha_cierre,
        "ultimo_mensaje_usuario": conv.ultimo_mensaje_usuario,
        "ventana_abierta": ventana_abierta(conv),
        "ultimo_texto": preview,
        "ultimo_tipo": ultimo.tipo.value if ultimo else None,
        "ultimo_autor": ultimo.autor.value if ultimo else None,
        "ultimo_id": ultimo.id if ultimo else None,
        "ultimo_fecha": ultimo.fecha if ultimo else None,
    }


def visible_para_admin(evento: dict, admin_id: int) -> bool:
    tipo = evento.get("tipo")
    data = evento.get("data") or {}
    if tipo in ("en_espera", "asignada", "liberada", "cerrada"):
        return True
    if tipo in ("mensaje", "mensaje_actualizado"):
        estado = data.get("estado")
        if estado == EstadoConversacion.ESPERANDO_OPERADOR.value:
            return True
        return data.get("operador_id") == admin_id
    return False


def actualizar_transcripcion(db: Session, mensaje_id: int, texto: str | None) -> MensajeConversacion | None:
    mensaje = (
        db.query(MensajeConversacion)
        .options(joinedload(MensajeConversacion.operador))
        .filter(MensajeConversacion.id == mensaje_id)
        .first()
    )
    if mensaje is None:
        return None
    mensaje.transcripcion = texto
    db.flush()
    conv = activa(db, mensaje.telefono)
    _evento_mensaje(db, "mensaje_actualizado", conv, mensaje)
    return mensaje


def guardar_media_operador(contenido: bytes, mime_type: str) -> str | None:
    if not contenido:
        return None
    if len(contenido) > media_max_bytes():
        return None
    from core.whatsapp_client import EXTENSIONES_MIME

    mime = (mime_type or "").split(";")[0].strip()
    extension = EXTENSIONES_MIME.get(mime, ".bin")
    return storage.guardar_bytes(contenido, SUBCARPETA_MEDIA, extension)


def limpiar_media_vencida(db: Session) -> int:
    ahora = datetime.now(timezone.utc)
    vencidos = (
        db.query(MensajeConversacion)
        .filter(
            MensajeConversacion.media_url.isnot(None),
            MensajeConversacion.media_eliminada.is_(False),
            MensajeConversacion.media_expira_en.isnot(None),
            MensajeConversacion.media_expira_en < ahora,
        )
        .limit(500)
        .all()
    )
    for m in vencidos:
        if m.media_url:
            storage.eliminar(m.media_url)
        m.media_eliminada = True
    db.flush()
    _limpiar_huerfanos(db)
    return len(vencidos)


def _limpiar_huerfanos(db: Session) -> None:
    carpeta = UPLOADS_DIR / SUBCARPETA_MEDIA
    if not carpeta.is_dir():
        return
    vivas = {
        url
        for (url,) in db.query(MensajeConversacion.media_url).filter(
            MensajeConversacion.media_url.isnot(None),
            MensajeConversacion.media_eliminada.is_(False),
        )
    }
    limite = datetime.now(timezone.utc) - timedelta(days=1)
    for archivo in carpeta.iterdir():
        if not archivo.is_file():
            continue
        url = f"/uploads/{SUBCARPETA_MEDIA}/{archivo.name}"
        if url in vivas:
            continue
        mtime = datetime.fromtimestamp(archivo.stat().st_mtime, tz=timezone.utc)
        if mtime < limite:
            archivo.unlink(missing_ok=True)


def correr_timeouts(db: Session) -> None:
    ahora = datetime.now(timezone.utc)
    aviso_desde = ahora - timedelta(minutes=espera_aviso_minutos())
    pendientes = (
        db.query(Conversacion)
        .filter(
            Conversacion.estado == EstadoConversacion.ESPERANDO_OPERADOR,
            Conversacion.aviso_espera_enviado.is_(False),
            Conversacion.fecha_solicitud <= aviso_desde,
        )
        .all()
    )
    from core.whatsapp_client import enviar_mensaje

    aviso = (
        "⏳ Todavía no hay un operador disponible. "
        "Seguí escribiendo acá; te responden apenas puedan.\n\n"
        "Si preferís no esperar, escribí *cancelar* o *volver al bot*."
    )
    for conv in pendientes:
        conv.aviso_espera_enviado = True
        registrar_saliente(db, conv.telefono, aviso, autor=AutorMensaje.BOT)
        if not es_simulador(conv.telefono):
            try:
                enviar_mensaje(conv.telefono, aviso)
            except Exception:
                logger.exception("No se pudo avisar espera al %s", conv.telefono)

    from services.configuracion_atencion import inactividad_usuario_minutos

    inactivo_desde = ahora - timedelta(minutes=inactividad_usuario_minutos(db))
    asignadas = (
        db.query(Conversacion)
        .options(joinedload(Conversacion.operador))
        .filter(Conversacion.estado == EstadoConversacion.CON_OPERADOR)
        .all()
    )
    cierre = (
        "Esta conversación se cerró por inactividad. "
        "El asistente vuelve a atenderte. Escribí *operador* si necesitás a una persona."
    )
    for conv in asignadas:
        ultimo = (
            db.query(MensajeConversacion)
            .filter(
                MensajeConversacion.conversacion_id == conv.id,
                MensajeConversacion.autor != AutorMensaje.SISTEMA,
            )
            .order_by(MensajeConversacion.id.desc())
            .first()
        )
        if ultimo is None or ultimo.autor == AutorMensaje.USUARIO:
            continue
        ultima = ultimo.fecha or conv.fecha_toma or conv.fecha_solicitud
        if ultima.tzinfo is None:
            ultima = ultima.replace(tzinfo=timezone.utc)
        if ultima > inactivo_desde:
            continue
        conv.estado = EstadoConversacion.CERRADA
        conv.fecha_cierre = ahora
        registrar_saliente(db, conv.telefono, cierre, autor=AutorMensaje.BOT)
        _mensaje_sistema(db, conv, "Se cerró por inactividad. El bot vuelve a atender.")
        _evento_estado(db, "cerrada", conv)
        if not es_simulador(conv.telefono):
            try:
                enviar_mensaje(conv.telefono, cierre)
            except Exception:
                logger.exception("No se pudo avisar el cierre al %s", conv.telefono)


_PEDIDO_OPERADOR = re.compile(
    r"\b("
    r"operador(?:es)?"
    r"|humano(?:s)?"
    r"|persona\s+real"
    r"|atenci[oó]n\s+humana"
    r"|hablar\s+con\s+(?:alguien|una?\s+persona|un\s+humano|un\s+operador)"
    r")\b",
    re.IGNORECASE,
)


def pedir_operador(texto: str) -> bool:
    t = (texto or "").strip().lower()
    if not t:
        return False
    if t in (
        "operador",
        "humano",
        "persona",
        "hablar_con_operador",
        "hablar con alguien",
    ):
        return True
    return bool(_PEDIDO_OPERADOR.search(t))


_VOLVER_BOT = re.compile(
    r"\b("
    r"volver(?:me)?\s+al\s+bot"
    r"|cancelar(?:\s+espera)?"
    r"|no\s+(?:quiero\s+)?esperar"
    r"|hablar\s+con\s+el\s+bot"
    r")\b",
    re.IGNORECASE,
)


def pedir_volver_bot(texto: str, *, en_espera: bool = True) -> bool:
    t = (texto or "").strip().lower()
    if not t:
        return False
    if t in ("cancelar", "volver", "volver_al_bot", "volver al bot"):
        return True
    if en_espera and t in ("bot", "menu", "menú", "ayuda"):
        return True
    return bool(_VOLVER_BOT.search(t))


def cancelar_por_usuario(db: Session, conv_id: int) -> Conversacion:
    """El usuario deja de esperar / corta al operador y vuelve al bot."""
    conv = _obtener(db, conv_id)
    if conv.estado == EstadoConversacion.CERRADA:
        return conv
    conv.estado = EstadoConversacion.CERRADA
    conv.fecha_cierre = datetime.now(timezone.utc)
    _mensaje_sistema(db, conv, "El usuario canceló y volvió al asistente.")
    db.flush()
    _evento_estado(db, "cerrada", conv)
    return conv
