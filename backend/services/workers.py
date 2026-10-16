"""Loops de fondo: cola WhatsApp y recordatorios a contratistas."""

from __future__ import annotations

import asyncio
import logging

from core.database import SessionLocal
from services.cola_whatsapp import consumir_uno
from services.seguimiento import ejecutar_seguimiento, seguimiento_intervalo_segundos

logger = logging.getLogger(__name__)


async def loop_cola_whatsapp(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            hubo = await asyncio.to_thread(consumir_uno, 1)
            if not hubo:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error en worker WhatsApp")
            await asyncio.sleep(1)


async def loop_seguimiento(stop: asyncio.Event) -> None:
    intervalo = max(30, seguimiento_intervalo_segundos())
    while not stop.is_set():
        try:
            await asyncio.sleep(intervalo)
            if stop.is_set():
                break
            await asyncio.to_thread(_correr_seguimiento)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error en loop de seguimiento")


def _correr_seguimiento() -> None:
    db = SessionLocal()
    try:
        resultado = ejecutar_seguimiento(db)
        db.commit()
        if resultado.enviados:
            logger.info("Seguimiento: %s recordatorio(s) enviado(s)", resultado.enviados)
    except Exception:
        db.rollback()
        logger.exception("Falló el job de seguimiento")
    finally:
        db.close()


async def loop_limpieza_conversaciones(stop: asyncio.Event) -> None:
    from services.conversaciones import limpieza_intervalo_segundos

    intervalo = limpieza_intervalo_segundos()
    while not stop.is_set():
        try:
            await asyncio.sleep(intervalo)
            if stop.is_set():
                break
            await asyncio.to_thread(_correr_limpieza_media)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error en loop de limpieza de chats")


def _correr_limpieza_media() -> None:
    from services.conversaciones import limpiar_media_vencida

    db = SessionLocal()
    try:
        borrados = limpiar_media_vencida(db)
        db.commit()
        if borrados:
            logger.info("Chats: %s archivo(s) de media vencido(s) borrado(s)", borrados)
    except Exception:
        db.rollback()
        logger.exception("Falló la limpieza de media de chats")
    finally:
        db.close()


async def loop_timeouts_conversaciones(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.sleep(60)
            if stop.is_set():
                break
            await asyncio.to_thread(_correr_timeouts_chats)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error en loop de timeouts de chats")


def _correr_timeouts_chats() -> None:
    from services.conversaciones import correr_timeouts

    db = SessionLocal()
    try:
        correr_timeouts(db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Falló el job de timeouts de chats")
    finally:
        db.close()
