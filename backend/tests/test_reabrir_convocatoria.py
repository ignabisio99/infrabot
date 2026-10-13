from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from decimal import Decimal

from models.presupuesto import EstadoPresupuesto, ItemPresupuesto, Presupuesto
from models.reclamo import EstadoReclamo
from models.recordatorio_contratista import RecordatorioContratista
from models.visita import EstadoVisita
from services.reabrir_convocatoria import (
    ReaperturaInvalida,
    asignar_oferta_existente,
    listar_ofertas_reutilizables,
    reabrir_por_inaccion,
)
from services.seguimiento import MARCA_INTERVENCION, forzar_intervencion


@patch("services.reabrir_convocatoria.enviar_mensaje")
def test_reabrir_cancela_presupuesto_y_vuelve_a_convocar(
    mock_enviar,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
):
    mock_enviar.return_value = {}
    contratista = crear_contratista()
    reclamo = crear_reclamo(
        estado=EstadoReclamo.EN_EJECUCION,
        telefono_creador="5491111111111",
    )
    crear_presupuesto_aprobado(
        reclamo,
        items=[(1, 100)],
        fecha_aprobacion=reclamo.fecha_creacion,
        contratista=contratista,
    )
    forzar_intervencion(db, reclamo)
    db.add(
        RecordatorioContratista(
            reclamo_id=reclamo.id,
            ultimo_envio=datetime.now(timezone.utc),
            cantidad_envios=5,
        )
    )
    db.flush()

    reabrir_por_inaccion(db, reclamo)
    db.flush()
    db.refresh(reclamo)

    assert reclamo.estado == EstadoReclamo.PENDIENTE_PRESUPUESTO
    assert MARCA_INTERVENCION not in (reclamo.observaciones or "")
    presupuestos = list(reclamo.presupuestos)
    assert all(p.estado != EstadoPresupuesto.APROBADO for p in presupuestos)
    assert any(p.estado == EstadoPresupuesto.RECHAZADO for p in presupuestos)
    assert db.query(RecordatorioContratista).filter_by(reclamo_id=reclamo.id).count() == 0
    destinos = [args[0] for args, _ in mock_enviar.call_args_list]
    assert "5491111111111" in destinos
    assert contratista.telefono in destinos
    assert any("volvió a presupuestos" in args[1] for args, _ in mock_enviar.call_args_list)


def test_reabrir_si_sigue_en_ejecucion_falla(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    contratista = crear_contratista()
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    crear_presupuesto_aprobado(
        reclamo,
        items=[(1, 100)],
        fecha_aprobacion=reclamo.fecha_creacion,
        contratista=contratista,
    )
    db.flush()
    with pytest.raises(ReaperturaInvalida):
        reabrir_por_inaccion(db, reclamo)
    assert reclamo.estado == EstadoReclamo.EN_EJECUCION


def _oferta_no_seleccionada(db, reclamo, contratista, monto=80):
    presupuesto = Presupuesto(
        reclamo_id=reclamo.id,
        contratista_id=contratista.id,
        estado=EstadoPresupuesto.NO_SELECCIONADO,
    )
    db.add(presupuesto)
    db.flush()
    db.add(
        ItemPresupuesto(
            presupuesto_id=presupuesto.id,
            descripcion="Ítem",
            cantidad=Decimal("1"),
            costo_unitario=Decimal(str(monto)),
        )
    )
    db.flush()
    return presupuesto


@patch("core.whatsapp_handler.registrar_estado_conversacion")
@patch("core.whatsapp_client.enviar_mensaje")
@patch("services.reabrir_convocatoria.enviar_mensaje")
def test_asignar_oferta_ya_enviada_cambia_contratista(
    mock_enviar_reabrir,
    mock_enviar_wa,
    _mock_conv,
    db,
    crear_reclamo,
    crear_presupuesto_aprobado,
    crear_contratista,
    crear_visita,
):
    mock_enviar_reabrir.return_value = {}
    mock_enviar_wa.return_value = {}
    anterior = crear_contratista("Plomería Uno")
    anterior.telefono = "549111000001"
    nuevo = crear_contratista("Plomería Dos")
    nuevo.telefono = "549111000002"
    reclamo = crear_reclamo(
        estado=EstadoReclamo.EN_EJECUCION,
        telefono_creador="5491111111111",
    )
    crear_presupuesto_aprobado(
        reclamo,
        items=[(1, 100)],
        fecha_aprobacion=reclamo.fecha_creacion,
        contratista=anterior,
    )
    alternativa = _oferta_no_seleccionada(db, reclamo, nuevo, monto=80)
    visita = crear_visita(reclamo, reclamo.fecha_creacion, contratista=anterior)
    forzar_intervencion(db, reclamo)
    db.flush()

    ofertas = listar_ofertas_reutilizables(db, reclamo)
    assert [o.presupuesto_id for o in ofertas] == [alternativa.id]

    asignar_oferta_existente(db, reclamo, alternativa.id)
    db.flush()
    db.refresh(reclamo)
    db.refresh(alternativa)
    db.refresh(visita)

    assert alternativa.estado == EstadoPresupuesto.APROBADO
    assert all(
        p.estado != EstadoPresupuesto.APROBADO or p.id == alternativa.id
        for p in reclamo.presupuestos
    )
    assert visita.estado == EstadoVisita.CANCELADA
    assert reclamo.estado in {
        EstadoReclamo.APROBADO,
        EstadoReclamo.PENDIENTE_COORDINACION,
    }
    assert reclamo.estado == EstadoReclamo.PENDIENTE_COORDINACION
    destinos = [args[0] for args, _ in mock_enviar_reabrir.call_args_list]
    assert "5491111111111" in destinos
    assert anterior.telefono in destinos
    assert any("cambia el contratista" in args[1] for args, _ in mock_enviar_reabrir.call_args_list)


def test_asignar_oferta_rechazada_no_vale(
    db, crear_reclamo, crear_presupuesto_aprobado, crear_contratista
):
    anterior = crear_contratista("Uno")
    otro = crear_contratista("Dos")
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION)
    aprobado = crear_presupuesto_aprobado(
        reclamo,
        items=[(1, 100)],
        fecha_aprobacion=reclamo.fecha_creacion,
        contratista=anterior,
    )
    rechazado = _oferta_no_seleccionada(db, reclamo, otro)
    rechazado.estado = EstadoPresupuesto.RECHAZADO
    forzar_intervencion(db, reclamo)
    db.flush()

    with pytest.raises(ReaperturaInvalida):
        asignar_oferta_existente(db, reclamo, rechazado.id)
    with pytest.raises(ReaperturaInvalida):
        asignar_oferta_existente(db, reclamo, aprobado.id)
