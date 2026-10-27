"""Tests para la validación de fechas pasadas en la coordinación de visitas por WhatsApp."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.whatsapp_handler import _conversaciones, procesar_mensaje, registrar_estado_conversacion
from models.reclamo import EstadoReclamo
from models.visita import EstadoVisita
from services import coordinacion_visita


def test_fecha_pasada_sin_anio_no_salta_al_anio_siguiente(
    db, crear_reclamo, crear_contratista, crear_visita
):
    from core import reloj

    # 15/07/2026 12:00 ART
    reloj.fijar_tiempo(datetime(2026, 7, 15, 15, 0, tzinfo=timezone.utc))
    try:
        assert coordinacion_visita.opciones_pasadas("12/05 10:00") == ["12/05 10:00"]
        assert coordinacion_visita.formatear_opcion("12/05 10:00") == "12/05/2026 10:00"
        assert coordinacion_visita.opciones_pasadas("14/07 10:00") == ["14/07 10:00"]
        assert coordinacion_visita.opciones_pasadas("12/05/2027 10:00") == []
        assert coordinacion_visita.formatear_opcion("12/05/2027 10:00") == "12/05/2027 10:00"

        # En diciembre, enero sin año sigue siendo el enero que viene.
        reloj.fijar_tiempo(datetime(2026, 12, 20, 15, 0, tzinfo=timezone.utc))
        assert coordinacion_visita.formatear_opcion("08/01 09:00") == "08/01/2027 09:00"
        assert coordinacion_visita.opciones_pasadas("19/12 10:00") == ["19/12 10:00"]

        contratista = crear_contratista()
        reclamo = crear_reclamo(estado=EstadoReclamo.PENDIENTE_COORDINACION)
        visita = crear_visita(
            reclamo,
            fecha_visita=None,
            estado=EstadoVisita.ESPERANDO_DISPONIBILIDAD,
            contratista=contratista,
        )
        visita.disponibilidades = "15/01 10:00"
        visita.horario_confirmado = "20/12 11:00"
        visita.fecha_visita = datetime(2026, 12, 20, 14, 0, tzinfo=timezone.utc)
        db.flush()

        assert coordinacion_visita.normalizar_fechas_visitas(db) == 1
        db.refresh(visita)
        assert visita.disponibilidades == "15/01/2027 10:00"
        assert visita.horario_confirmado == "20/12/2026 11:00"
    finally:
        reloj.resetear_tiempo()


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
        resp = procesar_mensaje(db, "01/01/2020 10:00", usuario=contratista.telefono)
        assert "ya pasó" in resp
        assert "con el año" in resp

        db.refresh(visita)
        assert visita.disponibilidades is None  # no se guardó

        # Ahora carga una fecha futura válida
        art = timezone(timedelta(hours=-3))
        futura = (datetime.now(timezone.utc).astimezone(art) + timedelta(days=3)).strftime("%d/%m 10:00")
        resp_ok = procesar_mensaje(db, futura, usuario=contratista.telefono)
        assert "Van 1 opción" in resp_ok

        otra = (datetime.now(timezone.utc).astimezone(art) + timedelta(days=4)).strftime("%d/%m 11:00")
        resp_dos = procesar_mensaje(db, otra, usuario=contratista.telefono)
        assert "Van 2 opciones" in resp_dos

        db.refresh(visita)
        assert visita.disponibilidades == "\n".join(
            coordinacion_visita.formatear_opcion(op) for op in (futura, otra)
        )


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
        resp = procesar_mensaje(db, "1", usuario=tel_escuela)
        assert "ya pasó y no se puede coordinar" in resp
        assert "opciones que siguen vigentes" in resp

        db.refresh(visita)
        assert visita.estado == EstadoVisita.ESPERANDO_ELECCION
        assert visita.horario_confirmado is None

        # La escuela elige la opción 2 (futura)
        resp_ok = procesar_mensaje(db, "2", usuario=tel_escuela)
        assert "Confirmé la visita" in resp_ok

        db.refresh(visita)
        assert visita.estado == EstadoVisita.CONFIRMADA
        assert visita.horario_confirmado == coordinacion_visita.formatear_opcion(opcion_futura)



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
