from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

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


@patch("services.seguimiento.enviar_mensaje")
def test_al_quinto_intento_escala_y_no_sigue(
    mock_enviar,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
    monkeypatch,
):
    monkeypatch.setenv("SEGUIMIENTO_HORAS", "0")
    monkeypatch.setenv("SEGUIMIENTO_MAX_INTENTOS", "5")
    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    mock_enviar.return_value = {}

    for n in range(5):
        r = ejecutar_seguimiento(db)
        assert r.enviados == 1
        if n < 4:
            assert r.escalados == 0
        else:
            assert r.escalados == 1

    assert reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION
    assert MARCA_INTERVENCION not in (reclamo.observaciones or "")
    from services.notificaciones import contar_pendiente_intervencion

    assert contar_pendiente_intervencion(db) == 1
    sexto = ejecutar_seguimiento(db)
    assert sexto.enviados == 0
    assert mock_enviar.call_count == 5


@patch("services.seguimiento.enviar_mensaje")
def test_una_respuesta_reinicia_los_intentos(
    mock_enviar,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
    monkeypatch,
):
    from services.avance_contratista import registrar_avance_texto

    monkeypatch.setenv("SEGUIMIENTO_HORAS", "0")
    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    mock_enviar.return_value = {}
    ejecutar_seguimiento(db)
    ejecutar_seguimiento(db)
    fila = db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).one()
    assert fila.cantidad_envios == 2

    registrar_avance_texto(db, reclamo, None, "Avance 10%")
    db.refresh(fila)
    assert fila.cantidad_envios == 0
    # El reloj se reinició ahora: sin umbral 0 no mandaría... SEGUIMIENTO_HORAS=0 sí vence.
    tercero = ejecutar_seguimiento(db)
    assert tercero.enviados == 1
    db.refresh(fila)
    assert fila.cantidad_envios == 1


@patch("services.seguimiento.enviar_mensaje")
def test_respuesta_despues_de_escalar_quita_la_marca(
    mock_enviar,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
    monkeypatch,
):
    from services.avance_contratista import registrar_avance_texto

    monkeypatch.setenv("SEGUIMIENTO_HORAS", "0")
    monkeypatch.setenv("SEGUIMIENTO_MAX_INTENTOS", "2")
    reclamo = _reclamo_en_obra(db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista)
    mock_enviar.return_value = {}
    ejecutar_seguimiento(db)
    ejecutar_seguimiento(db)
    assert reclamo.estado == EstadoReclamo.PENDIENTE_INTERVENCION

    registrar_avance_texto(db, reclamo, None, "Perdón, avance 30%")
    db.refresh(reclamo)
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION
    textos = [c.texto for c in reclamo.comentarios]
    assert any("vuelve a ejecución" in t for t in textos)
    assert all("[CU-05]" not in t for t in textos)


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
