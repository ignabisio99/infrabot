"""Tests para la validación de fechas pasadas en la coordinación de visitas por WhatsApp."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.whatsapp_handler import _conversaciones, procesar_mensaje, registrar_estado_conversacion
from models.reclamo import EstadoReclamo
from models.visita import EstadoVisita
from services import coordinacion_visita


def test_opciones_pasadas_detecta_fechas_anteriores():
    # Fechas en el pasado
    texto_pasado = "10/01/2020 10:00"
    pasadas = coordinacion_visita.opciones_pasadas(texto_pasado)
    assert len(pasadas) == 1
    assert "10/01/2020 10:00" in pasadas

    # Fecha en el futuro
    art = timezone(timedelta(hours=-3))
    futuro = (datetime.now(timezone.utc).astimezone(art) + timedelta(days=5)).strftime("%d/%m %H:%M")
    assert coordinacion_visita.opciones_pasadas(futuro) == []


def test_contratista_no_puede_cargar_fecha_pasada(
    db, crear_reclamo, crear_contratista, crear_visita
):
    contratista = crear_contratista()
    contratista.telefono = "5491100001111"
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_COORDINACION, telefono_creador="5491199998888")
    visita = crear_visita(reclamo, fecha_visita=None, estado=EstadoVisita.ESPERANDO_DISPONIBILIDAD, contratista=contratista)
    db.flush()

    registrar_estado_conversacion(
        contratista.telefono,
        {"paso": "visita_disponibilidad", "visita_id": visita.id},
    )

    with patch("core.whatsapp_client.enviar_mensaje"):
        # Intenta cargar fecha pasada
        resp = procesar_mensaje(db, contratista.telefono, "01/01/2020 10:00")
        assert "ya pasó" in resp
        assert "No podés coordinar visitas en fechas pasadas" in resp

        db.refresh(visita)
        assert visita.disponibilidades is None  # no se guardó

        # Ahora carga una fecha futura válida
        art = timezone(timedelta(hours=-3))
        futura = (datetime.now(timezone.utc).astimezone(art) + timedelta(days=3)).strftime("%d/%m 10:00")
        resp_ok = procesar_mensaje(db, contratista.telefono, futura)
        assert "Anoté 1 opción" in resp_ok

        db.refresh(visita)
        assert visita.disponibilidades is not None
        assert futura in visita.disponibilidades


def test_escuela_no_puede_elegir_opcion_que_ya_paso(
    db, crear_reclamo, crear_contratista, crear_visita
):
    contratista = crear_contratista()
    contratista.telefono = "5491100002222"
    tel_escuela = "5491199997777"
    reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_COORDINACION, telefono_creador=tel_escuela)

    # Supongamos que la visita tiene una opción pasada y una futura
    art = timezone(timedelta(hours=-3))
    opcion_futura = (datetime.now(timezone.utc).astimezone(art) + timedelta(days=2)).strftime("%d/%m 14:00")
    opcion_pasada = "01/01/2020 09:00"

    visita = crear_visita(reclamo, fecha_visita=None, estado=EstadoVisita.ESPERANDO_ELECCION, contratista=contratista)
    visita.disponibilidades = f"{opcion_pasada}\n{opcion_futura}"
    db.flush()

    registrar_estado_conversacion(
        tel_escuela,
        {"paso": "visita_eleccion", "visita_id": visita.id},
    )

    with patch("core.whatsapp_client.enviar_mensaje"):
        # La escuela intenta elegir la opción 1 (que ya pasó)
        resp = procesar_mensaje(db, tel_escuela, "1")
        assert "ya pasó y no se puede coordinar" in resp
        assert "opciones que siguen vigentes" in resp

        db.refresh(visita)
        assert visita.estado == EstadoVisita.ESPERANDO_ELECCION
        assert visita.horario_confirmado is None

        # La escuela elige la opción 2 (futura)
        resp_ok = procesar_mensaje(db, tel_escuela, "2")
        assert "Visita confirmada" in resp_ok

        db.refresh(visita)
        assert visita.estado == EstadoVisita.CONFIRMADA
        assert visita.horario_confirmado == opcion_futura



def _contratista_cargando(db, crear_reclamo, crear_contratista, crear_visita, telefono):
    from core.whatsapp_handler import reiniciar_conversacion

    contratista = crear_contratista()
    contratista.telefono = telefono
    reclamo = crear_reclamo(
        estado=EstadoReclamo.PENDIENTE_COORDINACION, telefono_creador="5491199990000"
    )
    visita = crear_visita(
        reclamo,
        fecha_visita=None,
        estado=EstadoVisita.ESPERANDO_DISPONIBILIDAD,
        contratista=contratista,
    )
    reiniciar_conversacion(telefono)
    registrar_estado_conversacion(telefono, {"paso": "visita_disponibilidad", "visita_id": visita.id})
    return reclamo, visita


def test_cancelar_la_carga_de_horario_no_lo_vuelve_a_meter_hasta_retomarla(
    db, crear_reclamo, crear_contratista, crear_visita
):
    tel = "5491100003333"
    reclamo, visita = _contratista_cargando(
        db, crear_reclamo, crear_contratista, crear_visita, tel
    )

    with patch("services.coordinacion_visita._enviar"):
        r = procesar_mensaje(db, "cancelar", usuario=tel)
        assert "cancelaste la carga del horario" in r
        assert f"cargar horario {reclamo.id}" in r
        assert visita.disponibilidad_pausada is True

        # Aunque se pierda el estado en memoria, no se reconstruye la carga pausada.
        _conversaciones.pop(tel, None)
        r = procesar_mensaje(db, "hola", usuario=tel)
        assert tel not in _conversaciones or _conversaciones[tel].get("paso") != "visita_disponibilidad"

        r = procesar_mensaje(db, f"cargar horario {reclamo.id}", usuario=tel)
        assert f"reclamo #{reclamo.id}" in r
        assert visita.disponibilidad_pausada is False
        assert _conversaciones[tel] == {"paso": "visita_disponibilidad", "visita_id": visita.id}


def test_cargar_horario_de_un_reclamo_ajeno_no_lo_retoma(
    db, crear_reclamo, crear_contratista, crear_visita
):
    reclamo, visita = _contratista_cargando(
        db, crear_reclamo, crear_contratista, crear_visita, "5491100004444"
    )
    coordinacion_visita.pausar_disponibilidad(db, visita)

    r = procesar_mensaje(db, f"cargar horario {reclamo.id}", usuario="5491100005555")

    assert "No tenés una visita pendiente" in r
    assert visita.disponibilidad_pausada is True
