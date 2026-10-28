"""Seguimiento de avance del contratista (CU-05 pieza 2).

El bot pregunta "¿terminaste?" con botones. Sin respuesta al plazo de la última de
SEGUIMIENTO_MAX_INTENTOS preguntas, el reclamo pasa a DESIERTO (reconvocar). La
herramienta de admin forzar_intervencion sigue yendo a PENDIENTE_INTERVENCION.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from core import reloj
from models.recordatorio_contratista import RecordatorioContratista
from models.reclamo import EstadoReclamo
from services.seguimiento import MARCA_INTERVENCION, ejecutar_seguimiento, forzar_intervencion


def _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista):
    contratista = crear_contratista()
    contratista.telefono = "5491100001111"
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(
        reclamo,
        items=[(1, 100)],
        fecha_aprobacion=reclamo.fecha_creacion,
        contratista=contratista,
    )
    return reclamo


@patch("core.whatsapp_client.enviar_botones")
def test_la_quinta_pregunta_queda_abierta_y_despues_pasa_a_desierto(
    mock_botones,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
    monkeypatch,
):
    monkeypatch.setenv("SEGUIMIENTO_HORAS", "0")
    monkeypatch.setenv("SEGUIMIENTO_MAX_INTENTOS", "5")
    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    mock_botones.return_value = {}

    for _ in range(5):
        r = ejecutar_seguimiento(db)
        assert r.enviados == 1
        assert r.escalados == 0

    # La quinta pregunta queda abierta: el contratista todavía puede responder.
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION
    assert mock_botones.call_count == 5

    cierre = ejecutar_seguimiento(db)
    assert cierre.enviados == 0
    assert cierre.escalados == 1
    assert reclamo.estado == EstadoReclamo.DESIERTO
    assert mock_botones.call_count == 5


@patch("core.whatsapp_client.enviar_botones")
def test_una_respuesta_reinicia_los_intentos(
    mock_botones,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
    monkeypatch,
):
    from services.avance_contratista import registrar_avance_texto

    monkeypatch.setenv("SEGUIMIENTO_HORAS", "0")
    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    mock_botones.return_value = {}
    ejecutar_seguimiento(db)
    ejecutar_seguimiento(db)
    fila = db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()
    assert fila.cantidad_envios == 2

    registrar_avance_texto(db, reclamo, None, "Avance 10%")
    db.refresh(fila)
    assert fila.cantidad_envios == 0
    tercero = ejecutar_seguimiento(db)
    assert tercero.enviados == 1
    db.refresh(fila)
    assert fila.cantidad_envios == 1


@patch("core.whatsapp_client.enviar_botones")
def test_tiempo_estimado_no_cambia_el_ritmo_de_24_horas(
    mock_botones,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
    monkeypatch,
):
    """Aunque el contratista diga que le faltan 2 días, se le vuelve a preguntar a las 24 h."""
    monkeypatch.setenv("SEGUIMIENTO_HORAS", "24")
    from services.seguimiento import registrar_tiempo_estimado

    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    mock_botones.return_value = {}
    fila = RecordatorioContratista(
        reclamo_id=reclamo.id,
        ultimo_envio=datetime.now(timezone.utc) - timedelta(hours=25),
        cantidad_envios=1,
    )
    db.add(fila)
    db.flush()

    registrar_tiempo_estimado(db, reclamo, "2 días")

    assert ejecutar_seguimiento(db).enviados == 1
    # Recién preguntado: no se repite hasta que pasen otras 24 h.
    assert ejecutar_seguimiento(db).enviados == 0


@patch("core.whatsapp_client.enviar_botones")
def test_consulto_escuela_frena_las_preguntas_al_contratista(
    mock_botones,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
    monkeypatch,
):
    from services.seguimiento import preguntar_a_escuela_si_resuelto

    monkeypatch.setenv("SEGUIMIENTO_HORAS", "0")
    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    reclamo.telefono_creador = "5491199998888"
    db.flush()
    mock_botones.return_value = {}

    preguntar_a_escuela_si_resuelto(db, reclamo)
    # Mientras se espera a la escuela, no se molesta al contratista.
    r = ejecutar_seguimiento(db)
    assert r.enviados == 0


def test_quita_marca_vieja_con_prefijo_cu(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista):
    from services.avance_contratista import registrar_avance_texto

    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    reclamo.observaciones = "[CU-05] Pendiente de intervención: sin respuesta"
    db.flush()
    registrar_avance_texto(db, reclamo, None, "Avance 10%")
    db.refresh(reclamo)
    assert reclamo.observaciones is None or "Pendiente de intervención" not in reclamo.observaciones


def test_seguimiento_migra_marca_vieja_al_estado(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    reclamo.observaciones = f"{MARCA_INTERVENCION}: sin respuesta"
    db.flush()
    ejecutar_seguimiento(db)
    db.refresh(reclamo)
    assert reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION
    assert MARCA_INTERVENCION not in (reclamo.observaciones or "")


def test_forzar_intervencion_sin_cinco_avisos(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    from services.notificaciones import contar_pendiente_intervencion

    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    assert forzar_intervencion(db, reclamo) is True
    db.flush()
    assert reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION
    assert contar_pendiente_intervencion(db) == 1
    assert forzar_intervencion(db, reclamo) is False


def test_forzar_intervencion_desde_aprobado(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    from services.seguimiento import IntervencionNoForzable

    contratista = crear_contratista()
    reclamo = crear_reclamo(estado=EstadoReclamo.APROBADO)
    crear_presupuesto_aprobado(
        reclamo,
        items=[(1, 100)],
        fecha_aprobacion=reclamo.fecha_creacion,
        contratista=contratista,
    )
    assert forzar_intervencion(db, reclamo) is True
    db.flush()
    assert reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION

    otro = crear_reclamo(estado=EstadoReclamo.PENDIENTE_PRESUPUESTO)
    with pytest.raises(IntervencionNoForzable):
        forzar_intervencion(db, otro)


def test_admin_puede_volver_a_ejecucion_desde_intervencion(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    from models.historial_estado_reclamo import OrigenCambioEstado
    from models.recordatorio_contratista import RecordatorioContratista
    from services.estados_reclamo import cambiar_estado, transiciones_posibles

    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    forzar_intervencion(db, reclamo)
    db.add(
        RecordatorioContratista(
            reclamo_id=reclamo.id,
            ultimo_envio=datetime.now(timezone.utc),
            cantidad_envios=5,
        )
    )
    db.flush()

    assert EstadoReclamo.EN_EJECUCION in transiciones_posibles(reclamo.estado)
    cambiar_estado(
        db,
        reclamo,
        EstadoReclamo.EN_EJECUCION,
        motivo="Hablé con el contratista, sigue en obra",
        origen=OrigenCambioEstado.MANUAL,
    )
    db.flush()
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION
    fila = db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()
    assert fila.cantidad_envios == 0


def test_el_simulador_guarda_el_paso_a_desierto(
    db, client, crear_reclamo, monkeypatch
):
    """Avanzar el reloj tiene que persistir DESIERTO: ese paso no envía un mensaje."""
    monkeypatch.setenv("SEGUIMIENTO_HORAS", "48")
    reloj.resetear_tiempo()
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    db.add(
        RecordatorioContratista(
            reclamo_id=reclamo.id,
            ultimo_envio=datetime.now(timezone.utc) - timedelta(days=5),
            cantidad_envios=5,
        )
    )
    db.flush()
    commits = {"n": 0}
    original = db.commit

    def contar():
        commits["n"] += 1
        return original()

    db.commit = contar
    try:
        respuesta = client.post("/simulador-tiempo/avanzar", json={"dias": 2})
        assert respuesta.status_code == 200
        db.refresh(reclamo)
        assert reclamo.estado == EstadoReclamo.DESIERTO
        assert commits["n"] >= 1
        assert any("desierto" in accion for accion in respuesta.json()["acciones_disparadas"])
    finally:
        reloj.resetear_tiempo()


def test_seguimiento_horas_default_es_24(monkeypatch):
    """Por defecto se pregunta al día siguiente a la misma hora (24 horas)."""
    from services.seguimiento import seguimiento_horas

    monkeypatch.delenv("SEGUIMIENTO_HORAS", raising=False)
    assert seguimiento_horas() == 24.0
