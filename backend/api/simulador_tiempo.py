"""API de simulación de avance de tiempo para administradores.

Permite adelantar el reloj del sistema (en horas, días o hasta la próxima visita)
para probar y demostrar todo el flujo operativo de InfraBot:
- Notificaciones de recordatorio de visita (24 h antes y el mismo día).
- Verificación del inicio de la obra al cumplirse el horario pactado (CU-05).
- Consultas de seguimiento periódico durante la ejecución ("¿Terminaste el trabajo?").
- Consulta a la escuela para verificar la resolución ("¿Quedó resuelto?").
- Retorno y reseteo al tiempo real en cualquier momento.
"""

from __future__ import annotations

from datetime import timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from core import reloj
from core.database import get_db
from core.dependencies import get_current_admin
from core.whatsapp_client import obtener_historial_salientes
from models.contratista import Contratista
from models.presupuesto import Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.recordatorio_contratista import RecordatorioContratista
from models.usuario import Usuario
from models.visita import EstadoVisita, Visita
from schemas.simulador_tiempo import (
    AvanzarTiempoIn,
    EstadoSimuladorTiempoOut,
    MensajeSalienteOut,
    ReclamoEjecucionSimuladoOut,
    VisitaSimuladaOut,
)
from services import recordatorios, seguimiento

router = APIRouter(prefix="/simulador-tiempo", tags=["simulador-tiempo"])


def _construir_estado(db: Session, acciones: list[str] | None = None) -> EstadoSimuladorTiempoOut:
    ahora = reloj.ahora()

    # 1. Próximas visitas confirmadas
    visitas = (
        db.query(Visita)
        .filter(
            Visita.estado == EstadoVisita.CONFIRMADA,
            Visita.fecha_visita.isnot(None),
        )
        .order_by(Visita.fecha_visita.asc())
        .all()
    )

    lista_visitas: list[VisitaSimuladaOut] = []
    for v in visitas:
        f = v.fecha_visita
        if f is None:
            continue
        if f.tzinfo is None:
            f = f.replace(tzinfo=timezone.utc)
        horas_faltantes = round((f - ahora).total_seconds() / 3600.0, 1)

        reclamo = db.get(Reclamo, v.reclamo_id)
        contratista = db.get(Contratista, v.contratista_id)

        lista_visitas.append(
            VisitaSimuladaOut(
                id=v.id,
                reclamo_id=v.reclamo_id,
                escuela=reclamo.nombre_escuela if reclamo else f"Reclamo #{v.reclamo_id}",
                contratista=contratista.nombre_empresa if contratista else "Contratista",
                contratista_telefono=contratista.telefono if contratista else None,
                creador_telefono=reclamo.telefono_creador if reclamo else None,
                horario_confirmado=v.horario_confirmado,
                fecha_visita=f.isoformat(),
                fecha_visita_art=reloj.formatear_art(f),
                horas_faltantes=horas_faltantes,
                dia_antes_enviado=v.recordatorio_dia_antes_enviado is not None,
                mismo_dia_enviado=v.recordatorio_mismo_dia_enviado is not None,
                pregunta_inicio_enviada=v.pregunta_inicio_enviada is not None,
            )
        )

    # 2. Reclamos en ejecución
    reclamos_ejec = (
        db.query(Reclamo)
        .filter(Reclamo.estado == EstadoReclamo.EN_EJECUCION)
        .order_by(Reclamo.id.desc())
        .all()
    )

    lista_ejecucion: list[ReclamoEjecucionSimuladoOut] = []
    for r in reclamos_ejec:
        presupuesto = (
            db.query(Presupuesto)
            .options(joinedload(Presupuesto.contratista))
            .filter(Presupuesto.reclamo_id == r.id)
            .order_by(Presupuesto.fecha.desc())
            .first()
        )
        contratista = presupuesto.contratista if presupuesto else None
        recordatorio = (
            db.query(RecordatorioContratista)
            .filter(RecordatorioContratista.reclamo_id == r.id)
            .first()
        )

        prox_art = None
        if recordatorio and recordatorio.proxima_pregunta:
            prox_art = reloj.formatear_art(recordatorio.proxima_pregunta)

        lista_ejecucion.append(
            ReclamoEjecucionSimuladoOut(
                id=r.id,
                escuela=r.nombre_escuela,
                contratista=contratista.nombre_empresa if contratista else None,
                contratista_telefono=contratista.telefono if contratista else None,
                creador_telefono=r.telefono_creador,
                cantidad_envios=recordatorio.cantidad_envios if recordatorio else 0,
                consulto_escuela=bool(recordatorio.consulto_escuela) if recordatorio else False,
                proxima_pregunta_art=prox_art,
            )
        )

    # 3. Mensajes salientes recientes registrados por el mock/cliente de WhatsApp
    mensajes_raw = obtener_historial_salientes(limite=20)
    ultimos_mensajes = [
        MensajeSalienteOut(
            id=m["id"],
            fecha=m["fecha"],
            fecha_art=m["fecha_art"],
            to=m["to"],
            tipo=m["tipo"],
            body=m["body"],
            botones=m.get("botones") or [],
            secciones=m.get("secciones") or [],
        )
        for m in mensajes_raw
    ]

    return EstadoSimuladorTiempoOut(
        ahora_simulado=ahora.isoformat(),
        ahora_art=reloj.formatear_art(),
        offset_segundos=reloj.obtener_offset().total_seconds(),
        offset_descripcion=reloj.descripcion_offset(),
        es_simulado=reloj.esta_simulado(),
        proximas_visitas=lista_visitas,
        reclamos_en_ejecucion=lista_ejecucion,
        ultimos_mensajes=ultimos_mensajes,
        acciones_disparadas=acciones or [],
    )


