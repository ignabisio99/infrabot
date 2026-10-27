"""Cancelar el reclamo da de baja su visita: no más recordatorios ni coordinación."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from core import reloj
from core.whatsapp_handler import (
    procesar_mensaje,
    registrar_estado_conversacion,
    reiniciar_conversacion,
)
from models.reclamo import EstadoReclamo
from models.visita import EstadoVisita
from models.usuario import TipoUsuario, Usuario
from services import estados_reclamo
from services.recordatorios import revisar_recordatorios

CONTRATISTA = "5491155660055"
ESCUELA = "5491155660066"


def _cancelar(client, reclamo):
    return client.post(
        f"/reclamos/{reclamo.id}/estado", json={"estado": "CANCELADO", "motivo": "Se resolvió"}
    )


@pytest.fixture
def contratista_con_cuenta(db, crear_contratista):
    contratista = crear_contratista(nombre_empresa="Igna Repara SA")
    contratista.telefono = CONTRATISTA
    usuario = Usuario(
        nombre="Igna",
        email="igna@test.local",
        password_hash="x",
        tipo=TipoUsuario.CONTRATISTA,
    )
    db.add(usuario)
    db.flush()
    contratista.usuario_id = usuario.id
    return contratista


def _cancelar_registrando_avisos(client, reclamo):
    with (
        patch("services.coordinacion_visita._enviar") as whatsapp,
        patch("services.coordinacion_visita.enviar_reclamo_cancelado_asignado") as mail,
    ):
        assert _cancelar(client, reclamo).status_code == 200
    return {llamada.args[0]: llamada.args[1] for llamada in whatsapp.call_args_list}, mail


def test_cancelar_avisa_que_la_visita_coordinada_queda_suspendida(
    client, crear_reclamo, crear_visita, contratista_con_cuenta
):
    reclamo = crear_reclamo(estado=EstadoReclamo.VISITA_COORDINADA, telefono_creador=ESCUELA)
    visita = crear_visita(
        reclamo,
        fecha_visita=reloj.ahora() + timedelta(days=2),
        contratista=contratista_con_cuenta,
    )
    visita.horario_confirmado = "29/10 10:00"

    whatsapps, mail = _cancelar_registrando_avisos(client, reclamo)

    assert whatsapps.keys() == {CONTRATISTA, ESCUELA}
    assert "ya no estás asignado" in whatsapps[CONTRATISTA]
    assert "Igna Repara SA ya no va a hacer el trabajo" in whatsapps[ESCUELA]
    for texto in whatsapps.values():
        assert "La visita del 29/10 10:00 queda suspendida" in texto
        assert "Motivo: Se resolvió" in texto
    mail.assert_called_once_with(
        "igna@test.local", reclamo.id, "Escuela de prueba", "29/10 10:00", "Se resolvió"
    )


def test_con_la_obra_en_curso_el_aviso_no_habla_de_una_visita_suspendida(
    client, crear_reclamo, crear_visita, contratista_con_cuenta
):
    reclamo = crear_reclamo(estado=EstadoReclamo.EN_EJECUCION, telefono_creador=ESCUELA)
    visita = crear_visita(
        reclamo,
        fecha_visita=reloj.ahora() - timedelta(days=3),
        contratista=contratista_con_cuenta,
    )
    visita.horario_confirmado = "24/10 10:00"

    whatsapps, mail = _cancelar_registrando_avisos(client, reclamo)

    assert whatsapps.keys() == {CONTRATISTA, ESCUELA}
    for texto in whatsapps.values():
        assert "suspendida" not in texto
    assert mail.call_args.args[3] is None


def test_cancelar_el_reclamo_cancela_la_visita_y_corta_los_recordatorios(
    client, db, crear_reclamo, crear_visita
):
    reclamo = crear_reclamo(
        estado=EstadoReclamo.VISITA_COORDINADA, telefono_creador="5491155660011"
    )
    # Dentro de la ventana del recordatorio "la visita es mañana".
    visita = crear_visita(reclamo, fecha_visita=reloj.ahora() + timedelta(hours=24))

    _cancelar_registrando_avisos(client, reclamo)

    db.refresh(visita)
    assert visita.estado == EstadoVisita.CANCELADA
    with patch("core.whatsapp_client.enviar_mensaje") as enviar:
        assert revisar_recordatorios(db) == []
    enviar.assert_not_called()


def test_el_contratista_que_cargaba_horarios_no_reabre_la_visita_cancelada(
    db, crear_reclamo, crear_contratista, crear_visita
):
    contratista = crear_contratista()
    contratista.telefono = "5491155660022"
    reclamo = crear_reclamo(
        estado=EstadoReclamo.PENDIENTE_COORDINACION, telefono_creador="5491155660033"
    )
    visita = crear_visita(
        reclamo,
        fecha_visita=None,
        estado=EstadoVisita.ESPERANDO_DISPONIBILIDAD,
        contratista=contratista,
    )
    visita.disponibilidades = (reloj.ahora_art() + timedelta(days=2)).strftime("%d/%m 10:00")
    reiniciar_conversacion(contratista.telefono)
    registrar_estado_conversacion(
        contratista.telefono, {"paso": "visita_disponibilidad", "visita_id": visita.id}
    )
    estados_reclamo.cambiar_estado(db, reclamo, EstadoReclamo.CANCELADO, motivo="Se resolvió")
    db.flush()

    with patch("services.coordinacion_visita._enviar") as enviar:
        respuesta = procesar_mensaje(db, "listo", usuario=contratista.telefono)

    assert "se canceló" in respuesta
    enviar.assert_not_called()
    assert visita.estado == EstadoVisita.CANCELADA


def test_la_escuela_que_elegia_horario_no_reabre_la_visita_cancelada(
    db, crear_reclamo, crear_visita
):
    escuela = "5491155660044"
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_COORDINACION, telefono_creador=escuela)
    visita = crear_visita(reclamo, fecha_visita=None, estado=EstadoVisita.ESPERANDO_ELECCION)
    visita.disponibilidades = (reloj.ahora_art() + timedelta(days=2)).strftime("%d/%m 10:00")
    reiniciar_conversacion(escuela)
    registrar_estado_conversacion(escuela, {"paso": "visita_eleccion", "visita_id": visita.id})
    estados_reclamo.cambiar_estado(db, reclamo, EstadoReclamo.CANCELADO, motivo="Se resolvió")
    db.flush()

    with patch("services.coordinacion_visita._enviar") as enviar:
        respuesta = procesar_mensaje(db, "1", usuario=escuela)

    assert "se canceló" in respuesta
    enviar.assert_not_called()
    assert visita.estado == EstadoVisita.CANCELADA
    assert visita.fecha_visita is None
