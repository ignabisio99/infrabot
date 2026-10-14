"""Pruebas unitarias para el reloj virtual y simulador de tiempo."""

from datetime import datetime, timedelta, timezone

from core import reloj
from models.contratista import Contratista
from models.presupuesto import EstadoPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo, Reclamo
from models.visita import EstadoVisita, Visita
from services.recordatorios import revisar_recordatorios
from services.seguimiento import ejecutar_seguimiento


def test_reloj_virtual_operaciones_basicas():
    reloj.resetear_tiempo()
    assert not reloj.esta_simulado()
    assert reloj.descripcion_offset() == "Tiempo real"

    # Avanzar 6 horas
    reloj.avanzar_tiempo(horas=6)
    assert reloj.esta_simulado()
    assert "+6 horas" in reloj.descripcion_offset()

    # Avanzar 1 día adicional
    reloj.avanzar_tiempo(dias=1)
    assert "+1 día, 6 horas" in reloj.descripcion_offset()

    # Resetear
    reloj.resetear_tiempo()
    assert not reloj.esta_simulado()
    assert reloj.descripcion_offset() == "Tiempo real"


def test_simulacion_recordatorios_visita(db):
    reloj.resetear_tiempo()
    tiempo_real = reloj.ahora()

    # Crear contratista y reclamo coordinado con visita en 2 días (48h)
    contratista = Contratista(
        nombre_empresa="Electricidad Test SRL",
        cuit="20-99999999-9",
        telefono="5491199998888",
        activo=True,
    )
    db.add(contratista)
    db.flush()

    reclamo = Reclamo(
        nombre_escuela="Escuela N° 10 San Martín",
        ubicacion="Avenida Corrientes 1234",
        categoria="Electricidad",
        estado=EstadoReclamo.VISITA_COORDINADA,
        telefono_creador="5491111112222",
    )
    db.add(reclamo)
    db.flush()

    fecha_visita = tiempo_real + timedelta(days=2)
    visita = Visita(
        reclamo_id=reclamo.id,
        contratista_id=contratista.id,
        estado=EstadoVisita.CONFIRMADA,
        fecha_visita=fecha_visita,
        horario_confirmado=reloj.formatear_art(fecha_visita),
    )
    db.add(visita)
    db.commit()

    # 1. En tiempo actual (48h antes): no debe disparar recordatorio
    eventos = revisar_recordatorios(db)
    assert len(eventos) == 0
    assert visita.recordatorio_dia_antes_enviado is None
    assert visita.recordatorio_mismo_dia_enviado is None
    assert visita.pregunta_inicio_enviada is None

    # 2. Avanzar 1 día (+24h): queda a 24h de la visita -> debe enviar recordatorio día antes
    reloj.avanzar_tiempo(dias=1)
    eventos = revisar_recordatorios(db)
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "dia_antes"
    db.refresh(visita)
    assert visita.recordatorio_dia_antes_enviado is not None
    assert visita.recordatorio_mismo_dia_enviado is None

    # 3. Avanzar 18 horas más: queda a 6h de la visita -> debe enviar recordatorio mismo día
    reloj.avanzar_tiempo(horas=18)
    eventos = revisar_recordatorios(db)
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "mismo_dia"
    db.refresh(visita)
    assert visita.recordatorio_mismo_dia_enviado is not None
    assert visita.pregunta_inicio_enviada is None

    # 4. Avanzar 7 horas más: la hora ya pasó (visita cumplida) -> debe enviar pregunta de inicio
    reloj.avanzar_tiempo(horas=7)
    eventos = revisar_recordatorios(db)
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "pregunta_inicio"
    db.refresh(visita)
    assert visita.pregunta_inicio_enviada is not None

    # Limpiar estado
    reloj.resetear_tiempo()