@router.get("/estado", response_model=EstadoSimuladorTiempoOut)
def obtener_estado_simulador(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Obtiene el estado actual del reloj simulado, visitas agendadas y reclamos en ejecución."""
    return _construir_estado(db)


@router.post("/avanzar", response_model=EstadoSimuladorTiempoOut)
def avanzar_tiempo(
    datos: AvanzarTiempoIn,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Avanza el reloj virtual y dispara de inmediato los chequeos de recordatorios y seguimiento."""
    acciones: list[str] = []
    ahora_actual = reloj.ahora()

    if datos.hasta_proxima_visita:
        visita_proxima = (
            db.query(Visita)
            .filter(
                Visita.estado == EstadoVisita.CONFIRMADA,
                Visita.fecha_visita.isnot(None),
                Visita.fecha_visita > ahora_actual,
            )
            .order_by(Visita.fecha_visita.asc())
            .first()
        )
        if visita_proxima and visita_proxima.fecha_visita:
            f = visita_proxima.fecha_visita
            if f.tzinfo is None:
                f = f.replace(tzinfo=timezone.utc)
            destino = f + timedelta(hours=datos.horas_despues_visita)
            reloj.fijar_tiempo(destino)
            acciones.append(
                f"⏰ Reloj avanzado a la hora de la Visita #{visita_proxima.id} ({reloj.formatear_art(destino)})"
            )
        else:
            # Si no hay visitas futuras, avanzamos 24 horas por defecto
            reloj.avanzar_tiempo(dias=1.0)
            acciones.append("No había visitas futuras agendadas. Se avanzó 1 día por defecto.")
    else:
        if datos.horas == 0 and datos.dias == 0:
            raise HTTPException(status_code=400, detail="Debe especificar horas o días a avanzar")
        reloj.avanzar_tiempo(horas=datos.horas, dias=datos.dias)
        delta_txt = []
        if datos.dias > 0:
            delta_txt.append(f"{datos.dias} día(s)")
        if datos.horas > 0:
            delta_txt.append(f"{datos.horas} hora(s)")
        acciones.append(f"⏰ Reloj avanzado en {', '.join(delta_txt)} (Nueva hora: {reloj.formatear_art()})")

    # Ejecutar comprobaciones de recordatorios de visitas sincrónicamente
    try:
        eventos_recordatorios = recordatorios.revisar_recordatorios(db)
        for ev in eventos_recordatorios:
            acciones.append(ev["detalle"])
    except Exception as e:
        acciones.append(f"⚠️ Error al revisar recordatorios: {e}")

    # Ejecutar comprobaciones de seguimiento de reclamos en ejecución sincrónicamente
    try:
        res_seguimiento = seguimiento.ejecutar_seguimiento(db)
        for d in res_seguimiento.detalles:
            acciones.append(d["detalle"])
        if res_seguimiento.enviados > 0:
            db.commit()
    except Exception as e:
        acciones.append(f"⚠️ Error al ejecutar seguimiento: {e}")

    return _construir_estado(db, acciones=acciones)


@router.post("/reset", response_model=EstadoSimuladorTiempoOut)
def resetear_tiempo(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_current_admin),
):
    """Restablece el reloj virtual al tiempo real."""
    reloj.resetear_tiempo()
    return _construir_estado(
        db,
        acciones=["🔄 Reloj virtual restablecido a la fecha y hora real."],
    )


@router.get("/mensajes", response_model=list[MensajeSalienteOut])
def obtener_mensajes_whatsapp_salientes(
    destinatario: str | None = None,
    limite: int = 50,
    _admin: Usuario = Depends(get_current_admin),
):
    """Devuelve los últimos mensajes enviados por el bot de WhatsApp."""
    mensajes_raw = obtener_historial_salientes(to=destinatario, limite=limite)
    return [
        MensajeSalienteOut(
            id=m["id"],
            fecha=m["fecha"],
            fecha_art=m["fecha_art"],
            to=m["to"],
            tipo=m["tipo"],
            body=m["body"],
            botones=m.get("botones") or [],
            secciones=m.get("secciones") or [],
        )
        for m in mensajes_raw
    ]

